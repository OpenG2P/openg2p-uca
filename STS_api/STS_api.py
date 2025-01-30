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
processing_output = False

def clean_response(response: str) -> str:
    """Clean the API response to get only the actual message content
    
    Args:
        response (str): Raw response from API
        
    Returns:
        str: Cleaned message without formatting characters
    """
    
    if '================================== Ai Message ==================================' in response:
        
        message = response.split('================================== Ai Message ==================================')[-1]
        message = message.replace('=', '')
        message = message.strip()
        return message
    return response  

def initialize_engine():
    """Initialize and configure the TTS engine"""
    engine = pyttsx3.init()
    engine.setProperty('rate', 150)
    return engine

def audio_callback(indata, frames, time, status):
    """Process incoming audio data"""
    global processing_output
    if status:
        print(status)
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
        
        # Get the AI message and clean it
        ai_message = result.get('ai_message')
        if ai_message:
            return clean_response(ai_message)
        return None
        
    except Exception as e:
        print(f"\nUCA API Request failed: {str(e)}")
        return None

def speech_to_speech_loop(thread_id: str):
    """Main program loop"""
    global processing_output
    
    engine = initialize_engine()
    model = vosk.Model("models/vosk-model-en-us-0.22")
    samplerate = 16000
    recognizer = vosk.KaldiRecognizer(model, samplerate)
    
    print("\n=== UCA Speech Interaction System ===")
    print(f"Thread ID: {thread_id}")
    print("\nReady! Start speaking (Press Ctrl+C to exit)")
    print("-" * 40)
    
    last_speech_time = time.time()
    silence_threshold = 2.0
    
    with sd.RawInputStream(samplerate=samplerate, 
                         blocksize=8000, 
                         dtype='int16',
                         channels=1, 
                         callback=audio_callback):
        
        while True:
            try:
                try:
                    audio_data = q.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                if recognizer.AcceptWaveform(audio_data):
                    result = json.loads(recognizer.Result())
                    
                    if result["text"]:
                        current_time = time.time()
                        
                        if current_time - last_speech_time >= silence_threshold:
                            recognized_text = result["text"]
                            print(f"\nYou said: {recognized_text}")
                            
                            processing_output = True
                            
                            print("Getting response from UCA...")
                            uca_response = send_to_uca(recognized_text, thread_id)
                            
                            if uca_response:
                                print(f"UCA Response (cleaned): {uca_response}")
                                engine.say(uca_response)
                            else:
                                error_message = "Sorry, I couldn't get a response at the moment."
                                print(error_message)
                                engine.say(error_message)
                            
                            while not q.empty():
                                q.get()
                            
                            engine.runAndWait()
                            
                            processing_output = False
                            last_speech_time = time.time()
                            
                            print("\nReady for next input...")
                
            except KeyboardInterrupt:
                print("\nGracefully shutting down...")
                break
            except Exception as e:
                print(f"\nError in main loop: {str(e)}")
                processing_output = False
                continue

if __name__ == "__main__":
    THREAD_ID = 'user01_12'
    
    try:
        speech_to_speech_loop(THREAD_ID)
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
    except Exception as e:
        print(f"\nProgram terminated due to error: {str(e)}")