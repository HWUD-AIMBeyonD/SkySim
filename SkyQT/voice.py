import os
import wave
import tempfile
import pyaudio
from faster_whisper import WhisperModel

# Configuration
MODEL_SIZE = "base.en"
COMPUTE_TYPE = "int8" 
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK = 1024

class VoiceService:
    _model = None

    @classmethod
    def get_model(cls):
        if cls._model is None:
            print(f"Loading Whisper Model ({MODEL_SIZE})...")
            cls._model = WhisperModel(MODEL_SIZE, device="cpu", compute_type=COMPUTE_TYPE)
            print("Model Loaded.")
        return cls._model

    @staticmethod
    def transcribe(audio_path):
        model = VoiceService.get_model()
        segments, info = model.transcribe(audio_path, beam_size=5)
        
        text = ""
        for segment in segments:
            text += segment.text + " "
        return text.strip()

class AudioRecorder:
    def __init__(self):
        self.frames = []
        self.recording = False
        self.p = None
        self.stream = None

    def _ensure_pyaudio(self):
        if self.p is None:
            self.p = pyaudio.PyAudio()

    def start_recording(self):
        self._ensure_pyaudio()
        self.frames = []
        self.recording = True
        self.stream = self.p.open(format=pyaudio.paInt16,
                                  channels=CHANNELS,
                                  rate=SAMPLE_RATE,
                                  input=True,
                                  frames_per_buffer=CHUNK)
    
    def process_chunk(self):
        if self.recording and self.stream:
            data = self.stream.read(CHUNK)
            self.frames.append(data)

    def stop_recording(self):
        self.recording = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

    def save(self, filename):
        self._ensure_pyaudio()
        wf = wave.open(filename, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(self.p.get_sample_size(pyaudio.paInt16))
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(b''.join(self.frames))
        wf.close()
