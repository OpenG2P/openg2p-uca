import logging

from openg2p_fastapi_common.context import dbengine
from openg2p_llm_common.services.tools.base import BaseTool
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..config import Settings
from ..controllers.auth import AuthController
from ..schemas.beneficiary import GetBeneficiaryIdToolRequest, GetBeneficiaryIdToolResponse

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class GetBeneficiaryIdTool(BaseTool):
    """
    This tool can be called to check the beneficiary status or enrollment status of the user against given program.
    User Authentication required to be Successful.
    """

    def __init__(self, **kw):
        super().__init__(**kw)
        self._auth_controller = None

    @property
    def auth_controller(self) -> AuthController:
        if not self._auth_controller:
            self._auth_controller = AuthController.get_component()
        return self._auth_controller

    async def call_tool(
        self, request: GetBeneficiaryIdToolRequest, agent=None, messages=None, **kw
    ) -> GetBeneficiaryIdToolResponse:
        async_session_maker = async_sessionmaker(dbengine.get())
        async with async_session_maker() as session:
            partner_id = await self.auth_controller.get_partner_id_from_user_id(
                request.user_id, session=session
            )
            ben = await self.get_beneficiary_id(partner_id, request.program_id, session)
        if not ben:
            return GetBeneficiaryIdToolResponse(beneficiary_status="not_found", program_id=request.program_id)
        else:
            ben = GetBeneficiaryIdToolResponse.model_validate(ben)
            if ben.beneficiary_status == "draft":
                ben.beneficiary_status = "applied"
            return ben

    async def get_beneficiary_id(self, partner_id: int, program_id: int, session: AsyncSession) -> int:
        if partner_id:
            stmt = text(
                """
                SELECT
                    id as beneficiary_id,
                    program_id,
                    state as beneficiary_status
                from g2p_program_membership
                    where partner_id = :partner_id and program_id = :program_id
                """
            )
            result = await session.execute(stmt, {"partner_id": partner_id, "program_id": program_id})
            bens = [res._asdict() for res in result.all()]

            if bens:
                return bens[0]

        return None
