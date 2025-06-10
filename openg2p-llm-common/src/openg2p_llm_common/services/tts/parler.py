import logging
from typing import BinaryIO

import av
import numpy as np
import soundfile as sf
import torch
from parler_tts import ParlerTTSForConditionalGeneration
from transformers import AutoTokenizer, PreTrainedTokenizerBase

from ...config import Settings
from .base import BaseTTSResponse, BaseTTSService

_config: Settings = Settings.get_config(strict=False)
_logger = logging.getLogger(_config.logging_default_logger_name)


class ParlerTTSResponse(BaseTTSResponse):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.raw_audio: np.ndarray = None


class ParlerTTSService(BaseTTSService):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.device: str = None
        self.model: ParlerTTSForConditionalGeneration = None
        self.tokenizer: PreTrainedTokenizerBase = None
        self.description_input_ids: torch.Tensor = None

    async def initialize(self):
        """ParlerTTS Initialization"""
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        _logger.info("ParlerTTS Initialization. Device: %s", self.device)
        model_path = _config.tts_parler_model_directory.removesuffix("/")
        model_path = f"{model_path}/{_config.tts_parler_model_name}"
        self.model = ParlerTTSForConditionalGeneration.from_pretrained(model_path).to(self.device)
        _logger.info("ParlerTTS Initialization - Model Initialized. model_path: %s", model_path)

        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        _logger.info("ParlerTTS Initialization - tokenizer initialized")

        vd = _config.tts_parler_voice_description
        if _config.tts_parler_description_tokenizer:
            model_name_or_path = self.model.config.text_encoder._name_or_path
            description_tokenizer = AutoTokenizer.from_pretrained(model_name_or_path)
            self.description_input_ids = description_tokenizer(vd, return_tensors="pt").to(self.device)
        else:
            self.description_input_ids = self.tokenizer(vd, return_tensors="pt").to(self.device)
        _logger.info("ParlerTTS Initialization - voice description initialized")

    async def aclose(self):
        """Closes Parler TTS service."""
        # No closing required for ParlerTTSService

    def get_sample_rate(self) -> int:
        """Gets the sample rate of output audio."""
        return self.model.config.sampling_rate

    def get_no_of_channels(self) -> int:
        """Gets number of channels in the output audio."""
        return 1  # TODO: remove hardcoding

    def get_bit_depth(self) -> int:
        """Gets bit depth of the output audio."""
        return 16  # TODO: remove hardcoding

    def get_audio_format(self) -> str:
        """Gets the output audio format."""
        return "WAV"  # TODO: remove hardcoding

    def convert_text_to_raw_audio(self, text: str) -> ParlerTTSResponse:
        """Converts text to raw audio."""
        prompt_input_ids = self.tokenizer(text, return_tensors="pt").to(self.device)
        generation = self.model.generate(
            input_ids=self.description_input_ids.input_ids,
            attention_mask=self.description_input_ids.attention_mask,
            prompt_input_ids=prompt_input_ids.input_ids,
            prompt_attention_mask=prompt_input_ids.attention_mask,
        )
        response = ParlerTTSResponse()
        response.raw_audio = generation.cpu().numpy()

        # Scale and cast to int16
        # np.clip is used to prevent overflow/underflow if scaled values exceed int16 range
        max_int16_val = np.iinfo(np.int16).max
        response.raw_audio = np.clip(
            response.raw_audio * max_int16_val, -max_int16_val - 1, max_int16_val
        ).astype(np.int16)
        return response

    def convert_raw_audio_to_playable(self, raw_audio: ParlerTTSResponse, audio: BinaryIO):
        """Converts raw audio to playable audio and writes to the given file-like object."""
        sf.write(audio, raw_audio.raw_audio.squeeze(), self.get_sample_rate(), format="WAV")

    def generate_audio_frame_from_raw_audio(self, raw_audio: ParlerTTSResponse) -> av.AudioFrame:
        """Generates PyAV AudioFrame object from raw_audio."""
        alayout = "mono" if self.get_no_of_channels() < 2 else "stereo"
        aformat = None
        if self.get_bit_depth() == 16:
            aformat = "s16"
        elif self.get_bit_depth() == 32:
            aformat = "flt"
        aframe = av.AudioFrame.from_ndarray(raw_audio.raw_audio, format=aformat, layout=alayout)
        aframe.sample_rate = self.get_sample_rate()
        return aframe
