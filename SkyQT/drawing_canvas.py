"""
Drawing Canvas Widget for SkySim GUI
Allows users to draw drone formation patterns visually.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QButtonGroup, QRadioButton
)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor


class Canvas(QWidget):
    """Simple drawing surface for placing drone waypoints."""
    points_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setMinimumSize(250, 250)
        self.setAutoFillBackground(True)

        # Set background color via palette instead of stylesheet
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor("#1a1a2e"))
        self.setPalette(palette)

        self.points = []  # List of (x, y) tuples (integers)
        self.mode = "click"
        self.world_range = 10.0

    def set_mode(self, mode: str):
        self.mode = mode

    def clear(self):
        self.points = []
        self.points_changed.emit()
        self.update()

    def get_world_coordinates(self, height: float) -> list:
        """Convert canvas points to world coordinates."""
        coords = []
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return coords

        for px, py in self.points:
            x = (px / w - 0.5) * 2 * self.world_range
            y = -(py / h - 0.5) * 2 * self.world_range
            coords.append([round(x, 2), round(y, 2), height])
        return coords

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Add point
            pos = event.position()
            self.points.append((int(pos.x()), int(pos.y())))
            self.points_changed.emit()
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            # Remove nearest point
            if not self.points:
                return
            pos = event.position()
            px, py = int(pos.x()), int(pos.y())

            min_dist = float('inf')
            nearest_idx = -1
            for i, (x, y) in enumerate(self.points):
                dist = (x - px)**2 + (y - py)**2
                if dist < min_dist:
                    min_dist = dist
                    nearest_idx = i

            if nearest_idx >= 0 and min_dist < 625:  # Within 25 pixels
                self.points.pop(nearest_idx)
                self.points_changed.emit()
                self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        w = self.width()
        h = self.height()

        if w <= 0 or h <= 0:
            return

        # Background
        painter.fillRect(0, 0, w, h, QColor("#1a1a2e"))

        # Grid
        painter.setPen(QPen(QColor("#2a2a4a"), 1))
        grid = 25
        for x in range(0, w, grid):
            painter.drawLine(x, 0, x, h)
        for y in range(0, h, grid):
            painter.drawLine(0, y, w, y)

        # Axes
        painter.setPen(QPen(QColor("#4a6a8a"), 2))
        painter.drawLine(w//2, 0, w//2, h)
        painter.drawLine(0, h//2, w, h//2)

        # Axis labels
        painter.setPen(QColor("#8a8aaa"))
        painter.drawText(w - 25, h//2 - 5, "X+")
        painter.drawText(w//2 + 5, 15, "Y+")

        # Draw lines between points
        if len(self.points) > 1:
            painter.setPen(QPen(QColor("#4ade80"), 1, Qt.PenStyle.DashLine))
            for i in range(len(self.points) - 1):
                x1, y1 = self.points[i]
                x2, y2 = self.points[i + 1]
                painter.drawLine(x1, y1, x2, y2)

        # Draw points
        for i, (px, py) in enumerate(self.points):
            # Glow
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(74, 222, 128, 80))
            painter.drawEllipse(px - 12, py - 12, 24, 24)

            # Point
            painter.setBrush(QColor("#4ade80"))
            painter.setPen(QPen(QColor("#22c55e"), 2))
            painter.drawEllipse(px - 6, py - 6, 12, 12)

            # Number
            painter.setPen(QColor("#ffffff"))
            painter.drawText(px + 10, py - 5, str(i + 1))


class PatternDrawingWidget(QWidget):
    """Pattern drawing panel with controls."""
    pattern_ready = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        layout.addWidget(QLabel("<b>Pattern Drawing</b>"))

        # Mode selection
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Mode:"))

        self.click_mode = QRadioButton("Click")
        self.click_mode.setChecked(True)
        mode_layout.addWidget(self.click_mode)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # Canvas
        self.canvas = Canvas()
        self.canvas.points_changed.connect(self._update_count)
        layout.addWidget(self.canvas, stretch=1)

        # Height slider
        h_layout = QHBoxLayout()
        h_layout.addWidget(QLabel("Height:"))
        self.height_slider = QSlider(Qt.Orientation.Horizontal)
        self.height_slider.setRange(5, 30)
        self.height_slider.setValue(10)
        self.height_slider.valueChanged.connect(self._update_height_label)
        h_layout.addWidget(self.height_slider)
        self.height_label = QLabel("1.0m")
        h_layout.addWidget(self.height_label)
        layout.addLayout(h_layout)

        # Point count
        self.count_label = QLabel("Points: 0")
        self.count_label.setStyleSheet("color: #888;")
        layout.addWidget(self.count_label)

        # Buttons
        btn_layout = QHBoxLayout()

        btn_clear = QPushButton("Clear")
        btn_clear.setStyleSheet("background-color: #6b7280; color: white; padding: 6px;")
        btn_clear.clicked.connect(self.canvas.clear)
        btn_layout.addWidget(btn_clear)

        btn_send = QPushButton("Send Pattern")
        btn_send.setStyleSheet("background-color: #8b5cf6; color: white; padding: 6px; font-weight: bold;")
        btn_send.clicked.connect(self._send)
        btn_layout.addWidget(btn_send)

        layout.addLayout(btn_layout)

        layout.addWidget(QLabel("L-click: Add | R-click: Remove"))

    def _update_count(self):
        self.count_label.setText(f"Points: {len(self.canvas.points)}")

    def _update_height_label(self, val):
        self.height_label.setText(f"{val/10:.1f}m")

    def _send(self):
        height = self.height_slider.value() / 10.0
        coords = self.canvas.get_world_coordinates(height)
        if coords:
            self.pattern_ready.emit(coords)
