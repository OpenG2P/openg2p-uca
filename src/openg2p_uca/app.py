# ruff: noqa: E402

import asyncio

from fastapi import FastAPI

from .config import Settings

_config: Settings = Settings.get_config()

from openg2p_fastapi_auth.controllers.oauth_controller import OAuthController
from openg2p_fastapi_common.app import Initializer as BaseInitializer
from openg2p_fastapi_common.context import component_registry
from openg2p_fastapi_common.ping import PingController

from .controllers.auth import AuthController
from .controllers.chat import ChatController
from .services.agents import BaseAgent, MainAgent
from .services.chat_store import ChatStoreService, ESChatStoreService
from .services.tools.box import ToolboxService


class Initializer(BaseInitializer):
    def initialize(self, **kwargs):
        super().initialize()

        PingController().post_init()
        AuthController().post_init()
        OAuthController().post_init()
        ChatController().post_init()
        if _config.chat_store_es_enabled:
            ESChatStoreService()
        MainAgent()
        ToolboxService()

    def migrate_database(self, args, **kw):
        super().migrate_database(args, **kw)
        for chat_store in component_registry.get():
            if isinstance(chat_store, ChatStoreService) and chat_store.enabled:
                asyncio.run(chat_store.migrate())

    async def fastapi_app_startup(self, app: FastAPI):
        await super().fastapi_app_startup(app)
        for service in component_registry.get():
            if isinstance(service, ChatStoreService) and service.enabled:
                await service.initialize()
            if isinstance(service, BaseAgent) and service.enabled:
                await service.initialize()
            if isinstance(service, ToolboxService) and service.enabled:
                service.register_tools()

    async def fastapi_app_shutdown(self, app: FastAPI):
        await super().fastapi_app_shutdown(app)
        for service in component_registry.get():
            if isinstance(service, ChatStoreService) and service.enabled:
                await service.aclose()
            if isinstance(service, BaseAgent) and service.enabled:
                await service.aclose()
