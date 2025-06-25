import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import orjson
from fastapi import Depends, Request, Response
from fastapi.responses import ORJSONResponse
from openg2p_fastapi_auth.controllers.auth_controller import AuthController as BaseAuthController
from openg2p_fastapi_auth.models.orm.login_provider import LoginProvider
from openg2p_fastapi_auth.models.profile import BasicProfile
from openg2p_fastapi_common.context import dbengine
from openg2p_fastapi_common.errors.http_exceptions import InternalServerError, UnauthorizedError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from valkey import Valkey

from ..auth_dep import UcaSessionAuth
from ..config import Settings
from ..orm.auth_oauth_provider import AuthOauthProviderORM
from ..schemas.auth import (
    AuthStatus,
    AuthType,
    UcaAuthAuthenticateOtpRequest,
    UcaAuthAuthenticateOtpResponse,
    UcaAuthCredentials,
    UcaAuthSendOtpRequest,
    UcaAuthSendOtpResponse,
)

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class AuthController(BaseAuthController):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.router.add_api_route(
            "/send_otp",
            self.post_send_otp,
            responses={200: {"model": UcaAuthSendOtpResponse}},
            methods=["POST"],
        )
        self.router.add_api_route(
            "/authenticate_otp",
            self.post_authenticate_otp,
            responses={200: {"model": UcaAuthAuthenticateOtpResponse}},
            methods=["POST"],
        )

        self._session_store = None
        self._lp_id_type_cache: dict[int, int] = {}
        self._id_type_id_cache: dict[str, int] = {}

    @property
    def session_store(self) -> Valkey:
        if not self._session_store:
            self._session_store = Valkey(
                host=_config.auth_session_store_host,
                port=_config.auth_session_store_port,
                db=_config.auth_session_store_db,
                password=_config.auth_session_store_password,
            )
        return self._session_store

    async def get_login_providers_db(self) -> list[LoginProvider]:
        return [ap.map_auth_provider_to_login_provider() for ap in await AuthOauthProviderORM.get_all()]

    async def get_login_provider_db_by_id(self, id: int) -> LoginProvider:
        ap = await AuthOauthProviderORM.get_by_id(id)
        return ap.map_auth_provider_to_login_provider() if ap else None

    async def get_login_provider_db_by_iss(self, iss: str) -> LoginProvider:
        ap = await AuthOauthProviderORM.get_auth_provider_from_iss(iss)
        return ap.map_auth_provider_to_login_provider() if ap else None

    async def get_login_provider_id_type(self, login_provider_id: int) -> int:
        if login_provider_id not in self._lp_id_type_cache:
            ap = await AuthOauthProviderORM.get_by_id(login_provider_id)
            self._lp_id_type_cache[login_provider_id] = ap.g2p_id_type
        return self._lp_id_type_cache[login_provider_id]

    async def get_profile(self, auth: Annotated[UcaAuthCredentials, Depends(UcaSessionAuth())]):
        """
        Get Profile Data of the authenticated user/entity.
        This can also be used to check whether or not the Authentication is present and valid.
        """
        return BasicProfile.model_validate(auth.user_profile)

    async def logout(self, request: Request, response: Response):
        session_id = request.cookies.get(_config.session_id_cookie_name)
        if session_id:
            self.delete_cred_from_store(session_id)
        response.delete_cookie(_config.session_id_cookie_name)
        response.delete_cookie(_config.thread_id_cookie_name)

    async def post_send_otp(self, request: UcaAuthSendOtpRequest):
        # TODO: Validate User ID
        cred = await self.send_otp_to_user_id(request.user_id)
        res = ORJSONResponse(content=UcaAuthSendOtpResponse(status="ok").model_dump(mode="json"))
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

    async def post_authenticate_otp(self, otp: UcaAuthAuthenticateOtpRequest, request: Request):
        session_id = request.cookies.get(_config.session_id_cookie_name)
        if not session_id:
            raise UnauthorizedError()

        try:
            creds = self.get_credentials_from_session(session_id)
        except Exception as e:
            _logger.exception("Session Authentication Failed.")
            raise InternalServerError() from e
        if (not creds) or creds.type != AuthType.otp:
            raise UnauthorizedError(message="Unauthorized. Invalid session_id")

        if otp.otp != creds.otp:
            raise UnauthorizedError(message="Unauthorized. Invalid otp")
        # TODO: Fetch user_profile and update creds
        creds.status = AuthStatus.success
        self.update_cred_in_store(creds)
        return UcaAuthAuthenticateOtpResponse(status="ok")

    async def send_otp_to_user_id(self, user_id: str) -> UcaAuthCredentials:
        # This method needs to be changed based on impl.
        cred = UcaAuthCredentials(
            session_id=str(uuid.uuid4()),
            type=AuthType.otp,
            status=AuthStatus.inprogress,
            otp=_config.auth_dummy_otp,
            user_id=user_id,
            created_at=datetime.now(timezone.utc),
            expires_in=_config.session_id_cookie_max_age,
        )
        self.update_cred_in_store(cred)
        return cred

    def update_cred_in_store(self, creds: UcaAuthCredentials):
        self.session_store.set(
            creds.session_id, orjson.dumps(creds.model_dump(mode="json")).decode(), ex=creds.expires_in
        )

    def delete_cred_from_store(self, session_id: str):
        self.session_store.delete(session_id)

    def get_credentials_from_session(self, session_id: str) -> UcaAuthCredentials | None:
        if (not session_id) and _config.auth_dummy_user_data:
            # Return dummy cred
            return UcaAuthCredentials(
                session_id=_config.auth_dummy_user_data.get("session_id"),
                type=AuthType.otp,
                status=AuthStatus.success,
                user_id=_config.auth_dummy_user_data.get("user_id"),
                user_profile=_config.auth_dummy_user_data,
                created_at=datetime.now(timezone.utc),
            )
        sess = self.session_store.get(session_id)
        if not sess:
            return None
        return UcaAuthCredentials.model_validate(orjson.loads(sess))

    async def get_partner_id_from_user_id(self, user_id: str, session: AsyncSession = None) -> int | None:
        orig_session = session
        if not orig_session:
            session = async_sessionmaker(dbengine.get())()
        stmt = text("SELECT partner_id from g2p_reg_id where value = :value and id_type = :id_type")
        result = await session.execute(
            stmt, {"value": user_id, "id_type": await self.get_id_type_id(_config.user_id_id_type, session)}
        )
        partner_id = result.scalar()

        if not orig_session:
            await session.close()

        return int(partner_id) if partner_id else None

    async def get_id_type_id(self, id_type: str, session: AsyncSession = None) -> int | None:
        if self._id_type_id_cache.get(id_type) is not None:
            return self._id_type_id_cache[id_type]
        orig_session = session
        if not orig_session:
            session = async_sessionmaker(dbengine.get())()
        stmt = text("SELECT id from g2p_id_type where name = :name")
        result = await session.execute(stmt, {"name": id_type})
        id_type_id = result.scalar()
        self._id_type_id_cache[id_type] = int(id_type_id) if id_type_id else None  # Cache the id_type_id
        if not orig_session:
            await session.close()
        return self._id_type_id_cache[id_type]
