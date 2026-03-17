"""
Simulation Control Tab for SkyScript GUI
Provides controls for drone spawning, APF toggle, LLM commands, and test formations.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QComboBox, QLineEdit, QTextEdit, QGroupBox,
    QFrame, QCheckBox, QSplitter
)
from PyQt6.QtCore import Qt, QTimer

from SkyQT.ros_interface import get_ros2_interface
from SkyQT.drawing_canvas import PatternDrawingWidget

# Import Gemini model listing
import os

try:
    import google.generativeai as genai
    from dotenv import load_dotenv
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


def fetch_gemini_models() -> list:
    """Fetch available Gemini models from Google API."""
    if not GENAI_AVAILABLE:
        return ["gemini-2.0-flash (default)", "gemini-1.5-pro", "gemini-1.5-flash"]

    try:
        env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
        load_dotenv(dotenv_path=env_path)

        api_key = os.getenv('GEMINI_API_KEY') or os.getenv('API_KEY')
        if not api_key:
            return ["gemini-2.0-flash (default)", "gemini-1.5-pro", "gemini-1.5-flash"]

        genai.configure(api_key=api_key)
        models = genai.list_models()

        # Filter models that support generateContent
        model_names = []
        for m in models:
            if 'generateContent' in m.supported_generation_methods:
                name = m.name.replace('models/', '')
                model_names.append(name)

        return model_names if model_names else ["gemini-2.0-flash"]
    except Exception as e:
        print(f"Error fetching Gemini models: {e}")
        return ["gemini-2.0-flash (default)", "gemini-1.5-pro", "gemini-1.5-flash"]


class SimulationTab(QWidget):
    def __init__(self):
        super().__init__()
        self.selected_model = "gemini-2.0-flash"
        self.ros2 = get_ros2_interface()
        self.init_ui()
        self.connect_callbacks()

        # Auto-connect to ROS 2 on tab creation
        QTimer.singleShot(500, self.connect_ros2)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # === TOP ROW: Drone Controls + APF + Test Commands ===
        top_layout = QHBoxLayout()

        # Drone Spawning
        drone_group = QGroupBox("Drone Spawning")
        drone_layout = QVBoxLayout(drone_group)

        count_layout = QHBoxLayout()
        count_layout.addWidget(QLabel("Current Drones:"))
        self.drone_count_label = QLabel("3")
        self.drone_count_label.setStyleSheet("font-weight: bold; font-size: 18px; color: #4ade80;")
        count_layout.addWidget(self.drone_count_label)
        count_layout.addStretch()
        drone_layout.addLayout(count_layout)

        self.btn_add_one = QPushButton("Add Single Drone")
        self.btn_add_one.setStyleSheet("background-color: #3b82f6; color: white; padding: 6px;")
        self.btn_add_one.clicked.connect(self.add_single_drone)
        drone_layout.addWidget(self.btn_add_one)

        spawn_layout = QHBoxLayout()
        spawn_layout.addWidget(QLabel("Spawn:"))
        self.spawn_spinbox = QSpinBox()
        self.spawn_spinbox.setRange(1, 50)
        self.spawn_spinbox.setValue(5)
        spawn_layout.addWidget(self.spawn_spinbox)
        self.btn_spawn = QPushButton("Go")
        self.btn_spawn.setStyleSheet("background-color: #22c55e; color: white; padding: 6px;")
        self.btn_spawn.clicked.connect(self.spawn_multiple_drones)
        spawn_layout.addWidget(self.btn_spawn)
        drone_layout.addLayout(spawn_layout)

        top_layout.addWidget(drone_group)

        # APF Toggle
        apf_group = QGroupBox("Collision Avoidance")
        apf_layout = QVBoxLayout(apf_group)

        self.apf_checkbox = QCheckBox("Enable APF")
        self.apf_checkbox.setChecked(True)
        self.apf_checkbox.stateChanged.connect(self.toggle_apf)
        apf_layout.addWidget(self.apf_checkbox)

        self.apf_status = QLabel("Status: Enabled")
        self.apf_status.setStyleSheet("color: #4ade80; font-weight: bold;")
        apf_layout.addWidget(self.apf_status)

        apf_layout.addWidget(QLabel("Safety: 0.8m"))
        apf_layout.addStretch()

        top_layout.addWidget(apf_group)

        # Test Commands
        test_group = QGroupBox("Test Formations")
        test_layout = QVBoxLayout(test_group)

        self.btn_triangle = QPushButton("Triangle")
        self.btn_triangle.setStyleSheet("background-color: #f59e0b; color: black; padding: 6px;")
        self.btn_triangle.clicked.connect(lambda: self.send_test_command("triangle"))
        test_layout.addWidget(self.btn_triangle)

        self.btn_unsafe = QPushButton("Unsafe (APF Test)")
        self.btn_unsafe.setStyleSheet("background-color: #ef4444; color: white; padding: 6px;")
        self.btn_unsafe.clicked.connect(lambda: self.send_test_command("unsafe"))
        test_layout.addWidget(self.btn_unsafe)

        self.btn_safe_hover = QPushButton("Safe Hover")
        self.btn_safe_hover.setStyleSheet("background-color: #22c55e; color: white; padding: 6px;")
        self.btn_safe_hover.clicked.connect(lambda: self.send_test_command("safe_hover"))
        test_layout.addWidget(self.btn_safe_hover)

        top_layout.addWidget(test_group)

        main_layout.addLayout(top_layout)

        # === MIDDLE ROW: LLM Commands + Pattern Drawing (side by side) ===
        middle_splitter = QSplitter(Qt.Orientation.Horizontal)

        # LLM Commands Panel
        llm_widget = QWidget()
        llm_layout = QVBoxLayout(llm_widget)
        llm_layout.setContentsMargins(0, 0, 0, 0)

        llm_label = QLabel("<b>LLM Commands</b>")
        llm_layout.addWidget(llm_label)

        # Model selector
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(150)
        self.model_combo.currentTextChanged.connect(self.on_model_changed)
        model_layout.addWidget(self.model_combo)
        self.btn_refresh_models = QPushButton("Refresh")
        self.btn_refresh_models.clicked.connect(self.refresh_models)
        model_layout.addWidget(self.btn_refresh_models)
        llm_layout.addLayout(model_layout)

        # Command input
        llm_layout.addWidget(QLabel("Natural Language Command:"))
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("e.g., Form a line with 1m spacing at height 1.5m")
        self.command_input.returnPressed.connect(self.send_llm_command)
        llm_layout.addWidget(self.command_input)

        self.btn_send_command = QPushButton("Send to LLM")
        self.btn_send_command.setStyleSheet("background-color: #8b5cf6; color: white; padding: 8px; font-weight: bold;")
        self.btn_send_command.clicked.connect(self.send_llm_command)
        llm_layout.addWidget(self.btn_send_command)

        llm_layout.addStretch()
        middle_splitter.addWidget(llm_widget)

        # Pattern Drawing Panel
        self.pattern_widget = PatternDrawingWidget()
        self.pattern_widget.pattern_ready.connect(self.send_pattern_coordinates)
        middle_splitter.addWidget(self.pattern_widget)

        middle_splitter.setSizes([400, 400])
        main_layout.addWidget(middle_splitter, stretch=1)

        # === CONNECTION STATUS BAR ===
        status_frame = QFrame()
        status_frame.setFrameShape(QFrame.Shape.StyledPanel)
        status_layout = QHBoxLayout(status_frame)

        self.connection_status = QLabel("ROS 2: Not Connected")
        self.connection_status.setStyleSheet("color: #ef4444; font-weight: bold;")
        status_layout.addWidget(self.connection_status)

        status_layout.addStretch()

        self.btn_connect = QPushButton("Connect to ROS 2")
        self.btn_connect.setStyleSheet("background-color: #3b82f6; color: white; padding: 6px;")
        self.btn_connect.clicked.connect(self.connect_ros2)
        status_layout.addWidget(self.btn_connect)

        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.setStyleSheet("background-color: #6b7280; color: white; padding: 6px;")
        self.btn_disconnect.clicked.connect(self.disconnect_ros2)
        self.btn_disconnect.setEnabled(False)
        status_layout.addWidget(self.btn_disconnect)

        main_layout.addWidget(status_frame)

        # === LOG DISPLAY ===
        log_group = QGroupBox("Activity Log")
        log_layout = QVBoxLayout(log_group)

        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet("background-color: #1e1e1e; color: #4ade80; font-family: monospace;")
        self.log_display.setMaximumHeight(120)
        log_layout.addWidget(self.log_display)

        main_layout.addWidget(log_group)

        # Load models on startup
        QTimer.singleShot(100, self.refresh_models)

    def connect_callbacks(self):
        """Register callbacks for ROS 2 interface events."""
        self.ros2.on_drone_count_changed(self.update_drone_count)
        self.ros2.on_status_changed(self.update_connection_status)
        self.ros2.on_log(self.append_log)

    def connect_ros2(self):
        """Initialize connection to ROS 2."""
        self.append_log("Connecting to ROS 2...")
        if self.ros2.initialize():
            self.btn_connect.setEnabled(False)
            self.btn_disconnect.setEnabled(True)
            self.connection_status.setText("ROS 2: Connected")
            self.connection_status.setStyleSheet("color: #4ade80; font-weight: bold;")
        else:
            self.connection_status.setText("ROS 2: Connection Failed")
            self.connection_status.setStyleSheet("color: #ef4444; font-weight: bold;")

    def disconnect_ros2(self):
        """Disconnect from ROS 2."""
        self.ros2.shutdown()
        self.btn_connect.setEnabled(True)
        self.btn_disconnect.setEnabled(False)
        self.connection_status.setText("ROS 2: Disconnected")
        self.connection_status.setStyleSheet("color: #ef4444; font-weight: bold;")

    def update_drone_count(self, count: int):
        """Update drone count display."""
        self.drone_count_label.setText(str(count))

    def update_connection_status(self, status: str):
        """Update connection status display."""
        if "Connected" in status:
            self.connection_status.setText(f"ROS 2: {status}")
            self.connection_status.setStyleSheet("color: #4ade80; font-weight: bold;")
        else:
            self.connection_status.setText(f"ROS 2: {status}")
            self.connection_status.setStyleSheet("color: #ef4444; font-weight: bold;")

    def append_log(self, msg: str):
        """Append message to log display."""
        self.log_display.append(f">> {msg}")
        cursor = self.log_display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.log_display.setTextCursor(cursor)

    def add_single_drone(self):
        """Add a single drone to the simulation."""
        if self.ros2.add_single_drone():
            self.append_log("Adding single drone...")
        else:
            self.append_log("Failed to add drone - check ROS 2 connection")

    def spawn_multiple_drones(self):
        """Spawn multiple drones."""
        count = self.spawn_spinbox.value()
        if self.ros2.spawn_drones(count):
            self.append_log(f"Spawning {count} drones...")
        else:
            self.append_log("Failed to spawn drones - check ROS 2 connection")

    def toggle_apf(self, state):
        """Toggle APF collision avoidance."""
        enabled = state == Qt.CheckState.Checked.value
        if self.ros2.set_apf_enabled(enabled):
            if enabled:
                self.apf_status.setText("Status: Enabled")
                self.apf_status.setStyleSheet("color: #4ade80; font-weight: bold;")
            else:
                self.apf_status.setText("Status: Disabled")
                self.apf_status.setStyleSheet("color: #ef4444; font-weight: bold;")
        else:
            self.append_log("Failed to toggle APF - check ROS 2 connection")

    def refresh_models(self):
        """Refresh the list of available Gemini models."""
        self.append_log("Fetching Gemini models...")
        self.model_combo.clear()

        models = fetch_gemini_models()
        self.model_combo.addItems(models)

        idx = self.model_combo.findText(self.selected_model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)

        self.append_log(f"Found {len(models)} models")

    def on_model_changed(self, model_name: str):
        """Handle model selection change."""
        self.selected_model = model_name
        if model_name:
            self.append_log(f"Selected: {model_name}")

    def send_llm_command(self):
        """Send natural language command to LLM."""
        command = self.command_input.text().strip()
        if not command:
            self.append_log("Please enter a command")
            return

        if self.ros2.send_user_command(command):
            self.append_log(f"LLM: {command}")
            self.command_input.clear()
        else:
            self.append_log("Failed to send command - check ROS 2 connection")

    def send_test_command(self, command: str):
        """Send predefined test command."""
        if self.ros2.send_test_command(command):
            self.append_log(f"Test: {command}")
        else:
            self.append_log("Failed to send test command - check ROS 2 connection")

    def send_pattern_coordinates(self, coordinates: list):
        """Send drawn pattern coordinates as drone waypoints."""
        if not coordinates:
            self.append_log("No pattern points to send")
            return

        self.append_log(f"Sending pattern with {len(coordinates)} waypoints...")
        coord_str = str(coordinates)
        self.append_log(f"Coordinates: {coord_str}")

        if self.ros2.send_pattern_waypoints(coordinates):
            self.append_log("Pattern sent successfully!")
        else:
            self.append_log("Failed to send pattern - check ROS 2 connection")
