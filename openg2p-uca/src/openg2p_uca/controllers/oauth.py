import http.cookies
import logging
import uuid
from datetime import datetime, timedelta, timezone

import orjson
from fastapi import Request
from openg2p_fastapi_auth.controllers.oauth_controller import OAuthController as BaseOauthController

from ..config import Settings
from ..schemas.auth import AuthStatus, AuthType, UcaAuthCredentials
from .auth import AuthController

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class OAuthController(BaseOauthController):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def auth_controller(self) -> AuthController:
        if not self._auth_controller:
            self._auth_controller = AuthController.get_component()
        return self._auth_controller

    async def oauth_callback(self, request: Request, **kw):
        res = await super().oauth_callback(request, **kw)

        login_provider_id = orjson.loads(request.query_params.get("state", "{}")).get("p", None)
        login_provider = await self.auth_controller.get_login_provider_db_by_id(login_provider_id)

        set_cookies = res.headers.getlist("set-cookie")
        if "set-cookie" in res.headers:
            del res.headers["set-cookie"]
        access_token = None
        id_token = None
        for set_cookie_str in set_cookies:
            set_cookie = http.cookies.SimpleCookie()
            set_cookie.load(set_cookie_str)
            access_token = set_cookie.get("X-Access-Token")
            access_token = access_token.value if access_token else None
            id_token = set_cookie.get("X-ID-Token")
            id_token = id_token.value if id_token else None

        user_profile = await self.auth_controller.get_oauth_validation_data(
            access_token, id_token=id_token, provider=login_provider, combine=True
        )

        cred = UcaAuthCredentials(
            session_id=str(uuid.uuid4()),
            type=AuthType.oauth2_auth_code,
            status=AuthStatus.success,
            user_id=None,  # TODO: Set user_id
            user_profile=user_profile,
            created_at=datetime.now(timezone.utc),
            expires_in=_config.session_id_cookie_max_age,
            oauth2_login_provider_id=login_provider_id,
            oauth2_id_type=await self.auth_controller.get_login_provider_id_type(login_provider_id),
            oauth2_sub=user_profile.get("sub", None),
            oauth2_iss=user_profile.get("iss", None),
            oauth2_access_token=access_token,
            oauth2_id_token=id_token,
        )
        self.auth_controller.update_cred_in_store(cred)
        res.set_cookie(
            _config.session_id_cookie_name,
            cred.session_id,
            max_age=_config.session_id_cookie_max_age,
            expires=(cred.created_at + timedelta(seconds=cred.expires_in)) if cred.expires_in else None,
            path=_config.session_id_cookie_path or None,
            httponly=_config.session_id_cookie_httponly,
            secure=_config.session_id_cookie_secure,
        )
        return res
