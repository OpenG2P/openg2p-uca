import logging
from datetime import datetime, timezone
from uuid import uuid4

from openg2p_fastapi_auth.controllers.auth_controller import AuthController
from openg2p_fastapi_auth.models.credentials import AuthCredentials
from openg2p_fastapi_auth.models.profile import BasicProfile
from openg2p_fastapi_common.service import BaseService

from ..config import Settings
from ..errors import AuthMissingUserId, ThreadIdInvalid
from ..schemas.chat import ChatMessage, ChatThread
from ..schemas.ollama import OllamaChatMessage, OllamaChatRequest, OllamaChatResponse
from .chat_store import ChatStoreService
from .ollama_client import OllamaClientService
from .tools.box import ToolboxService

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class BaseAgent(BaseService):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.enabled = True
        self.ollama_client: OllamaClientService = None

        self.system_prompt: str = None
        self.system_prompt_suffix_to_store: str = None

        self._chat_store: ChatStoreService = None
        self._auth_controller: AuthController = None
        self._tool_box: ToolboxService = None

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

    @property
    def tool_box(self):
        if not self._tool_box:
            self._tool_box = ToolboxService.get_component()
        return self._tool_box

    async def initialize(self):
        """
        Each agent implementation needs to override this.
        Typically configuring ollama client etc tasks will be called in this step.
        Example at the end of this file.
        """
        raise NotImplementedError()

    async def aclose(self):
        await self.ollama_client.unload_model()
        await self.ollama_client.aclose()

    async def initialize_chat_thread(
        self,
        thread_id: str,
        auth: AuthCredentials,
        system_prompt_params: dict | None = None,
        initialized_at: datetime | None = None,
    ) -> ChatThread:
        initialized_at = initialized_at or datetime.now(timezone.utc)
        profile = await self.auth_controller.get_profile(auth, online=True)
        user_id = self.get_user_id(profile)
        auth_params = {f"auth_{key}": val for key, val in profile.model_dump(mode="json").items()}
        auth_params["auth_user_id"] = user_id
        system_prompt_params = system_prompt_params or {}
        system_prompt_params = {**auth_params, **system_prompt_params}
        thread = ChatThread(
            id=thread_id,
            user_id=user_id,
            created_at=initialized_at,
        )
        await self.chat_store_service.put_thread(thread)
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
        return thread

    async def chat(
        self,
        thread_id: str,
        message: str | None,
        user_id: str | None = None,
        message_sent_at: datetime | None = None,
        system_prompt_params: dict | None = None,
    ) -> list[OllamaChatResponse]:
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
            system_prompt_params["current_time"] = message_sent_at.strftime("%I: %M %p UTC")
        full_messages[0].content = self.system_prompt.format(**system_prompt_params)

        return [
            await self.ollama_client.chat(
                OllamaChatRequest(messages=full_messages, stream=False, tools=self.tool_box.get_tools())
            )
        ]

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

        user_id = self.get_user_id(auth)

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
        for msg in res:
            chat_msg = ChatMessage(
                id=str(uuid4()),
                thread_id=thread_id,
                user_id=user_id,
                sent_at=msg.created_at,
                message_by=msg.message.role,
                message=msg.message.content,
            )
            await self.chat_store_service.put_message(chat_msg)

        # Returns the last chat message to User
        return chat_msg

    def get_user_id(self, auth: AuthCredentials | BasicProfile):
        try:
            return getattr(auth, _config.user_id_key_in_auth)
        except Exception as e:
            raise AuthMissingUserId() from e


class MainAgent(BaseAgent):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.enabled = _config.main_agent_enabled

    async def initialize(self):
        with open(_config.main_agent_system_prompt_path) as file:
            self.system_prompt = file.read()

        with open(_config.main_agent_system_prompt_suffix_to_store_path) as file:
            self.system_prompt_suffix_to_store = file.read()

        self.ollama_client = OllamaClientService(
            _config.main_agent_ollama_base_url,
            _config.main_agent_ollama_model,
            api_timeout=_config.main_agent_ollama_api_timeout,
            keep_alive=_config.main_agent_ollama_keep_alive,
            options=_config.main_agent_ollama_extra_options,
        )
        await self.ollama_client.load_model()
