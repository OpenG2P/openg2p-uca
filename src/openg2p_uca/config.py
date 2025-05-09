import re

from openg2p_fastapi_auth.config import ApiAuthSettings
from openg2p_fastapi_auth.config import Settings as AuthSettings
from openg2p_fastapi_common.config import Settings as BaseSettings
from pydantic import BaseModel, ConfigDict, model_validator
from pydantic_settings import SettingsConfigDict

from . import __version__


class OllamaOptions(BaseModel):
    model_config = ConfigDict(extra="allow")
    temperature: int = 0


class Settings(AuthSettings, BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="uca_", env_file=".env", extra="allow", env_nested_delimiter="__"
    )

    openapi_title: str = "OpenG2P Unified Conversation Agent"
    openapi_description: str = """
    ***********************************
    Further details goes here
    ***********************************
    """
    openapi_version: str = __version__

    auth_api_post_new_chat_thread: ApiAuthSettings = ApiAuthSettings(enabled=True)
    auth_api_put_change_chat_thread: ApiAuthSettings = ApiAuthSettings(enabled=True)
    auth_api_get_current_chat_thread: ApiAuthSettings = ApiAuthSettings(enabled=True)
    auth_api_get_chat_threads: ApiAuthSettings = ApiAuthSettings(enabled=True)
    auth_api_post_new_chat_message: ApiAuthSettings = ApiAuthSettings(enabled=True)
    auth_api_get_chat_messages: ApiAuthSettings = ApiAuthSettings(enabled=True)

    default_ollama_base_url: str = "http://localhost:11434"
    default_ollama_model: str = "deepseek-r1:8b"
    default_ollama_api_timeout: int = 50
    default_ollama_keep_alive: int | None = -1
    default_ollama_extra_options: OllamaOptions | None = OllamaOptions()

    default_system_prompt_suffix_to_store_path: str = "system_prompts/suffix_to_store.txt"

    main_agent_enabled: bool = True
    main_agent_ollama_base_url: str = ""
    main_agent_ollama_model: str = ""
    main_agent_ollama_api_timeout: int | None = None
    main_agent_ollama_keep_alive: int | None = None
    main_agent_ollama_extra_options: OllamaOptions | None = None
    main_agent_system_prompt_path: str = "system_prompts/main_orchestration_agent.txt"
    main_agent_system_prompt_suffix_to_store_path: str = ""

    user_id_key_in_auth: str = "sub"
    thread_id_cookie_name: str = "thread_id"
    thread_id_cookie_path: str = "/"
    thread_id_cookie_secure: bool = True
    thread_id_cookie_httponly: bool = True
    thread_id_cookie_max_age: int | None = 3600 * 2

    # Ensure this is less than Chat store's limit.
    # Example; ES has an search result limit of 10000. See index.max_result_window in ES.
    # TODO: Implement clearly.
    chat_store_messages_limit: int = 1000

    chat_store_es_enabled: bool = True
    chat_store_es_url: str = "http://localhost:9200"
    chat_store_es_username: str = ""
    chat_store_es_password: str = ""
    chat_store_es_ssl_verify: bool = True
    chat_store_es_timeout_secs: int = 10
    chat_store_messages_es_index: str = "uca_messages"
    chat_store_threads_es_index: str = "uca_threads"

    api_message_response_filters_regex: list[str] = [r"<think>.*?</.*?>"]
    api_message_response_filters_sub: list[str] = ["", ""]
    api_message_response_filter_flags: int = re.DOTALL

    @model_validator(mode="after")
    def main_agent_config_validator(self):
        if not self.main_agent_ollama_base_url:
            self.main_agent_ollama_base_url = self.default_ollama_base_url
        if not self.main_agent_ollama_model:
            self.main_agent_ollama_model = self.default_ollama_model
        if self.main_agent_ollama_api_timeout is None:
            self.main_agent_ollama_api_timeout = self.default_ollama_api_timeout
        if self.main_agent_ollama_keep_alive is None:
            self.main_agent_ollama_keep_alive = self.default_ollama_keep_alive
        if not self.main_agent_ollama_extra_options:
            self.main_agent_ollama_extra_options = self.default_ollama_extra_options
        if not self.main_agent_system_prompt_suffix_to_store_path:
            self.main_agent_system_prompt_suffix_to_store_path = (
                self.default_system_prompt_suffix_to_store_path
            )
        return self
