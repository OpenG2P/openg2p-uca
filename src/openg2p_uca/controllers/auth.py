from fastapi import Response
from openg2p_fastapi_auth.controllers.auth_controller import AuthController as BaseAuthController
from openg2p_fastapi_auth.models.orm.login_provider import LoginProvider

from ..config import Settings
from ..models.auth_oauth_provider import AuthOauthProviderORM

_config = Settings.get_config()


class AuthController(BaseAuthController):
    async def get_login_providers_db(self) -> list[LoginProvider]:
        return [ap.map_auth_provider_to_login_provider() for ap in await AuthOauthProviderORM.get_all()]

    async def get_login_provider_db_by_id(self, id: int) -> LoginProvider:
        ap = await AuthOauthProviderORM.get_by_id(id)
        return ap.map_auth_provider_to_login_provider() if ap else None

    async def get_login_provider_db_by_iss(self, iss: str) -> LoginProvider:
        ap = await AuthOauthProviderORM.get_auth_provider_from_iss(iss)
        return ap.map_auth_provider_to_login_provider() if ap else None

    async def logout(self, response: Response):
        await super().logout(response)
        response.delete_cookie(_config.thread_id_cookie_name)
