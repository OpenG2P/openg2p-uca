import logging

from openg2p_fastapi_common.context import dbengine
from openg2p_llm_common.services.tools.base import BaseTool
from openg2p_llm_common.utils.timing import time_it
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..config import Settings
from ..schemas.grievance_status import (
    GetGrievanceTicketStatusToolRequest,
    GetGrievanceTicketStatusToolResponse,
    TicketInfo,
)

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class GetGrievanceTicketStatusTool(BaseTool):
    """
    Retrieves the status of grievance tickets for a specific beneficiary and program.
    Call the GetBeneficiaryIdTool to get the beneficiary ID.
    User Authentication required to be Successful.
    Returns ticket details including status, resolution message, and resolution time.
    """

    def __init__(self, **kw):
        super().__init__(**kw)
        self._stage_name_cache: dict[int, str] = {}
        self.stage_to_status_mapping: dict[str, str] = {
            "new": "Created",
            "in progress": "Assigned. Work in Progress",
            "waiting": "Waiting for confirmation",
            "done": "Resolved",
            "cancelled": "Closed without finishing",
        }

    @time_it("GetGrievanceTicketStatusTool.call_tool")
    async def call_tool(
        self, request: GetGrievanceTicketStatusToolRequest, agent=None, messages=None, **kw
    ) -> GetGrievanceTicketStatusToolResponse:
        async_session_maker = async_sessionmaker(dbengine.get())
        async with async_session_maker() as session:
            try:
                stmt = text(
                    """
                    SELECT
                        number as ticket_number,
                        stage_id,
                        resolution_message as ticket_resolution_message,
                        resolution_time as ticket_resolution_time
                    FROM support_ticket
                    WHERE beneficiary_id = :beneficiary_id
                    AND program_id = :program_id
                    AND active = :active
                    ORDER BY create_date DESC
                    """
                )

                result = await session.execute(
                    stmt,
                    {
                        "beneficiary_id": request.beneficiary_id,
                        "program_id": request.program_id,
                        "active": True,
                    },
                )

                tickets_data = [res._asdict() for res in result.all()]

                if not tickets_data:
                    return GetGrievanceTicketStatusToolResponse(tickets=[])

                tickets = []
                for ticket_row in tickets_data:
                    stage_name = await self.get_stage_name(ticket_row.pop("stage_id"), session)
                    ticket_row["ticket_status"] = self.get_stage_to_status_mapping(stage_name)

                    ticket_info = TicketInfo.model_validate(ticket_row)
                    if ticket_info.ticket_status != "Resolved":
                        ticket_info.ticket_resolution_message = None
                        ticket_info.ticket_resolution_time = None
                    tickets.append(ticket_info)

                return GetGrievanceTicketStatusToolResponse(tickets=tickets)

            except Exception:
                _logger.exception("Failed to retrieve grievance ticket status")
                return GetGrievanceTicketStatusToolResponse(tickets=[])

    @time_it("GetGrievanceTicketStatusTool.get_stage_name")
    async def get_stage_name(self, stage_id: int, session: AsyncSession) -> str:
        if stage_id not in self._stage_name_cache:
            stmt = text("SELECT name ->> :lang from support_stage where id = :stage_id")
            result = await session.execute(
                stmt, {"lang": _config.grm_ticket_new_stage_lang, "stage_id": stage_id}
            )
            stage_name = result.scalar()
            self._stage_name_cache[stage_id] = stage_name or "Unknown"  # Cache the stage_name
        return self._stage_name_cache[stage_id]

    def get_stage_to_status_mapping(self, stage: str) -> str:
        return self.stage_to_status_mapping[stage.lower()]
