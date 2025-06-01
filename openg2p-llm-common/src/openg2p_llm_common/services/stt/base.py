import logging
from typing import BinaryIO

from openg2p_fastapi_common.service import BaseService

from ...config import Settings

_config: Settings = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class BaseSTTService(BaseService):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.enabled = True

    async def initialize(self):
        """Each STT Service impl needs to override this.
        This should include initial setup of the STT service."""
        raise NotImplementedError()

    async def aclose(self):
        """Each STT Service impl needs to override this.
        This should include closing setup of the STT service."""
        raise NotImplementedError()

    async def verify_audio_format(self, audio: BinaryIO) -> tuple[bytes, float, str, int]:
        """Takes audio from file object, verifies format,
        return bytes, sample_rate, format, channels which can be passed to convert function.
        To be implemented by STT impl."""
        return audio.read(), _config.stt_supported_sample_rates[0], "WAV", 1

    async def convert_audio_to_text(self, audio: bytes, sample_rate: float) -> str:
        """Converts audio, a file-like object, to text. Returns string. To be implemented by STT impl."""
        raise NotImplementedError()

    async def flush(self, sample_rate: float) -> str:
        """Flushes any audio present in the buffers and returns leftover text.
        To be implemented by STT impl."""
        return ""
