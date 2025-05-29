import logging

from ...config import Settings
from .base import BaseSTTService

_config: Settings = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class VoskSTTService(BaseSTTService):
    async def initialize(self):
        """VOSK initialization."""

    async def convert_audio_to_text(self, data: bytes) -> str:
        """Converts audio to text. Returns string."""
