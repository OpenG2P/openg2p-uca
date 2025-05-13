import logging
from typing import Any

from openg2p_fastapi_common.context import component_registry
from openg2p_fastapi_common.service import BaseService

from ...config import Settings
from ...errors import ToolNotFound
from ...schemas.tools import ToolBaseResponse
from .base import BaseTool

_config = Settings.get_config(strict=False)
_logger = logging.getLogger(_config.logging_default_logger_name)


class ToolboxService(BaseService):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.enabled = True
        self._tool_name_map: dict[str, BaseTool] = {}
        self._ollama_tools: list[dict] = []

    def get_tool_name_map(self):
        """
        This generates an internal map of all tools against their names
        """
        if not self._tool_name_map:
            self._tool_name_map = {}
            for tool in component_registry.get():
                if isinstance(tool, BaseTool) and tool.enabled:
                    self._tool_name_map[tool.name] = tool
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

    async def call_each_tool_from_ollama(self, tool_call: dict[str, Any]) -> ToolBaseResponse:
        # TODO: Put validation on tool_call json.
        tool_name: str = (tool_call.get("function") or {}).get("name") or ""
        tool_args: dict[str, Any] = (tool_call.get("function") or {}).get("arguments") or {}
        try:
            tool = self.get_tool_name_map()[tool_name]
        except Exception as e:
            raise ToolNotFound() from e
        res = await tool.call_tool(tool.get_request_model().model_validate(tool_args))
        res.tool_name = tool_name
        return res

    async def call_tools_from_ollama(self, tool_calls: list[dict[str, Any]]) -> list[ToolBaseResponse]:
        final_res = []
        for tool_call in tool_calls:
            res = await self.call_each_tool_from_ollama(tool_call)
            final_res.append(res)
        return final_res
