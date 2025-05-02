# ruff: noqa: E402

import asyncio

from fastapi import FastAPI

from .config import Settings

_config: Settings = Settings.get_config()

from openg2p_fastapi_auth.controllers.oauth_controller import OAuthController
from openg2p_fastapi_common.app import Initializer as BaseInitializer
from openg2p_fastapi_common.ping import PingController

from .controllers.auth import AuthController
from .controllers.chat import ChatController
from .services.agents import MainAgent
from .services.chat_store import ESChatStoreService


class Initializer(BaseInitializer):
    def initialize(self, **kwargs):
        super().initialize()

        PingController().post_init()
        AuthController().post_init()
        OAuthController().post_init()
        ChatController().post_init()
        self.main_agent = MainAgent()
        if _config.chat_store_es_enabled:
            self.chat_store = ESChatStoreService()

    def migrate_database(self, args, **kw):
        super().migrate_database(args, **kw)
        asyncio.run(self.chat_store.migrate())

    async def fastapi_app_shutdown(self, app: FastAPI):
        await super().fastapi_app_shutdown(app)
        await self.main_agent.aclose()
        if _config.chat_store_es_enabled:
            await self.chat_store.aclose()
