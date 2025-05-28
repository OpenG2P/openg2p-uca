# ruff: noqa: E402

import asyncio

from .config import Settings

_config: Settings = Settings.get_config(strict=False)

from openg2p_fastapi_common.app import Initializer as BaseInitializer
from openg2p_fastapi_common.context import component_registry

from .services.agents import BaseAgent
from .services.chat_store import ChatStoreService


class Initializer(BaseInitializer):
    def migrate_database(self, args, **kw):
        super().migrate_database(args, **kw)
        for chat_store in component_registry.get():
            if isinstance(chat_store, ChatStoreService) and chat_store.enabled:
                asyncio.run(chat_store.migrate())

    async def fastapi_app_startup(self, app):
        await super().fastapi_app_startup(app)
        for service in component_registry.get():
            if isinstance(service, ChatStoreService) and service.enabled:
                await service.initialize()
            if isinstance(service, BaseAgent) and service.enabled:
                await service.initialize()

    async def fastapi_app_shutdown(self, app):
        await super().fastapi_app_shutdown(app)
        for service in component_registry.get():
            if isinstance(service, ChatStoreService) and service.enabled:
                await service.aclose()
            if isinstance(service, BaseAgent) and service.enabled:
                await service.aclose()
