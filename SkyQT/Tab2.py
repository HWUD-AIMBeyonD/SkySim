from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter
)
from PyQt6.QtCore import Qt
from SkyQT.components import ChatWidget, PlotWidget, CodeWidget

class SkySLMAgentTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # Left: Chat
        self.chat_widget = ChatWidget()
        splitter.addWidget(self.chat_widget)

        # Right: Plot + Code
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        self.plot_widget = PlotWidget()
        right_layout.addWidget(self.plot_widget, stretch=1)

        self.code_widget = CodeWidget()
        right_layout.addWidget(self.code_widget, stretch=1)

        splitter.addWidget(right_widget)
        splitter.setSizes([400, 400])

        # Connect
        self.chat_widget.code_generated.connect(self.plot_widget.update_plot)
        self.chat_widget.code_generated.connect(self.code_widget.set_code)