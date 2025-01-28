# Speech-to-Speech Conversion System

This repository contains an integrated speech-to-speech conversion system that combines real-time speech recognition with text-to-speech capabilities. The system utilizes Vosk for speech recognition and pyttsx3 for speech synthesis, creating a seamless voice-to-voice transformation pipeline.

## System Overview

The Speech-to-Speech Conversion System provides real-time voice transformation capabilities through a two-stage process. The system first converts spoken input to text using the Vosk speech recognition engine, then immediately synthesizes the recognized text back into speech using the pyttsx3 engine. This creates a complete pipeline for voice transformation and processing.

## Technical Requirements

### System Prerequisites
- Python 3.7 or higher
- pip (Python package installer)
- Working microphone for input


## Installation Process

1. Clone the repo

2. Create and activate a virtual environment:
```bash
python -m venv venv

# Windows activation:
venv\Scripts\activate

# Unix/MacOS activation:
source venv/bin/activate
```

3. Install required dependencies:
```bash
pip install vosk sounddevice pyttsx3
```

4. Download and configure the Vosk model:
```bash
mkdir models
# Download vosk-model-small-en-us-0.15 from https://alphacephei.com/vosk/models
# Extract the model to the models directory
```

## System Architecture

```
.
├── README.md
├── STS_integrated/
    └── STS_loop_pytts.py
└── models/
    └── vosk-model-small-en-us-0.15/
```

## Core Components

The system implements three primary functions:

initialize_engine():
- Establishes the text-to-speech engine
- Configures default speech parameters
- Optimizes performance settings

audio_callback():
- Manages real-time audio stream processing
- Handles input buffer management
- Provides status monitoring

speech_to_speech_loop():
- Coordinates the conversion pipeline
- Manages audio I/O operations


## Implementation Usage

Execute the application using:
```bash
python STS_loop_pytts.py
```

## Operational Workflow

1. System Initialization
   - The system initializes both speech recognition and synthesis engines
   - Audio input stream is established
   - Recognition model is loaded

2. Active Operation
   - System begins monitoring for voice input
   - Recognized speech is displayed as text
   - Text is automatically converted back to speech
   - Continuous operation until manual termination

3. System Termination
   - Ctrl+C initiates graceful shutdown
   - Resources are properly released
   - System provides termination confirmation

## Technical Specifications

Speech Recognition (Vosk):
- Sample Rate: 16000 Hz
- Block Size: 8000
- Channels: 1 (mono)
- Model: vosk-model-small-en-us-0.15

Text-to-Speech (pyttsx3):
- Speech Rate: 150 words per minute
- Voice: System default
- Volume: System default



## Acknowledgments

- Vosk Speech Recognition Project (https://github.com/alphacep/vosk-api)
- pyttsx3 Development Team (https://github.com/nateshmbhat/pyttsx3)
- Python Audio Community (https://github.com/spatialaudio/python-sounddevice)

