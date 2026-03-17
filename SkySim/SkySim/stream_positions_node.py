import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Point
from std_msgs.msg import Int32

class StreamPositionsNode(Node):
    def __init__(self):
        super().__init__('stream_positions_node')
        
        self.tracked_drones = set()
        self.publishers_ = {}
        self.subscriptions_ = []

        self.create_subscription(
            Int32,
            '/swarm/drone_count',
            self.drone_count_callback,
            10
        )
            
        self.get_logger().info('Stream Positions Node Started')

    def drone_count_callback(self, msg):
        count = msg.data
        
        target_names = []
        if count >= 1:
            target_names.append('crazyflie')
        for i in range(2, count + 1):
            target_names.append(f'crazyflie{i}')
            
        for name in target_names:
            if name not in self.tracked_drones:
                self.get_logger().info(f'Adding stream for {name}')
                
                # Create sub/pub
                self.subscriptions_.append(
                    self.create_subscription(
                        Odometry,
                        f'/{name}/odom',
                        lambda msg, n=name: self.odom_callback(msg, n),
                        10
                    )
                )
                
                self.publishers_[name] = self.create_publisher(
                    Point,
                    f'/{name}/position',
                    10
                )
                
                self.tracked_drones.add(name)

    def _round_and_threshold(self, value, threshold=1e-3, decimals=3):
        if abs(value) < threshold:
            return 0.0
        return round(value, decimals)

    def odom_callback(self, msg, output_name):
        position = msg.pose.pose.position
        
        point_msg = Point()
        point_msg.x = self._round_and_threshold(position.x)
        point_msg.y = self._round_and_threshold(position.y)
        point_msg.z = self._round_and_threshold(position.z)
        
        self.publishers_[output_name].publish(point_msg)

def main(args=None):
    rclpy.init(args=args)
    node = StreamPositionsNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
