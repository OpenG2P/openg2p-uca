import logging
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Cookie, Depends
from fastapi.responses import ORJSONResponse
from openg2p_fastapi_auth.dependencies import JwtBearerAuth
from openg2p_fastapi_auth.models.credentials import AuthCredentials
from openg2p_fastapi_common.controller import BaseController

from ..config import Settings
from ..schemas.chat import (
    UcaChatMessageRequest,
    UcaChatMessageResponse,
    UcaChatMessagesResponse,
    UcaChatThreadResponse,
    UcaChatThreadsResponse,
)
from ..services.agents import AuthMissingUserId, MainAgent
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
            methods=["POST"],
        )

        self.router.add_api_route(
            "/newChatMessage",
            self.post_new_chat_message,
            responses={200: {"model": UcaChatMessageResponse}},
            methods=["POST"],
        )

        self.router.add_api_route(
            "/getMessages",
            self.get_chat_messages,
            responses={200: {"model": UcaChatMessagesResponse}},
            methods=["GET"],
        )

        self.router.add_api_route(
            "/getThreads",
            self.get_chat_threads,
            responses={200: {"model": UcaChatThreadsResponse}},
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
        response = ORJSONResponse(
            UcaChatMessageResponse(message=res.message, message_by=res.message_by, sent_at=res.sent_at)
        )
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
        return UcaChatMessageResponse(message=res.message, message_by=res.message_by, sent_at=res.sent_at)

    async def get_chat_messages(
        self,
        thread_id: Annotated[str, Cookie(alias=_config.thread_id_cookie_name)],
        auth: Annotated[AuthCredentials, Depends(JwtBearerAuth())],
        page: int = 0,
        limit: int = 10,
        sort: Literal["asc", "desc"] = "desc",
    ):
        try:
            user_id = getattr(auth, _config.user_id_key_in_auth)
        except Exception as e:
            raise AuthMissingUserId() from e
        res = await self.chat_store_service.get_messages(
            thread_id=thread_id,
            user_id=user_id,
            message_by=["assistant", "user"],
            page=page,
            limit=limit,
            sort=sort,
        )
        return UcaChatMessagesResponse(
            messages=[
                UcaChatMessageResponse(message=msg.message, message_by=msg.message_by, sent_at=msg.sent_at)
                for msg in res.messages
            ]
        )

    async def get_chat_threads(
        self,
        auth: Annotated[AuthCredentials, Depends(JwtBearerAuth())],
        page: int = 0,
        limit: int = 10,
        sort: Literal["asc", "desc"] = "desc",
    ):
        try:
            user_id = getattr(auth, _config.user_id_key_in_auth)
        except Exception as e:
            raise AuthMissingUserId() from e
        res = await self.chat_store_service.get_threads(user_id=user_id, page=page, limit=limit, sort=sort)
        return UcaChatThreadsResponse(
            threads=[
                UcaChatThreadResponse(thread_id=thread.id, created_at=thread.created_at)
                for thread in res.threads
            ]
        )
