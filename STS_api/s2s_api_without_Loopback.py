import pyttsx3
import vosk
import sounddevice as sd
import json
import queue
import time
import requests
import os
from typing import Optional

# Global queue for audio data
q = queue.Queue()

# API Configuration
UCA_API_URL = 'http://13.202.113.132:8000/chat'
THREAD_ID = 'user01_10'  # Constant thread ID for the session

# Audio configuration
SAMPLE_RATE = 16000
BLOCK_SIZE = 8000

class AudioProcessor:
    def __init__(self):
        self.is_responding = False
        self.recognition_enabled = True

    def clear_queue(self):
        """Thread-safe queue clearance"""
        with q.mutex:
            q.queue.clear()
            q.all_tasks_done.notify_all()
            q.unfinished_tasks = 0

def initialize_engine():
    """Initialize and configure the TTS engine"""
    engine = pyttsx3.init()
    engine.setProperty('rate', 150)  # Speaking speed
    engine.setProperty('voice', engine.getProperty('voices')[0].id)  # First available voice
    return engine

def audio_callback(indata, frames, time, status):
    """Audio input callback with processing control"""
    if status:
        print(status)
    if not audio_processor.is_responding:
        q.put(bytes(indata))

def send_to_uca(text: str, thread_id: str) -> Optional[str]:
    """Send text to UCA API with enhanced error handling"""
    try:
        payload = {'query': text, 'thread_id': thread_id}
        response = requests.post(UCA_API_URL, json=payload, timeout=10)
        response.raise_for_status()
        return response.json().get('ai_message')
    except requests.exceptions.RequestException as e:
        print(f"\nAPI Error: {str(e)}")
        return None
    except json.JSONDecodeError:
        print("\nInvalid API response format")
        return None

def safe_tts_speak(engine, text: str):
    """Safe text-to-speech with audio processing control"""
    try:
        audio_processor.is_responding = True
        audio_processor.clear_queue()
        engine.say(text)
        engine.runAndWait()
    finally:
        # Add cooldown period after speaking
        time.sleep(0.5)
        audio_processor.clear_queue()
        audio_processor.is_responding = False

def speech_to_speech_loop(thread_id: str):
    """Main interaction loop with echo prevention"""
    global audio_processor
    
    # Initialize components
    audio_processor = AudioProcessor()
    engine = initialize_engine()
    
    # Verify Vosk model
    model_path = "models/vosk-model-small-en-us-0.15"
    if not os.path.exists(model_path):
        print(f"\nMissing Vosk model at {os.path.abspath(model_path)}")
        print("Download from https://alphacephei.com/vosk/models")
        return

    model = vosk.Model(model_path)
    recognizer = vosk.KaldiRecognizer(model, SAMPLE_RATE)

    print("\n=== UCA Speech Interface ===")
    print(f"Thread ID: {thread_id}")
    print("Initializing audio...")
    
    with sd.RawInputStream(samplerate=SAMPLE_RATE,
                         blocksize=BLOCK_SIZE,
                         dtype='int16',
                         channels=1,
                         callback=audio_callback) as stream:
        
        print("\nReady for input (Speak now)...")
        print("Press Ctrl+C to exit\n" + "-"*40)
        
        while True:
            try:
                if audio_processor.is_responding or q.empty():
                    time.sleep(0.1)
                    continue

                audio_data = q.get_nowait()
                
                if recognizer.AcceptWaveform(audio_data):
                    result = json.loads(recognizer.Result())
                    text = result.get('text', '').strip()
                    
                    if len(text) < 3:  # Ignore short noises
                        continue
                        
                    print(f"\nUser: {text}")
                    
                    # Clear previous audio data
                    audio_processor.clear_queue()
                    
                    # Get API response
                    print("Processing...")
                    response = send_to_uca(text, thread_id)
                    
                    # Handle response
                    if response:
                        print(f"UCA: {response}")
                        safe_tts_speak(engine, response)
                    else:
                        error_msg = "I'm having trouble connecting. Please try again later."
                        print(error_msg)
                        safe_tts_speak(engine, error_msg)
                    
                    print("\nReady for next input...")

            except KeyboardInterrupt:
                print("\nTerminating...")
                break
            except queue.Empty:
                continue
            except Exception as e:
                print(f"\nSystem Error: {str(e)}")
                time.sleep(1)  # Prevent tight error loops

if __name__ == "__main__":
    try:
        speech_to_speech_loop(THREAD_ID)
    except Exception as e:
        print(f"\nFatal Error: {str(e)}")
    finally:
        print("\nSystem shutdown complete")