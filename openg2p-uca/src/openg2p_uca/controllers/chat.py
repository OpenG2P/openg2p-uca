import io
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Cookie, Depends, Response, UploadFile
from fastapi.responses import ORJSONResponse
from openg2p_fastapi_common.controller import BaseController
from openg2p_llm_common.errors import MessageIdInvalid, STTUnsupportedAudioFormat, ThreadIdInvalid
from openg2p_llm_common.services.agents import BaseAgentSystem
from openg2p_llm_common.services.stt.base import BaseSTTService
from openg2p_llm_common.services.tts.base import BaseTTSService

from ..auth_dep import UcaSessionAuth
from ..config import Settings
from ..schemas.auth import UcaAuthCredentials
from ..schemas.chat import (
    UcaChatMessageRequest,
    UcaChatMessageResponse,
    UcaChatMessagesResponse,
    UcaChatSpeakMessageRequest,
    UcaChatThreadCreateResponse,
    UcaChatThreadRequest,
    UcaChatThreadResponse,
    UcaChatThreadsResponse,
)
from .auth import AuthController

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

        self.router.add_api_route(
            "/voice_message",
            self.post_new_voice_message,
            responses={200: {"model": UcaChatMessageResponse}},
            methods=["POST"],
        )

        self.router.add_api_route(
            "/speak_message",
            self.post_speak_message,
            response_class=Response,
            responses={200: {"content": {"audio/wav": {}}}},
            methods=["POST"],
        )

        self._agent_system: BaseAgentSystem = None
        self._auth_controller: AuthController = None
        self._stt_service: BaseSTTService = None
        self._tts_service: BaseTTSService = None

    @property
    def agent_system(self):
        if not self._agent_system:
            self._agent_system = BaseAgentSystem.get_component()
        return self._agent_system

    @property
    def auth_controller(self):
        if not self._auth_controller:
            self._auth_controller = AuthController.get_component()
        return self._auth_controller

    @property
    def stt_service(self):
        if not self._stt_service:
            self._stt_service = BaseSTTService.get_component()
        return self._stt_service

    @property
    def tts_service(self):
        if not self._tts_service:
            self._tts_service = BaseTTSService.get_component()
        return self._tts_service

    async def post_new_chat_thread(self, auth: Annotated[UcaAuthCredentials, Depends(UcaSessionAuth())]):
        """
        Initiate new chat threads. Returns new thread_id in cookie
        and the AI greeting message in response body.
        """
        new_thread_id = str(uuid4())
        user_profile = auth.user_profile
        user_profile["user_id"] = auth.user_id

        res_thread = await self.agent_system.initialize_chat_thread(new_thread_id, user_profile=user_profile)
        if _config.greeting_message_on_chat:
            res_msg = await self.agent_system.chat_and_store(new_thread_id, None, user_id=auth.user_id)
            message = self.filter_message(res_msg.message)
            message_id = res_msg.id
            message_by = res_msg.message_by
            message_sent_at = res_msg.sent_at
        else:
            message = ""
            message_id = ""
            message_by = "assistant"
            message_sent_at = datetime.now(timezone.utc)
        response = ORJSONResponse(
            content=UcaChatThreadCreateResponse(
                thread_id=res_thread.id,
                thread_created_at=res_thread.created_at,
                message=message,
                message_id=message_id,
                message_by=message_by,
                message_sent_at=message_sent_at,
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
        auth: Annotated[UcaAuthCredentials, Depends(UcaSessionAuth())],
        response: Response,
    ):
        """
        Switch to new thread_id given in request body. Or clear current thread_id if given null.
        """
        if not thread.thread_id:
            response.delete_cookie(_config.thread_id_cookie_name)
        else:
            res = await self.agent_system.get_chat_store().get_threads(
                user_id=auth.user_id, thread_id=thread.thread_id
            )
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
        auth: Annotated[UcaAuthCredentials, Depends(UcaSessionAuth())],
    ):
        """
        Get the current thread_id of logged in user.
        """
        res = await self.agent_system.get_chat_store().get_threads(user_id=auth.user_id, thread_id=thread_id)
        if len(res.threads) < 1:
            # Raise error if thread_id doesn't exists against give user_id.
            raise ThreadIdInvalid()
        # Returns the same thread_id given in cookie.
        return UcaChatThreadResponse(thread_id=res.threads[0].id, created_at=res.threads[0].created_at)

    async def get_chat_threads(
        self,
        auth: Annotated[UcaAuthCredentials, Depends(UcaSessionAuth())],
        page: int = 0,
        limit: int = 100,
        sort: Literal["asc", "desc"] = "desc",
    ):
        """
        Get all threads of the logged in user,
        based on limit and page number and sort order.
        """
        res = await self.agent_system.get_chat_store().get_threads(
            user_id=auth.user_id, page=page, limit=limit, sort=sort
        )
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
        auth: Annotated[UcaAuthCredentials, Depends(UcaSessionAuth())],
    ):
        """
        Posts new message, from request body, into the thread_id given in cookie.
        Returns AI's response in body.
        """
        res = await self.agent_system.chat_and_store(thread_id, message.message, user_id=auth.user_id)
        return UcaChatMessageResponse(
            message=self.filter_message(res.message),
            message_id=res.id,
            message_by=res.message_by,
            sent_at=res.sent_at,
        )

    async def get_chat_messages(
        self,
        thread_id: Annotated[str, Cookie(alias=_config.thread_id_cookie_name)],
        auth: Annotated[UcaAuthCredentials, Depends(UcaSessionAuth())],
        page: int = 0,
        limit: int = 100,
        sort: Literal["asc", "desc"] = "desc",
    ):
        """
        Get all messages of the given thread,
        based on limit and page number and sort order.
        """
        res = await self.agent_system.get_chat_store().get_messages(
            thread_id=thread_id,
            user_id=auth.user_id,
            message_by=["assistant", "user"],
            page=page,
            limit=limit,
            sort=sort,
        )
        return UcaChatMessagesResponse(
            messages=[
                UcaChatMessageResponse(
                    message=self.filter_message(msg.message),
                    message_id=msg.id,
                    message_by=msg.message_by,
                    sent_at=msg.sent_at,
                )
                for msg in res.messages
                if msg.message
            ]
        )

    async def post_new_voice_message(
        self,
        audio: UploadFile,
        thread_id: Annotated[str, Cookie(alias=_config.thread_id_cookie_name)],
        auth: Annotated[UcaAuthCredentials, Depends(UcaSessionAuth())],
    ):
        """
        Posts new voice message, from request body, into the thread_id given in cookie.
        Returns AI's response in body.
        """
        if not audio.content_type.startswith("audio/"):
            raise STTUnsupportedAudioFormat()
        text_msg = self.stt_service.convert_audio_to_text(await audio.read())
        return await self.post_new_chat_message(UcaChatMessageRequest(message=text_msg), thread_id, auth)

    async def post_speak_message(
        self,
        request: UcaChatSpeakMessageRequest,
        thread_id: Annotated[str, Cookie(alias=_config.thread_id_cookie_name)],
        auth: Annotated[UcaAuthCredentials, Depends(UcaSessionAuth())],
    ):
        message = await self.agent_system.get_chat_store().get_messages(
            user_id=auth.user_id, message_id=request.message_id, thread_id=thread_id
        )
        if len(message.messages) < 1:
            raise MessageIdInvalid()

        audio_file = io.BytesIO()
        self.tts_service.convert_text_to_audio(message.messages[0].message, audio_file)
        media_type = None
        if self.tts_service.get_audio_format() == "WAV":
            media_type = "audio/wav"
        return Response(content=audio_file.getvalue(), media_type=media_type)

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
