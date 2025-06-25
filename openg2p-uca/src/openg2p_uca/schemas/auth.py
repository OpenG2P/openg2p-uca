from datetime import datetime
from enum import Enum

from pydantic import BaseModel, field_serializer


class AuthType(Enum):
    otp = "otp"
    quick_chat = "quick_chat"
    oauth2_auth_code = "oauth2_auth_code"


class AuthStatus(Enum):
    inprogress = "inprogress"
    success = "success"
    failed = "failed"


class UcaAuthCredentials(BaseModel):
    session_id: str
    type: AuthType
    status: AuthStatus
    otp: str | None = None
    user_id: str | None = None
    user_profile: dict | None = None
    created_at: datetime
    expires_in: int | None = None
    quick_chat_thread_id: str | None = None
    oauth2_login_provider_id: int | None = None
    oauth2_id_type: int | None = None
    oauth2_sub: str | None = None
    oauth2_iss: str | None = None
    oauth2_access_token: str | None = None
    oauth2_id_token: str | None = None

    @field_serializer("created_at")
    def serialize_dt(self, value: datetime):
        return value.replace(tzinfo=None).isoformat(timespec="milliseconds") + "Z"


class UcaAuthSendOtpRequest(BaseModel):
    user_id: str  # This should change based on impl.


class UcaAuthSendOtpResponse(BaseModel):
    status: str


class UcaAuthAuthenticateOtpRequest(BaseModel):
    otp: str


class UcaAuthAuthenticateOtpResponse(BaseModel):
    status: str
