import logging
import wave
from typing import BinaryIO

import numpy as np
import orjson
import vosk

from ...config import Settings
from ...errors import STTUnsupportedAudioFormat, STTUnsupportedSampleRate
from .base import BaseSTTService

_config: Settings = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class VoskSTTService(BaseSTTService):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.model: vosk.Model = None
        self.recognizers: dict[float, vosk.KaldiRecognizer] = {}

    async def initialize(self):
        """VOSK initialization."""
        model_path = _config.stt_vosk_model_directory.removesuffix("/")
        self.model = vosk.Model(model_path=f"{model_path}/{_config.stt_vosk_model_name}")
        for sr in _config.stt_supported_sample_rates:
            self.recognizers[sr] = vosk.KaldiRecognizer(self.model, sr)

    async def aclose(self):
        """No closing required for VOSK service."""

    async def verify_audio_format(self, audio: BinaryIO) -> tuple[bytes, float, str, int]:
        """Takes audio from file object, verifies format,
        return bytes, sample_rate, format, original_channels which can be passed to convert function."""
        try:
            sfile = wave.open(audio, "rb")
            aformat = "WAV"
        except Exception as e:
            err = STTUnsupportedAudioFormat()
            err.message += '. Currently supported formats are ["wav"].'
            raise err from e
        sample_rate = sfile.getframerate()
        if sample_rate not in self.recognizers:
            err = STTUnsupportedSampleRate()
            err.message += f". Currently supported sample rates are: {_config.stt_supported_sample_rates}"
            raise err
        channels = sfile.getnchannels()
        frames = sfile.readframes(sfile.getnframes())
        sampwidth = sfile.getsampwidth()
        audio_bytes = self.merge_multiple_channels_of_wav(frames, channels, sampwidth)
        sfile.close()
        return audio_bytes, sample_rate, aformat, channels

    async def convert_audio_to_text(self, audio: bytes, sample_rate: float) -> str:
        """Converts audio, a file-like object, to text. Returns string."""
        silence = self.recognizers[sample_rate].AcceptWaveform(audio)
        if silence:
            return orjson.loads(self.recognizers[sample_rate].Result())["text"]
        else:
            return orjson.loads(self.recognizers[sample_rate].PartialResult())["text"]

    async def flush(self, sample_rate: float) -> str:
        """Flushes any audio present in the buffers and returns leftover text."""
        return orjson.loads(self.recognizers[sample_rate].FinalResult())["text"]

    def merge_multiple_channels_of_wav(self, frames: bytes, nchannels: int, sample_width: int) -> bytes:
        if sample_width == 1:
            samples = np.frombuffer(frames, dtype=np.int8).astype(np.int64)
        elif sample_width == 2:
            samples = np.frombuffer(frames, dtype=np.int16).astype(np.int64)
        elif sample_width == 3:
            # 24-bit, convert to 32-bit then to 64-bit
            samples_raw = np.frombuffer(frames, dtype=np.uint8)
            samples = np.zeros(len(samples_raw) // 3, dtype=np.int32)
            for i in range(len(samples)):
                chunk = samples_raw[i * 3 : (i + 1) * 3]
                val = int.from_bytes(
                    chunk + (b"\x00" if chunk[2] & 0x80 == 0 else b"\xFF"), byteorder="little", signed=True
                )
                samples[i] = val
            samples = samples.astype(np.int64)
        else:
            # elif sample_width == 4: # Assumed same as else
            samples = np.frombuffer(frames, dtype=np.int32).astype(np.int64)

        if nchannels > 1:
            return samples.mean(axis=1).tobytes()
        else:
            return samples.tobytes()
