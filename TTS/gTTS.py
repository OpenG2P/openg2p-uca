from gtts import gTTS
import os
import pygame
import threading
import queue
import time

class TextToSpeech:
    def __init__(self):
        self.text_queue = queue.Queue()
        self.running = True
        pygame.mixer.init()
        self.current_file = 1
        self.lock = threading.Lock()
        
        # Start the processing thread
        self.thread = threading.Thread(target=self._process_queue, daemon=True)
        self.thread.start()

    def _process_queue(self):
        while self.running:
            try:
                if not self.text_queue.empty():
                    text = self.text_queue.get()
                    
                    # Generate and play speech
                    with self.lock:
                        # Create speech file
                        tts = gTTS(text=text, lang='en', slow=False)
                        filename = f'speech_{self.current_file}.mp3'
                        tts.save(filename)
                        
                        # Play the file
                        pygame.mixer.music.load(filename)
                        pygame.mixer.music.play()
                        
                        # Wait for playback to finish
                        while pygame.mixer.music.get_busy():
                            time.sleep(0.1)
                            
                        # Clean up
                        pygame.mixer.music.unload()
                        os.remove(filename)
                        
                        # Update file counter
                        self.current_file = 1 if self.current_file == 2 else 2
                        
                    self.text_queue.task_done()
                time.sleep(0.1)
                
            except Exception as e:
                print(f"Error in processing: {e}")
                continue

    def speak(self, text):
        """Add text to the speech queue"""
        if text:
            self.text_queue.put(text)

    def stop(self):
        """Stop the TTS engine"""
        self.running = False
        self.thread.join(timeout=2)
        pygame.mixer.quit()

def main():
    tts = TextToSpeech()
    print("Text-to-Speech System Started")
    print("Enter text to speak (or 'q' to quit)")
    
    try:
        while True:
            text = input("> ")
            if text.lower() == 'q':
                break
            tts.speak(text)
    
    except KeyboardInterrupt:
        print("\nStopping the program...")
    finally:
        tts.stop()
        # Clean up any remaining temporary files
        for i in [1, 2]:
            try:
                os.remove(f'speech_{i}.mp3')
            except:
                pass
        print("Program terminated.")

if __name__ == "__main__":
    main()