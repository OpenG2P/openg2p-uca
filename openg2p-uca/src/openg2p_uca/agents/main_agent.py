import logging
from datetime import datetime

from openg2p_llm_common.errors import ThreadIdInvalid
from openg2p_llm_common.schemas.ollama import OllamaChatMessage, OllamaChatRequest, OllamaChatResponse
from openg2p_llm_common.services.agents import BaseAgent
from openg2p_llm_common.services.ollama_client import OllamaClientService

from ..config import Settings
from .application import ApplicationAgent
from .grievance import GrievanceAgent
from .program_info_agent import ProgramInfoAgent

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class MainAgent(BaseAgent):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.enabled = _config.main_agent_enabled

        self._program_info_agent: ProgramInfoAgent = None
        self._grievance_agent: GrievanceAgent = None
        self._application_agent: ApplicationAgent = None

    @property
    def program_info_agent(self):
        if not self._program_info_agent:
            self._program_info_agent = ProgramInfoAgent.get_component()
        return self._program_info_agent

    @property
    def grievance_agent(self):
        if not self._grievance_agent:
            self._grievance_agent = GrievanceAgent.get_component()
        return self._grievance_agent

    @property
    def application_agent(self):
        if not self._application_agent:
            self._application_agent = GrievanceAgent.get_component()
        return self._application_agent

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
            res_filters_regex=_config.main_agent_ollama_response_filters_regex,
            res_filters_sub=_config.main_agent_ollama_response_filters_sub,
            res_filters_flags=_config.main_agent_ollama_response_filter_flags,
        )
        await self.ollama_client.load_model()

    async def chat(
        self,
        thread_id: str,
        message: str | None,
        user_id: str | None = None,
        message_sent_at: datetime | None = None,
        system_prompt_params: dict | None = None,
        past_messages: list[OllamaChatMessage] | None = None,
        **kw
    ) -> list[OllamaChatResponse | OllamaChatMessage]:
        if past_messages is None:
            full_messages = await self.chat_store_service.get_messages(
                thread_id=thread_id, user_id=user_id, limit=-1, sort="asc"
            )
            full_messages = [
                OllamaChatMessage(role=msg.message_by, content=msg.message) for msg in full_messages.messages
            ]
        else:
            full_messages = past_messages

        if not full_messages:
            raise ThreadIdInvalid()

        # TODO: implement limit on user chat messages according to `config.chat_store_messages_limit`.

        if message:
            full_messages.append(OllamaChatMessage(role="user", content=message))

        system_prompt_orig = full_messages[0].content
        await self.render_system_prompt(
            full_messages, message_sent_at=message_sent_at, system_prompt_params=system_prompt_params
        )

        ollama_res = await self.ollama_client.chat(
            OllamaChatRequest(messages=full_messages, stream=False, tools=self.tool_box.get_ollama_tools())
        )
        print("xxxxxxxxxxxxxxxxxxxxxxx",ollama_res.message.content)
        sub_agent = self.get_sub_agent(ollama_res.message.content)
        full_messages[0].content = system_prompt_orig  # Restore system prompt to original
        return await sub_agent.chat(
            thread_id,
            None,
            user_id=user_id,
            message_sent_at=message_sent_at,
            system_prompt_params=system_prompt_params,
            past_messages=full_messages,
            **kw
        )

    def get_sub_agent(self, agent_class: str) -> BaseAgent:
        if agent_class == "program_info":
            return self.program_info_agent
        elif agent_class == "grievance":
            return self.grievance_agent
        elif agent_class == "application":
            return self.application_agent
        else:
            # default case
            return self.program_info_agent
