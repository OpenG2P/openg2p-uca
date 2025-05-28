from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_serializer

from .ollama import OllamaChatMessageRole


class ChatThread(BaseModel):
    id: str
    user_id: str
    created_at: datetime

    @field_serializer("created_at")
    def serialize_dt(self, value: datetime):
        return value.replace(tzinfo=None).isoformat(timespec="milliseconds") + "Z"


class GetChatThreadResponse(BaseModel):
    count: int
    total_count: int
    threads: list[ChatThread]
    user_id: str | None = None


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    thread_id: str
    user_id: str
    sent_at: datetime
    message_by: OllamaChatMessageRole
    message: str
    tool_name: str | None = None
    last_used_agent: str | None = None

    @field_serializer("sent_at")
    def serialize_dt(self, value: datetime):
        return value.replace(tzinfo=None).isoformat(timespec="milliseconds") + "Z"


class GetChatMessageResponse(BaseModel):
    count: int
    total_count: int
    messages: list[ChatMessage]
    user_id: str | None = None
    thread_id: str | None = None
