#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from std_msgs.msg import Int32
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import numpy as np
import os
import argparse
import time

class CaptureAndPlot(Node):
    def __init__(self, run_idx, scenario, output_dir):
        super().__init__('capture_and_plot')
        
        self.run_idx = run_idx
        self.scenario = scenario
        self.output_dir = output_dir
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        self.drone_count = 0
        self.drone_positions = {} # {name: [x, y, z]}
        self.tracked_drones = set()
        self.subscriptions_ = []
        
        # History for distance plot
        # list of (time_offset, min_distance)
        self.history_min_dists = [] 
        self.start_time = None

        self.create_subscription(
            Int32,
            '/swarm/drone_count',
            self.drone_count_callback,
            10
        )
        
        # Timer for recording distances (10 Hz)
        self.create_timer(0.1, self.record_distances)
            
        self.get_logger().info(f'Capture Node Started. Run={run_idx}, Scenario={scenario}')
        self.get_logger().info('Waiting for drone positions...')

    def drone_count_callback(self, msg):
        self.drone_count = msg.data
        if self.start_time is None:
            self.start_time = time.time()
            self.get_logger().info(f"Received drone count {self.drone_count}. Recording started.")
        
        target_names = []
        if self.drone_count >= 1:
            target_names.append('crazyflie')
        for i in range(2, self.drone_count + 1):
            target_names.append(f'crazyflie{i}')
            
        for name in target_names:
            if name not in self.tracked_drones:
                self.get_logger().info(f'Tracking {name}')
                self.subscriptions_.append(
                    self.create_subscription(
                        Odometry,
                        f'/{name}/odom',
                        lambda msg, n=name: self.odom_callback(msg, n),
                        10
                    )
                )
                self.tracked_drones.add(name)

    def odom_callback(self, msg, name):
        pos = msg.pose.pose.position
        self.drone_positions[name] = [pos.x, pos.y, pos.z]

    def record_distances(self):
        # We need at least 2 drones to calculate a distance
        if len(self.drone_positions) < 2:
            return

        current_positions = list(self.drone_positions.values())
        # Convert to numpy array for fast dist calculation
        coords = np.array(current_positions) # (N, 3)
        
        # Compute pairwise distances
        # We want min distance between any pair
        min_dist = float('inf')
        
        diff = coords[:, np.newaxis, :] - coords[np.newaxis, :, :]
        # diff is (N, N, 3)
        dists = np.sqrt(np.sum(diff**2, axis=-1))
        # dists is (N, N) matrix of distances
        
        # Mask diagonal (dist to self is 0)
        np.fill_diagonal(dists, np.inf)
        
        current_min = np.min(dists)
        
        if self.start_time is not None:
            t = time.time() - self.start_time
            self.history_min_dists.append((t, current_min))

    def save_snapshot(self, run_idx, size, scenario):
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        
        active_names = []
        if self.drone_count >= 1: active_names.append('crazyflie')
        for i in range(2, self.drone_count + 1): active_names.append(f'crazyflie{i}')
        
        xs, ys, zs = [], [], []
        for n in active_names:
            if n in self.drone_positions:
                p = self.drone_positions[n]
                xs.append(p[0])
                ys.append(p[1])
                zs.append(p[2])
                
        ax.scatter(xs, ys, zs, c='b', marker='o')
        ax.set_title(f"Run {run_idx} | N={size} | {scenario}")
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')
        
        # Set equal limits roughly
        ax.set_xlim(-5, 5)
        ax.set_ylim(-5, 5)
        ax.set_zlim(0, 5)
        
        path = os.path.join(self.output_dir, f"snapshot_Run{run_idx}_N{size}_{scenario}.png")
        plt.savefig(path)
        plt.close(fig)
        self.get_logger().info(f"Snapshot saved to {path}")

    def save_distance_plot(self):
        if not self.history_min_dists:
            self.get_logger().warn("No distance data to plot.")
            return

        times = [p[0] for p in self.history_min_dists]
        dists = [p[1] for p in self.history_min_dists]
        
        plt.figure(figsize=(10, 6))
        plt.plot(times, dists, label='Min Inter-Agent Distance', color='blue')
        plt.axhline(y=0.8, color='r', linestyle='--', label='Safety Limit (0.8m)')
        
        plt.title(f"Minimum Inter-Agent Distance vs Time (N={self.drone_count}, {self.scenario})")
        plt.xlabel("Time (s)")
        plt.ylabel("Distance (m)")
        plt.legend()
        plt.grid(True)
        plt.ylim(0, max(max(dists)*1.1, 2.0)) # Auto scale Y but include 0
        
        path = os.path.join(self.output_dir, f"distance_Run{self.run_idx}_N{self.drone_count}_{self.scenario}.png")
        plt.savefig(path)
        plt.close()
        self.get_logger().info(f"Distance plot saved to {path}")

def main():
    parser = argparse.ArgumentParser(description='Capture drone positions and plot.')
    parser.add_argument('--run', type=int, default=1, help='Run index')
    parser.add_argument('--scenario', type=str, default='Live', help='Scenario name')
    parser.add_argument('--out', type=str, default='./experiment_results', help='Output directory')
    
    args = parser.parse_args()
    
    rclpy.init()
    node = CaptureAndPlot(args.run, args.scenario, args.out)
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Stopping recording...")
        # Save plots on exit
        node.save_snapshot(node.run_idx, node.drone_count, node.scenario)
        node.save_distance_plot()
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
