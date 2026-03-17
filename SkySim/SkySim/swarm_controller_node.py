import rclpy
import math
import os
import subprocess
from rclpy.node import Node
from geometry_msgs.msg import PoseArray, Twist
from nav_msgs.msg import Odometry
from std_srvs.srv import Trigger
from std_msgs.msg import Int32
import numpy as np

class SwarmControllerNode(Node):
    def __init__(self):
        super().__init__('swarm_controller_node')
        
        self.drone_names = ['crazyflie', 'crazyflie2', 'crazyflie3']
        
        self.current_poses = {name: None for name in self.drone_names}
        self.current_vels = {name: np.zeros(3) for name in self.drone_names} # Track velocities
        self.last_pose_time = {name: self.get_clock().now() for name in self.drone_names}
        self.goals = {name: None for name in self.drone_names}
        
        self.publishers_ = {}
        
        self.kp_pos = 1.0
        self.max_vel = 0.5
        
        self.declare_parameter('use_apf', True) # Default ON
        
        self.use_apf = self.get_parameter('use_apf').value
        
        self.min_dist = 0.8  # Increased safe distance
        self.repulsion_gain = 2.0 # Increased repulsive force
        self.sensing_range = 5.0 # Max distance to consider for repulsion

        for name in self.drone_names:
            self.create_subscription(
                Odometry,
                f'/{name}/odom',
                lambda msg, n=name: self.odom_callback(msg, n),
                10
            )
            
            self.publishers_[name] = self.create_publisher(
                Twist,
                f'/{name}/cmd_vel_teleop',
                10
            )

        self.create_subscription(
            PoseArray,
            '/swarm/desired_goals',
            self.goals_callback,
            10
        )
        
        self.spawn_sequence = []
        for x in range(-10, 10):
            for y in range(-10, 10):
                self.spawn_sequence.append((x, y))
        
        self.spawn_index = 0
        
        # Virtual Swarm Sizing
        self.active_count = 3 # Start with default 3
        self.create_subscription(Int32, '/swarm/set_active_count', self.set_active_count_callback, 10)

        self.srv = self.create_service(Trigger, 'add_drone', self.add_drone_callback)
        
        self.create_subscription(Int32, '/swarm/spawn_request', self.spawn_request_callback, 10)
        
        self.count_publisher = self.create_publisher(Int32, '/swarm/drone_count', 10)

        self.spawn_queue = 0
        self.spawn_timer = self.create_timer(0.5, self.spawn_timer_callback)

        self.timer = self.create_timer(0.05, self.control_loop)
        self.get_logger().info('Swarm Controller Node Started (Max Capacity: 400)')

    def set_active_count_callback(self, msg):
        self.active_count = msg.data
        self.get_logger().info(f"Active drone count set to: {self.active_count}")

    def spawn_request_callback(self, msg):
        count = msg.data
        self.get_logger().info(f"Received bulk spawn request for {count} drones. Added to queue.")
        self.spawn_queue += count

    def spawn_timer_callback(self):
        if self.spawn_queue > 0:
            self.spawn_drone_logic()
            self.spawn_queue -= 1
            
            # Auto-update active count if we spawn more
            total = len(self.drone_names)
            if total > self.active_count:
                self.active_count = total

    def spawn_drone_logic(self):
        if self.spawn_index >= len(self.spawn_sequence):
            self.get_logger().warn("No more spawn positions available.")
            return
        
        x_pos, y_pos = 0, 0
        while True:
            if self.spawn_index >= len(self.spawn_sequence):
                self.get_logger().warn("No more unique spawn positions.")
                return
            
            x_pos, y_pos = self.spawn_sequence[self.spawn_index]
            self.spawn_index += 1
            
            if (x_pos == 0 and y_pos == 0) or \
               (x_pos == 1 and y_pos == 0) or \
               (x_pos == -1 and y_pos == 0):
               continue
            else:
                break

        new_drone_name = f'crazyflie{len(self.drone_names) + 1}'
        
        gz_model_path = os.getenv('GZ_SIM_RESOURCE_PATH')
        if not gz_model_path:
             self.get_logger().error("GZ_SIM_RESOURCE_PATH not set.")
             return

        sdf_file_path = os.path.join(gz_model_path, 'crazyflie', 'model.sdf')
        if not os.path.exists(sdf_file_path):
            self.get_logger().error(f"SDF file not found at {sdf_file_path}")
            return

        meshes_path = os.path.abspath(os.path.join(gz_model_path, '..', '..', 'meshes'))
        
        try:
            with open(sdf_file_path, 'r') as f:
                sdf_content = f.read()
            
            sdf_content = sdf_content.replace('../../../meshes', meshes_path)
            sdf_content = sdf_content.replace('{{NAMESPACE}}', new_drone_name)
            
            cmd_spawn = [
                'ros2', 'run', 'ros_gz_sim', 'create',
                '-world', 'crazyflie_world',
                '-string', sdf_content,
                '-name', new_drone_name,
                '-x', str(x_pos),
                '-y', str(y_pos),
                '-z', '0.5'
            ]
            
            self.get_logger().info(f'Spawning {new_drone_name} at x={x_pos}, y={y_pos}...')
            subprocess.Popen(cmd_spawn)

            bridge_args = [
                f'/crazyflie{len(self.drone_names) + 1}/gazebo/command/twist@geometry_msgs/msg/Twist@gz.msgs.Twist',
                f'/model/crazyflie{len(self.drone_names) + 1}/odometry@nav_msgs/msg/Odometry@gz.msgs.Odometry',
                f'/model/crazyflie{len(self.drone_names) + 1}/lidar@sensor_msgs/msg/LaserScan@gz.msgs.LaserScan'
            ]
            
            cmd_bridge = [
                'ros2', 'run', 'ros_gz_bridge', 'parameter_bridge'
            ] + bridge_args + [
                '--ros-args',
                '-r', f'/crazyflie{len(self.drone_names) + 1}/gazebo/command/twist:=/{new_drone_name}/cmd_vel',
                '-r', f'/model/crazyflie{len(self.drone_names) + 1}/odometry:=/{new_drone_name}/odom',
                '-r', f'/model/crazyflie{len(self.drone_names) + 1}/lidar:=/{new_drone_name}/scan'
            ]

            subprocess.Popen(cmd_bridge)
            
            cmd_control = [
                'ros2', 'run', 'SkySim', 'control_services',
                '--ros-args',
                '-p', f'robot_prefix:=/{new_drone_name}',
                '-r', f'/cmd_vel:=/{new_drone_name}/cmd_vel_teleop'
            ]
            
            subprocess.Popen(cmd_control)
            
            self.drone_names.append(new_drone_name)
            self.current_poses[new_drone_name] = None
            self.goals[new_drone_name] = None
            
            self.create_subscription(
                Odometry,
                f'/{new_drone_name}/odom',
                lambda msg, n=new_drone_name: self.odom_callback(msg, n),
                10
            )
            
            self.publishers_[new_drone_name] = self.create_publisher(
                Twist,
                f'/{new_drone_name}/cmd_vel_teleop',
                10
            )
            
        except Exception as e:
            self.get_logger().error(f"Failed to add drone: {str(e)}")

    def add_drone_callback(self, request, response):
        self.spawn_drone_logic()
        response.success = True
        response.message = "Drone added via service."
        return response

    def odom_callback(self, msg, drone_name):
        self.current_poses[drone_name] = msg.pose.pose
        # Store velocity
        v = msg.twist.twist.linear
        self.current_vels[drone_name] = np.array([v.x, v.y, v.z])

    def goals_callback(self, msg):
        for i, pose in enumerate(msg.poses):
            if i < len(self.drone_names):
                self.goals[self.drone_names[i]] = pose
        self.get_logger().info(f'Received {len(msg.poses)} new goals')

    def control_loop(self):
        try:
            self.use_apf = self.get_parameter('use_apf').value
        except Exception:
            pass

        total_drones = len(self.drone_names)
        effective_count = min(total_drones, self.active_count)
        
        count_msg = Int32()
        count_msg.data = effective_count
        self.count_publisher.publish(count_msg)

        def clamp(val, limit):
            return max(min(val, limit), -limit)

        for i, name in enumerate(self.drone_names):
            # If drone is outside active set, stop it and skip logic
            if i >= effective_count:
                stop_cmd = Twist()
                self.publishers_[name].publish(stop_cmd)
                continue

            current_pose = self.current_poses[name]
            goal_pose = self.goals[name]
            
            if current_pose is None or goal_pose is None:
                continue
            
            # Calculate Preferred Velocity (Goal Seeking)
            attr_x = (goal_pose.position.x - current_pose.position.x) * self.kp_pos
            attr_y = (goal_pose.position.y - current_pose.position.y) * self.kp_pos
            attr_z = (goal_pose.position.z - current_pose.position.z) * self.kp_pos
            
            # Clamp preferred velocity magnitude to max_vel
            pref_vel = np.array([attr_x, attr_y, attr_z])
            speed = np.linalg.norm(pref_vel)
            if speed > self.max_vel:
                pref_vel = (pref_vel / speed) * self.max_vel
            
            final_vx, final_vy, final_vz = pref_vel[0], pref_vel[1], pref_vel[2]

            # APF Logic: Only consider repulsion from other ACTIVE drones
            if self.use_apf:
                rep_x, rep_y, rep_z = 0.0, 0.0, 0.0
                for j, other_name in enumerate(self.drone_names):
                    if i == j: continue
                    if j >= effective_count: continue # Ignore inactive drones in APF
                    
                    other_pose = self.current_poses[other_name]
                    if other_pose is None: continue
                    
                    dx = current_pose.position.x - other_pose.position.x
                    dy = current_pose.position.y - other_pose.position.y
                    dz = current_pose.position.z - other_pose.position.z
                    dist = math.sqrt(dx*dx + dy*dy + dz*dz)
                    
                    if dist < self.min_dist and dist > 0.01:
                        scale = self.repulsion_gain * (self.min_dist - dist) / dist
                        rep_x += dx * scale
                        rep_y += dy * scale
                        rep_z += dz * scale
                
                total_vx = attr_x + rep_x
                total_vy = attr_y + rep_y
                total_vz = attr_z + rep_z

                total_speed = math.sqrt(total_vx**2 + total_vy**2 + total_vz**2)
                if total_speed > self.max_vel:
                    scale_factor = self.max_vel / total_speed
                    final_vx = total_vx * scale_factor
                    final_vy = total_vy * scale_factor
                    final_vz = total_vz * scale_factor
                else:
                    final_vx = total_vx
                    final_vy = total_vy
                    final_vz = total_vz

            cmd = Twist()
            cmd.linear.x = float(final_vx)
            cmd.linear.y = float(final_vy)
            cmd.linear.z = float(final_vz)
            cmd.angular.z = 0.0
            
            self.publishers_[name].publish(cmd)

def main(args=None):
    rclpy.init(args=args)
    node = SwarmControllerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()