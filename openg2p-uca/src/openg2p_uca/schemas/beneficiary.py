from openg2p_llm_common.schemas.tools import ToolBaseRequest, ToolBaseResponse


class GetBeneficiaryIdToolRequest(ToolBaseRequest):
    program_id: int
    user_id: str


class GetBeneficiaryIdToolResponse(ToolBaseResponse):
    id: int | None
    status: str
