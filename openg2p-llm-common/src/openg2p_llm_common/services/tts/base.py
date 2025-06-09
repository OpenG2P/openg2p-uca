import logging
from typing import TYPE_CHECKING, BinaryIO

from openg2p_fastapi_common.service import BaseService

if TYPE_CHECKING:
    import av

from ...config import Settings

_config: Settings = Settings.get_config(strict=False)
_logger = logging.getLogger(_config.logging_default_logger_name)


class BaseTTSResponse:
    pass


class BaseTTSService(BaseService):
    def __init__(self, enabled=True, **kw):
        super().__init__(**kw)
        self.enabled = enabled

    async def initialize(self):
        """Initialize the TTS service. To be implemented by TTS impl."""
        raise NotImplementedError()

    async def aclose(self):
        """Close the TTS service. To be implemented by TTS impl."""
        raise NotImplementedError()

    def get_sample_rate(self) -> int:
        """Gets the sample rate of output audio. To be implemented by TTS impl."""
        raise NotImplementedError()

    def get_no_of_channels(self) -> int:
        """Gets number of channels in the output audio. To be implemented by TTS impl."""
        raise NotImplementedError()

    def get_bit_depth(self) -> int:
        """Gets bit depth of the output audio. Example: 8-bit, 16-bit, etc. To be implemented by TTS impl."""
        raise NotImplementedError()

    def get_audio_format(self) -> str:
        """Gets the output audio format. Example: WAV. To be implemented by TTS impl."""
        raise NotImplementedError()

    def convert_text_to_raw_audio(self, text: str) -> BaseTTSResponse:
        """Converts text to raw audio. To be implemented by TTS impl."""
        raise NotImplementedError()

    def convert_raw_audio_to_playable(self, raw_audio: BaseTTSResponse, audio: BinaryIO):
        """Converts raw audio to playable audio and writes to the given file-like object.
        To be implemented by TTS impl."""
        raise NotImplementedError()

    def convert_text_to_audio(self, text: str, audio: BinaryIO):
        """Converts text to audio and writes the given file-like object. This is a convenience
        function that wraps all the steps of the tts_service into one function.
        To be implemented by STT impl."""
        raw_audio = self.convert_text_to_raw_audio(text)
        self.convert_raw_audio_to_playable(raw_audio, audio)

    def generate_audio_frame_from_raw_audio(self, raw_audio: BaseTTSResponse) -> "av.AudioFrame":
        """Generates PyAV AudioFrame object from raw_audio.
        To be implemented by TTS impl."""
        raise NotImplementedError()
