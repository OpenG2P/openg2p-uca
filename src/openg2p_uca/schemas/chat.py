from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_serializer

ChatMessageRole = Literal[
    "system",
    "assistant",
    "user",
]


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
    message_by: ChatMessageRole
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


class UcaChatMessageRequest(BaseModel):
    message: str


class UcaChatMessageResponse(BaseModel):
    message: str
    message_by: ChatMessageRole
    sent_at: datetime

    @field_serializer("sent_at")
    def serialize_dt(self, value: datetime):
        return value.replace(tzinfo=None).isoformat(timespec="milliseconds") + "Z"


class UcaChatThreadResponse(BaseModel):
    thread_id: str
    created_at: datetime

    @field_serializer("created_at")
    def serialize_dt(self, value: datetime):
        return value.replace(tzinfo=None).isoformat(timespec="milliseconds") + "Z"


class UcaChatMessagesResponse(BaseModel):
    messages: list[UcaChatMessageResponse]


class UcaChatThreadsResponse(BaseModel):
    threads: list[UcaChatThreadResponse]
