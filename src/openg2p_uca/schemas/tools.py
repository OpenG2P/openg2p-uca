from pydantic import BaseModel, Field
from pydantic.json_schema import SkipJsonSchema


class ToolBaseRequest(BaseModel):
    pass


class ToolBaseResponse(BaseModel):
    tool_name: SkipJsonSchema[str] = Field(default="", exclude=True)


class ProgramInfo(BaseModel):
    name: str
    description: str | None


class ProgramToolRequest(ToolBaseRequest):
    pass


class ProgramToolResponse(ToolBaseResponse):
    programs: list[ProgramInfo]
