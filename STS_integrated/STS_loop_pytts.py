import pyttsx3
import vosk
import sounddevice as sd
import json
import queue
import time

def initialize_engine():
    """Initialize and configure the TTS engine"""
    engine = pyttsx3.init()
    engine.setProperty('rate', 150)  # Default speed
    return engine

def audio_callback(indata, frames, time, status):
    """Callback function for audio input"""
    if status:
        print(status)
    q.put(bytes(indata))

def speech_to_speech_loop():
    """Main loop for speech to text to speech conversion"""
    global q
    
    # Initialize TTS engine
    engine = initialize_engine()
    
    # Initialize STT components
    model = vosk.Model("models/vosk-model-en-us-0.22")
    samplerate = 16000
    q = queue.Queue()
    rec = vosk.KaldiRecognizer(model, samplerate)
    
    print("Starting Speech-to-Speech Loop...")
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
                        
                        # Convert the recognized text back to speech
                        print("Playing back...")
                        engine.say(recognized_text)
                        engine.runAndWait()
                        
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