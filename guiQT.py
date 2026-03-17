import sys
import signal
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QToolBar, QMessageBox, QLabel, QPushButton
)
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtCore import Qt

from SkyQT.Tab1 import FlightDeckTab
from SkyQT.Tab2 import SkySLMAgentTab
from SkyQT.Tab3 import HybridTab
from SkyQT.Tab4 import SimulationTab
from SkyQT.flight_commands import toggle_connection, toggle_arm, comm, state

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SkyScript")
        self.resize(1200, 800)
        
        # Toolbar
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        
        # Connect Button
        self.btn_connect = QPushButton("Connect")
        self.btn_connect.clicked.connect(toggle_connection)
        self.btn_connect.setStyleSheet("background-color: green; color: white; font-weight: bold; padding: 6px; border-radius: 4px;")
        toolbar.addWidget(self.btn_connect)
        
        # Spacer
        toolbar.addWidget(QLabel("  "))
        
        # Arm Button
        self.btn_arm = QPushButton("ARM")
        self.btn_arm.clicked.connect(toggle_arm)
        self.btn_arm.setEnabled(False)
        self.btn_arm.setStyleSheet("background-color: #555; color: #aaa; font-weight: bold; padding: 6px; border-radius: 4px;") 
        toolbar.addWidget(self.btn_arm)

        # Spacer
        toolbar.addWidget(QLabel("     "))
        
        # Status Label
        self.lbl_status = QLabel("Disconnected")
        self.lbl_status.setMargin(5)
        toolbar.addWidget(self.lbl_status)

        # Tabs
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        self.tab1 = FlightDeckTab()
        self.tab2 = SkySLMAgentTab()
        self.tab3 = HybridTab()
        self.tab4 = SimulationTab()

        self.tabs.addTab(self.tab1, "Flight Deck")
        self.tabs.addTab(self.tab2, "SkySLM Agent")
        self.tabs.addTab(self.tab3, "Dashboard")
        self.tabs.addTab(self.tab4, "Simulation")
        
        # Connect Signals
        comm.notify_signal.connect(self.show_notification)
        comm.connection_changed.connect(self.update_connection_state)
        comm.arming_changed.connect(self.update_arming_state)

    def show_notification(self, msg, type_):
        self.statusBar().showMessage(msg, 3000)
        
        if type_ in ['negative', 'warning']:
             pass

    def update_connection_state(self, connected):
        if connected:
            self.btn_connect.setText("Disconnect")
            self.btn_connect.setStyleSheet("background-color: red; color: white; font-weight: bold; padding: 6px; border-radius: 4px;")
            
            self.lbl_status.setText("Connected")
            self.lbl_status.setStyleSheet("color: green; font-weight: bold;")
            
            self.btn_arm.setEnabled(True)
            self.btn_arm.setStyleSheet("background-color: yellow; color: black; font-weight: bold; padding: 6px; border-radius: 4px;")
        else:
            self.btn_connect.setText("Connect")
            self.btn_connect.setStyleSheet("background-color: green; color: white; font-weight: bold; padding: 6px; border-radius: 4px;")
            
            self.lbl_status.setText("Disconnected")
            self.lbl_status.setStyleSheet("color: red;")
            
            self.btn_arm.setEnabled(False)
            self.btn_arm.setStyleSheet("background-color: #555; color: #aaa; font-weight: bold; padding: 6px; border-radius: 4px;")

    def update_arming_state(self, armed):
        if armed:
            self.btn_arm.setText("DISARM")
            self.btn_arm.setStyleSheet("background-color: red; color: white; font-weight: bold; padding: 6px; border-radius: 4px;")

            self.lbl_status.setText("ARMED")
            self.lbl_status.setStyleSheet("color: orange; font-weight: bold;")
        else:
            self.btn_arm.setText("ARM")
            if state.connected:
                self.btn_arm.setStyleSheet("background-color: yellow; color: black; font-weight: bold; padding: 6px; border-radius: 4px;")

            if state.connected:
                self.lbl_status.setText("Connected")
                self.lbl_status.setStyleSheet("color: green; font-weight: bold;")

    def closeEvent(self, event):
        """Clean up ROS 2 resources when closing the application."""
        from SkyQT.ros_interface import get_ros2_interface
        get_ros2_interface().shutdown()
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