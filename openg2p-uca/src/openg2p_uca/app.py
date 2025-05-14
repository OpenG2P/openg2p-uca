# ruff: noqa: E402

from .config import Settings

_config: Settings = Settings.get_config()

from openg2p_fastapi_auth.controllers.oauth_controller import OAuthController
from openg2p_fastapi_common.ping import PingController
from openg2p_llm_common.app import Initializer as BaseInitializer

from .controllers.auth import AuthController
from .controllers.chat import ChatController
from .services.agents import MainAgent


class Initializer(BaseInitializer):
    def initialize(self, **kwargs):
        super().initialize(**kwargs)

        PingController().post_init()
        AuthController().post_init()
        OAuthController().post_init()
        ChatController().post_init()
        MainAgent()
