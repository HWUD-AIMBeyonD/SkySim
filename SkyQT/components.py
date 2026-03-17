from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, QPushButton, QLabel, QProgressBar, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import tempfile
import os

from SkySLM.ollama_connect import generate_drone_code
from SkyVIZ.flight_plan import run_flightplan_visualization
from SkyQT.flight_commands import run_generated_mission

VOICE_AVAILABLE = False
VoiceService = None
AudioRecorder = None
try:
    from SkyQT.voice import VoiceService, AudioRecorder
    VOICE_AVAILABLE = True
except Exception as e:
    print(f"Voice module not available: {e}")


class VoiceWorker(QThread):
    text_ready = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.recorder = AudioRecorder() if VOICE_AVAILABLE and AudioRecorder else None
        self.is_recording = False

    def run(self):
        if not self.recorder or not VOICE_AVAILABLE:
            print("Voice recording not available")
            return

        self.recorder.start_recording()

        while self.is_recording:
            self.recorder.process_chunk()

        self.recorder.stop_recording()

        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_filename = tmp.name

        self.recorder.save(tmp_filename)

        try:
            if VoiceService:
                text = VoiceService.transcribe(tmp_filename)
                if text:
                    self.text_ready.emit(text)
        except Exception as e:
            print(f"Transcription Error: {e}")
        finally:
            if os.path.exists(tmp_filename):
                os.remove(tmp_filename)

    def stop(self):
        self.is_recording = False

class CodeGeneratorThread(QThread):
    finished = pyqtSignal(str)
    
    def __init__(self, prompt):
        super().__init__()
        self.prompt = prompt

    def run(self):
        try:
            code = generate_drone_code(self.prompt)
            self.finished.emit(code)
        except Exception as e:
            self.finished.emit(f"# Error generating code: {e}")

class ChatWidget(QWidget):
    code_generated = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.init_ui()
        self.voice_worker = VoiceWorker()
        self.voice_worker.text_ready.connect(self.on_voice_recognized)
        self.voice_worker.finished.connect(self.on_voice_finished)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(QLabel("<b>SkySLM Agent Chat</b>"))
        
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        layout.addWidget(self.chat_display)
        
        input_layout = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Ask SkySLM to plan a flight...")
        self.chat_input.returnPressed.connect(self.process_chat_input)
        input_layout.addWidget(self.chat_input)
        
        self.mic_btn = QPushButton("Microphone (Hold to Speak)")
        self.mic_btn.setToolTip("Hold to Speak")
        self.mic_btn.setStyleSheet("font-size: 16px; padding: 5px;")
        self.mic_btn.pressed.connect(self.start_recording)
        self.mic_btn.released.connect(self.stop_recording)
        input_layout.addWidget(self.mic_btn)
        
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.process_chat_input)
        input_layout.addWidget(self.send_btn)
        
        layout.addLayout(input_layout)
        
        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 0)
        self.loading_bar.setVisible(False)
        layout.addWidget(self.loading_bar)

    def start_recording(self):
        if self.voice_worker.isRunning():
            return
        self.mic_btn.setStyleSheet("background-color: red; font-size: 16px; padding: 5px;")
        self.voice_worker.is_recording = True
        self.voice_worker.start()

    def stop_recording(self):
        self.voice_worker.stop()
        self.mic_btn.setText("...")
        self.mic_btn.setEnabled(False)

    def on_voice_finished(self):
        self.mic_btn.setText("🎤")
        self.mic_btn.setEnabled(True)
        self.mic_btn.setStyleSheet("font-size: 16px; padding: 5px;")

    def on_voice_recognized(self, text):
        if text:
            self.chat_input.setText(text)
            # self.process_chat_input()

    def process_chat_input(self):
        user_text = self.chat_input.text().strip()
        if not user_text:
            return
            
        self.chat_input.clear()
        self.append_chat("You", user_text)
        self.append_chat("SkySLM", "Thinking...")
        
        self.loading_bar.setVisible(True)
        self.chat_input.setEnabled(False)
        self.send_btn.setEnabled(False)

        self.worker = CodeGeneratorThread(user_text)
        self.worker.finished.connect(self.on_code_generated)
        self.worker.start()

    def on_code_generated(self, code):
        self.loading_bar.setVisible(False)
        self.chat_input.setEnabled(True)
        self.send_btn.setEnabled(True)
        
        self.append_chat("SkySLM", "Code Generated, Please review from the Generated Code tab.")
        self.code_generated.emit(code)

    def append_chat(self, sender, message):
        self.chat_display.append(f"<b>{sender}:</b> {message}")

class PlotWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        self.label = QLabel("Generated Flight Plan")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.label)

    def update_plot(self, code):
        # Clear previous plot
        for i in reversed(range(self.layout.count())): 
            item = self.layout.itemAt(i)
            if item.widget():
                item.widget().setParent(None)

        try:
            fig = run_flightplan_visualization(code)
            if fig:
                canvas = FigureCanvas(fig)
                self.layout.addWidget(canvas)
            else:
                self.layout.addWidget(QLabel("Failed to generate plot."))
        except Exception as e:
            self.layout.addWidget(QLabel(f"Error plotting: {e}"))

class CodeWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.last_generated_code = ""

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        layout.addWidget(QLabel("<b>Generated Code:</b>"))
        self.code_display = QTextEdit()
        self.code_display.setReadOnly(True)
        self.code_display.setStyleSheet("background-color: #333; color: #eee; font-family: monospace;")
        layout.addWidget(self.code_display)

        self.run_btn = QPushButton("RUN MISSION")
        self.run_btn.setStyleSheet("background-color: green; color: white; font-weight: bold; padding: 10px;")
        self.run_btn.clicked.connect(self.run_mission)
        layout.addWidget(self.run_btn)

    def set_code(self, code):
        self.last_generated_code = code
        self.code_display.setPlainText(code)

    def run_mission(self):
        if not self.last_generated_code:
            QMessageBox.warning(self, "Warning", "No code generated yet.")
            return
        run_generated_mission(self.last_generated_code)
