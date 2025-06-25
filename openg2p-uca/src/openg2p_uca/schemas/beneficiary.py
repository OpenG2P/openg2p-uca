from openg2p_llm_common.schemas.tools import ToolBaseRequest, ToolBaseResponse


class GetBeneficiaryIdToolRequest(ToolBaseRequest):
    program_id: int
    authenticated_user_id: str


class GetBeneficiaryIdToolResponse(ToolBaseResponse):
    beneficiary_id: int | None = None
    program_id: int | None = None
    beneficiary_status: str
