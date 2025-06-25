import logging
from typing import TYPE_CHECKING, Any

from openg2p_fastapi_common.context import component_registry
from openg2p_fastapi_common.service import BaseService
from openg2p_fastapi_common.utils.holder import Holder

from ...config import Settings
from ...errors import ToolNotFound
from ...schemas.ollama import OllamaChatMessage
from ...schemas.tools import ToolBaseResponse
from ...utils.timing import time_it
from .base import BaseTool

if TYPE_CHECKING:
    from ..agents import BaseAgent

_config = Settings.get_config(strict=False)
_logger = logging.getLogger(_config.logging_default_logger_name)


class ToolboxService(BaseService):
    def __init__(self, enabled=True, **kw):
        super().__init__(**kw)
        self.enabled = enabled
        self._tool_name_map: dict[str, BaseTool] = {}
        self._ollama_tools: list[dict] = []

    def validate_tool_part_of_box(self, tool: BaseTool) -> bool:
        """Can be overriden by child class based on
        what all tools are allowed to be part of the box.

        Should return True or False based on whether a tool
        is considered part of the box or not."""
        return isinstance(tool, BaseTool) and tool.enabled

    def get_tool_name_map(self):
        """
        This generates an internal map of all tools against their names
        """
        if not self._tool_name_map:
            self._tool_name_map = {}
            for tool in component_registry.get():
                if self.validate_tool_part_of_box(tool):
                    self._tool_name_map[tool.get_name()] = tool
        return self._tool_name_map

    def get_ollama_tools(self):
        """
        Get list of all tools in this toolbox to be passed to ollama
        """
        if not self._ollama_tools:
            self.get_tool_name_map()
            self._ollama_tools = []
            for tool in self.get_tool_name_map().values():
                self._ollama_tools.append(self.convert_tool_for_ollama(tool))
        return self._ollama_tools

    def convert_tool_for_ollama(self, tool: BaseTool):
        """
        Get tool meta data, to pass to Ollama
        """
        return {
            "type": "function",
            "function": {
                "name": tool.get_name(),
                "description": tool.get_description(),
                "parameters": tool.get_request_model().model_json_schema(mode="validation"),
            },
        }

    @time_it("ToolboxService.call_each_tool_from_ollama")
    async def call_each_tool_from_ollama(
        self,
        tool_call: dict[str, Any],
        agent: Holder["BaseAgent"],
        messages: list[OllamaChatMessage] | None = None,
        **kw
    ) -> ToolBaseResponse:
        # TODO: Put validation on tool_call json.
        tool_name: str = (tool_call.get("function") or {}).get("name") or ""
        tool_args: dict[str, Any] = (tool_call.get("function") or {}).get("arguments") or {}
        _logger.info("Tool invoking. Name %s", tool_name)
        _logger.debug("Tool invoking. Request:", extra={"props": tool_args})
        try:
            tool = self.get_tool_name_map()[tool_name]
        except Exception as e:
            raise ToolNotFound() from e
        res = await tool.call_tool(
            tool.get_request_model().model_validate(tool_args), agent=agent, messages=messages, **kw
        )
        res.tool_name = tool_name
        return res

    @time_it("ToolboxService.call_tools_from_ollama")
    async def call_tools_from_ollama(
        self,
        tool_calls: list[dict[str, Any]],
        agent: Holder["BaseAgent"],
        messages: list[OllamaChatMessage] | None = None,
        **kw
    ) -> list[ToolBaseResponse]:
        final_res = []
        for tool_call in tool_calls:
            res = await self.call_each_tool_from_ollama(tool_call, agent, messages=messages, **kw)
            final_res.append(res)
        return final_res
