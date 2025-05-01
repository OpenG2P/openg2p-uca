# ruff: noqa: E402

from fastapi import FastAPI

from .config import Settings

_config: Settings = Settings.get_config()

from openg2p_fastapi_auth.controllers.oauth_controller import OAuthController
from openg2p_fastapi_common.app import Initializer as BaseInitializer

from .controllers.auth import AuthController


class Initializer(BaseInitializer):
    def initialize(self, **kwargs):
        super().initialize()

        AuthController().post_init()
        OAuthController().post_init()

    async def fastapi_app_startup(self, app: FastAPI):
        await super().fastapi_app_startup(app)

    async def fastapi_app_shutdown(self, app: FastAPI):
        await super().fastapi_app_shutdown(app)
