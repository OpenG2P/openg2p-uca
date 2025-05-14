import logging

from openg2p_llm_common.services.agents import BaseAgent
from openg2p_llm_common.services.ollama_client import OllamaClientService

from ..config import Settings

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class ProgramInfoAgent(BaseAgent):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.enabled = _config.prog_info_agent_enabled

    async def initialize(self):
        with open(_config.prog_info_agent_system_prompt_path) as file:
            self.system_prompt = file.read()

        with open(_config.prog_info_agent_system_prompt_suffix_to_store_path) as file:
            self.system_prompt_suffix_to_store = file.read()

        self.ollama_client = OllamaClientService(
            _config.prog_info_agent_ollama_base_url,
            _config.prog_info_agent_ollama_model,
            api_timeout=_config.prog_info_agent_ollama_api_timeout,
            keep_alive=_config.prog_info_agent_ollama_keep_alive,
            options=_config.prog_info_agent_ollama_extra_options,
            res_filters_regex=_config.prog_info_agent_ollama_response_filters_regex,
            res_filters_sub=_config.prog_info_agent_ollama_response_filters_sub,
            res_filters_flags=_config.prog_info_agent_ollama_response_filter_flags,
        )
        await self.ollama_client.load_model()
