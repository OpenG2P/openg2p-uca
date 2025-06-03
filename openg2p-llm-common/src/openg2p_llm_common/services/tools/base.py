import logging
from typing import TYPE_CHECKING, get_type_hints

from openg2p_fastapi_common.service import BaseService
from openg2p_fastapi_common.utils.holder import Holder

from ...config import Settings
from ...errors import ToolInvalidRequestResponse
from ...schemas.ollama import OllamaChatMessage
from ...schemas.tools import ToolBaseRequest, ToolBaseResponse

if TYPE_CHECKING:
    from ..agents import BaseAgent

_config = Settings.get_config(strict=False)
_logger = logging.getLogger(_config.logging_default_logger_name)


class BaseTool(BaseService):
    """
    Base Tool to be used as parent class for all Tools to be passed to LLM.
    """

    def __init__(self, enabled=True, **kw):
        super().__init__(**kw)
        self.enabled = enabled

        self._tool_request_model: type[ToolBaseRequest] = None
        self._tool_response_model: type[ToolBaseResponse] = None

    def get_name(self) -> str:
        """
        Can be extended by the child class
        """
        return self.name or self.__class__.__name__

    def get_description(self) -> str:
        """
        Can be extended by the child class
        """
        return self.__doc__

    def get_tool_request_response_types(self):
        """
        Generates request and response models from call_tool function type hints
        """
        if not (self._tool_request_model and self._tool_response_model):
            call_tools_type_hints = get_type_hints(self.call_tool)
            if not ("request" in call_tools_type_hints and "return" in call_tools_type_hints):
                raise ToolInvalidRequestResponse()
            self._tool_request_model = call_tools_type_hints["request"]
            self._tool_response_model = call_tools_type_hints["return"]
        return self._tool_request_model, self._tool_response_model

    def get_request_model(self):
        self.get_tool_request_response_types()  # This is called just in case request model is not generated.
        return self._tool_request_model

    def get_response_model(self):
        self.get_tool_request_response_types()  # This is called just in case response model is not generated.
        return self._tool_response_model

    async def call_tool(
        self,
        request: ToolBaseRequest,
        agent: Holder["BaseAgent"] | None = None,
        messages: list[OllamaChatMessage] | None = None,
    ) -> ToolBaseResponse:
        """
        To be extended by the child class
        """
        raise NotImplementedError()
