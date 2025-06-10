from openg2p_llm_common.schemas.tools import ToolBaseRequest, ToolBaseResponse
from pydantic import BaseModel


class ProgramInfo(BaseModel):
    program_id: int
    program_name: str
    program_description: str | None


class ProgramToolRequest(ToolBaseRequest):
    pass


class ProgramToolResponse(ToolBaseResponse):
    programs: list[ProgramInfo]
