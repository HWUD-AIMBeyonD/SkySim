import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Point
from std_msgs.msg import String

class TranslatorNode(Node):
    def __init__(self):
        super().__init__('translator_node')
        
        self.positions = {
            'crazyflie': [0.0, 0.0, 0.0],
            'crazyflie2': [0.0, 0.0, 0.0],
            'crazyflie3': [0.0, 0.0, 0.0]
        }
        
        self.display_names = {
            'crazyflie': 'Drone 1',
            'crazyflie2': 'Drone 2',
            'crazyflie3': 'Drone 3'
        }

        for name in self.positions.keys():
            self.create_subscription(
                Point,
                f'/{name}/position',
                lambda msg, n=name: self.position_callback(msg, n),
                10
            )

        self.create_subscription(
            String,
            '/skyscript/user_command',
            self.command_callback,
            10
        )

        self.prompt_publisher = self.create_publisher(
            String,
            '/skyscript/llm_prompt',
            10
        )
        
        self.get_logger().info('Translator Node Started. Waiting for /skyscript/user_command...')

    def position_callback(self, msg, drone_name):
        self.positions[drone_name] = [msg.x, msg.y, msg.z]

    def command_callback(self, msg):
        user_command = msg.data
        
        prompt_lines = ["Current State:"]
        
        ordered_keys = ['crazyflie', 'crazyflie2', 'crazyflie3']
        
        for key in ordered_keys:
            pos = self.positions[key]
            display_name = self.display_names[key]
            pos_str = f"[{pos[0]}, {pos[1]}, {pos[2]}]"
            prompt_lines.append(f"- {display_name}: {pos_str}")
            
        prompt_lines.append(f"User Command: {user_command}")
        
        full_prompt = "\n".join(prompt_lines)
        
        prompt_msg = String()
        prompt_msg.data = full_prompt
        self.prompt_publisher.publish(prompt_msg)
        
        self.get_logger().info(f"Generated Prompt:\n{full_prompt}")

def main(args=None):
    rclpy.init(args=args)
    node = TranslatorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
