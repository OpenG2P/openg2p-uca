import logging

from openg2p_fastapi_common.context import dbengine
from openg2p_llm_common.services.tools.base import BaseTool
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from ..config import Settings
from ..schemas.program_info import ProgramInfo, ProgramToolRequest, ProgramToolResponse

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class ProgramInfoTool(BaseTool):
    """Retrieves information about all the programs."""

    async def call_tool(
        self, request: ProgramToolRequest, agent=None, messages=None, **kw
    ) -> ProgramToolResponse:
        async_session_maker = async_sessionmaker(dbengine.get())
        async with async_session_maker() as session:
            stmt = text(
                "SELECT id, name, description from g2p_program where state='active' and active = True"
            )

            result = await session.execute(stmt)

            response = ProgramToolResponse(
                programs=[ProgramInfo.model_validate(rec._asdict()) for rec in result.all()]
            )
        return response
