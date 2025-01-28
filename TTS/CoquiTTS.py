from TTS.api import TTS
from IPython.display import Audio, display

def stream_tts(text, model_name="tts_models/en/jenny/jenny"):
    """Convert text to speech using Coqui model"""
    tts = TTS(model_name=model_name)
    wav = tts.tts(text)
    return Audio(wav, rate=22050, autoplay=True)

def tts_loop():
    print("Starting Text-to-Speech Loop with Coqui model...")
    print("Enter text to convert to speech (Press Ctrl+C to stop)")
    
    while True:
        try:
            # Get input from user
            text = input("\nEnter text: ")
            
            # Skip if empty input
            if not text.strip():
                print("Please enter some text!")
                continue
                
            print("Converting to speech...")
            audio = stream_tts(text)
            display(audio)
            
        except KeyboardInterrupt:
            print("\nStopping the TTS loop...")
            break
        except Exception as e:
            print(f"\nError occurred: {str(e)}")
            print("Error details:", e)  # Added more detailed error reporting
            continue