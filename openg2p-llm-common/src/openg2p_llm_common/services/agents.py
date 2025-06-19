import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import orjson
from openg2p_fastapi_common.service import BaseService
from openg2p_fastapi_common.utils.holder import Holder

from ..config import Settings
from ..errors import ThreadIdInvalid
from ..schemas.chat import ChatMessage, ChatThread
from ..schemas.ollama import OllamaChatMessage, OllamaChatRequest, OllamaChatResponse
from .chat_store import ChatStoreService
from .ollama_client import OllamaClientService
from .tools.box import ToolboxService

_config = Settings.get_config(strict=False)
_logger = logging.getLogger(_config.logging_default_logger_name)


class BaseAgent(BaseService):
    def __init__(self, name: str = "", enabled=True, **kw):
        super().__init__(name=name, **kw)
        self.enabled = enabled
        self.ollama_client: OllamaClientService = None

        self.system_prompt: str = None

        self._tool_box: ToolboxService = None

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

    async def chat(
        self,
        messages: list[OllamaChatMessage],
        message_sent_at: datetime | None = None,
        system_prompt_params: dict | None = None,
        **kw,
    ) -> list[OllamaChatResponse | OllamaChatMessage]:
        """
        Chat API - Agent Level. Given list of messages, this agent will communicate with Ollama according to its function.
        """
        pre_render_system_msg = messages[0].content
        self.render_system_prompt(
            messages, message_sent_at=message_sent_at, system_prompt_params=system_prompt_params, **kw
        )

        ollama_res = [
            await self.ollama_client.chat(
                OllamaChatRequest(messages=messages, stream=False, tools=self.tool_box.get_ollama_tools())
            )
        ]
        ollama_res[0].message.agent_name = self.name
        if ollama_res[0].message.content:
            messages.append(ollama_res[0].message)
        messages[0].content = pre_render_system_msg
        await self.handle_tool_calls(
            messages,
            ollama_res,
            message_sent_at=message_sent_at,
            system_prompt_params=system_prompt_params,
            **kw,
        )
        return ollama_res

    async def handle_tool_calls(
        self,
        messages: list[OllamaChatMessage],
        responses: list[OllamaChatResponse | OllamaChatMessage],
        message_sent_at: datetime | None = None,
        system_prompt_params: dict | None = None,
        **kw,
    ):
        """
        Recursive function that handles the Ollama tool_calls requests, sends the tool response to agent.
        Receives tools calls requests again from ollama and repeats the process until no tool_calls requested by ollama.
        """
        if not (
            len(responses) >= 1
            and isinstance(responses[-1], OllamaChatResponse)
            and responses[-1].message.tool_calls
        ):
            return
        self_h = Holder[BaseAgent](self)
        tool_res = await self.tool_box.call_tools_from_ollama(
            responses[-1].message.tool_calls, self_h, messages=messages, **kw
        )
        new_agent = self_h.get()
        for msg in tool_res:
            tool_msg = orjson.dumps(msg.model_dump(mode="json")).decode()
            tool_msg = OllamaChatMessage(
                role="tool", name=msg.tool_name, content=tool_msg, agent_name=new_agent.name
            )
            messages.append(tool_msg)
            responses.append(tool_msg)
        responses += await new_agent.chat(
            messages, message_sent_at=message_sent_at, system_prompt_params=system_prompt_params, **kw
        )

    def render_system_prompt(
        self,
        full_messages: list[OllamaChatMessage],
        message_sent_at: datetime | None = None,
        system_prompt_params: dict | None = None,
        **kw,
    ):
        # Render System Prompt
        # TODO: Check if first message is system role.
        system_prompt_params = system_prompt_params or {}
        system_prompt_params["stored_suffix"] = full_messages[0].content
        if message_sent_at:
            system_prompt_params["current_date"] = message_sent_at.strftime("%Y-%m-%d")
            system_prompt_params["current_time"] = message_sent_at.strftime("%I: %M %p UTC")
        full_messages[0].content = self.system_prompt.format(**system_prompt_params)


