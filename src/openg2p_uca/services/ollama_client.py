import logging

import httpx
import orjson
from openg2p_fastapi_common.service import BaseService

from ..config import Settings
from ..schemas.ollama import OllamaChatRequest, OllamaChatResponse

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class OllamaClientService(BaseService):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.httpx_client = httpx.AsyncClient()
        self.ollama_url: str = None
        self.system_prompt: str = None
        self.system_prompt_suffix_to_store: str = None
        self.model: str = None
        self.ollama_api_timeout: int = None

    def configure(
        self,
        url: str,
        system_prompt: str,
        model: str,
        system_prompt_suffix_to_store: str = "",
        api_timeout: int = None,
    ):
        self.ollama_url = url
        self.system_prompt = system_prompt
        self.system_prompt_suffix_to_store = system_prompt_suffix_to_store
        self.model = model
        self.ollama_api_timeout = api_timeout

    async def aclose(self):
        await self.httpx_client.aclose()

    async def ollama_chat_api(self, request: OllamaChatRequest) -> OllamaChatResponse:
        """
        Low level Ollama API call. Use chat method in instead.
        """
        res = await self.httpx_client.post(
            f"{self.ollama_url}/api/chat",
            headers={"content-type": "application/json"},
            content=orjson.dumps(request.model_dump(mode="json")),
            timeout=self.ollama_api_timeout,
        )
        res.raise_for_status()
        return OllamaChatResponse.model_validate(orjson.loads(res.text))
