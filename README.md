## System Configuration
- Ubuntu 24.04
- ROS 2 Jazzy
- Gazebo Harmonic LTS

## Getting Started with Simulation
- Download Gazebo Harmonic, refer to [Getting Started with Gazebo Harmonic LTS](https://gazebosim.org/docs/harmonic/getstarted/)

- Follow the steps in the crazyflie documentation to setup crazyswarm on gazebo [Crazyflie simulation in Gazebo](https://www.bitcraze.io/2024/09/crazyflies-adventures-with-ros-2-and-gazebo/)

- Before running the scripts run the following command:
    ```
    export GZ_SIM_RESOURCE_PATH="/home/$USER/SkyScript/SkySim/simulator_files/gazebo/"
    ```

- Clone the package using the command:
    ```
    git clone https://github.com/HWUD-AIMBeyonD/SkyScript.git
    ```


- Then run the skyscript simulation package using the command:
    ```bash
    cd ~/SkyScript
    colcon build
    source install/setup.bash
    export PYTHONPATH=$PYTHONPATH:$(pwd)/venv/lib/python3.12/site-packages
    ros2 launch SkySim SkySim_launch.py
    ```

### Multi-Drone Simulation and Keyboard Control
The simulation is now configured to spawn three Crazyflie drones. You can control them individually using the custom keyboard teleoperation script.

- Run the multi-drone keyboard teleoperation script in a new terminal:
    ```bash
    python3 scripts/keyboard_control_multi.py
    ```

- **Keyboard Controls:**
    *   **Select Drone**: Press `1`, `2`, or `3` to choose which drone to control.
    *   **Movement**: Use `w`, `a`, `s`, `d` for forward/left/backward/right linear movement.
    *   **Altitude**: Use `Up Arrow` to increase altitude and `Down Arrow` to decrease altitude.
    *   **Takeoff**: Press `t` to initiate takeoff to the default hover height.
    *   **Land**: Press `l` to initiate landing.
    *   **Stop**: Press `space` or `k` to force stop all movement.
    *   **Quit**: Press `CTRL-C` to exit the script.

### Drone Spawning
Drones are spawned on a 20x20 grid at 1-meter intervals on the XY plane (X from -10 to 9, Y from -10 to 9), providing up to 400 unique spawn locations. Initial drones (crazyflie, crazyflie2, crazyflie3) are spawned by default by the launch file, and new drones will attempt to avoid their initial positions.

*   **Add a single drone:**
    ```bash
    ros2 service call /add_drone std_srvs/srv/Trigger
    ```
*   **Add multiple drones at once:**
    To spawn `N` additional drones, publish an integer `N` to the `/swarm/spawn_request` topic. For example, to add 10 drones:
    ```bash
    ros2 topic pub --once /swarm/spawn_request std_msgs/msg/Int32 "data: 10"
    ```

### Safety & Collision Avoidance (APF)
The Swarm Controller implements an **Artificial Potential Field (APF)** to prevent drone-to-drone collisions. When enabled, drones will actively repel each other if they get too close (default safety radius: 0.8m).

*   **Default State:** Enabled (`True`)
*   **Toggle Dynamically:** You can turn the safety filter on or off while the simulation is running using ROS 2 parameters.

    **Turn OFF collision avoidance:**
    ```bash
    ros2 param set /swarm_controller use_apf false
    ```

    **Turn ON collision avoidance:**
    ```bash
    ros2 param set /swarm_controller use_apf true
    ```

### LLM Command Workflow
To send a natural language command to the LLM that will generate drone waypoints:

1.  The command first goes to the `translator_node`.
2.  The `translator_node` combines current drone states with your command to form a prompt.
3.  This prompt is then sent to the `llm_planner_node` which queries the Gemini LLM.

Run an LLM command using:
```bash
ros2 topic pub --once /skyscript/user_command std_msgs/msg/String "data: 'Form a vertical line with 1 meter spacing at a height of 1.5m'"
```
*(Remember to set your `GEMINI_API_KEY` environment variable for the LLM to work)*

### Hardcoded Test Commands
For debugging or testing specific scenarios without the LLM, you can use the `/skyscript/test_command` topic. These commands bypass the LLM and directly trigger predefined waypoint generation.

Run a hardcoded test command using:
*   **Triangle Formation:**
    ```bash
    ros2 topic pub --once /skyscript/test_command std_msgs/msg/String "data: 'triangle'"
    ```
*   **Unsafe Formation (to test APF):**
    ```bash
    ros2 topic pub --once /skyscript/test_command std_msgs/msg/String "data: 'unsafe'"
    ```
*   **Safe Hover Formation (fallback/default):**
    ```bash
    ros2 topic pub --once /skyscript/test_command std_msgs/msg/String "data: 'safe_hover'"
    ```

## Application GUI

### Running the Ground Control Station
To launch the main control interface (QT-based)
```bash
python guiQT.py
```

