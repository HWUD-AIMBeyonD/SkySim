from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGridLayout, QTextEdit, QFrame, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QPolygonF
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

from SkyQT.flight_commands import state, run_command, comm

class ArtificialHorizon(QWidget):
    def __init__(self):
        super().__init__()
        self.roll = 0
        self.pitch = 0
        self.setMinimumSize(200, 200)
        self.setStyleSheet("background-color: black;")

    def update_attitude(self, roll, pitch):
        self.roll = roll
        self.pitch = pitch
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        cx = w / 2
        cy = h / 2

        # Translate to center and rotate
        painter.translate(cx, cy)
        painter.rotate(-self.roll)

        pitch_px = self.pitch * 4.0 
        
        painter.translate(0, pitch_px)

        # Sky
        painter.setBrush(QBrush(QColor("#0055a4")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(int(-w), int(-h*2), int(w*2), int(h*2))

        # Ground
        painter.setBrush(QBrush(QColor("#4e3629")))
        painter.drawRect(int(-w), 0, int(w*2), int(h*2))
        
        # Horizon Line
        painter.setPen(QPen(Qt.GlobalColor.white, 2))
        painter.drawLine(int(-w), 0, int(w), 0)

        # Pitch Lines (simplified)
        painter.setPen(QPen(Qt.GlobalColor.white, 1))
        for i in [10, 20, 30]:
            y = -i * 4.0
            painter.drawLine(-30, int(y), 30, int(y)) # Up
            y = i * 4.0
            painter.drawLine(-30, int(y), 30, int(y)) # Down

        # Reset transform for static elements (crosshair)
        painter.resetTransform()
        painter.translate(cx, cy)
        
        # Crosshair (Yellow airplane symbol)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(Qt.GlobalColor.yellow))
        
        # Center dot
        painter.drawEllipse(QPointF(0, 0), 3, 3)
        # Left wing
        painter.drawRect(-40, -2, 35, 4)
        # Right wing
        painter.drawRect(5, -2, 35, 4)

class RadarWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        self.fig = Figure(figsize=(3, 3), dpi=100)
        self.ax = self.fig.add_subplot(111, projection='polar')
        self.canvas = FigureCanvas(self.fig)
        layout.addWidget(self.canvas)
        
        self.ax.set_theta_zero_location("N")
        self.ax.set_theta_direction(-1) # Clockwise
        self.ax.set_ylim(0, 2.0)
        self.ax.set_yticklabels([])
        
        # Explicitly set thetagrids for precise label placement
        grid_angles = [0, 90, 180, 270] # In degrees: Front, Right, Back, Left
        grid_labels = ['Front', 'Right', 'Back', 'Left']
        self.ax.set_thetagrids(grid_angles, labels=grid_labels)
        
        self.angles = [0, np.pi/2, np.pi, 3*np.pi/2] # Corresponding angles for bars
        self.bars = self.ax.bar(self.angles, [2, 2, 2, 2], width=0.5, color='#4ade80')

    def update_radar(self, radar_data):        
        data_map = [radar_data[0], radar_data[3], radar_data[2], radar_data[1]]
        
        for bar, val in zip(self.bars, data_map):
            bar.set_height(min(val, 2.0))
            if val < 0.3:
                bar.set_color('#ef4444') # Red
            elif val < 0.6:
                bar.set_color('#eab308') # Yellow
            else:
                bar.set_color('#4ade80') # Green
        
        self.canvas.draw()

class FlightDeckTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(100) # 10Hz

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        top_layout = QHBoxLayout()
        
        self.scene_container = QFrame()
        self.scene_container.setFrameShape(QFrame.Shape.StyledPanel)
        self.scene_container.setStyleSheet("background-color: #222;")
        
        # Use Grid Layout for robust centering
        scene_layout = QGridLayout(self.scene_container)
        scene_layout.setContentsMargins(0, 0, 0, 0)

        scene_label = QLabel("3D View (Not Implemented in Qt Port yet)")
        scene_label.setStyleSheet("color: white;")
        scene_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Add widget with alignment to center it in the grid cell
        scene_layout.addWidget(scene_label, 0, 0, Qt.AlignmentFlag.AlignCenter)
        top_layout.addWidget(self.scene_container, stretch=1)
        
        self.horizon = ArtificialHorizon()
        top_layout.addWidget(self.horizon, stretch=1)
        
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        self.radar = RadarWidget()
        right_layout.addWidget(self.radar, stretch=1)

        # Battery
        batt_layout = QHBoxLayout()
        batt_label = QLabel("Battery:")
        batt_layout.addWidget(batt_label, 0, Qt.AlignmentFlag.AlignVCenter)
        
        self.batt_bar = QProgressBar()
        self.batt_bar.setRange(0, 100)
        self.batt_bar.setValue(0)
        self.batt_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        batt_layout.addWidget(self.batt_bar)
        
        right_layout.addLayout(batt_layout)
        
        controls_group = QWidget()
        grid = QGridLayout(controls_group)
        
        btn_style = "font-size: 10px; padding: 5px;"
        
        # Grid layout for arrows
        #   ^
        # < v >
        
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
        
        # Takeoff/Land
        self.btn_takeoff = QPushButton("TAKEOFF")
        self.btn_takeoff.setStyleSheet("background-color: red; color: white;")
        self.btn_takeoff.clicked.connect(lambda: run_command('takeoff'))
        grid.addWidget(self.btn_takeoff, 0, 3)
        
        self.btn_land = QPushButton("LAND")
        self.btn_land.setStyleSheet("background-color: red; color: white;")
        self.btn_land.clicked.connect(lambda: run_command('land'))
        grid.addWidget(self.btn_land, 1, 3)
        
        # Up/Down
        self.btn_up = QPushButton("UP")
        self.btn_up.clicked.connect(lambda: run_command('up'))
        grid.addWidget(self.btn_up, 0, 4)
        
        self.btn_down = QPushButton("DWN")
        self.btn_down.clicked.connect(lambda: run_command('down'))
        grid.addWidget(self.btn_down, 1, 4)
        
        right_layout.addWidget(controls_group, stretch=0)
        
        top_layout.addWidget(right_panel, stretch=0)
        
        layout.addLayout(top_layout, stretch=2)
        
        # Bottom Section: Logs
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet("background-color: black; color: #4ade80; font-family: monospace;")
        self.log_display.setMaximumHeight(150)
        layout.addWidget(self.log_display, stretch=0)
        
        # Connect Log Signal
        comm.log_signal.connect(self.append_log)

    def append_log(self, msg):
        self.log_display.append(f">> {msg}")
        cursor = self.log_display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.log_display.setTextCursor(cursor)

    def update_ui(self):
        # Update Horizon
        self.horizon.update_attitude(state.roll, state.pitch)
        
        self.radar.update_radar(state.radar)
        
        self.batt_bar.setValue(state.battery)
        if state.battery < 20:
             self.batt_bar.setStyleSheet("QProgressBar::chunk { background-color: red; }")
        else:
             self.batt_bar.setStyleSheet("QProgressBar::chunk { background-color: green; }")
