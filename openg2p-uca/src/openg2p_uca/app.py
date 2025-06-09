# ruff: noqa: E402


from .config import Settings

_config: Settings = Settings.get_config()

from openg2p_fastapi_auth.controllers.oauth_controller import OAuthController
from openg2p_fastapi_common.context import component_registry
from openg2p_fastapi_common.ping import PingController
from openg2p_llm_common.app import Initializer as BaseInitializer
from openg2p_llm_common.services.agents import BaseAgentSystem
from openg2p_llm_common.services.chat_store import ESChatStoreService
from openg2p_llm_common.services.tools.box import ToolboxService
from openg2p_llm_common.services.tools.change_agent import ChangeAgentTool

from .agents.main import MainAgent
from .controllers.auth import AuthController
from .controllers.call import CallController
from .controllers.chat import ChatController
from .tools.beneficiary import GetBeneficiaryIdTool
from .tools.grievance_ticket import CreateGrievanceTicketTool
from .tools.program_info_tool import ProgramInfoTool


class Initializer(BaseInitializer):
    def initialize(self, **kwargs):
        super().initialize(**kwargs)

        PingController().post_init()
        AuthController().post_init()
        OAuthController().post_init()
        ChatController().post_init()
        CallController().post_init()
        if _config.chat_store_es_enabled:
            ESChatStoreService(enabled=_config.chat_store_es_enabled)

        if _config.stt_vosk_enabled:
            from openg2p_llm_common.services.stt.vosk import VoskSTTService

            VoskSTTService(enabled=_config.stt_vosk_enabled)

        if _config.tts_parler_enabled:
            from openg2p_llm_common.services.tts.parler import ParlerTTSService

            ParlerTTSService(enabled=_config.tts_parler_enabled)

        ChangeAgentTool()
        ProgramInfoTool()
        GetBeneficiaryIdTool()
        CreateGrievanceTicketTool()
        ToolboxService()
        if _config.main_agent_enabled:
            MainAgent(enabled=_config.main_agent_enabled)
        BaseAgentSystem()

    async def fastapi_app_startup(self, app):
        await super().fastapi_app_startup(app)
        for service in component_registry.get():
            if isinstance(service, CallController):
                await service.initialize()
