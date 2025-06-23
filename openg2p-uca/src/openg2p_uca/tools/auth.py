import logging

from openg2p_llm_common.schemas.tools import ToolBaseRequest, ToolBaseResponse
from openg2p_llm_common.services.tools.base import BaseTool

from ..config import Settings
from ..controllers.auth import AuthController

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class SendOtpToolRequest(ToolBaseRequest):
    social_id: str


class SendOtpToolResponse(ToolBaseResponse):
    send_otp_status: str
    authentication_session_id: str | None = None


class ValidateOtpToolRequest(ToolBaseRequest):
    authentication_session_id: str
    otp: str


class ValidateOtpToolResponse(ToolBaseResponse):
    authentication_status: str
    authenticated_user_id: str | None = None


class PerformAuthenticationStepOneSendOtpTool(BaseTool):
    """
    This tool can perform step one of authentication, which is to send an OTP to the user,
    if authentication is not already successful.
    """

    def __init__(self, enabled=True, **kw):
        super().__init__(enabled=enabled, **kw)
        self._auth_controller = None

    @property
    def auth_controller(self) -> AuthController:
        if not self._auth_controller:
            self._auth_controller = AuthController.get_component()
        return self._auth_controller

    async def call_tool(
        self, request: SendOtpToolRequest, agent=None, messages=None, **kw
    ) -> SendOtpToolResponse:
        # TODO: validate social id
        cred = await self.auth_controller.send_otp_to_user_id(request.social_id)
        return SendOtpToolResponse(authentication_session_id=cred.session_id, send_otp_status="OTP Sent")


class PerformAuthenticationStepTwoValidateOtpTool(BaseTool):
    """
    This tool can perform step two of authentication, which is to validate the OTP,
    if authentication is not already successful.
    This can only be called if step one is completed.
    Returns authenticated_user_id only if authentication successful.
    The user is NOT aware of authentication_session_id.
    """

    def __init__(self, enabled=True, **kw):
        super().__init__(enabled=enabled, **kw)
        self._auth_controller = None

    @property
    def auth_controller(self) -> AuthController:
        if not self._auth_controller:
            self._auth_controller = AuthController.get_component()
        return self._auth_controller

    async def call_tool(
        self, request: ValidateOtpToolRequest, agent=None, messages=None, **kw
    ) -> ValidateOtpToolResponse:
        cred = self.auth_controller.get_credentials_from_session(request.authentication_session_id)
        if (not cred) or cred.otp != request.otp:
            return ValidateOtpToolResponse(authentication_status="Failed. OTP doesn't match")
        else:
            return ValidateOtpToolResponse(
                authenticated_user_id=cred.user_id, authentication_status="Successful. OTP matched."
            )
