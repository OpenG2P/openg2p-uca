from datetime import datetime

from openg2p_llm_common.schemas.tools import ToolBaseRequest, ToolBaseResponse
from pydantic import BaseModel


class TicketInfo(BaseModel):
    ticket_number: str
    ticket_status: str
    ticket_resolution_message: str | None = None
    ticket_resolution_time: datetime | None = None


class GetGrievanceTicketStatusToolRequest(ToolBaseRequest):
    beneficiary_id: int
    program_id: int


class GetGrievanceTicketStatusToolResponse(ToolBaseResponse):
    tickets: list[TicketInfo]
