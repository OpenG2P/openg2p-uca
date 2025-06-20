import io
import logging

import av
import orjson
import vosk

from ...config import Settings
from ...errors import BaseLlmCommonException, STTUnsupportedAudioFormat
from ...utils.timing import time_it
from .base import BaseSTTRequest, BaseSTTService

_config: Settings = Settings.get_config(strict=False)
_logger = logging.getLogger(_config.logging_default_logger_name)


class VoskSTTRequest(BaseSTTRequest):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.recognizer: vosk.KaldiRecognizer = None
        self.is_silence_detected_in_end: bool = False


class VoskSTTService(BaseSTTService):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.model: vosk.Model = None
        self.resampler: av.AudioResampler = None

    @time_it("VoskSTTService.initialize")
    async def initialize(self):
        """VOSK initialization."""
        model_path = _config.stt_vosk_model_directory.removesuffix("/")
        self.model = vosk.Model(model_path=f"{model_path}/{_config.stt_vosk_model_name}")
        self.resampler = av.AudioResampler(
            format="s16", layout="mono", rate=_config.stt_supported_sample_rate
        )

    @time_it("VoskSTTService.aclose")
    async def aclose(self):
        """Closes VOSK STT service."""
        # No closing required for Vosk STT service.

    @time_it("VoskSTTService.create_new_request")
    def create_new_request(self) -> VoskSTTRequest:
        """Creates a new Vosk STT request."""
        request = VoskSTTRequest()
        request.recognizer = vosk.KaldiRecognizer(self.model, _config.stt_supported_sample_rate)
        return request

    @time_it("VoskSTTService.convert_audio_format")
    def convert_audio_format(self, request: VoskSTTRequest, audio: bytes) -> bytes:
        """Convert input audio into the format required by VOSK."""
        return self.convert_audio_to_pcm_s16le(audio)

    @time_it("VoskSTTService.add_audio_to_request")
    def add_audio_to_request(self, request: VoskSTTRequest, audio: bytes):
        """Adds the given audio bytes into the Vosk STT request."""
        request.is_silence_detected_in_end = request.recognizer.AcceptWaveform(audio)

    @time_it("VoskSTTService.convert_request_to_text")
    def convert_request_to_text(self, request: VoskSTTRequest) -> str:
        """Converts VoskSTTRequest to text."""
        if self.is_silence_detected(request):
            return orjson.loads(request.recognizer.Result())["text"]
        else:
            return orjson.loads(request.recognizer.PartialResult())["partial"]

    @time_it("VoskSTTService.flush_audio_in_request")
    def flush_audio_in_request(self, request: VoskSTTRequest) -> str:
        """Flushes any VoskSTTRequest and returns leftover text."""
        return orjson.loads(request.recognizer.FinalResult())["text"]

    @time_it("VoskSTTService.is_silence_detected")
    def is_silence_detected(self, request: VoskSTTRequest) -> bool:
        """Returns if silence is detected at the end of the audio in the request."""
        return request.is_silence_detected_in_end

    @time_it("VoskSTTService.convert_audio_to_pcm_s16le")
    def convert_audio_to_pcm_s16le(self, audio: bytes) -> bytes:
        output_bytes_io = io.BytesIO()
        input_bytes_io = io.BytesIO(audio)
        try:
            with av.open(input_bytes_io, mode="r") as container:
                audio_stream = None
                for stream in container.streams.audio:
                    audio_stream = stream
                    break

                if not audio_stream:
                    err = STTUnsupportedAudioFormat()
                    err.message += ". Empty Audio file received."
                    raise err

                for frame in container.decode(audio_stream):
                    resampled_frames = self.resampler.resample(frame)

                    for resampled_frame in resampled_frames:
                        output_bytes_io.write(resampled_frame.to_ndarray().flatten().tobytes())

            return output_bytes_io.getvalue()
        except BaseLlmCommonException as e:
            raise e
        except Exception as e:
            err = STTUnsupportedAudioFormat()
            err.message += ". Unknown error occured during audio decoding."
            raise err from e
