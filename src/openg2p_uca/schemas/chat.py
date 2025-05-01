from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ChatMessageRole = Literal[
    "assistant",
    "user",
]


class ChatMessage(BaseModel):
    id: str
    thread_id: str
    user_id: str
    sent_at: datetime
    message_by: ChatMessageRole
    message: str


class GetChatMessageResponse(BaseModel):
    count: int
    total_count: int
    messages: list[ChatMessage]
    user_id: str | None = None
    thread_id: str | None = None
