import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Int32, Float32
from geometry_msgs.msg import PoseArray, Pose
from nav_msgs.msg import Odometry
import os
import sys
import math
import time
import csv
from datetime import datetime

from .LLMs.gemini_client import GeminiClient

LATENCY_LOG_FILE = os.path.join(os.getcwd(), 'experiment_results', 'llm_latency_log.csv')
VELOCITY_LOG_FILE = os.path.join(os.getcwd(), 'experiment_results', 'velocity_log.csv')

class LLMPlannerNode(Node):
    def __init__(self):
        super().__init__('llm_planner_node')

        self.num_drones = 3
        self.current_positions = {}
        self.tracked_drones = set()
        self.odom_subs = []
        
        # Velocity logging state
        self.maneuver_start_time = None
        self.current_maneuver_id = None
        self.velocity_buffer = []
        self.last_flush_time = time.time()
        
        self.current_goals = {}
        self.goal_tolerance = 0.1
        
        self.goals_publisher = self.create_publisher(PoseArray, '/swarm/desired_goals', 10)
        self.latency_publisher = self.create_publisher(Float32, '/skysim/llm_latency', 10)

        self.subscription_prompt = self.create_subscription(
            String,
            '/skysim/llm_prompt',
            self.prompt_callback,
            10
        )


        self.subscription_test_command = self.create_subscription(
            String,
            '/skysim/test_command',
            self.test_command_callback,
            10
        )
        
        self.subscription_count = self.create_subscription(
            Int32,
            '/swarm/drone_count',
            self.drone_count_callback,
            10
        )

        self.llm_client = GeminiClient(logger=self.get_logger())
        if self.llm_client.client:
            self.get_logger().info("Gemini Client Initialized Successfully.")
        else:
            self.get_logger().warn("Gemini Client initialized without API Key. LLM features will be disabled.")

        self.get_logger().info('LLM Planner Node has started. Waiting for prompts on /skysim/llm_prompt and /skysim/test_command')

        # Ensure log directory exists
        os.makedirs(os.path.dirname(LATENCY_LOG_FILE), exist_ok=True)
        # Initialize CSV header if file doesn't exist
        if not os.path.exists(LATENCY_LOG_FILE):
            with open(LATENCY_LOG_FILE, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['timestamp', 'prompt', 'latency_seconds', 'num_drones'])

        # Initialize Velocity CSV header
        if not os.path.exists(VELOCITY_LOG_FILE):
            with open(VELOCITY_LOG_FILE, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['maneuver_id', 'time_since_start', 'drone_name', 'velocity_magnitude'])

    def drone_count_callback(self, msg):
        if self.num_drones != msg.data:
            self.get_logger().info(f'Drone count updated: {msg.data}')
            self.num_drones = msg.data
            
        target_names = []
        if self.num_drones >= 1:
            target_names.append('crazyflie')
        for i in range(2, self.num_drones + 1):
            target_names.append(f'crazyflie{i}')
            
        for name in target_names:
            if name not in self.tracked_drones:
                self.get_logger().info(f'LLM Planner tracking {name}')
                sub = self.create_subscription(
                    Odometry,
                    f'/{name}/odom',
                    lambda msg, n=name: self.odom_callback(msg, n),
                    10
                )
                self.odom_subs.append(sub)
                self.tracked_drones.add(name)

    def check_goals_reached(self):
        if not self.current_goals:
            return False
            
        active_drones_checked = 0
        reached_count = 0
        
        # Determine active drone names
        target_names = []
        if self.num_drones >= 1:
            target_names.append('crazyflie')
        for i in range(2, self.num_drones + 1):
            target_names.append(f'crazyflie{i}')
            
        for name in target_names:
            if name in self.current_positions and name in self.current_goals:
                active_drones_checked += 1
                curr = self.current_positions[name]
                goal = self.current_goals[name]
                
                dist = math.sqrt(
                    (curr[0] - goal[0])**2 + 
                    (curr[1] - goal[1])**2 + 
                    (curr[2] - goal[2])**2
                )
                
                if dist < self.goal_tolerance:
                    reached_count += 1
        
        if active_drones_checked > 0 and reached_count == active_drones_checked:
            return True
        return False

    def odom_callback(self, msg, name):
        pos = msg.pose.pose.position
        self.current_positions[name] = [pos.x, pos.y, pos.z]
        
        # Velocity logging
        if self.maneuver_start_time is not None:
            now = self.get_clock().now()
            elapsed = (now - self.maneuver_start_time).nanoseconds / 1e9
            
            # Check if all drones reached goals
            if self.check_goals_reached():
                 self.maneuver_start_time = None
                 self.flush_velocity_buffer()
                 self.get_logger().info(f"Maneuver completed (All goals reached) in {elapsed:.2f}s.")
                 return

            # Stop logging after 60 seconds (safety timeout)
            if elapsed > 60.0:
                self.maneuver_start_time = None
                self.flush_velocity_buffer()
                self.get_logger().info("Maneuver logging timeout (60s).")
                return

            vel = msg.twist.twist.linear
            speed = math.sqrt(vel.x**2 + vel.y**2 + vel.z**2)
            
            self.velocity_buffer.append([self.current_maneuver_id, f"{elapsed:.4f}", name, f"{speed:.4f}"])
            
            # Flush buffer every 1 second approx (assuming 50Hz * 3 drones = 150 calls/sec -> buffer 150)
            if len(self.velocity_buffer) >= 50:
                self.flush_velocity_buffer()

    def flush_velocity_buffer(self):
        if not self.velocity_buffer:
            return
        try:
            with open(VELOCITY_LOG_FILE, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(self.velocity_buffer)
            self.velocity_buffer = []
        except Exception as e:
            self.get_logger().error(f"Failed to log velocity: {e}")

    def prompt_callback(self, msg):
        self.get_logger().info("Callback TRIGGERED. Processing new prompt...")
        
        user_command = msg.data
        self.get_logger().info(f"Incoming Prompt: '{user_command}'")

        if not self.llm_client.client:
            self.get_logger().error("LLM Client not ready (missing API Key). Falling back to safe hover.")
            self.generate_safe_hover_formation()
            return

        self.get_logger().info("Sending request to Gemini Client...")
        
        relevant_positions = []
        ordered_names = ['crazyflie'] + [f'crazyflie{i}' for i in range(2, self.num_drones + 1)]
        
        current_pos_list = []
        for name in ordered_names:
            if name in self.current_positions:
                current_pos_list.append(self.current_positions[name])
            else:
                current_pos_list.append([0.0, 0.0, 0.0])

        start_time = time.time()
        waypoints = self.llm_client.generate_waypoints(
            user_prompt=user_command,
            num_drones=self.num_drones,
            current_positions=current_pos_list
        )
        end_time = time.time()
        
        latency = end_time - start_time
        self.latency_publisher.publish(Float32(data=latency))

        # Log to CSV
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(LATENCY_LOG_FILE, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([timestamp, user_command, f"{latency:.4f}", self.num_drones])
            self.get_logger().info(f"Logged latency: {latency:.4f}s for prompt: '{user_command}'")
        except Exception as e:
            self.get_logger().error(f"Failed to log latency: {e}")

        if waypoints:
            self.get_logger().info(f"Received Waypoints: {waypoints}")
            if self.validate_waypoints(waypoints):
                self.publish_goals_from_list(waypoints)
            else:
                self.get_logger().error("Waypoints violate safety bounds! Holding current positions.")
                self.hold_current_positions()
        else:
            self.get_logger().error("Failed to generate valid waypoints. Holding current positions.")
            self.hold_current_positions()

    def hold_current_positions(self):
        self.get_logger().info("Holding current positions...")
        goals = PoseArray()
        goals.header.stamp = self.get_clock().now().to_msg()
        goals.header.frame_id = "world"
        
        ordered_names = ['crazyflie'] + [f'crazyflie{i}' for i in range(2, self.num_drones + 1)]
        
        for name in ordered_names:
            p = Pose()
            if name in self.current_positions:
                pos = self.current_positions[name]
                p.position.x = float(pos[0])
                p.position.y = float(pos[1])
                p.position.z = float(pos[2])
            else:
                p.position.z = 0.5 # Default safe height if unknown
            goals.poses.append(p)

        self.goals_publisher.publish(goals)

    def validate_waypoints(self, waypoints):
        # Safety Bounds
        MIN_XY, MAX_XY = -10.0, 10.0
        MIN_Z, MAX_Z = 0.2, 10.0
        
        for p in waypoints:
            x, y, z = p[0], p[1], p[2]
            if not (MIN_XY <= x <= MAX_XY): return False
            if not (MIN_XY <= y <= MAX_XY): return False
            if not (MIN_Z <= z <= MAX_Z): return False
        return True

    def publish_goals_from_list(self, coords_list):
        goals = PoseArray()
        goals.header.stamp = self.get_clock().now().to_msg()
        goals.header.frame_id = "world"
        
        # Reset current goals
        self.current_goals = {}
        target_names = []
        if self.num_drones >= 1:
            target_names.append('crazyflie')
        for i in range(2, self.num_drones + 1):
            target_names.append(f'crazyflie{i}')

        for i, coord in enumerate(coords_list):
            if i < len(target_names):
                self.current_goals[target_names[i]] = coord

            pose = Pose()
            pose.position.x = float(coord[0])
            pose.position.y = float(coord[1])
            pose.position.z = float(coord[2])
            goals.poses.append(pose)

        self.goals_publisher.publish(goals)
        self.get_logger().info("Successfully published new swarm goals.")
        
        # Start velocity logging
        self.maneuver_start_time = self.get_clock().now()
        # Use a simplified timestamp ID for the maneuver
        self.current_maneuver_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.velocity_buffer = [] # Clear old buffer
        self.get_logger().info(f"Started logging velocity for maneuver: {self.current_maneuver_id}")

    def test_command_callback(self, msg):
        command = msg.data.lower()
        self.get_logger().info(f'Received test command: "{command}"')

        if "triangle" in command:
            self.generate_triangle_formation()
        elif "unsafe" in command:
            self.generate_unsafe_formation()
        elif "safe_hover" in command:
            self.generate_safe_hover_formation()
        else:
            self.get_logger().warn('Unknown test command. Understands "triangle", "unsafe", or "safe_hover".')

    def generate_triangle_formation(self):
        self.get_logger().info(f'Generating TRIANGLE formation plan for {self.num_drones} drones...')
        
        h = 1.5 * math.sqrt(3) / 2
        p1 = [1.5, 0.0, 2.0]
        p2 = [-0.75, 1.3, 2.0]
        p3 = [-0.75, -1.3, 2.0]
        
        all_positions = [p1, p2, p3]
        
        current_edges = [(0, 1), (1, 2), (2, 0)]
                
        temp_edges_queue = list(current_edges)
        next_level_edges = []
        
        while len(all_positions) < self.num_drones:
            if not temp_edges_queue:
                temp_edges_queue = next_level_edges
                next_level_edges = []
                if not temp_edges_queue:
                     break
            
            idx_a, idx_b = temp_edges_queue.pop(0)
            
            pos_a = all_positions[idx_a]
            pos_b = all_positions[idx_b]
            
            mid_x = (pos_a[0] + pos_b[0]) / 2.0
            mid_y = (pos_a[1] + pos_b[1]) / 2.0
            mid_z = (pos_a[2] + pos_b[2]) / 2.0
            
            new_pos = [mid_x, mid_y, mid_z]
            
            new_idx = len(all_positions)
            all_positions.append(new_pos)
            
            next_level_edges.append((idx_a, new_idx))
            next_level_edges.append((new_idx, idx_b))
            
        target_positions = all_positions[:self.num_drones]
        
        goals = PoseArray()
        goals.header.stamp = self.get_clock().now().to_msg()
        goals.header.frame_id = "world"
        
        for pos in target_positions:
            p = Pose()
            p.position.x = float(pos[0])
            p.position.y = float(pos[1])
            p.position.z = float(pos[2])
            goals.poses.append(p)

        self.goals_publisher.publish(goals)
        self.get_logger().info(f'Published {len(goals.poses)} triangle waypoints.')

    def generate_unsafe_formation(self):
        self.get_logger().info(f'Generating UNSAFE formation plan for {self.num_drones} drones...')
        
        goals = PoseArray()
        goals.header.stamp = self.get_clock().now().to_msg()
        goals.header.frame_id = "world"
        
        for i in range(self.num_drones):
            p = Pose()
            p.position.x = i * 0.05
            p.position.y = 0.0
            p.position.z = 1.0
            goals.poses.append(p)

        self.goals_publisher.publish(goals)
        self.get_logger().info(f'Published {len(goals.poses)} UNSAFE test waypoints.')

    def generate_safe_hover_formation(self):
        self.get_logger().info('Generating SAFE HOVER (return to spawn) plan...')
        
        goals = PoseArray()
        goals.header.stamp = self.get_clock().now().to_msg()
        goals.header.frame_id = "world"
        
        spawn_sequence = [x for x in range(2, 11)] + [x for x in range(-10, -1)]
        
        for i in range(1, self.num_drones + 1):
            p = Pose()
            p.position.y = 0.0
            p.position.z = 1.0
            
            if i == 1:
                p.position.x = 0.0
            elif i == 2:
                p.position.x = 1.0
            elif i == 3:
                p.position.x = -1.0
            else:
                seq_idx = i - 4
                if seq_idx < len(spawn_sequence):
                    p.position.x = float(spawn_sequence[seq_idx])
                else:
                    p.position.x = 0.0
            
            goals.poses.append(p)

        self.goals_publisher.publish(goals)
        self.get_logger().info(f'Published {len(goals.poses)} safe hover (return to spawn) waypoints.')

def main(args=None):
    rclpy.init(args=args)
    node = LLMPlannerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
