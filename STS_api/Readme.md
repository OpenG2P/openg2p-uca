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
pip install vosk sounddevice pyttsx3 requests
```

4. Download the Vosk model:
- Create a `models` directory in your project root
- Download the [vosk-model-en-us-0.22](https://alphacephei.com/vosk/models) model
- Extract the downloaded model to the `models` directory

## Project Structure

```
.
├── README.md
├── Vosk_s2t.py
└── models/
    └── vosk-model-en-us-0.22/
```

## Usage

1. Make sure your microphone is connected and working
2. Run the script:
```bash
python .py
```
3. Start speaking - the recognized text will appear in the console
4. Press Ctrl+C to stop the program

## Acknowledgments

- Vosk Speech Recognition Project (https://github.com/alphacep/vosk-api)
- pyttsx3 Development Team (https://github.com/nateshmbhat/pyttsx3)
- Python Audio Community (https://github.com/spatialaudio/python-sounddevice)

