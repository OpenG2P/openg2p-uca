import sounddevice as sd

def list_devices():
    print("Available audio devices:")
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        print(f"Device {i}: {device['name']}")
        print(f"  Input channels: {device['max_input_channels']}")
        print(f"  Output channels: {device['max_output_channels']}")
        print(f"  Default samplerate: {device['default_samplerate']}")
        print("-----")

if __name__ == "__main__":
    list_devices()
