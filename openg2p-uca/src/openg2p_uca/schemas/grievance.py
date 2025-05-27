from datetime import datetime

from openg2p_llm_common.schemas.tools import ToolBaseRequest, ToolBaseResponse
from pydantic import BaseModel


class CreateGrievanceTicketToolRequest(ToolBaseRequest):
    name: str
    program_id: int
    beneficiary_id: int


class CreateGrievanceTicketToolResponse(ToolBaseResponse):
    ticket_id: int | None = None
    status: str
    message: str | None = None


class GrievanceTicket(BaseModel):
    name: str
    program_id: int
    beneficiary_id: int
    created_at: datetime | None = None
