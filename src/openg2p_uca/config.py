from openg2p_fastapi_common.config import Settings as BaseSettings
from pydantic import model_validator
from pydantic_settings import SettingsConfigDict

from . import __version__


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="uca_", env_file=".env", extra="allow")

    openapi_title: str = "OpenG2P Unified Conversation Agent"
    openapi_description: str = """
    ***********************************
    Further details goes here
    ***********************************
    """
    openapi_version: str = __version__

    # ollama_base_url: str = "http://localhost:11434"
    # ollama_api_timeout: int = 10

    user_id_key_in_auth: str = "sub"

    # Ensure this is <= Chat store implementation's limit.
    # Example; ES has an index result limit of 10000. See index.max_result_window in ES.
    chat_store_messages_limit: int = 1000

    chat_store_es_enabled: bool = True
    chat_store_es_url: str = ""
    chat_store_es_username: str = ""
    chat_store_es_password: str = ""
    chat_store_es_ssl_verify: bool = True
    chat_store_es_timeout_secs: int = 10
    chat_store_es_index: str = "uca_messages"

    @model_validator(mode="after")
    def fix_fields_model_validator(self):
        return self


Settings()
