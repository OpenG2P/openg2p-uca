from pydantic import BaseModel, Field
from pydantic.json_schema import SkipJsonSchema


class ToolBaseRequest(BaseModel):
    pass


class ToolBaseResponse(BaseModel):
    tool_name: SkipJsonSchema[str] = Field(default="", exclude=True)
