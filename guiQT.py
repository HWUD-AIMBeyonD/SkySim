import sys
import signal
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget
)

from SkyQT.Tab4 import SimulationTab

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SkySim Control Station")
        self.resize(1200, 800)
        
        # Tabs
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Only include the Simulation Tab
        self.tab_sim = SimulationTab()
        self.tabs.addTab(self.tab_sim, "Simulation")

    def closeEvent(self, event):
        """Clean up ROS 2 resources when closing the application."""
        try:
            from SkyQT.ros_interface import get_ros2_interface
            get_ros2_interface().shutdown()
        except Exception:
            pass
        event.accept()

def main():
    app = QApplication(sys.argv)
    
    # Allow Ctrl+C to quit
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
