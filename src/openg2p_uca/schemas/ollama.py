from datetime import datetime, timedelta, timezone
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
            value = value.strip()
            if value.endswith("Z"):
                value = value.removesuffix("Z")
                tz = timezone.utc
            elif value.count(":") > 2:
                tz_str = value[-6:]  # Last 6 digits are timezone info not ending with Z.
                tz_sign = 1 if tz_str[0] == "+" else -1
                tz_hours_str, tz_minutes_str = tz_str[1:].split(":")
                tz = timezone(
                    timedelta(seconds=(tz_sign * (3600 * int(tz_hours_str) + 60 * int(tz_minutes_str))))
                )
                value = value[:-6]
            else:
                # No Timezone is present
                tz = None
            msecs = None
            if len(value.split(".")) > 1:
                msecs_str = value.split(".")[1]
                value = value.split(".")[0]
                if len(msecs_str) <= 3:
                    msecs = int(msecs_str) * 1000  # Milliseconds
                elif len(msecs_str) <= 6:
                    msecs = int(msecs_str)  # Microseconds
                else:
                    msecs = int(msecs_str[0:6])  # Nanoseconds or more
            value = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
            value = value.replace(microsecond=msecs, tzinfo=tz).astimezone(tz=timezone.utc)
        return value
