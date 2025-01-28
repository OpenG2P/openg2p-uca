# Coqui TTS Implementation Guide

A simple text-to-speech implementation using Coqui TTS with the LJSpeech Tacotron2-DDC model.

## Installation

1. Set up Python environment (Python 3.7+ required):
```bash
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Unix/MacOS:
source venv/bin/activate
```

2. Install required packages:
```bash
pip install TTS sounddevice #if TTS giving error ,then try pip install coqui-tts
```

The Tacotron2-DDC model will be downloaded automatically on first use.

## Running the Application

1. Start the program:
```bash
python MozillaLoop.py

#or any other script
```

2. Using the program:
- Enter text when prompted
- Press Enter to convert text to speech
- Press Ctrl+C to exit

