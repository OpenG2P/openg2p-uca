import logging

import httpx
import orjson
from openg2p_fastapi_common.service import BaseService

from ..config import OllamaOptions, Settings
from ..schemas.ollama import OllamaChatRequest, OllamaChatResponse

_config = Settings.get_config(strict=False)
_logger = logging.getLogger(_config.logging_default_logger_name)


class OllamaClientService(BaseService):
    def __init__(
        self,
        url: str,
        model: str,
        api_timeout: int | None = None,
        keep_alive: int | None = None,
        options: OllamaOptions | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self.httpx_client = httpx.AsyncClient()

        self.url = url
        self.model = model
        self.api_timeout = api_timeout
        self.keep_alive = keep_alive
        self.options = options

    async def aclose(self):
        await self.httpx_client.aclose()

    async def load_model(self):
        res = await self.httpx_client.post(
            f"{self.url}/api/chat",
            json={
                "model": self.model,
                "messages": [],
                "keep_alive": self.keep_alive,
            },
            timeout=self.api_timeout,
        )
        res.raise_for_status()
        return res.json()

    async def unload_model(self):
        res = await self.httpx_client.post(
            f"{self.url}/api/chat",
            json={
                "model": self.model,
                "messages": [],
                "keep_alive": 0,
            },
            timeout=self.api_timeout,
        )
        res.raise_for_status()
        return res.json()

    async def chat(self, request: OllamaChatRequest) -> OllamaChatResponse:
        """
        Low level Ollama Chat API call.
        """
        httpx_req = request.model_dump(mode="json")
        httpx_req["model"] = self.model
        if self.options:
            httpx_req["options"] = self.options.model_dump(mode="json")

        res = await self.httpx_client.post(
            f"{self.url}/api/chat",
            headers={"content-type": "application/json"},
            content=orjson.dumps(httpx_req),
            timeout=self.api_timeout,
        )
        res.raise_for_status()
        return OllamaChatResponse.model_validate(orjson.loads(res.text))
