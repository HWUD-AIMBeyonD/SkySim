#!/usr/bin/env python3
import logging
import time
import curses  # Built-in library for terminal control

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.positioning.motion_commander import MotionCommander
from cflib.utils import uri_helper

URI = 'radio://0/80/2M/E7E7E7E7EA'

# Only output errors from the logging framework
logging.basicConfig(level=logging.ERROR)

# Define the control speeds
VELOCITY = 0.3  # m/s
YAW_RATE = 45   # deg/s


def print_controls(stdscr):
    """Prints controls to the curses screen."""
    stdscr.clear()
    stdscr.addstr(0, 0, "--- Crazyflie Keyboard Control (curses) ---")
    stdscr.addstr(2, 0, " t = Takeoff           l = Land")
    stdscr.addstr(3, 0, " q = Land & Quit")
    stdscr.addstr(5, 0, "   --- Movement (while flying) ---")
    stdscr.addstr(6, 2, "      [w] (climb)")
    stdscr.addstr(7, 2, " [a] [s] [d] (yaw L/D, descend)")
    stdscr.addstr(9, 2, "      [↑] (forward)")
    stdscr.addstr(10, 2, " [←] [↓] [→] (left, back, right)")
    stdscr.addstr(12, 0, "----------------------------------")
    stdscr.addstr(14, 0, "STATUS:")
    stdscr.refresh()


def update_status(stdscr, message):
    """Updates the status line without flickering."""
    stdscr.move(14, 7)  # Move cursor to status line
    stdscr.clrtoeol()   # Clear from cursor to end of line
    stdscr.addstr(14, 7, " " + message)
    stdscr.refresh()


def main(stdscr):
    """Main function that is wrapped by curses."""
    # --- Curses Setup ---
    stdscr.nodelay(True)  # Don't block waiting for a key press
    stdscr.keypad(True)   # Enable arrow keys
    curses.cbreak()       # React to keys instantly (no Enter)
    curses.noecho()       # Don't echo keys to the screen

    print_controls(stdscr)
    update_status(stdscr, "Connecting to drone...")

    # --- Crazyflie Setup ---
    cflib.crtp.init_drivers()
    cf = Crazyflie(rw_cache='./cache')

    with SyncCrazyflie(URI, cf=cf) as scf:
        
        # --- ARM THE DRONE ---
        # (This is the fix you pointed out)
        update_status(stdscr, "Arming drone...")
        scf.cf.platform.send_arming_request(True)
        time.sleep(1.0) # Wait for the arming to complete
        # ---------------------

        mc = MotionCommander(scf)
        is_flying = False
        update_status(stdscr, "Armed! Press 't' to takeoff.")

        try:
            while True:
                # Get the last key pressed (or -1 if no key)
                key = stdscr.getch()

                # --- Takeoff/Land/Quit ---
                if key == ord('t') and not is_flying:
                    update_status(stdscr, "Taking off... (This will block)")
                    mc.take_off()  # <-- Uses the blocking method
                    is_flying = True
                    update_status(stdscr, "Flying! Use keys to move.")

                elif key == ord('l') and is_flying:
                    update_status(stdscr, "Landing... (This will block)")
                    mc.land()  # <-- Uses the blocking method
                    is_flying = False
                    update_status(stdscr, "Landed. Press 't' to fly again.")

                elif key == ord('q'):
                    if is_flying:
                        update_status(stdscr, "Landing and quitting...")
                        mc.land()
                    update_status(stdscr, "Exiting.")
                    time.sleep(0)
                    break

                # --- Motion (Only if flying) ---
                if is_flying:
                    vx, vy, vz, yaw_rate = 0.0, 0.0, 0.0, 0.0

                    if key == ord('w'):
                        vz = VELOCITY
                    elif key == ord('s'):
                        vz = -VELOCITY
                    elif key == ord('a'):
                        yaw_rate = YAW_RATE
                    elif key == ord('d'):
                        yaw_rate = -YAW_RATE
                    elif key == curses.KEY_UP:
                        vx = VELOCITY
                    elif key == curses.KEY_DOWN:
                        vx = -VELOCITY
                    elif key == curses.KEY_LEFT:
                        vy = VELOCITY  # Move left
                    elif key == curses.KEY_RIGHT:
                        vy = -VELOCITY # Move right

                    # --- Send the one and only motion command ---
                    mc.start_linear_motion(vx, vy, vz, yaw_rate=yaw_rate)

                # Loop at ~20Hz
                time.sleep(0.05)

        except Exception as e:
            # Log errors if they happen
            logging.error(f"Error in main loop: {e}")
        
        finally:
            # This ensures we land if the loop breaks
            if is_flying:
                mc.land()


if __name__ == '__main__':
    # curses.wrapper handles all terminal setup and,
    # crucially, restores it to normal on exit/crash
    curses.wrapper(main)