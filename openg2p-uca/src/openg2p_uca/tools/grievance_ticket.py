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
    def __init__(self, **kw):
        super().__init__(**kw)

    def get_description(self):
        """
        Creates a grievance ticket in the support system for a verified beneficiary.
        Requires beneficiary_id, program_id, and complaint details.
        """
        return self.get_description.__doc__

    async def verify_beneficiary_program(
        self, session: AsyncSession, beneficiary_id: int = 51, program_id: int = 6
    ) -> bool:
        """Verify that the beneficiary is enrolled in the specified program"""
        stmt = text(
            "SELECT id, state from g2p_program_membership "
            "where id = :beneficiary_id and program_id = :program_id"
        )
        result = await session.execute(
            stmt, {"beneficiary_id": beneficiary_id, "program_id": program_id}
        )
        membership = result.first()
        
        if membership and membership.state in ["enrolled", "active", "Running"]:
            return True
        return False

    async def create_ticket(
        self, name: str, session: AsyncSession, beneficiary_id: int, program_id: int
    ) -> int:
        """Create a new support ticket and return its ID"""
        stmt = text(
            "INSERT INTO support.ticket (name, program_id, beneficiary_id, create_date) "
            "VALUES (:name, :program_id, :beneficiary_id, :create_date) "
            "RETURNING number"
        )
        result = await session.execute(
            stmt,
            {
                "name": name,
                "program_id": program_id,
                "beneficiary_id": beneficiary_id,
                "create_date": datetime.now(timezone.utc),
            },
        )
        await session.commit()
        return result.scalar()

    async def call_tool(
        self, request: CreateGrievanceTicketToolRequest, messages=None
    ) -> CreateGrievanceTicketToolResponse:
        async_session_maker = async_sessionmaker(dbengine.get())
        async with async_session_maker() as session:
            is_valid = await self.verify_beneficiary_program(
                session, request.beneficiary_id, request.program_id
            )
            
            if not is_valid:
                return CreateGrievanceTicketToolResponse(
                    ticket_id=None,
                    status="error",
                    message="Beneficiary is not enrolled in the specified program or enrollment is not active",
                )
            
            try:
                ticket_id = await self.create_ticket(
                    request.name, session, request.beneficiary_id, request.program_id
                )
                
                return CreateGrievanceTicketToolResponse(
                    ticket_id=ticket_id,
                    status="success",
                    message=f"Grievance ticket #{ticket_id} has been created successfully",
                )
            except Exception as e:
                _logger.error(f"Failed to create grievance ticket: {e}")
                return CreateGrievanceTicketToolResponse(
                    ticket_id=None,
                    status="error",
                    message="Failed to create grievance ticket. Please try again later.",
                )