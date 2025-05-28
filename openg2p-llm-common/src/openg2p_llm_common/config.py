import re

from openg2p_fastapi_common.config import Settings as BaseSettings
from pydantic import BaseModel, ConfigDict
from pydantic_settings import SettingsConfigDict

from . import __version__


class OllamaOptions(BaseModel):
    model_config = ConfigDict(extra="allow")
    temperature: int = 0


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="common_", env_file=".env", extra="allow", env_nested_delimiter="__"
    )

    openapi_title: str = "OpenG2P LLM Common Tools"
    openapi_description: str = """
    ***********************************
    Further details goes here
    ***********************************
    """
    openapi_version: str = __version__

    default_ollama_base_url: str = "http://localhost:11434"
    default_ollama_model: str = "qwen3:8b"
    default_ollama_api_timeout: int = 50
    default_ollama_keep_alive: int | None = -1
    default_ollama_extra_options: OllamaOptions | None = OllamaOptions()

    default_ollama_response_filters_regex: list[str] = [r"<think>.*?</.*?>"]
    default_ollama_response_filters_sub: list[str] = [""]
    default_ollama_response_filter_flags: int = re.DOTALL

    default_system_prompt_suffix_to_store_path: str = "system_prompts/suffix_to_store.md"

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
    chat_store_messages_es_index: str = "llm_messages"
    chat_store_threads_es_index: str = "llm_threads"
