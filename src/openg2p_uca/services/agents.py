import logging
from datetime import datetime, timezone
from uuid import uuid4

from openg2p_fastapi_auth.models.credentials import AuthCredentials

from ..config import Settings
from ..errors import UcaCommonException
from ..schemas.chat import ChatMessage
from ..schemas.ollama import OllamaChatMessage, OllamaChatRequest, OllamaChatResponse
from .chat_store import ChatStoreService
from .ollama_client import OllamaClientService

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


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

    @property
    def chat_store_service(self):
        if not self._chat_store:
            self._chat_store = ChatStoreService.get_component()
        return self._chat_store

    async def chat(
        self,
        thread_id: str,
        message: str,
        system_prompt_params: dict | None = None,
    ) -> OllamaChatResponse:
        """
        Chat API. Gets past messages from the thread and sends new message to Ollama.
        `message` maybe None also.
        """
        full_messages = await self.chat_store_service.get_messages(thread_id=thread_id, limit=-1, sort="asc")
        full_messages = [
            OllamaChatMessage(role=msg.message_by, content=msg.message) for msg in full_messages.messages
        ]

        if message:
            full_messages.append(OllamaChatMessage(role="user", content=message))

        system_prompt_params = system_prompt_params or {}
        full_messages.insert(
            0, OllamaChatMessage(role="system", content=self.system_prompt.format(**system_prompt_params))
        )

        return await self.ollama_chat_api(
            OllamaChatRequest(model=self.model, messages=full_messages, stream=False)
        )

    async def chat_and_store_by_user(
        self,
        thread_id: str,
        message: str,
        auth: AuthCredentials,
        message_sent_at: datetime | None = None,
        system_prompt_params: dict | None = None,
        **kw,
    ) -> ChatMessage:
        """
        User facing chat API, to be used for user chats.
        After successful response, user message and assistant response are stored back into Chat store.
        """
        message_sent_at = message_sent_at or datetime.now(timezone.utc).replace(tzinfo=None)

        auth_params = {f"auth_{key}": val for key, val in auth.model_dump(mode="json").items()}
        system_prompt_params = system_prompt_params or {}
        system_prompt_params = {**auth_params, **system_prompt_params}
        try:
            user_id = getattr(auth, _config.user_id_key_in_auth)
        except Exception as e:
            raise AuthMissingUserId() from e

        # Call Chat API
        res = await self.chat(thread_id, message, system_prompt_params=system_prompt_params, **kw)

        # Store original User message and assistant response
        user_chat_message = ChatMessage(
            id=str(uuid4()),
            thread_id=thread_id,
            user_id=user_id,
            sent_at=message_sent_at,
            message_by="user",
            message=message,
        )
        assistant_chat_message = ChatMessage(
            id=str(uuid4()),
            thread_id=thread_id,
            user_id=user_id,
            sent_at=res.created_at,
            message_by=res.message.role,
            message=res.message.content,
        )
        await self.chat_store_service.put_message(user_chat_message)
        await self.chat_store_service.put_message(assistant_chat_message)

        return assistant_chat_message
