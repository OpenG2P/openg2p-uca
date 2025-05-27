import logging

from openg2p_fastapi_common.context import dbengine
from openg2p_llm_common.services.tools.base import BaseTool
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..config import Settings
from ..schemas.beneficiary import GetBeneficiaryIdToolRequest, GetBeneficiaryIdToolResponse

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class GetBeneficiaryIdTool(BaseTool):
    """
    Checks whether the user, with the given user_id,
    exists in the program, with the program_id
    and returns beneficiary id and status.
    """

    def __init__(self, **kw):
        super().__init__(**kw)
        self._id_type_id: int = None

    async def get_partner_id(self, user_id: str, session: AsyncSession) -> int | None:
        stmt = text("SELECT partner_id from g2p_reg_id where value = :value and id_type = :id_type")
        result = await session.execute(
            stmt, {"value": user_id, "id_type": await self.get_id_type_id(session)}
        )
        partner_id = result.scalar()

        return int(partner_id) if partner_id else None

    async def get_beneficiary_id(self, partner_id: int, program_id: int, session: AsyncSession) -> int:
        if partner_id:
            stmt = text(
                "SELECT id, state as status from g2p_program_membership where partner_id = :partner_id and program_id = :program_id"
            )
            result = await session.execute(stmt, {"partner_id": partner_id, "program_id": program_id})
            bens = [res._asdict() for res in result.all()]

            if bens:
                return bens[0]

        return None

    async def get_id_type_id(self, session: AsyncSession):
        if not self._id_type_id:
            stmt = text("SELECT id from g2p_id_type where name = :name")
            result = await session.execute(stmt, {"name": _config.user_id_id_type})
            self._id_type_id = result.scalar()  # Cache the id_type_id
        return self._id_type_id

    async def call_tool(
        self, request: GetBeneficiaryIdToolRequest, messages=None
    ) -> GetBeneficiaryIdToolResponse:
        async_session_maker = async_sessionmaker(dbengine.get())
        async with async_session_maker() as session:
            partner_id = await self.get_partner_id(request.user_id, session)
            ben = await self.get_beneficiary_id(partner_id, request.program_id, session)
        if not ben:
            return GetBeneficiaryIdToolResponse(status="not_found")
        else:
            ben = GetBeneficiaryIdToolResponse.model_validate(ben)
            if ben.status == "draft":
                ben.status = "applied"
            return ben
