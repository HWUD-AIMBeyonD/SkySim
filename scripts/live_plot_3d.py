#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from std_msgs.msg import Int32
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.animation import FuncAnimation
import threading
import numpy as np

MAX_TRAJECTORY_POINTS = 100 # Maximum number of historical points to keep for each drone's trajectory

class LivePlotter(Node):
    def __init__(self):
        super().__init__('live_plot_3d_node')
        
        self.drone_positions = {} # {name: [x, y, z]}
        self.drone_trajectories = {} # {name: [[x1,y1,z1], [x2,y2,z2], ...]}
        self.tracked_drones = set()
        self.drone_count = 0
        
        # ROS subscriptions management
        self.subs = []
        
        self.create_subscription(
            Int32,
            '/swarm/drone_count',
            self.drone_count_callback,
            10
        )
        
        self.get_logger().info("Live 3D Plotter Node Started. Waiting for drones...")

    def drone_count_callback(self, msg):
        count = msg.data
        if count == self.drone_count:
            return
            
        self.drone_count = count
        
        target_names = []
        if count >= 1:
            target_names.append('crazyflie')
        for i in range(2, count + 1):
            target_names.append(f'crazyflie{i}')
            
        for name in target_names:
            if name not in self.tracked_drones:
                self.get_logger().info(f"Tracking {name}")
                self.tracked_drones.add(name)
                self.drone_positions[name] = [0.0, 0.0, 0.0] # Init current position
                self.drone_trajectories[name] = [] # Init empty trajectory list
                
                # Dynamic subscription
                self.subs.append(
                    self.create_subscription(
                        Odometry,
                        f'/{name}/odom',
                        lambda msg, n=name: self.odom_callback(msg, n),
                        10
                    )
                )

    def odom_callback(self, msg, name):
        pos = msg.pose.pose.position
        current_pos = [pos.x, pos.y, pos.z]
        self.drone_positions[name] = current_pos
        
        # Add to trajectory, keeping max N points
        self.drone_trajectories[name].append(current_pos)
        if len(self.drone_trajectories[name]) > MAX_TRAJECTORY_POINTS:
            self.drone_trajectories[name].pop(0) # Remove oldest point

# Global node reference for the animation callback
node = None
ax = None # Define ax globally for update_plot to access

def update_plot(frame):
    if node is None or ax is None: return
    
    ax.clear() # Clear the previous frame
    
    ax.set_title(f"Live Swarm Positions & Trajectories (N={node.drone_count})")
    ax.set_xlabel('X (m)')
    ax.set_ylabel('Y (m)')
    ax.set_zlabel('Z (m)')
    
    # Set fixed limits to make motion visible
    ax.set_xlim(-5, 5)
    ax.set_ylim(-5, 5)
    ax.set_zlim(0, 5)
    
    # Draw "floor" grid for reference
    ax.plot([-5, 5], [0, 0], [0, 0], 'k-', lw=0.5, alpha=0.3)
    ax.plot([0, 0], [-5, 5], [0, 0], 'k-', lw=0.5, alpha=0.3)

    # Plot current positions (scatter) and trajectories (lines)
    for name, current_pos in node.drone_positions.items():
        if name in node.drone_trajectories and node.drone_trajectories[name]:
            # Plot trajectory line
            trajectory = np.array(node.drone_trajectories[name])
            ax.plot(trajectory[:,0], trajectory[:,1], trajectory[:,2], linestyle='-', linewidth=1, alpha=0.7, label=f'Trace {name}')
            
            # Plot current position as a larger dot
            ax.scatter(current_pos[0], current_pos[1], current_pos[2], marker='o', s=50, label=f'{name}')

def spin_ros(n):
    rclpy.spin(n)

def main():
    global node, ax
    
    rclpy.init()
    node = LivePlotter()
    
    # Run ROS spin in a separate thread so it doesn't block the GUI/Plot
    ros_thread = threading.Thread(target=spin_ros, args=(node,), daemon=True)
    ros_thread.start()
    
    # Setup Matplotlib
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')
    
    # Animation: 100ms interval = 10 FPS
    ani = FuncAnimation(fig, update_plot, interval=100)
    
    try:
        plt.show()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
