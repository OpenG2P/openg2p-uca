import pyttsx3

def initialize_engine():
    """Initialize and configure the TTS engine"""
    engine = pyttsx3.init()
    engine.setProperty('rate', 150)  # Default speed
    return engine

def text_to_speech_loop():
    """Run an infinite loop to get text input and convert to speech"""
    engine = initialize_engine()
    
    print("Text-to-Speech Terminal (type 'quit' to exit)")
    print("-" * 40)
    
    while True:
        # Get input from user
        text = input("Enter text to speak: ").strip()
        
        # Check for exit command
        if text.lower() == 'quit':
            print("Exiting text-to-speech...")
            break
        
        # Skip empty input
        if not text:
            print("Please enter some text!")
            continue
            
        try:
            # Convert to speech
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            print(f"Error occurred: {str(e)}")

if __name__ == "__main__":
    try:
        text_to_speech_loop()
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
    except Exception as e:
        print(f"An error occurred: {str(e)}")