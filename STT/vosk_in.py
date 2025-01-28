import vosk
import sounddevice as sd
import json
import queue

# Initialize Vosk
model = vosk.Model("models/vosk-model-small-en-in-0.4")
samplerate = 16000
q = queue.Queue()

def callback(indata, frames, time, status):
    if status:
        print(status)
    q.put(bytes(indata))

def main():
    # Create recognizer
    rec = vosk.KaldiRecognizer(model, samplerate)
    
    # Start recording
    with sd.RawInputStream(samplerate=samplerate, blocksize=8000, dtype='int16',
                          channels=1, callback=callback):
        print("Start speaking... (Press Ctrl+C to stop)")
        
        while True:
            try:
                data = q.get()
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    if result["text"]:
                        print("You said:", result["text"])
            except KeyboardInterrupt:
                print("\nStopping...")
                break

if __name__ == "__main__":
    main()