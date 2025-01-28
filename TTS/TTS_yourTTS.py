from TTS.api import TTS
from IPython.display import Audio, display

def stream_tts(text, language="en", speaker_wav=None):
    """Convert text to speech using YourTTS model"""
    # Initialize YourTTS
    tts = TTS(model_name="tts_models/multilingual/multi-dataset/your_tts")
    
    # Get available languages
    print("\nAvailable languages:", tts.languages)
    
    # Generate speech
    if speaker_wav:
        wav = tts.tts(text=text, language=language, speaker_wav=speaker_wav)
    else:
        wav = tts.tts(text=text, language=language)
    
    return Audio(wav, rate=22050, autoplay=True)

def tts_loop():
    print("Starting YourTTS Text-to-Speech Loop...")
    print("This model supports multiple languages!")
    print("\nLanguage codes: 'en' (English), 'fr' (French), 'de' (German), 'es' (Spanish), 'it' (Italian)")
    
    while True:
        try:
            # Get language choice
            language = input("\nEnter language code (default is 'en'): ").strip().lower()
            if not language:
                language = 'en'
            
            # Get text input
            text = input("\nEnter text: ")
            
            # Skip if empty input
            if not text.strip():
                print("Please enter some text!")
                continue
                
            print("Converting to speech...")
            audio = stream_tts(text, language)
            display(audio)
            
        except KeyboardInterrupt:
            print("\nStopping the TTS loop...")
            break
        except Exception as e:
            print(f"\nError occurred: {str(e)}")
            print("If language error, try using one of: en, fr, de, es, it")
            continue

if __name__ == "__main__":
    try:
        tts_loop()
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
    except Exception as e:
        print(f"\nProgram terminated due to error: {str(e)}")