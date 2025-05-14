import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Cookie, Depends, Response
from fastapi.responses import ORJSONResponse
from openg2p_fastapi_auth.controllers.auth_controller import AuthController
from openg2p_fastapi_auth.dependencies import JwtBearerAuth
from openg2p_fastapi_auth.models.credentials import AuthCredentials
from openg2p_fastapi_auth.models.profile import BasicProfile
from openg2p_fastapi_common.controller import BaseController
from openg2p_llm_common.errors import ThreadIdInvalid
from openg2p_llm_common.services.chat_store import ChatStoreService

from ..config import Settings
from ..errors import AuthMissingUserId
from ..schemas.chat import (
    UcaChatMessageRequest,
    UcaChatMessageResponse,
    UcaChatMessagesResponse,
    UcaChatThreadCreateResponse,
    UcaChatThreadRequest,
    UcaChatThreadResponse,
    UcaChatThreadsResponse,
)
from ..services.agents import MainAgent

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class ChatController(BaseController):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.router.prefix += "/chat"
        self.router.tags += ["chat"]
        self.router.add_api_route(
            "/thread",
            self.post_new_chat_thread,
            responses={200: {"model": UcaChatThreadCreateResponse}},
            methods=["POST"],
        )

        self.router.add_api_route(
            "/thread",
            self.put_change_chat_thread,
            methods=["PUT"],
        )

        self.router.add_api_route(
            "/thread",
            self.get_current_chat_thread,
            responses={200: {"model": UcaChatThreadResponse}},
            methods=["GET"],
        )

        self.router.add_api_route(
            "/threads",
            self.get_chat_threads,
            responses={200: {"model": UcaChatThreadsResponse}},
            methods=["GET"],
        )

        self.router.add_api_route(
            "/message",
            self.post_new_chat_message,
            responses={200: {"model": UcaChatMessageResponse}},
            methods=["POST"],
        )

        self.router.add_api_route(
            "/messages",
            self.get_chat_messages,
            responses={200: {"model": UcaChatMessagesResponse}},
            methods=["GET"],
        )

        self._main_agent: MainAgent = None
        self._chat_store: ChatStoreService = None
        self._auth_controller: AuthController = None

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

    @property
    def auth_controller(self):
        if not self._auth_controller:
            self._auth_controller = AuthController.get_component()
        return self._auth_controller

    async def post_new_chat_thread(self, auth: Annotated[AuthCredentials, Depends(JwtBearerAuth())]):
        """
        Initiate new chat threads. Returns new thread_id in cookie
        and the AI greeting message in response body.
        """
        new_thread_id = str(uuid4())
        user_profile = await self.auth_controller.get_profile(auth, online=True)
        user_id = self.get_user_id(user_profile)

        res_thread = await self.main_agent.initialize_chat_thread(
            new_thread_id, user_id, user_profile=user_profile
        )
        res_msg = await self.main_agent.chat_and_store_by_user(new_thread_id, None, user_id)
        response = ORJSONResponse(
            content=UcaChatThreadCreateResponse(
                thread_id=res_thread.id,
                thread_created_at=res_thread.created_at,
                message=self.filter_message(res_msg.message),
                message_by=res_msg.message_by,
                message_sent_at=res_msg.sent_at,
            ).model_dump(mode="json")
        )
        cookie_expires = None
        if _config.thread_id_cookie_max_age:
            cookie_expires = res_thread.created_at + timedelta(seconds=_config.thread_id_cookie_max_age)
        response.set_cookie(
            _config.thread_id_cookie_name,
            res_thread.id,
            max_age=_config.thread_id_cookie_max_age,
            expires=cookie_expires,
            path=_config.thread_id_cookie_path or None,
            httponly=_config.thread_id_cookie_httponly,
            secure=_config.thread_id_cookie_secure,
        )
        return response

    async def put_change_chat_thread(
        self,
        thread: UcaChatThreadRequest,
        auth: Annotated[AuthCredentials, Depends(JwtBearerAuth())],
        response: Response,
    ):
        """
        Switch to new thread_id given in request body. Or clear current thread_id if given null.
        """
        if not thread.thread_id:
            response.delete_cookie(_config.thread_id_cookie_name)
        else:
            user_id = self.get_user_id(auth)
            res = await self.chat_store_service.get_threads(user_id=user_id, thread_id=thread.thread_id)
            if len(res.threads) < 1:
                # Raise error if thread_id doesn't exists against give user_id.
                raise ThreadIdInvalid()
            cookie_age = _config.thread_id_cookie_max_age
            cookie_expires = None
            if cookie_age:
                cookie_expires = datetime.now(timezone.utc) + timedelta(seconds=cookie_age)
            response.set_cookie(
                _config.thread_id_cookie_name,
                thread.thread_id,
                max_age=cookie_age,
                expires=cookie_expires,
                path=_config.thread_id_cookie_path or None,
                httponly=_config.thread_id_cookie_httponly,
                secure=_config.thread_id_cookie_secure,
            )

    async def get_current_chat_thread(
        self,
        thread_id: Annotated[str, Cookie(alias=_config.thread_id_cookie_name)],
        auth: Annotated[AuthCredentials, Depends(JwtBearerAuth())],
    ):
        """
        Get the current thread_id of logged in user.
        """
        user_id = self.get_user_id(auth)
        res = await self.chat_store_service.get_threads(user_id=user_id, thread_id=thread_id)
        if len(res.threads) < 1:
            # Raise error if thread_id doesn't exists against give user_id.
            raise ThreadIdInvalid()
        # Returns the same thread_id given in cookie.
        return UcaChatThreadResponse(thread_id=res.threads[0].id, created_at=res.threads[0].created_at)

    async def get_chat_threads(
        self,
        auth: Annotated[AuthCredentials, Depends(JwtBearerAuth())],
        page: int = 0,
        limit: int = 100,
        sort: Literal["asc", "desc"] = "desc",
    ):
        """
        Get all threads of the logged in user,
        based on limit and page number and sort order.
        """
        user_id = self.get_user_id(auth)
        res = await self.chat_store_service.get_threads(user_id=user_id, page=page, limit=limit, sort=sort)
        return UcaChatThreadsResponse(
            threads=[
                UcaChatThreadResponse(thread_id=thread.id, created_at=thread.created_at)
                for thread in res.threads
            ]
        )

    async def post_new_chat_message(
        self,
        message: UcaChatMessageRequest,
        thread_id: Annotated[str, Cookie(alias=_config.thread_id_cookie_name)],
        auth: Annotated[AuthCredentials, Depends(JwtBearerAuth())],
    ):
        """
        Posts new message, from request body, into the thread_id given in cookie.
        Returns AI's response in body.
        """
        res = await self.main_agent.chat_and_store_by_user(thread_id, message.message, self.get_user_id(auth))
        return UcaChatMessageResponse(
            message=self.filter_message(res.message), message_by=res.message_by, sent_at=res.sent_at
        )

    async def get_chat_messages(
        self,
        thread_id: Annotated[str, Cookie(alias=_config.thread_id_cookie_name)],
        auth: Annotated[AuthCredentials, Depends(JwtBearerAuth())],
        page: int = 0,
        limit: int = 100,
        sort: Literal["asc", "desc"] = "desc",
    ):
        """
        Get all messages of the given thread,
        based on limit and page number and sort order.
        """
        user_id = self.get_user_id(auth)
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
                UcaChatMessageResponse(
                    message=self.filter_message(msg.message), message_by=msg.message_by, sent_at=msg.sent_at
                )
                for msg in res.messages
                if msg.message
            ]
        )

    def filter_message(self, message: str, strip=True) -> str:
        flags = _config.api_message_response_filter_flags
        regexs = _config.api_message_response_filters_regex
        subs = _config.api_message_response_filters_sub
        if message and regexs:
            for regex, subst in zip(regexs, subs):
                message = re.sub(regex, subst, message, flags=flags)
                if strip:
                    message = message.strip()
        return message

    def get_user_id(self, auth: AuthCredentials | BasicProfile):
        try:
            return getattr(auth, _config.user_id_key_in_auth)
        except Exception as e:
            raise AuthMissingUserId() from e
