from TTS.api import TTS
import sounddevice as sd

def stream_tts(text, model_name="tts_models/en/ljspeech/tacotron2-DDC"):
    tts = TTS(model_name=model_name)
    wav = tts.tts(text)
    sd.play(wav, samplerate=22050)
    sd.wait()

def stream_with_different_voice(text, voice_index=0):
    tts = TTS(model_name="tts_models/en/vctk/vits")
    wav = tts.tts(text, speaker=tts.speakers[voice_index])
    sd.play(wav, samplerate=22050)
    sd.wait()

# Example usage
text = "hello "
stream_tts(text)  # Default voice