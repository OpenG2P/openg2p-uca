from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_serializer

from .ollama import OllamaChatMessageRole


##
## Internal APIs' schemas
##
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
    id: str
    thread_id: str
    user_id: str
    sent_at: datetime
    message_by: OllamaChatMessageRole
    message: str

    @field_serializer("sent_at")
    def serialize_dt(self, value: datetime):
        return value.replace(tzinfo=None).isoformat(timespec="milliseconds") + "Z"


class GetChatMessageResponse(BaseModel):
    count: int
    total_count: int
    messages: list[ChatMessage]
    user_id: str | None = None
    thread_id: str | None = None


##
## User facing chat APIs' schemas
##
UcaChatMessageRole = Literal[
    "assistant",
    "user",
]


class UcaChatMessageRequest(BaseModel):
    message: str


class UcaChatMessageResponse(BaseModel):
    message: str
    message_by: UcaChatMessageRole
    sent_at: datetime

    @field_serializer("sent_at")
    def serialize_dt(self, value: datetime):
        return value.replace(tzinfo=None).isoformat(timespec="milliseconds") + "Z"


class UcaChatMessagesResponse(BaseModel):
    messages: list[UcaChatMessageResponse]


class UcaChatThreadCreateResponse(BaseModel):
    thread_id: str
    thread_created_at: datetime
    message: str
    message_by: UcaChatMessageRole
    message_sent_at: datetime

    @field_serializer("message_sent_at", "thread_created_at")
    def serialize_dt(self, value: datetime):
        return value.replace(tzinfo=None).isoformat(timespec="milliseconds") + "Z"


class UcaChatThreadRequest(BaseModel):
    thread_id: str | None


class UcaChatThreadResponse(BaseModel):
    thread_id: str
    created_at: datetime

    @field_serializer("created_at")
    def serialize_dt(self, value: datetime):
        return value.replace(tzinfo=None).isoformat(timespec="milliseconds") + "Z"


class UcaChatThreadsResponse(BaseModel):
    threads: list[UcaChatThreadResponse]
