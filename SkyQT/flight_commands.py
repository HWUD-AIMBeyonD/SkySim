import threading
import time
from PyQt6.QtCore import QObject, pyqtSignal

try:
    import cflib.crtp
    from cflib.crazyflie import Crazyflie
    from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
    from cflib.utils.multiranger import Multiranger
    from cflib.crazyflie.log import LogConfig
    from cflib.positioning.motion_commander import MotionCommander
    CFLIB_AVAILABLE = True
except ImportError:
    CFLIB_AVAILABLE = False
    print("Warning: cflib not found. Drone features will be mocked or fail.")

URI = 'radio://0/80/2M/E7E7E7E7E8'

# --- SIGNALS ---
class Communicator(QObject):
    log_signal = pyqtSignal(str)
    notify_signal = pyqtSignal(str, str)
    connection_changed = pyqtSignal(bool)
    arming_changed = pyqtSignal(bool)

comm = Communicator()

# --- DRONE STATE ---
class DroneState:
    def __init__(self):
        self.x = 0; self.y = 0; self.z = 0
        self.roll = 0; self.pitch = 0; self.yaw = 0
        self.battery = 0
        self.radar = [2.0, 2.0, 2.0, 2.0] # Front, Left, Back, Right
        self.connected = False
        self.is_armed = False
        self.keep_connecting = False
        self.scf = None

state = DroneState()

def log(msg):
    comm.log_signal.emit(msg)

class MockMultiranger:
    """Adapts global state.radar to the interface expected by SafeMotionCommander."""
    @property
    def front(self): return state.radar[0]
    @property
    def left(self): return state.radar[1]
    @property
    def back(self): return state.radar[2]
    @property
    def right(self): return state.radar[3]
    @property
    def up(self): return 2.0
    @property
    def down(self): return 2.0

class SafeMotionCommander:
    def __init__(self, mc, mr):
        self.mc = mc
        self.mr = mr
        self.velocity = 0.5
        self.safe_dist = 0.5

    def _check_range(self, range_val, threshold):
        if range_val is None:
            return True 
        return range_val > threshold

    def _is_safe(self, vx, vy):
        if vx > 0 and not self._check_range(self.mr.front, self.safe_dist): 
            return False
        if vx < 0 and not self._check_range(self.mr.back, self.safe_dist): 
            return False
        if vy > 0 and not self._check_range(self.mr.left, self.safe_dist): 
            return False
        if vy < 0 and not self._check_range(self.mr.right, self.safe_dist): 
            return False
        if not self._check_range(self.mr.up, self.safe_dist): 
            return False
        return True

    def _move_linear(self, vx, vy, vz, distance):
        if distance <= 0: return
        duration = distance / self.velocity
        start_time = time.time()

        while (time.time() - start_time) < duration:
            if not self._is_safe(vx, vy):
                log(f"!! OBSTACLE DETECTED ({self.safe_dist}m) - STOPPING !!")
                self.mc.stop()
                return

            self.mc.start_linear_motion(vx, vy, vz)
            time.sleep(0.02) 
        self.mc.stop()

    def forward(self, dist): self._move_linear(self.velocity, 0, 0, dist)
    def back(self, dist):    self._move_linear(-self.velocity, 0, 0, dist)
    def left(self, dist):    self._move_linear(0, self.velocity, 0, dist)
    def right(self, dist):   self._move_linear(0, -self.velocity, 0, dist)
    def up(self, dist):      self._move_linear(0, 0, self.velocity, dist)
    def down(self, dist):    self._move_linear(0, 0, -self.velocity, dist)
    
    def turn_left(self, deg):  self.mc.turn_left(deg)
    def turn_right(self, deg): self.mc.turn_right(deg)
    def circle_left(self, r):  self.mc.circle_left(r)
    def circle_right(self, r): self.mc.circle_right(r)
    def land(self):            self.mc.land()
    def take_off(self):        self.mc.take_off()
    def stop(self):            self.mc.stop()


def run_generated_mission(code_str):
    if not state.connected or not state.scf:
        comm.notify_signal.emit("Not Connected!", 'negative')
        return

    if not state.is_armed:
        comm.notify_signal.emit("Drone must be ARMED before running mission!", 'warning')
        return

    def _mission_thread():
        try:
            log("Preparing Mission...")
            
            indented_code = "\n".join(["    " + line for line in code_str.splitlines()])
            wrapper_code = f"def mission(mc):\n{indented_code}"
            
            local_scope = {}
            exec(wrapper_code, {}, local_scope)
            
            if 'mission' not in local_scope:
                log("Error: Failed to define 'mission' function.")
                return
            
            MissionFunc = local_scope['mission']

            with MotionCommander(state.scf, default_height=0.5) as real_mc:
                log("Taking Control (MotionCommander)...")
                
                mock_mr = MockMultiranger()
                safe_mc = SafeMotionCommander(real_mc, mock_mr)
                
                log("Running Mission Logic...")
                MissionFunc(safe_mc)
                log("Mission Complete.")
            
            log("Disarming Drone...")
            state.scf.cf.platform.send_arming_request(False)
            state.is_armed = False
            comm.arming_changed.emit(False)
            comm.notify_signal.emit('Mission Done - Disarmed', 'positive')
            log("DISARMED")

        except Exception as e:
            log(f"Mission Error: {e}")
            print(f"Mission Exception: {e}")
            try:
                if state.scf:
                    state.scf.cf.platform.send_arming_request(False)
                    state.is_armed = False
                    comm.arming_changed.emit(False)
                    comm.notify_signal.emit('Mission Aborted - Disarmed', 'warning')
            except:
                pass

    threading.Thread(target=_mission_thread, daemon=True).start()

