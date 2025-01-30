import pyttsx3
import vosk
import sounddevice as sd
import json
import queue
import time
import requests
from typing import Optional

# Initialize global queue for audio processing
q = queue.Queue()

# Flag to control audio processing
processing_output = False

def initialize_engine():
    """Initialize and configure the TTS engine for optimal speech output"""
    engine = pyttsx3.init()
    engine.setProperty('rate', 150)
    return engine

def audio_callback(indata, frames, time, status):
    """Process incoming audio data from the microphone stream"""
    global processing_output
    if status:
        print(status)
    # Only process audio input when not playing output
    if not processing_output:
        q.put(bytes(indata))

def send_to_uca(text: str, thread_id: str) -> Optional[str]:
    """Send text to UCA API and receive response"""
    try:
        payload = {
            'query': text,
            'thread_id': thread_id
        }
        
        response = requests.post(
            'http://13.202.113.132:8000/chat',
            json=payload,
            timeout=10
        )
        
        response.raise_for_status()
        result = response.json()
        return result.get('ai_message')
        
    except Exception as e:
        print(f"\nUCA API Request failed: {str(e)}")
        return None

def speech_to_speech_loop(thread_id: str):
    """Main program loop handling the complete pipeline"""
    global processing_output
    
    # Initialize engines
    engine = initialize_engine()
    model = vosk.Model("models/vosk-model-small-en-us-0.15")
    samplerate = 16000
    recognizer = vosk.KaldiRecognizer(model, samplerate)
    
    print("\n=== UCA Speech Interaction System ===")
    print(f"Thread ID: {thread_id}")
    print("\nReady! Start speaking (Press Ctrl+C to exit)")
    print("-" * 40)
    
    # Variables to track silence and prevent feedback
    last_speech_time = time.time()
    silence_threshold = 2.0  # seconds
    
    with sd.RawInputStream(samplerate=samplerate, 
                         blocksize=8000, 
                         dtype='int16',
                         channels=1, 
                         callback=audio_callback):
        
        while True:
            try:
                # Get audio data from queue with timeout
                try:
                    audio_data = q.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                # Process audio through speech recognition
                if recognizer.AcceptWaveform(audio_data):
                    result = json.loads(recognizer.Result())
                    
                    if result["text"]:
                        current_time = time.time()
                        
                        # Only process if enough time has passed since last speech
                        if current_time - last_speech_time >= silence_threshold:
                            recognized_text = result["text"]
                            print(f"\nYou said: {recognized_text}")
                            
                            # Set flag before playing audio
                            processing_output = True
                            
                            # Send text to UCA API
                            print("Getting response from UCA...")
                            uca_response = send_to_uca(recognized_text, thread_id)
                            
                            if uca_response:
                                print(f"UCA Response: {uca_response}")
                                engine.say(uca_response)
                            else:
                                error_message = "Sorry, I couldn't get a response at the moment."
                                print(error_message)
                                engine.say(error_message)
                            
                            # Clear the audio queue before playing response
                            while not q.empty():
                                q.get()
                            
                            # Play the response
                            engine.runAndWait()
                            
                            # Reset flag after playing audio
                            processing_output = False
                            
                            # Update last speech time
                            last_speech_time = time.time()
                            
                            print("\nReady for next input...")
                
            except KeyboardInterrupt:
                print("\nGracefully shutting down...")
                break
            except Exception as e:
                print(f"\nError in main loop: {str(e)}")
                processing_output = False  # Reset flag in case of error
                continue

if __name__ == "__main__":
    THREAD_ID = 'user01_10'
    
    try:
        speech_to_speech_loop(THREAD_ID)
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
    except Exception as e:
        print(f"\nProgram terminated due to error: {str(e)}")