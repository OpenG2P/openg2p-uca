import logging
from datetime import datetime, timezone

from openg2p_fastapi_common.context import dbengine
from openg2p_llm_common.services.tools.base import BaseTool
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..config import Settings
from ..schemas.grievance import (
    CreateGrievanceTicketToolRequest,
    CreateGrievanceTicketToolResponse,
)

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class CreateGrievanceTicketTool(BaseTool):
    """
    Creates a grievance ticket in the support system for a verified beneficiary.
    Requires beneficiary_id, program_id, and complaint details.
    "subject" is a summarized version of user's issue.
    "description" is the elaborate version of user's issue.
    User Authentication required to be Successful.
    """

    def __init__(self, **kw):
        super().__init__(**kw)
        self._stage_id: int = None

    async def call_tool(
        self, request: CreateGrievanceTicketToolRequest, agent=None, messages=None, **kw
    ) -> CreateGrievanceTicketToolResponse:
        ticket_create_time = datetime.now(timezone.utc).replace(tzinfo=None)
        async_session_maker = async_sessionmaker(dbengine.get())
        async with async_session_maker() as session:
            try:
                ticket_number = await self.generate_ticket_number(session)
                stmt = text(
                    """
                    INSERT INTO support_ticket (
                        number,
                        name,
                        description,
                        priority,
                        stage_id,
                        program_id,
                        beneficiary_id,
                        active,
                        create_uid,
                        create_date
                    )
                    VALUES (
                        :ticket_number,
                        :subject,
                        :description,
                        :priority,
                        :stage_id,
                        :program_id,
                        :beneficiary_id,
                        :active,
                        :create_uid,
                        :create_date
                    )
                    """
                )
                await session.execute(
                    stmt,
                    {
                        "ticket_number": ticket_number,
                        "subject": request.grievance_subject,
                        "description": request.grievance_description,
                        "priority": "1",
                        "stage_id": await self.get_stage_id(session),
                        "program_id": request.program_id,
                        "beneficiary_id": request.beneficiary_id,
                        "active": True,
                        "create_uid": _config.grm_ticket_create_uid,
                        "create_date": ticket_create_time,
                    },
                )
                await session.commit()

                return CreateGrievanceTicketToolResponse(
                    ticket_number=ticket_number,
                    ticket_creation_status="success",
                    ticket_creation_message=f"Grievance ticket {ticket_number} has been created successfully",
                )
            except Exception:
                _logger.exception("Failed to create grievance ticket")
                return CreateGrievanceTicketToolResponse(
                    ticket_number=None,
                    ticket_creation_status="error",
                    ticket_creation_message="Failed to create grievance ticket.",
                )

    async def get_stage_id(self, session: AsyncSession) -> int:
        if not self._stage_id:
            stmt = text("SELECT id from support_stage where name ->> :lang = :name")
            result = await session.execute(
                stmt, {"lang": _config.grm_ticket_new_stage_lang, "name": _config.grm_ticket_new_stage_name}
            )
            self._stage_id = result.scalar()  # Cache the stage_id
        return self._stage_id

    async def generate_ticket_number(self, session: AsyncSession) -> str:
        stmt = text("SELECT count(1) from support_ticket")
        result = await session.execute(stmt)
        ticket_count = result.scalar()
        ticket_count += 1
        return f"{_config.grm_ticket_number_prefix}{ticket_count:0{_config.grm_ticket_number_padding}d}"
