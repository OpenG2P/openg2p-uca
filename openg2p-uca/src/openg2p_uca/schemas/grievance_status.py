from openg2p_llm_common.schemas.tools import ToolBaseRequest, ToolBaseResponse
from pydantic import BaseModel
from datetime import datetime


class TicketInfo(BaseModel):
    ticket_number: str
    stage_name: str
    resolution_message: str | None = None
    resolution_time: datetime | None = None


class GetGrievanceTicketStatusToolRequest(ToolBaseRequest):
    beneficiary_id: int
    program_id: int


class GetGrievanceTicketStatusToolResponse(ToolBaseResponse):
    ticket_number: str | None
    stage_name: str
    resolution_message: str | None
    resolution_time: datetime | None
    status_check_message: str