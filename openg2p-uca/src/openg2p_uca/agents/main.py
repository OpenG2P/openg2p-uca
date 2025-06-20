import logging

from openg2p_llm_common.services.agents import BaseAgent
from openg2p_llm_common.services.ollama_client import OllamaClientService
from openg2p_llm_common.utils.timing import time_it

from ..config import Settings

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class MainAgent(BaseAgent):
    def __init__(self, name="main", **kw):
        super().__init__(name=name, **kw)

    @time_it("MainAgent.initialize")
    async def initialize(self):
        with open(_config.main_agent_system_prompt_path) as file:
            self.system_prompt = file.read()

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