def run_command(action_name):
    """
    Executes a blocking MotionCommander command in a separate thread.
    """
    if not state.connected or not state.scf:
        comm.notify_signal.emit("Not Connected!", 'negative')
        return

    def _thread_target():
        try:
            with MotionCommander(state.scf, default_height=0.5) as mc:
                log(f"Executing: {action_name}")
                if action_name == 'takeoff': mc.take_off()
                elif action_name == 'land': mc.land()
                elif action_name == 'up': mc.up(0.3)
                elif action_name == 'down': mc.down(0.3)
                elif action_name == 'forward': mc.forward(0.5)
                elif action_name == 'back': mc.back(0.5)
                elif action_name == 'left': mc.left(0.5)
                elif action_name == 'right': mc.right(0.5)
        except Exception as e:
            log(f"Cmd Error: {e}")

    threading.Thread(target=_thread_target, daemon=True).start()

def drone_connection_thread():
    if not CFLIB_AVAILABLE:
        log("CFLib not available. Cannot connect.")
        state.keep_connecting = False
        comm.connection_changed.emit(False)
        return

    cflib.crtp.init_drivers()
    log("Drivers Initialized. Connecting...")
    try:
        with SyncCrazyflie(URI, cf=Crazyflie(rw_cache='./cache')) as scf:
            state.scf = scf
            state.connected = True
            comm.connection_changed.emit(True)
            log(f"Connected to {URI}!")

            lg_stab = LogConfig(name='Stabilizer', period_in_ms=50)
            lg_stab.add_variable('stabilizer.roll', 'float')
            lg_stab.add_variable('stabilizer.pitch', 'float')
            lg_stab.add_variable('stabilizer.yaw', 'float')
            
            def stab_callback(timestamp, data, logconf):
                state.roll = data['stabilizer.roll']
                state.pitch = data['stabilizer.pitch']
                state.yaw = data['stabilizer.yaw']

            scf.cf.log.add_config(lg_stab)
            lg_stab.data_received_cb.add_callback(stab_callback)
            lg_stab.start()

            lg_bat = LogConfig(name='Battery', period_in_ms=1000)
            lg_bat.add_variable('pm.batteryLevel', 'float')

            def bat_callback(timestamp, data, logconf):
                state.battery = int(data['pm.batteryLevel'])

            scf.cf.log.add_config(lg_bat)
            lg_bat.data_received_cb.add_callback(bat_callback)
            lg_bat.start()
            
            with Multiranger(scf) as mr:
                log("Sensors Active.")
                while state.keep_connecting:
                    def clean(val): return val if val is not None else 2.0
                    state.radar = [clean(mr.front), clean(mr.left), clean(mr.back), clean(mr.right)]
                    time.sleep(0.02) 
            
            lg_stab.stop()
            lg_bat.stop()
            log("Disconnecting...")
    except Exception as e:
        log(f"Connection Error: {e}")
    
    state.connected = False
    state.is_armed = False
    state.scf = None
    state.keep_connecting = False
    comm.connection_changed.emit(False)
    comm.arming_changed.emit(False)
    log("Disconnected.")

def toggle_connection():
    if state.connected:
        state.keep_connecting = False
        comm.notify_signal.emit('Disconnecting...', 'info')
    else:
        state.keep_connecting = True
        threading.Thread(target=drone_connection_thread, daemon=True).start()
        comm.notify_signal.emit('Connecting...', 'info')

def toggle_arm():
    if state.connected and state.scf:
        try:
            new_state = not state.is_armed
            state.scf.cf.platform.send_arming_request(new_state)
            state.is_armed = new_state
            comm.arming_changed.emit(new_state)
            if new_state: 
                comm.notify_signal.emit('DRONE ARMED', 'warning')
                log("ARMED")
            else: 
                comm.notify_signal.emit('DRONE DISARMED', 'positive')
                log("DISARMED")
        except Exception as e:
            log(f"Arm Error: {e}")
    else:
        comm.notify_signal.emit('Not Connected', 'negative')
