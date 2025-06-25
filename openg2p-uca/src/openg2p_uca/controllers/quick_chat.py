import io
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Cookie, Response, UploadFile
from fastapi.responses import ORJSONResponse
from openg2p_fastapi_common.controller import BaseController
from openg2p_llm_common.errors import MessageIdInvalid, STTUnsupportedAudioFormat, ThreadIdInvalid
from openg2p_llm_common.services.chat_store import ChatStoreService

from ..config import Settings
from ..schemas.auth import AuthStatus, AuthType, UcaAuthCredentials
from ..schemas.chat import (
    UcaChatMessageRequest,
    UcaChatMessageResponse,
    UcaChatMessagesResponse,
    UcaChatSpeakMessageRequest,
)
from .chat import ChatController

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class QuickChatController(BaseController):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.router.prefix += "/quick_chat"
        self.router.tags += ["quick_chat"]
        self.router.add_api_route(
            "/thread",
            self.post_new_chat_thread,
            responses={200: {"model": UcaChatMessageResponse}},
            methods=["POST"],
        )

        self.router.add_api_route(
            "/thread",
            self.get_verify_current_chat_thread,
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

        self._chat_store: ChatStoreService = None
        self._chat_controller: ChatController = None

    @property
    def chat_store(self):
        if not self._chat_store:
            self._chat_store = ChatStoreService.get_component(name=_config.chat_store_transient_name)
        return self._chat_store

    @property
    def chat_controller(self):
        if not self._chat_controller:
            self._chat_controller = ChatController.get_component()
        return self._chat_controller

    @property
    def agent_system(self):
        return self.chat_controller.agent_system

    @property
    def auth_controller(self):
        return self.chat_controller.auth_controller

    @property
    def stt_service(self):
        return self.chat_controller.stt_service

    @property
    def tts_service(self):
        return self.chat_controller.tts_service

    async def post_new_chat_thread(self):
        """
        Initiate new quick chat. Quick Chat doesnt require auth.
        Quick chat messages are not stored and they are deleted after user is finished.
        Returns new session_id in cookie and the AI greeting message in response body.
        """
        new_thread_id = str(uuid4())

        await self.agent_system.initialize_chat_thread(new_thread_id, chat_store=self.chat_store)
        if _config.greeting_message_on_quick_chat:
            res_msg = await self.agent_system.chat_and_store(new_thread_id, None, chat_store=self.chat_store)
            message = self.chat_controller.filter_message(res_msg.message)
            message_id = res_msg.id
            message_by = res_msg.message_by
            message_sent_at = res_msg.sent_at
        else:
            message = ""
            message_id = ""
            message_by = "assistant"
            message_sent_at = datetime.now(timezone.utc)
        cred = UcaAuthCredentials(
            session_id=str(uuid.uuid4()),
            type=AuthType.quick_chat,
            status=AuthStatus.success,
            created_at=datetime.now(timezone.utc),
            expires_in=_config.qc_session_id_cookie_max_age,
            quick_chat_thread_id=new_thread_id,
        )
        self.auth_controller.update_cred_in_store(cred)
        response = ORJSONResponse(
            content=UcaChatMessageResponse(
                message=message,
                message_id=message_id,
                message_by=message_by,
                sent_at=message_sent_at,
            ).model_dump(mode="json")
        )
        response.set_cookie(
            _config.qc_session_id_cookie_name,
            cred.session_id,
            max_age=_config.qc_session_id_cookie_max_age,
            expires=(cred.created_at + timedelta(seconds=cred.expires_in)) if cred.expires_in else None,
            path=_config.qc_session_id_cookie_path or None,
            httponly=_config.qc_session_id_cookie_httponly,
            secure=_config.qc_session_id_cookie_secure,
        )
        return response

    async def get_verify_current_chat_thread(
        self, session_id: Annotated[str, Cookie(alias=_config.qc_session_id_cookie_name)]
    ):
        auth = self.auth_controller.get_credentials_from_session(session_id)
        if (not auth) or (auth.type != AuthType.quick_chat) or (not auth.quick_chat_thread_id):
            raise ThreadIdInvalid()

    async def post_new_chat_message(
        self,
        message: UcaChatMessageRequest,
        session_id: Annotated[str, Cookie(alias=_config.qc_session_id_cookie_name)],
    ):
        """
        Posts new message into quick chat, from request body.
        Returns AI's response in body.
        """
        auth = self.auth_controller.get_credentials_from_session(session_id)
        if (not auth) or (auth.type != AuthType.quick_chat) or (not auth.quick_chat_thread_id):
            raise ThreadIdInvalid()
        res = await self.agent_system.chat_and_store(
            auth.quick_chat_thread_id, message.message, chat_store=self.chat_store
        )
        return UcaChatMessageResponse(
            message=self.chat_controller.filter_message(res.message),
            message_id=res.id,
            message_by=res.message_by,
            sent_at=res.sent_at,
        )

    async def get_chat_messages(
        self,
        session_id: Annotated[str, Cookie(alias=_config.qc_session_id_cookie_name)],
        page: int = 0,
        limit: int = 100,
        sort: Literal["asc", "desc"] = "desc",
    ):
        """
        Get all messages of the given thread,
        based on limit and page number and sort order.
        """
        auth = self.auth_controller.get_credentials_from_session(session_id)
        if (not auth) or (auth.type != AuthType.quick_chat) or (not auth.quick_chat_thread_id):
            raise ThreadIdInvalid()
        res = await self.agent_system.get_chat_store(chat_store=self.chat_store).get_messages(
            thread_id=auth.quick_chat_thread_id,
            message_by=["assistant", "user"],
            page=page,
            limit=limit,
            sort=sort,
        )
        return UcaChatMessagesResponse(
            messages=[
                UcaChatMessageResponse(
                    message=self.chat_controller.filter_message(msg.message),
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
        session_id: Annotated[str, Cookie(alias=_config.qc_session_id_cookie_name)],
    ):
        """
        Posts new voice message into quick chat, from request body.
        Returns AI's response in body.
        """
        auth = self.auth_controller.get_credentials_from_session(session_id)
        if (not auth) or (auth.type != AuthType.quick_chat) or (not auth.quick_chat_thread_id):
            raise ThreadIdInvalid()
        if not audio.content_type.startswith("audio/"):
            raise STTUnsupportedAudioFormat()
        text_msg = self.stt_service.convert_audio_to_text(await audio.read())
        return await self.post_new_chat_message(UcaChatMessageRequest(message=text_msg), session_id)

    async def post_speak_message(
        self,
        request: UcaChatSpeakMessageRequest,
        session_id: Annotated[str, Cookie(alias=_config.qc_session_id_cookie_name)],
    ):
        auth = self.auth_controller.get_credentials_from_session(session_id)
        if (not auth) or (auth.type != AuthType.quick_chat) or (not auth.quick_chat_thread_id):
            raise ThreadIdInvalid()
        message = await self.chat_store.get_messages(
            message_id=request.message_id, thread_id=auth.quick_chat_thread_id
        )
        if len(message.messages) < 1:
            raise MessageIdInvalid()

        audio_file = io.BytesIO()
        self.tts_service.convert_text_to_audio(message.messages[0].message, audio_file)
        media_type = None
        if self.tts_service.get_audio_format() == "WAV":
            media_type = "audio/wav"
        return Response(content=audio_file.getvalue(), media_type=media_type)
