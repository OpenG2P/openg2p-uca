import logging
from typing import Annotated
from uuid import uuid4

from fastapi import Cookie, Depends
from fastapi.responses import ORJSONResponse
from openg2p_fastapi_auth.dependencies import JwtBearerAuth
from openg2p_fastapi_auth.models.credentials import AuthCredentials
from openg2p_fastapi_common.controller import BaseController

from ..config import Settings
from ..schemas.chat import UcaChatMessageRequest, UcaChatMessageResponse
from ..services.agents import MainAgent
from ..services.chat_store import ChatStoreService

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class ChatController(BaseController):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.router.add_api_route(
            "/newChat",
            self.post_new_chat_thread,
            responses={200: {"model": UcaChatMessageResponse}},
            methods=["GET"],
        )

        self.router.add_api_route(
            "/newChatMessage",
            self.post_new_chat_thread,
            responses={200: {"model": UcaChatMessageResponse}},
            methods=["GET"],
        )

        self._main_agent: MainAgent = None
        self._chat_store: ChatStoreService = None

    @property
    def main_agent(self):
        if not self._main_agent:
            self._main_agent = MainAgent.get_component()
        return self._main_agent

    @property
    def chat_store_service(self):
        if not self._chat_store:
            self._chat_store = ChatStoreService.get_component()
        return self._chat_store

    async def post_new_chat_thread(self, auth: Annotated[AuthCredentials, Depends(JwtBearerAuth())]):
        new_thread_id = str(uuid4())
        await self.main_agent.initialize_chat_thread(new_thread_id, auth)
        res = await self.main_agent.chat_and_store_by_user(new_thread_id, None, auth)
        response = ORJSONResponse(UcaChatMessageResponse(message=res.message))
        response.set_cookie(
            _config.thread_id_cookie_name,
            new_thread_id,
            path=_config.thread_id_cookie_path or None,
            httponly=_config.thread_id_cookie_httponly,
            secure=_config.thread_id_cookie_secure,
        )
        return response

    async def post_new_chat_message(
        self,
        message: UcaChatMessageRequest,
        auth: Annotated[AuthCredentials, Depends(JwtBearerAuth())],
        thread_id: Annotated[str, Cookie(alias=_config.thread_id_cookie_name)],
    ):
        res = await self.main_agent.chat_and_store_by_user(thread_id, message.message, auth)
        return UcaChatMessageResponse(message=res.message)
