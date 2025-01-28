from TTS.api import TTS
import vosk
import sounddevice as sd
import json
import queue
import time

def stream_tts(text, model_name="tts_models/en/jenny/jenny"):
    """Convert text to speech and play it using Coqui model"""
    tts = TTS(model_name=model_name)
    wav = tts.tts(text)
    sd.play(wav, samplerate=22050)
    sd.wait()

def initialize_stt():
    """Initialize speech to text components"""
    model = vosk.Model("models/vosk-model-small-en-us-0.15")
    samplerate = 16000
    q = queue.Queue()
    return model, samplerate, q

def audio_callback(indata, frames, time, status):
    """Callback function for audio input"""
    if status:
        print(status)
    q.put(bytes(indata))

def speech_to_speech_loop():
    """Main loop for speech to text to speech conversion"""
    global q
    
    # Initialize STT components
    model = vosk.Model("models/vosk-model-small-en-us-0.15")
    samplerate = 16000
    q = queue.Queue()
    rec = vosk.KaldiRecognizer(model, samplerate)
    
    print("Starting Speech-to-Speech Loop with Coqui model...")
    print("Speak something... (Press Ctrl+C to stop)")
    
    # Start recording
    with sd.RawInputStream(samplerate=samplerate, 
                         blocksize=8000, 
                         dtype='int16',
                         channels=1, 
                         callback=audio_callback):
        
        while True:
            try:
                data = q.get()
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    if result["text"]:
                        recognized_text = result["text"]
                        print("\nRecognized:", recognized_text)
                        
                        # Convert the recognized text back to speech using Coqui
                        print("Playing back with Coqui model...")
                        stream_tts(recognized_text)
                        
                        print("\nSpeak something... (Press Ctrl+C to stop)")
                        
            except KeyboardInterrupt:
                print("\nStopping the loop...")
                break
            except Exception as e:
                print(f"\nError occurred: {str(e)}")
                continue

if __name__ == "__main__":
    try:
        speech_to_speech_loop()
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
    except Exception as e:
        print(f"\nProgram terminated due to error: {str(e)}")