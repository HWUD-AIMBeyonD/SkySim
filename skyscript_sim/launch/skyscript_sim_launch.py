import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    pkg_ros_gz_sim = get_package_share_directory('ros_gz_sim')
    pkg_skyscript_sim = get_package_share_directory('skyscript_sim')

    gz_model_path = os.getenv('GZ_SIM_RESOURCE_PATH')

    if gz_model_path is None:
        print("="*80)
        print("ERROR: GZ_SIM_RESOURCE_PATH environment variable is not set.")
        print("Please set it before launching.")
        print("Example: export GZ_SIM_RESOURCE_PATH=/path/to/your/models")
        print("="*80)
        return LaunchDescription([])

    world_file = os.path.join(gz_model_path, 'worlds', 'crazyflie_world.sdf')
    gz_args_string = f"{world_file} -r"

    gz_ln_arg = DeclareLaunchArgument(
        'gazebo_launch',
        default_value='True',
        description='Set to "False" to disable Gazebo launch'
    )
    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')
        ),
        
        # This is the *correct* way to use the conditional
        condition=IfCondition(LaunchConfiguration('gazebo_launch')),
        
        launch_arguments={'gz_args': gz_args_string}.items(),
    )

    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=['--ros-args', '-p', f'config_file:={os.path.join(pkg_skyscript_sim, "config", "ros_gz_crazyflie_bridge.yaml")}'],
        output='screen'
    )

    control_services_1 = Node(
        package='skyscript_sim',
        executable='control_services',
        name='control_services_1',
        output='screen',
        parameters=[{'robot_prefix': '/crazyflie'}],
        remappings=[('/cmd_vel', '/crazyflie/cmd_vel_teleop')]
    )

    control_services_2 = Node(
        package='skyscript_sim',
        executable='control_services',
        name='control_services_2',
        output='screen',
        parameters=[{'robot_prefix': '/crazyflie2'}],
        remappings=[('/cmd_vel', '/crazyflie2/cmd_vel_teleop')]
    )

    control_services_3 = Node(
        package='skyscript_sim',
        executable='control_services',
        name='control_services_3',
        output='screen',
        parameters=[{'robot_prefix': '/crazyflie3'}],
        remappings=[('/cmd_vel', '/crazyflie3/cmd_vel_teleop')]
    )

    sdf_file_path = os.path.join(gz_model_path, 'crazyflie', 'model.sdf')
    
    meshes_path = os.path.abspath(os.path.join(gz_model_path, '..', '..', 'meshes'))
    
    with open(sdf_file_path, 'r') as f:
        sdf_content = f.read()

    sdf_content = sdf_content.replace('../../../meshes', meshes_path)

    sdf_drone1 = sdf_content.replace('{{NAMESPACE}}', 'crazyflie')
    sdf_drone2 = sdf_content.replace('{{NAMESPACE}}', 'crazyflie2')
    sdf_drone3 = sdf_content.replace('{{NAMESPACE}}', 'crazyflie3')

    spawn_drone1 = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=['-world', 'crazyflie_world', '-string', sdf_drone1, '-name', 'crazyflie', '-x', '0', '-y', '0', '-z', '0'],
        output='screen'
    )

    spawn_drone2 = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=['-world', 'crazyflie_world', '-string', sdf_drone2, '-name', 'crazyflie2', '-x', '1', '-y', '0', '-z', '0'],
        output='screen'
    )

    spawn_drone3 = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=['-world', 'crazyflie_world', '-string', sdf_drone3, '-name', 'crazyflie3', '-x', '-1', '-y', '0', '-z', '0'],
        output='screen'
    )

    llm_planner = Node(
        package='skyscript_sim',
        executable='llm_planner',
        name='llm_planner',
        output='screen'
    )

    swarm_controller = Node(
        package='skyscript_sim',
        executable='swarm_controller',
        name='swarm_controller',
        output='screen'
    )

    stream_positions = Node(
        package='skyscript_sim',
        executable='stream_positions',
        name='stream_positions',
        output='screen'
    )

    translator = Node(
        package='skyscript_sim',
        executable='translator',
        name='translator',
        output='screen'
    )

    visualizer = Node(
        package='skyscript_sim',
        executable='visualizer',
        name='visualizer',
        output='screen'
    )

    return LaunchDescription([
        gz_ln_arg,
        gz_sim,
        bridge,
        control_services_1,
        control_services_2,
        control_services_3,
        spawn_drone1,
        spawn_drone2,
        spawn_drone3,
        llm_planner,
        swarm_controller,
        stream_positions,
        translator,
        visualizer
    ])