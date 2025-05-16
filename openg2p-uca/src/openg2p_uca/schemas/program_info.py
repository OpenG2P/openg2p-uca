from openg2p_llm_common.schemas.tools import ToolBaseRequest, ToolBaseResponse
from pydantic import BaseModel


class ProgramInfo(BaseModel):
    id: int
    name: str
    description: str | None


class ProgramToolRequest(ToolBaseRequest):
    pass


class ProgramToolResponse(ToolBaseResponse):
    programs: list[ProgramInfo]
