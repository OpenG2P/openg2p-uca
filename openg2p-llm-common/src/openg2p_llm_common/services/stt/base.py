import logging

from openg2p_fastapi_common.service import BaseService

from ...config import Settings
from ...utils.timing import time_it

_config: Settings = Settings.get_config(strict=False)
_logger = logging.getLogger(_config.logging_default_logger_name)


class BaseSTTRequest:
    pass


class BaseSTTService(BaseService):
    def __init__(self, enabled=True, **kw):
        super().__init__(**kw)
        self.enabled = enabled

    async def initialize(self):
        """Initialize the STT service. To be implemented by STT impl."""
        raise NotImplementedError()

    async def aclose(self):
        """Close the STT service. To be implemented by STT impl."""
        raise NotImplementedError()

    def create_new_request(self) -> BaseSTTRequest:
        """Create a new STT request that can be processed by the convert function.
        To be implemented by STT impl."""
        raise NotImplementedError()

    def convert_audio_format(self, request: BaseSTTRequest, audio: bytes) -> bytes:
        """Convert input audio into the format required for the convert_request_to_text function.
        To be implemented by STT impl."""
        return audio

    def add_audio_to_request(self, request: BaseSTTRequest, audio: bytes) -> None:
        """Adds the given audio bytes into the request so that the request
        can be passed to the convert_request_to_text function. To be implemented by STT impl."""
        raise NotImplementedError()

    def convert_and_add_audio_to_request(self, request: BaseSTTRequest, audio: bytes) -> None:
        """Converts the input audio and adds it to the request. The request can then be passed
        to the convert_request_to_text function. To be implemented by STT impl."""
        audio = self.convert_audio_format(request, audio)
        self.add_audio_to_request(request, audio)

    def convert_request_to_text(self, request: BaseSTTRequest) -> str:
        """Converts stt_request to text. Returns string. To be implemented by STT impl."""
        raise NotImplementedError()

    def flush_audio_in_request(self, request: BaseSTTRequest) -> str:
        """Flushes any audio present in the buffers and returns leftover text.
        To be implemented by STT impl."""
        return ""

    def is_silence_detected(self, request: BaseSTTRequest) -> bool:
        """Returns True if silence is detected at the end of the audio in the request.
        To be implemented by STT impl."""
        raise NotImplementedError()

    @time_it("BaseSTTService.convert_audio_to_text")
    def convert_audio_to_text(self, audio: bytes, **kw) -> str:
        """Converts audio to text and returns string. This is a convenience function that
        wraps all the steps of the stt_service into one function and returns the final
        speech-to-text.
        This is useful for converting prerecorded audio messages or audio files to text,
        where the entire audio is already available. To be implemented by STT impl."""
        request = self.create_new_request(**kw)
        self.convert_and_add_audio_to_request(request, audio, **kw)
        output_text = self.convert_request_to_text(request, **kw)
        output_text += " " + self.flush_audio_in_request(request, **kw)
        return output_text.strip()
