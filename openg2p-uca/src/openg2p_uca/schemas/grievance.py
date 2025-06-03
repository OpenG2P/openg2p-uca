from openg2p_llm_common.schemas.tools import ToolBaseRequest, ToolBaseResponse


class CreateGrievanceTicketToolRequest(ToolBaseRequest):
    grievance_subject: str
    grievance_description: str
    program_id: int
    beneficiary_id: int


class CreateGrievanceTicketToolResponse(ToolBaseResponse):
    ticket_number: str | None = None
    ticket_creation_status: str
    ticket_creation_message: str
