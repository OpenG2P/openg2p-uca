import logging
from typing import BinaryIO

from openg2p_fastapi_common.service import BaseService

from ...config import Settings

_config: Settings = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class BaseTTSService(BaseService):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.enabled = True

    async def initialize(self):
        """Each TTS Service impl needs to override this.
        This should include initial setup of the TTS service."""
        raise NotImplementedError()

    async def aclose(self):
        """Each TTS Service impl needs to override this.
        This should include closing setup of the TTS service."""
        raise NotImplementedError()

    async def convert_text_to_audio(self, text: str, audio: BinaryIO):
        """Converts text to audio, and writes it to the attached file-like object. To be implemented by TTS impl."""
        raise NotImplementedError()
