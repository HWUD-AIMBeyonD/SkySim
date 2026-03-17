from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGridLayout, QTextEdit, QFrame, QProgressBar, QSplitter
)
from PyQt6.QtCore import Qt
from SkyQT.Tab1 import ArtificialHorizon, RadarWidget
from SkyQT.components import ChatWidget, PlotWidget, CodeWidget
from SkyQT.flight_commands import run_command, state

class ManualControlsWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        # Battery
        batt_layout = QHBoxLayout()
        batt_label = QLabel("Battery:")
        batt_layout.addWidget(batt_label, 0, Qt.AlignmentFlag.AlignVCenter)
        
        self.batt_bar = QProgressBar()
        self.batt_bar.setRange(0, 100)
        self.batt_bar.setValue(0)
        self.batt_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        batt_layout.addWidget(self.batt_bar)
        
        layout.addLayout(batt_layout)

        controls_group = QWidget()
        grid = QGridLayout(controls_group)
        
        self.btn_fwd = QPushButton("⬆️")
        self.btn_fwd.clicked.connect(lambda: run_command('forward'))
        self.btn_left = QPushButton("⬅️")
        self.btn_left.clicked.connect(lambda: run_command('left'))
        self.btn_right = QPushButton("➡️")
        self.btn_right.clicked.connect(lambda: run_command('right'))
        self.btn_back = QPushButton("⬇️")
        self.btn_back.clicked.connect(lambda: run_command('back'))
        
        grid.addWidget(self.btn_fwd, 0, 1)
        grid.addWidget(self.btn_left, 1, 0)
        grid.addWidget(self.btn_back, 1, 1)
        grid.addWidget(self.btn_right, 1, 2)
        
        self.btn_takeoff = QPushButton("TAKEOFF")
        self.btn_takeoff.setStyleSheet("background-color: red; color: white;")
        self.btn_takeoff.clicked.connect(lambda: run_command('takeoff'))
        grid.addWidget(self.btn_takeoff, 0, 3)
        
        self.btn_land = QPushButton("LAND")
        self.btn_land.setStyleSheet("background-color: red; color: white;")
        self.btn_land.clicked.connect(lambda: run_command('land'))
        grid.addWidget(self.btn_land, 1, 3)
        
        self.btn_up = QPushButton("UP")
        self.btn_up.clicked.connect(lambda: run_command('up'))
        grid.addWidget(self.btn_up, 0, 4)
        
        self.btn_down = QPushButton("DWN")
        self.btn_down.clicked.connect(lambda: run_command('down'))
        grid.addWidget(self.btn_down, 1, 4)
        
        layout.addWidget(controls_group)

    def update_battery(self, battery_level):
        self.batt_bar.setValue(battery_level)
        if battery_level < 20:
             self.batt_bar.setStyleSheet("QProgressBar::chunk { background-color: red; }")
        else:
             self.batt_bar.setStyleSheet("QProgressBar::chunk { background-color: green; }")


class HybridTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.timer = self.startTimer(100) # 10Hz update

    def timerEvent(self, event):
        self.horizon.update_attitude(state.roll, state.pitch)
        self.radar.update_radar(state.radar)
        
        self.hybrid_batt_bar.setValue(state.battery)
        if state.battery < 20:
             self.hybrid_batt_bar.setStyleSheet("QProgressBar::chunk { background-color: red; }")
        else:
             self.hybrid_batt_bar.setStyleSheet("QProgressBar::chunk { background-color: green; }")

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # Top Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter, stretch=2)

        # --- COL 1: Chat (SkySLM Agent) ---
        self.chat_widget = ChatWidget()
        splitter.addWidget(self.chat_widget)

        # --- COL 2: Flight Plan ---
        col2_widget = QWidget()
        col2_layout = QVBoxLayout(col2_widget)
        col2_layout.setContentsMargins(0,0,0,0)
        
        self.plot_widget = PlotWidget()
        col2_layout.addWidget(self.plot_widget, stretch=1)
        
        splitter.addWidget(col2_widget)

        # --- COL 3: Radar (Top) + Attitude (Middle) + Battery (Bottom) ---
        col3_widget = QWidget()
        col3_widget.setMaximumWidth(350)
        col3_layout = QVBoxLayout(col3_widget)
        col3_layout.setContentsMargins(0,0,0,0)
        
        self.radar = RadarWidget()
        col3_layout.addWidget(self.radar, stretch=1)

        self.horizon = ArtificialHorizon()
        col3_layout.addWidget(self.horizon, stretch=1)
        
        batt_layout = QHBoxLayout()
        batt_label = QLabel("Battery:")
        batt_layout.addWidget(batt_label, 0, Qt.AlignmentFlag.AlignVCenter)
        
        self.hybrid_batt_bar = QProgressBar()
        self.hybrid_batt_bar.setRange(0, 100)
        self.hybrid_batt_bar.setValue(0)
        self.hybrid_batt_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        batt_layout.addWidget(self.hybrid_batt_bar)
        col3_layout.addLayout(batt_layout)
        
        splitter.addWidget(col3_widget)
        
        # --- BOTTOM: Generated Code ---
        self.code_widget = CodeWidget()
        main_layout.addWidget(self.code_widget, stretch=1)

        self.chat_widget.code_generated.connect(self.plot_widget.update_plot)
        self.chat_widget.code_generated.connect(self.code_widget.set_code)