class BaseAgentSystem(BaseService):
    def __init__(self, enabled=True, **kw):
        super().__init__(**kw)
        self.enabled = enabled
        self._system_prompt_suffix_to_store: str = None

        self._default_chat_store = None
        self._agent_name_map: dict[str, BaseAgent] = {}

    def get_chat_store(self, chat_store: ChatStoreService | None = None, **kw) -> ChatStoreService:
        if chat_store:
            return chat_store
        if not self._default_chat_store:
            self._default_chat_store = ChatStoreService.get_component(name=_config.chat_store_default_name)
        return self._default_chat_store

    def get_agent(self, agent_name: str) -> BaseAgent | None:
        """Returns agent with the given name. agent_name parameter cant be null or empty."""
        if agent_name not in self._agent_name_map:
            agent = BaseAgent.get_component(name=agent_name)
            if agent and agent.enabled:
                self._agent_name_map[agent_name] = agent
        return self._agent_name_map.get(agent_name)

    def get_default_agent(self) -> BaseAgent:
        """To be overriden by child class based on impl.
        By default, returns the first available agent.
        """
        return BaseAgent.get_component()

    def get_agent_or_default(self, agent_name: str | None = None) -> BaseAgent:
        """Returns agent with the given name if found, else returns default agent"""
        agent = None
        if agent_name:
            agent = self.get_agent(agent_name)
        return agent or self.get_default_agent()

    def get_agent_name_from_messages(self, messages: list[OllamaChatMessage | OllamaChatResponse]) -> str:
        last_msg = messages[-1]
        if isinstance(last_msg, OllamaChatResponse):
            last_msg = last_msg.message
        return last_msg.agent_name

    def get_system_prompt_suffix_to_store(self):
        if not self._system_prompt_suffix_to_store:
            with open(_config.default_system_prompt_suffix_to_store_path) as file:
                self._system_prompt_suffix_to_store = file.read()
        return self._system_prompt_suffix_to_store

    async def initialize_chat_thread(
        self,
        thread_id: str,
        user_profile: dict | None = None,
        system_prompt_params: dict | None = None,
        initialized_at: datetime | None = None,
        chat_store: ChatStoreService | None = None,
    ) -> ChatThread:
        initialized_at = initialized_at or datetime.now(timezone.utc)
        auth_params = {}
        if user_profile:
            auth_params.update({f"auth_{key}": val for key, val in user_profile.items()})
            auth_params.update(
                {
                    "auth_user_id_stmt": f'- ID: {auth_params.get("auth_user_id") or ""}',
                    "auth_profile_stmt": (
                        f'- Name: "{auth_params.get("auth_name") or ""}"\n'
                        f'- Date of birth: "{auth_params.get("auth_birthdate") or ""}"\n'
                        f'- Gender: "{auth_params.get("auth_gender") or ""}"'
                    ),
                    "auth_status_stmt": "User Authentication Successful.",
                }
            )
        else:
            auth_params.update(
                {
                    "auth_user_id": "",
                    "auth_user_id_stmt": "",
                    "auth_profile_stmt": "",
                    "auth_status_stmt": "",
                }
            )
        user_id = auth_params.get("auth_user_id") or None

        system_prompt_params = system_prompt_params or {}
        system_prompt_params = {**auth_params, **system_prompt_params}
        thread = ChatThread(
            id=thread_id,
            user_id=user_id,
            created_at=initialized_at,
        )
        await self.get_chat_store(chat_store=chat_store).put_thread(thread)
        await self.get_chat_store(chat_store=chat_store).put_message(
            ChatMessage(
                id=str(uuid4()),
                thread_id=thread_id,
                user_id=user_id,
                sent_at=initialized_at,
                message_by="system",
                message=self.get_system_prompt_suffix_to_store().format(**system_prompt_params).strip(),
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
        chat_store: ChatStoreService | None = None,
        **kw,
    ) -> list[OllamaChatResponse | OllamaChatMessage]:
        """
        Chat API - System Level. Gets past messages from the thread and sends new message to agent.
        """
        full_messages = await self.get_past_messages(thread_id, user_id=user_id, chat_store=chat_store, **kw)
        if not full_messages:
            raise ThreadIdInvalid()

        # TODO: implement limit on user chat messages according to `config.chat_store_messages_limit`.

        agent = self.get_agent_or_default(full_messages[-1].agent_name)
        if message:
            full_messages.append(OllamaChatMessage(role="user", content=message, agent_name=agent.name))

        return await agent.chat(
            full_messages, message_sent_at=message_sent_at, system_prompt_params=system_prompt_params, **kw
        )

    async def chat_and_store(
        self,
        thread_id: str,
        message: str | None,
        user_id: str | None = None,
        message_sent_at: datetime | None = None,
        system_prompt_params: dict | None = None,
        chat_store: ChatStoreService | None = None,
        **kw,
    ) -> ChatMessage:
        """
        User facing chat API, to be used for user chats.
        After successful response, user message and assistant response are stored back into Chat store.
        """
        message_sent_at = message_sent_at or datetime.now(timezone.utc)

        # Call Chat API
        res = await self.chat(
            thread_id,
            message,
            user_id=user_id,
            message_sent_at=message_sent_at,
            system_prompt_params=system_prompt_params,
            chat_store=chat_store,
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
                last_used_agent=self.get_agent_name_from_messages(res),
            )
            await self.get_chat_store(chat_store=chat_store).put_message(user_chat_message)
        for msg in res:
            if isinstance(msg, OllamaChatResponse):
                message_sent_at = msg.created_at
                chat_msg = ChatMessage(
                    id=str(uuid4()),
                    thread_id=thread_id,
                    user_id=user_id,
                    sent_at=message_sent_at,
                    message_by=msg.message.role,
                    message=msg.message.content,
                    tool_name=msg.message.name,
                    last_used_agent=msg.message.agent_name,
                )
                if msg.message.content:
                    await self.get_chat_store(chat_store=chat_store).put_message(chat_msg)
            elif isinstance(msg, OllamaChatMessage):
                message_sent_at += timedelta(milliseconds=1)
                chat_msg = ChatMessage(
                    id=str(uuid4()),
                    thread_id=thread_id,
                    user_id=user_id,
                    sent_at=message_sent_at,
                    message_by=msg.role,
                    message=msg.content,
                    tool_name=msg.name,
                    last_used_agent=msg.agent_name,
                )
                if msg.content:
                    await self.get_chat_store(chat_store=chat_store).put_message(chat_msg)

        # Returns the last chat message to User. TODO: Check last message is LLM Response.
        return chat_msg

    async def get_past_messages(
        self,
        thread_id: str | None,
        user_id: str | None = None,
        chat_store: ChatStoreService | None = None,
        **kw,
    ) -> list[OllamaChatMessage]:
        full_messages = await self.get_chat_store(chat_store=chat_store).get_messages(
            thread_id=thread_id, user_id=user_id, limit=-1, sort="asc", **kw
        )
        return [
            OllamaChatMessage(
                role=msg.message_by, content=msg.message, name=msg.tool_name, agent_name=msg.last_used_agent
            )
            for msg in full_messages.messages
        ]
