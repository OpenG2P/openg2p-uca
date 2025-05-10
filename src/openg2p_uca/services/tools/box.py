import logging

from openg2p_fastapi_common.context import component_registry
from openg2p_fastapi_common.service import BaseService

from ...config import Settings
from ...errors import ToolNotFound
from .base import BaseTool

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class ToolboxService(BaseService):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.enabled = True
        self._tool_name_map: dict[str, BaseTool] = {}
        self._tools: list[dict] = []

    def register_tools(self):
        for tool in component_registry.get():
            if isinstance(tool, BaseTool) and tool.enabled:
                """
                TODO: Add tool into box when enabled
                """

    def get_tools(self):
        return self._tools

    async def call_tool(self, name, *args, **kw):
        try:
            tool = self._tool_name_map[name]
        except Exception as e:
            raise ToolNotFound() from e
        return await tool(*args, **kw)
