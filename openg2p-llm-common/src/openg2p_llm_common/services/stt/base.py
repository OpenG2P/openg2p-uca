import logging
from typing import BinaryIO

from openg2p_fastapi_common.service import BaseService

from ...config import Settings

_config: Settings = Settings.get_config(strict=False)
_logger = logging.getLogger(_config.logging_default_logger_name)


class BaseSTTService(BaseService):
    def __init__(self, enabled=True, **kw):
        super().__init__(**kw)
        self.enabled = enabled

    async def initialize(self):
        """Each STT Service impl needs to override this.
        This should include initial setup of the STT service."""
        raise NotImplementedError()

    async def aclose(self):
        """Each STT Service impl needs to override this.
        This should include closing setup of the STT service."""
        raise NotImplementedError()

    async def verify_audio_format(self, audio: BinaryIO) -> bytes:
        """Takes audio from file object, verifies format,
        return audio_bytes which can be directly passed to the convert function.
        To be implemented by STT impl."""
        return audio.read()

    async def convert_audio_to_text(self, audio: bytes) -> str:
        """Converts audio to text. Returns string. To be implemented by STT impl."""
        raise NotImplementedError()

    async def flush(self) -> str:
        """Flushes any audio present in the buffers and returns leftover text.
        To be implemented by STT impl."""
        return ""
