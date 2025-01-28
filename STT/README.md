# Speech-to-Text Application

This repository contains a real-time speech-to-text application using the Vosk speech recognition toolkit. The application captures audio from your microphone and converts it to text in real-time.

## Features

- Real-time speech recognition
- English language support
- Low latency processing
- Offline functionality (no internet required)
- Command-line interface

## Prerequisites

Before installing this project, make sure you have:

- Python 3.7 or higher
- pip (Python package installer)


## Installation
1.Clone the repo

2. Create and activate a virtual environment (recommended):
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Unix or MacOS:
source venv/bin/activate
```

3. Install the required packages:
```bash
pip install vosk sounddevice
```

4. Download the Vosk model:
- Create a `models` directory in your project root
- Download the [vosk-model-small-en-us-0.15](https://alphacephei.com/vosk/models) model
- Extract the downloaded model to the `models` directory

## Project Structure

```
.
├── README.md
├── Vosk_s2t.py
└── models/
    └── vosk-model-small-en-us-0.15/
```

## Usage

1. Make sure your microphone is connected and working
2. Run the script:
```bash
python vosk_STT_us_en.py
```
3. Start speaking - the recognized text will appear in the console
4. Press Ctrl+C to stop the program

## Configuration

The current configuration uses these default settings:
- Sample rate: 16000 Hz
- Block size: 8000
- Audio channels: 1 (mono)
- Model: vosk-model-small-en-us-0.15

These settings can be modified in the script if needed.

## Models Used

This project uses the Vosk speech recognition model:
- Model: vosk-model-small-en-us-0.15,
- Language: English (US)
- Size: ~42MB
- Quality: Suitable for real-time recognition on modest hardware

Other Vosk models are available at [Vosk Models](https://alphacephei.com/vosk/models) if you need different languages or higher accuracy.



2. **Model not found error**: 
   - Ensure the model is downloaded and extracted to the `models` directory
   - Verify the model path in the script matches your directory structure

## Dependencies

- vosk: Speech recognition toolkit
- sounddevice: Audio input handling
- Python standard libraries: json, queue


## Acknowledgments

- [Vosk Speech Recognition Toolkit](https://github.com/alphacep/vosk-api)
