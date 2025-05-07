import logging
from datetime import datetime, timezone
from uuid import uuid4

from openg2p_fastapi_auth.controllers.auth_controller import AuthController
from openg2p_fastapi_auth.models.credentials import AuthCredentials

from ..config import Settings
from ..errors import UcaCommonException
from ..schemas.chat import ChatMessage, ChatThread
from ..schemas.ollama import OllamaChatMessage, OllamaChatRequest, OllamaChatResponse
from .chat_store import ChatStoreService
from .ollama_client import OllamaClientService

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class ThreadIdInvalid(UcaCommonException):
    def __init__(self, **kwargs):
        super().__init__(
            "G2P-UCA-404",
            "Thread id not found or invalid.",
            http_status_code=400,
            **kwargs,
        )


class AuthMissingUserId(UcaCommonException):
    def __init__(self, **kwargs):
        super().__init__(
            "G2P-UCA-103",
            "Missing user_id key auth credentials. Set valid value for `config.user_id_key_in_auth`.",
            **kwargs,
        )


class BaseAgent(OllamaClientService):
    def __init__(self, **kw):
        super().__init__(**kw)
        self._chat_store: ChatStoreService = None
        self._auth_controller: AuthController = None

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

    async def initialize_chat_thread(
        self,
        thread_id: str,
        auth: AuthCredentials,
        system_prompt_params: dict | None = None,
        initialized_at: datetime | None = None,
    ):
        initialized_at = initialized_at or datetime.now(timezone.utc)
        profile = await self.auth_controller.get_profile(auth, online=True)
        try:
            user_id = getattr(auth, _config.user_id_key_in_auth)
        except Exception as e:
            raise AuthMissingUserId() from e
        auth_params = {f"auth_{key}": val for key, val in profile.model_dump(mode="json").items()}
        auth_params["auth_user_id"] = user_id
        system_prompt_params = system_prompt_params or {}
        system_prompt_params = {**auth_params, **system_prompt_params}
        await self.chat_store_service.put_thread(
            ChatThread(
                id=thread_id,
                user_id=user_id,
                created_at=initialized_at,
            )
        )
        await self.chat_store_service.put_message(
            ChatMessage(
                id=str(uuid4()),
                thread_id=thread_id,
                user_id=user_id,
                sent_at=initialized_at,
                message_by="system",
                message=self.system_prompt_suffix_to_store.format(**system_prompt_params),
            )
        )

    async def chat(
        self,
        thread_id: str,
        message: str | None,
        user_id: str | None = None,
        message_sent_at: datetime | None = None,
        system_prompt_params: dict | None = None,
    ) -> OllamaChatResponse:
        """
        Chat API. Gets past messages from the thread and sends new message to Ollama.
        """
        full_messages = await self.chat_store_service.get_messages(
            thread_id=thread_id, user_id=user_id, limit=-1, sort="asc"
        )

        if not full_messages.messages:
            raise ThreadIdInvalid()

        # TODO: implement limit on user chat messages according to `config.chat_store_messages_limit`.

        full_messages = [
            OllamaChatMessage(role=msg.message_by, content=msg.message) for msg in full_messages.messages
        ]

        if message:
            full_messages.append(OllamaChatMessage(role="user", content=message))

        # Render System Prompt
        # TODO: Check if first message is system role.
        system_prompt_params = system_prompt_params or {}
        system_prompt_params["stored_suffix"] = full_messages[0].content
        if message_sent_at:
            system_prompt_params["current_date"] = message_sent_at.strftime("%Y-%m-%d")
            system_prompt_params["current_time"] = message_sent_at.strftime("%I: %M %p")
        full_messages[0].content = self.system_prompt.format(**system_prompt_params)

        return await self.ollama_chat_api(
            OllamaChatRequest(model=self.model, messages=full_messages, stream=False)
        )

    async def chat_and_store_by_user(
        self,
        thread_id: str,
        message: str | None,
        auth: AuthCredentials,
        message_sent_at: datetime | None = None,
        system_prompt_params: dict | None = None,
        **kw,
    ) -> ChatMessage:
        """
        User facing chat API, to be used for user chats.
        After successful response, user message and assistant response are stored back into Chat store.
        """
        message_sent_at = message_sent_at or datetime.now(timezone.utc)

        try:
            user_id = getattr(auth, _config.user_id_key_in_auth)
        except Exception as e:
            raise AuthMissingUserId() from e

        # Call Chat API
        res = await self.chat(
            thread_id,
            message,
            user_id=user_id,
            message_sent_at=message_sent_at,
            system_prompt_params=system_prompt_params,
            **kw,
        )

        # Store original User message and assistant response
        if message:
            user_chat_message = ChatMessage(
                id=str(uuid4()),
                thread_id=thread_id,
                user_id=user_id,
                sent_at=message_sent_at,
                message_by="user",
                message=message,
            )
            await self.chat_store_service.put_message(user_chat_message)
        assistant_chat_message = ChatMessage(
            id=str(uuid4()),
            thread_id=thread_id,
            user_id=user_id,
            sent_at=res.created_at,
            message_by=res.message.role,
            message=res.message.content,
        )
        await self.chat_store_service.put_message(assistant_chat_message)

        return assistant_chat_message


class MainAgent(BaseAgent):
    def __init__(self, **kw):
        super().__init__(**kw)

        with open(_config.main_agent_system_prompt_path) as file:
            sys_prompt = file.read()

        with open(_config.main_agent_system_prompt_suffix_to_store_path) as file:
            sys_prompt_suffix = file.read()

        self.configure(
            _config.main_agent_ollama_base_url,
            sys_prompt,
            _config.main_agent_ollama_model,
            system_prompt_suffix_to_store=sys_prompt_suffix,
            api_timeout=_config.main_agent_ollama_api_timeout,
        )
