import logging
from typing import BinaryIO

import soundfile as sf
import torch
from parler_tts import ParlerTTSForConditionalGeneration
from transformers import AutoTokenizer

from ...config import Settings
from .base import BaseTTSService

_config: Settings = Settings.get_config(strict=False)
_logger = logging.getLogger(_config.logging_default_logger_name)


class ParlerTTSService(BaseTTSService):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.device: str = None
        self.model: ParlerTTSForConditionalGeneration = None
        self.tokenizer: AutoTokenizer = None
        self.description_tokenizer: AutoTokenizer = None
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

        self.description_tokenizer = AutoTokenizer.from_pretrained(
            self.model.config.text_encoder._name_or_path
        )
        self.description_input_ids = self.description_tokenizer(
            _config.tts_parler_voice_description, return_tensors="pt"
        ).to(self.device)
        _logger.info("ParlerTTS Initialization - voice description initialized")

    async def aclose(self):
        """No closing required for ParlerTTSService"""

    async def convert_text_to_audio(self, text: str, audio: BinaryIO):
        """Converts text to audio, and writes it to the attached file-like object."""
        prompt_input_ids = self.tokenizer(text, return_tensors="pt").to(self.device)
        generation = self.model.generate(
            input_ids=self.description_input_ids.input_ids,
            attention_mask=self.description_input_ids.attention_mask,
            prompt_input_ids=prompt_input_ids.input_ids,
            prompt_attention_mask=prompt_input_ids.attention_mask,
        )
        audio_arr = generation.cpu().numpy().squeeze()
        sf.write(audio, audio_arr, self.model.config.sampling_rate, format="WAV")
