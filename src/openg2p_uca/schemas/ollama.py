from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator

OllamaChatMessageRole = Literal[
    "assistant",
    "user",
    "system",
]


class OllamaChatMessage(BaseModel):
    role: OllamaChatMessageRole
    content: str


class OllamaChatRequest(BaseModel):
    model: str
    messages: list[OllamaChatMessage]
    stream: bool = False


class OllamaChatResponse(BaseModel):
    model: str
    created_at: datetime
    message: OllamaChatMessage
    done: bool
    total_duration: int
    load_duration: int
    prompt_eval_count: int
    prompt_eval_duration: int
    eval_count: int
    eval_duration: int

    @field_validator("created_at", mode="before")
    @classmethod
    def validate_created_at(cls, value) -> datetime:
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value
