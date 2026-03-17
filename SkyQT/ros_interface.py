"""
ROS 2 Interface for SkySim GUI
Provides communication with the simulation via subprocess calls to ros2 CLI.
Implements a Command Queue to serialize requests and prevent timeouts/resource exhaustion.
Implements a persistent Listener for real-time updates.
"""
import threading
import subprocess
import queue
import json
import time
import os
import sys

class ROS2Interface:
    """
    Interface for ROS 2 communication using subprocess calls.
    This avoids rclpy/Qt conflicts that cause segfaults.
    """

    def __init__(self):
        self._connected = False
        self._drone_count = 3  # Default
        self._callbacks = {
            'drone_count': [],
            'status': [],
            'log': []
        }
        self._main_thread_id = threading.current_thread().ident
        
        # Command Processing
        self._command_queue = queue.Queue()
        self._command_thread = None
        self._running = False
        
        # Real-time Listener
        self._listener_thread = None
        self._listener_process = None

    def on_drone_count_changed(self, callback):
        self._callbacks['drone_count'].append(callback)

    def on_status_changed(self, callback):
        self._callbacks['status'].append(callback)

    def on_log(self, callback):
        self._callbacks['log'].append(callback)

    def _emit_drone_count(self, count):
        for cb in self._callbacks['drone_count']:
            try: cb(count)
            except: pass

    def _emit_status(self, status):
        for cb in self._callbacks['status']:
            try: cb(status)
            except: pass

    def _emit_log(self, msg):
        for cb in self._callbacks['log']:
            try: cb(msg)
            except: pass

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def drone_count(self) -> int:
        return self._drone_count

    def initialize(self) -> bool:
        """Initialize ROS 2 connection."""
        if self._connected: return True
        
        self._connected = True
        self._running = True
        
        # Start Command Worker
        self._command_thread = threading.Thread(target=self._command_worker, daemon=True)
        self._command_thread.start()
        
        # Start Listener Worker
        self._listener_thread = threading.Thread(target=self._listener_worker, daemon=True)
        self._listener_thread.start()
        
        self._log("Connected (subprocess mode)")
        self._emit_status("Connected")
        return True

    def shutdown(self):
        """Shutdown connection."""
        self._connected = False
        self._running = False
        
        # Stop listener process
        if self._listener_process:
            self._listener_process.terminate()
            self._listener_process = None
            
        self._log("Disconnected")
        self._emit_status("Disconnected")

    def _log(self, msg: str):
        """Log message (safe to call from any thread)."""
        print(f"[ROS2Interface] {msg}")
        # If we are on main thread, emit directly
        if threading.current_thread().ident == self._main_thread_id:
            self._emit_log(msg)

    # --- Command Queue Methods ---

    def _command_worker(self):
        """Process commands from the queue sequentially."""
        while self._running:
            try:
                # Get command with timeout to allow checking self._running
                cmd_data = self._command_queue.get(timeout=1.0)
            except queue.Empty:
                continue
            
            description = cmd_data.get('desc', 'Unknown command')
            cmd_args = cmd_data.get('args', [])
            
            self._log(f"Processing: {description}")
            
            try:
                result = subprocess.run(
                    cmd_args,
                    capture_output=True,
                    text=True,
                    timeout=15.0 # Increased timeout
                )
                
                if result.returncode == 0:
                    self._log(f"Success: {description}")
                else:
                    err = result.stderr.strip() if result.stderr else "Unknown error"
                    self._log(f"Failed: {description} | Error: {err[:100]}...")
            except subprocess.TimeoutExpired:
                 self._log(f"Timeout: {description}")
            except Exception as e:
                 self._log(f"Error executing {description}: {str(e)}")
            
            self._command_queue.task_done()

    def _queue_command(self, description, args):
        """Add a command to the queue."""
        if not self._connected:
            self._log("Not connected. Command ignored.")
            return False
        
        self._command_queue.put({
            'desc': description,
            'args': args
        })
        return True

    # --- Public API (Async) ---

    def add_single_drone(self) -> bool:
        return self._queue_command(
            "Add Single Drone",
            ['ros2', 'service', 'call', '/add_drone', 'std_srvs/srv/Trigger']
        )

    def spawn_drones(self, count: int) -> bool:
        return self._queue_command(
            f"Spawn {count} Drones",
            ['ros2', 'topic', 'pub', '--once', '/swarm/spawn_request', 'std_msgs/msg/Int32', f'{{data: {count}}}']
        )

    def send_user_command(self, command: str) -> bool:
        safe_cmd = command.replace("'", "'\'")
        return self._queue_command(
            f"User Command: {command}",
            ['ros2', 'topic', 'pub', '--once', '/skysim/user_command', 'std_msgs/msg/String', f"{{data: '{safe_cmd}'}}"]
        )

    def send_test_command(self, command: str) -> bool:
        return self._queue_command(
            f"Test Command: {command}",
            ['ros2', 'topic', 'pub', '--once', '/skysim/test_command', 'std_msgs/msg/String', f"{{data: '{command}'}}"]
        )

    def set_apf_enabled(self, enabled: bool) -> bool:
        value_str = 'true' if enabled else 'false'
        return self._queue_command(
            f"Set APF: {enabled}",
            ['ros2', 'param', 'set', '/swarm_controller', 'use_apf', value_str]
        )

    def send_pattern_waypoints(self, coordinates: list) -> bool:
        if not coordinates: return False
        
        poses_str = ""
        for i, coord in enumerate(coordinates):
            x, y, z = float(coord[0]), float(coord[1]), float(coord[2])
            poses_str += f"{{position: {{x: {x}, y: {y}, z: {z}}}, orientation: {{w: 1.0}}}}"
            if i < len(coordinates) - 1:
                poses_str += ", "
        
        msg = f"'{{poses: [{poses_str}]}}'"
        
        # Use shell=True for complex arguments, handle carefully
        # We'll use a wrapper script or carefully constructed args for subprocess
        # Ideally, avoid shell=True. But for this complex string, it's easier.
        # We will reconstruct it as a list for subprocess to avoid shell=True
        
        return self._queue_command(
            "Send Pattern Waypoints",
            ['ros2', 'topic', 'pub', '--once', '/swarm/desired_goals', 'geometry_msgs/msg/PoseArray', f"{{poses: [{poses_str}]}}"]
        )

    def get_apf_enabled(self) -> bool:
        # Blocking call, discouraged but needed for UI init sometimes
        try:
            result = subprocess.run(
                ['ros2', 'param', 'get', '/swarm_controller', 'use_apf'],
                capture_output=True, text=True, timeout=2.0
            )
            return 'true' in result.stdout.lower()
        except:
            return True

    # --- Listener Worker ---
    
    def _listener_worker(self):
        """
        Runs a persistent 'ros2 topic echo' process to get updates.
        This is faster than repeated polling.
        """
        import re
        
        # We will monitor /swarm/drone_count
        cmd = ['ros2', 'topic', 'echo', '/swarm/drone_count', 'std_msgs/msg/Int32']
        
        while self._running:
            try:
                self._listener_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )
                
                # Read line by line
                for line in self._listener_process.stdout:
                    if not self._running: break
                    
                    # Parse data: 5
                    match = re.search(r'data:\s*(-?\d+)', line)
                    if match:
                        new_count = int(match.group(1))
                        if new_count != self._drone_count:
                            self._drone_count = new_count
                            # Dispatch to main thread ideally, but direct call is okay if slots handle it
                            self._emit_drone_count(new_count)
                            
                self._listener_process.wait()
            except Exception as e:
                print(f"Listener error: {e}")
                time.sleep(1.0)
                
            time.sleep(1.0) # Retry delay if process dies

# Global instance
_ros2_interface = None

def get_ros2_interface():
    global _ros2_interface
    if _ros2_interface is None:
        _ros2_interface = ROS2Interface()
    return _ros2_interface