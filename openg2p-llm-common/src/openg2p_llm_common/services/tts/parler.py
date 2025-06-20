import io
import logging
import re
import string
from typing import BinaryIO

import av
import num2words
import numpy as np
import soundfile as sf
import torch
from parler_tts import ParlerTTSForConditionalGeneration
from transformers import AutoTokenizer, PreTrainedTokenizerBase

from ...config import Settings
from ...utils.timing import time_it
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
        self.nltk_sent_tokenizer = None

    @time_it("ParlerTTSService.initialize")
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

        if _config.tts_parler_splitlines_while_convert:
            from nltk.data import find
            from nltk.downloader import Downloader
            from nltk.tokenize.punkt import PunktSentenceTokenizer, load_punkt_params

            nltk_down_dir = _config.tts_parler_nltk_download_dir.removesuffix("/")
            nltk_lang = _config.tts_parler_nltk_lang
            try:
                nltk_down_path = find(f"tokenizers/punkt_tab/{nltk_lang}/", paths=[nltk_down_dir])
            except LookupError:
                _logger.info("Parler TTS: Nltk tokenizer not found. Downloading...")
                nltk_downloader = Downloader(
                    server_index_url=_config.tts_parler_nltk_server_url, download_dir=nltk_down_dir
                )
                nltk_downloader.download(info_or_id="punkt_tab")
                nltk_down_path = find(f"tokenizers/punkt_tab/{nltk_lang}/", paths=[nltk_down_dir])
            self.nltk_sent_tokenizer = PunktSentenceTokenizer()
            self.nltk_sent_tokenizer._params = load_punkt_params(nltk_down_path)
            self.nltk_sent_tokenizer._lang = nltk_lang

        if _config.tts_parler_arbitrary_text_mode:
            self.test_arbitrary_speech_gen()

    @time_it("ParlerTTSService.aclose")
    async def aclose(self):
        """Closes Parler TTS service."""
        # No closing required for ParlerTTSService

    @time_it("ParlerTTSService.get_sample_rate")
    def get_sample_rate(self) -> int:
        """Gets the sample rate of output audio."""
        return self.model.config.sampling_rate

    @time_it("ParlerTTSService.get_no_of_channels")
    def get_no_of_channels(self) -> int:
        """Gets number of channels in the output audio."""
        return 1  # TODO: remove hardcoding

    @time_it("ParlerTTSService.get_bit_depth")
    def get_bit_depth(self) -> int:
        """Gets bit depth of the output audio."""
        return 16  # TODO: remove hardcoding

    @time_it("ParlerTTSService.get_audio_format")
    def get_audio_format(self) -> str:
        """Gets the output audio format."""
        return "WAV"  # TODO: remove hardcoding

    @time_it("ParlerTTSService.convert_text_to_raw_audio")
    def convert_text_to_raw_audio(self, text: str) -> ParlerTTSResponse:
        """Converts text to raw audio."""
        response = ParlerTTSResponse()
        text = self.clean_text_for_convert(text)
        if _config.tts_parler_splitlines_while_convert:
            textlines = self.nltk_sent_tokenizer.tokenize(text)
        else:
            textlines = [text]
        for textline in textlines:
            if not textline:
                continue
            prompt_input_ids = self.tokenizer(textline, return_tensors="pt").to(self.device)
            generation = self.model.generate(
                input_ids=self.description_input_ids.input_ids,
                attention_mask=self.description_input_ids.attention_mask,
                prompt_input_ids=prompt_input_ids.input_ids,
                prompt_attention_mask=prompt_input_ids.attention_mask,
            )
            raw_a = generation.cpu().numpy()

            # Scale and cast to int16
            # np.clip is used to prevent overflow/underflow if scaled values exceed int16 range
            max_int16_val = np.iinfo(np.int16).max
            raw_a = np.clip(raw_a * max_int16_val, -max_int16_val - 1, max_int16_val).astype(np.int16)
            if response.raw_audio is None:
                response.raw_audio = raw_a
            else:
                response.raw_audio = np.concatenate((response.raw_audio, raw_a), axis=1)
        return response

    @time_it("ParlerTTSService.convert_raw_audio_to_playable")
    def convert_raw_audio_to_playable(self, raw_audio: ParlerTTSResponse, audio: BinaryIO):
        """Converts raw audio to playable audio and writes to the given file-like object."""
        sf.write(audio, raw_audio.raw_audio.squeeze(), self.get_sample_rate(), format="WAV")

    @time_it("ParlerTTSService.generate_audio_frame_from_raw_audio")
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

    def clean_text_for_convert(self, text: str) -> str:
        if not text:
            return text
        text = text.replace("/", " or ")
        text = text.replace("+", " plus ")
        # numbers to words
        text = re.sub(r"\d+", lambda x: num2words.num2words(x.group(0), lang="en_IN"), text)
        # Clean up acronyms and camel case strings.
        text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)  # Handles "aB" -> "a B"
        text = re.sub(r"([A-Z])([A-Z][a-z])", r"\1 \2", text)  # Handles "ABCDefg" -> "AB CDefg"
        text = re.sub(r"(?<=[A-Z])([A-Z])(?![a-z])", r" \1", text)

        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+",
            flags=re.UNICODE,
        )
        text = emoji_pattern.sub(r" ", text)
        # Remove special characters and keep only alphanumeric and spaces
        # We create a set of allowed characters (alphanumeric and space)
        allowed_chars = string.ascii_letters + " ,?.-():"
        text = "".join(char if char in allowed_chars else " " for char in text)
        # Clean whitespaces.
        text = re.sub(r"\s+", " ", text).strip()
        _logger.debug("Parler TTS: Cleaned Text. %s", text)

        return text

    def test_arbitrary_speech_gen(self):
        """This is only to be used for testing."""
        count = 0
        while True:
            count += 1
            exit = False
            try:
                user_text = input("Give Text: ")
                user_text = user_text.replace("\\n", "\n")
                if user_text == "exit":
                    exit = True
            except Exception:
                exit = True
            if exit:
                import sys

                sys.exit(0)
            audio_bytes = io.BytesIO()
            self.convert_text_to_audio(user_text, audio_bytes)
            with open(f"my_res{count}.wav", "wb") as file:
                file.write(audio_bytes.getvalue())
