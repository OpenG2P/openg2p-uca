from openg2p_fastapi_common.utils.holder import Holder

from ...schemas.tools import ToolBaseRequest, ToolBaseResponse
from ...services.agents import BaseAgent, BaseAgentSystem
from .base import BaseTool


class ChangeAgentToolRequest(ToolBaseRequest):
    new_agent_name: str


class ChangeAgentToolResponse(ToolBaseResponse):
    pass


class ChangeAgentTool(BaseTool):
    """
    Call this tool to switch the current chat to new agent.
    """

    def __init__(self, **kw):
        super().__init__(**kw)
        self._agent_system: BaseAgentSystem = None

    @property
    def agent_system(self):
        if not self._agent_system:
            self._agent_system = BaseAgentSystem.get_component()
        return self._agent_system

    async def call_tool(
        self, request: ChangeAgentToolRequest, agent: Holder[BaseAgent], messages=None
    ) -> ChangeAgentToolResponse:
        agent.set(self.agent_system.get_agent(request.new_agent_name))
        return ChangeAgentToolResponse()
