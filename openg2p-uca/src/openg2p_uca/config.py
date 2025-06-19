from openg2p_fastapi_auth.config import ApiAuthSettings
from openg2p_fastapi_auth.config import Settings as AuthSettings
from openg2p_llm_common.config import OllamaOptions
from openg2p_llm_common.config import Settings as BaseSettings
from pydantic import model_validator
from pydantic_settings import SettingsConfigDict

from . import __version__


class Settings(AuthSettings, BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="uca_", env_file=".env", extra="allow", env_nested_delimiter="__"
    )

    openapi_title: str = "OpenG2P Unified Conversation Agent"
    openapi_description: str = ""
    openapi_version: str = __version__

    auth_session_store_host: str = "localhost"
    auth_session_store_port: int = 6379
    auth_session_store_db: int = 0
    auth_session_store_password: str = "valkey"
    auth_api_post_new_chat_thread: ApiAuthSettings = ApiAuthSettings(enabled=True)
    auth_api_put_change_chat_thread: ApiAuthSettings = ApiAuthSettings(enabled=True)
    auth_api_get_current_chat_thread: ApiAuthSettings = ApiAuthSettings(enabled=True)
    auth_api_get_chat_threads: ApiAuthSettings = ApiAuthSettings(enabled=True)
    auth_api_post_new_chat_message: ApiAuthSettings = ApiAuthSettings(enabled=True)
    auth_api_post_new_voice_message: ApiAuthSettings = ApiAuthSettings(enabled=True)
    auth_api_get_chat_messages: ApiAuthSettings = ApiAuthSettings(enabled=True)
    auth_api_post_speak_message: ApiAuthSettings = ApiAuthSettings(enabled=True)
    auth_dummy_user_data: dict = {}
    auth_dummy_otp: str = "111111"

    chat_store_messages_es_index: str = "uca_messages"
    chat_store_threads_es_index: str = "uca_threads"

    chat_store_transient_enabled: bool = True
    chat_store_transient_name: str = "transient"
    chat_store_transient_messages_index: str = "uca_messages_transient"
    chat_store_transient_threads_index: str = "uca_threads_transient"

    greeting_message_on_chat: bool = True
    greeting_message_on_quick_chat: bool = True

    ## Main Agent Config
    main_agent_enabled: bool = True
    main_agent_ollama_base_url: str = ""
    main_agent_ollama_model: str = ""
    main_agent_ollama_api_timeout: int | None = None
    main_agent_ollama_keep_alive: int | None = None
    main_agent_ollama_extra_options: OllamaOptions | None = None

    main_agent_ollama_response_filters_regex: list[str] | None = None
    main_agent_ollama_response_filters_sub: list[str] | None = None
    main_agent_ollama_response_filter_flags: int | None = None

    main_agent_system_prompt_path: str = "system_prompts/main_agent.md"

    default_system_prompt_suffix_for_call_path: str = "system_prompts/suffix_to_store_for_call.md"
    call_meta_ice_servers: list[dict[str, str]] = [{"urls": "stun:stun.l.google.com:19302"}]
    call_standby_message_path: str = "system_prompts/call_standby_message.md"
    call_standby_message_timer: int = 2

    grm_ticket_number_prefix: str = "UCA"
    grm_ticket_number_padding: int = 5
    grm_ticket_create_uid: int = 1
    grm_ticket_new_stage_lang: str = "en_US"
    grm_ticket_new_stage_name: str = "New"

    session_id_cookie_name: str = "session_id"
    session_id_cookie_path: str = "/"
    session_id_cookie_secure: bool = True
    session_id_cookie_httponly: bool = True
    session_id_cookie_max_age: int | None = None

    qc_session_id_cookie_name: str = "qc_session_id"
    qc_session_id_cookie_path: str = "/"
    qc_session_id_cookie_secure: bool = True
    qc_session_id_cookie_httponly: bool = True
    qc_session_id_cookie_max_age: int | None = None

    thread_id_cookie_name: str = "thread_id"
    thread_id_cookie_path: str = "/"
    thread_id_cookie_secure: bool = True
    thread_id_cookie_httponly: bool = True
    thread_id_cookie_max_age: int | None = None

    stt_vosk_enabled: bool = False
    tts_parler_enabled: bool = False

    api_message_response_filters_regex: list[str] | None = None
    api_message_response_filters_sub: list[str] | None = None
    api_message_response_filter_flags: int | None = None

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
        if self.main_agent_ollama_response_filters_regex is None:
            self.main_agent_ollama_response_filters_regex = self.default_ollama_response_filters_regex
        if self.main_agent_ollama_response_filters_sub is None:
            self.main_agent_ollama_response_filters_sub = self.default_ollama_response_filters_sub
        if self.main_agent_ollama_response_filter_flags is None:
            self.main_agent_ollama_response_filter_flags = self.default_ollama_response_filter_flags
        return self
