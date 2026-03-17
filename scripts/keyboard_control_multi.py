#!/usr/bin/env python3
import sys
import select
import termios
import tty
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

msg = """
Control Your Drones!
---------------------------
Select Drone:
   1: crazyflie
   2: crazyflie2
   3: crazyflie3

Moving around:
        w
   a    s    d

   arrow up   : lift (+z)
   arrow down : lower (-z)

   t : takeoff (lift to default height)
   l : land (drop to ground)

space key, k : force stop
CTRL-C to quit
"""

moveBindings = {
    'w': (1, 0, 0, 0),
    's': (-1, 0, 0, 0),
    'a': (0, 1, 0, 0),
    'd': (0, -1, 0, 0),
    '\x1b[A': (0, 0, 1, 0),  # Arrow Up
    '\x1b[B': (0, 0, -1, 0), # Arrow Down
    't': (0, 0, 1, 0), # Takeoff
    'l': (0, 0, -1, 0), # Land
}

drone_map = {
    '1': '/crazyflie/cmd_vel_teleop',
    '2': '/crazyflie2/cmd_vel_teleop',
    '3': '/crazyflie3/cmd_vel_teleop',
}

def getKey(settings):
    tty.setraw(sys.stdin.fileno())
    rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
    if rlist:
        key = sys.stdin.read(1)
        if key == '\x1b':
            key += sys.stdin.read(2)
    else:
        key = ''
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
    return key

class MultiDroneKeyboardControl(Node):
    def __init__(self):
        super().__init__('multi_drone_keyboard_control')
        
        self.pubs = {
            '1': self.create_publisher(Twist, drone_map['1'], 10),
            '2': self.create_publisher(Twist, drone_map['2'], 10),
            '3': self.create_publisher(Twist, drone_map['3'], 10),
        }
        
        self.active_drone = '1'
        self.print_status()

    def print_status(self):
        print(f"\rCurrent Drone: {self.active_drone} ({drone_map[self.active_drone]})")

    def publish_twist(self, x, y, z, th):
        twist = Twist()
        twist.linear.x = x * 0.5
        twist.linear.y = y * 0.5
        twist.linear.z = z * 0.5
        twist.angular.x = 0.0
        twist.angular.y = 0.0
        twist.angular.z = th * 0.5
        self.pubs[self.active_drone].publish(twist)

def main():
    settings = termios.tcgetattr(sys.stdin)

    rclpy.init()
    node = MultiDroneKeyboardControl()

    x = 0
    y = 0
    z = 0
    th = 0
    status = 0

    print(msg)
    
    try:
        while True:
            key = getKey(settings)
            
            if key in ['1', '2', '3']:
                node.active_drone = key
                node.print_status()
                x, y, z, th = 0, 0, 0, 0
                continue
            
            if key in moveBindings.keys():
                x = moveBindings[key][0]
                y = moveBindings[key][1]
                z = moveBindings[key][2]
                th = moveBindings[key][3]
                
                if key == 't':
                   z = 1.0
                elif key == 'l':
                   z = -1.0 

            elif key == ' ' or key == 'k':
                x = 0
                y = 0
                z = 0
                th = 0
            elif key == '\x03':
                break

            node.publish_twist(x, y, z, th)
            
            if key == '':
                x, y, z, th = 0, 0, 0, 0
                node.publish_twist(0.0, 0.0, 0.0, 0.0)

    except Exception as e:
        print(e)

    finally:
        twist = Twist()
        twist.linear.x = 0.0; twist.linear.y = 0.0; twist.linear.z = 0.0
        twist.angular.x = 0.0; twist.angular.y = 0.0; twist.angular.z = 0.0
        for pub in node.pubs.values():
            pub.publish(twist)

        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
