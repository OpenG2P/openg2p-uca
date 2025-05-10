import logging

from openg2p_fastapi_common.service import BaseService

from ...config import Settings

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class BaseTool(BaseService):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.enabled = True
        # TODO: Define what is a tool
