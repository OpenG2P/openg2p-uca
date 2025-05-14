import logging

from openg2p_fastapi_common.context import dbengine
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from ...config import Settings
from ...schemas.tools import ProgramInfo, ProgramToolRequest, ProgramToolResponse
from .base import BaseTool

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class ProgramInfoTool(BaseTool):
    async def call_tool(self, request: ProgramToolRequest) -> ProgramToolResponse:
        async_session_maker = async_sessionmaker(dbengine.get())
        async with async_session_maker() as session:
            stmt = text("SELECT name, description from g2p_program")

            result = await session.execute(stmt)

            response = ProgramToolResponse(
                programs=[ProgramInfo.model_validate(rec._asdict()) for rec in result.all()]
            )
        return response
