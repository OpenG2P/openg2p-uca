import logging
from typing import TYPE_CHECKING

from fastapi import Request
from fastapi.security.http import HTTPBase
from openg2p_fastapi_common.errors.http_exceptions import (
    InternalServerError,
    UnauthorizedError,
)

if TYPE_CHECKING:
    from .controllers.auth import AuthController

from .config import Settings
from .schemas.auth import AuthStatus, UcaAuthCredentials

_config = Settings.get_config(strict=False)
_logger = logging.getLogger(_config.logging_default_logger_name)


class UcaSessionAuth(HTTPBase):
    def __init__(self, scheme="session", **kwargs):
        super().__init__(scheme=scheme, **kwargs)
        self._auth_controller = None

    @property
    def auth_controller(self) -> "AuthController":
        if not self._auth_controller:
            from .controllers.auth import AuthController

            self._auth_controller = AuthController.get_component()
        return self._auth_controller

    async def __call__(self, request: Request) -> UcaAuthCredentials | None:
        config_dict = _config.model_dump()
        if not config_dict.get("auth_enabled", None):
            return self.auth_controller.get_credentials_from_session(None)

        api_call_name = str(request.scope["route"].name)

        api_auth_settings = config_dict.get("auth_api_" + api_call_name, {})

        if (not api_auth_settings) or (not api_auth_settings.get("enabled", None)):
            return self.auth_controller.get_credentials_from_session(None)

        session_id = request.cookies.get(_config.session_id_cookie_name)
        if not session_id:
            raise UnauthorizedError()

        try:
            creds = self.auth_controller.get_credentials_from_session(session_id)
        except Exception as e:
            _logger.exception("Session Authentication Failed.")
            raise InternalServerError() from e
        if (not creds) or creds.status != AuthStatus.success:
            raise UnauthorizedError(message="Unauthorized. Invalid session_id")
        return creds
