import logging
import subprocess
from typing import BinaryIO

import ffmpeg
import orjson
import vosk

from ...config import Settings
from ...errors import STTUnsupportedAudioFormat
from .base import BaseSTTService

_config: Settings = Settings.get_config(strict=False)
_logger = logging.getLogger(_config.logging_default_logger_name)


class VoskSTTService(BaseSTTService):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.model: vosk.Model = None
        self.recognizer: vosk.KaldiRecognizer = None

    async def initialize(self):
        """VOSK initialization."""
        model_path = _config.stt_vosk_model_directory.removesuffix("/")
        self.model = vosk.Model(model_path=f"{model_path}/{_config.stt_vosk_model_name}")
        self.recognizer = vosk.KaldiRecognizer(self.model, _config.stt_supported_sample_rate)

    async def aclose(self):
        """No closing required for VOSK service."""

    async def verify_audio_format(self, audio: BinaryIO) -> bytes:
        """Takes audio from file object, verifies format,
        return audio_bytes which can be directly passed to the convert function."""
        ffmpeg_process: subprocess.Popen = (
            ffmpeg.input("pipe:0")
            .output(
                "pipe:1",
                format="s16le",
                acodec="pcm_s16le",
                ac="1",
                ar=str(_config.stt_supported_sample_rate),
            )
            .run_async(pipe_stdin=True, pipe_stdout=True, pipe_stderr=True, overwrite_output=True)
        )
        out_bytes, err_bytes = ffmpeg_process.communicate(audio.read())
        _logger.debug("FFmpeg error_out. %s", err_bytes.decode())
        if ffmpeg_process.returncode != 0:
            _logger.debug("FFmpeg error_out. %s", err_bytes.decode())
            # _logger.debug("FFmpeg std_out. %s", out_bytes.decode())
            raise STTUnsupportedAudioFormat()
        return out_bytes

    async def convert_audio_to_text(self, audio: bytes) -> str:
        """Converts audio, a file-like object, to text. Returns string."""
        silence = self.recognizer.AcceptWaveform(audio)
        if silence:
            return orjson.loads(self.recognizer.Result())["text"]
        else:
            return orjson.loads(self.recognizer.PartialResult())["partial"]

    async def flush(self) -> str:
        """Flushes any audio present in the buffers and returns leftover text."""
        return orjson.loads(self.recognizer.FinalResult())["text"]
