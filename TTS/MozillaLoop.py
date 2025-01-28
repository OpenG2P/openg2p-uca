from TTS.api import TTS
import sounddevice as sd

def stream_tts(text, model_name="tts_models/en/ljspeech/tacotron2-DDC"):
    """Convert text to speech and play it"""
    tts = TTS(model_name=model_name)
    wav = tts.tts(text)
    sd.play(wav, samplerate=22050)
    sd.wait()

def tts_loop():
    print("Starting Text-to-Speech Loop...")
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
            stream_tts(text)
            
        except KeyboardInterrupt:
            print("\nStopping the TTS loop...")
            break
        except Exception as e:
            print(f"\nError occurred: {str(e)}")
            continue

if __name__ == "__main__":
    try:
        tts_loop()
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
    except Exception as e:
        print(f"\nProgram terminated due to error: {str(e)}")