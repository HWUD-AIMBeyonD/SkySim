import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Point
from std_msgs.msg import Int32
import threading
import math
import time
import sys
import os
from collections import deque
import itertools

try:
    import dash
    from dash import dcc, html
    from dash.dependencies import Input, Output
    import plotly.graph_objs as go
except ImportError:
    possible_venv = os.path.join(os.getcwd(), 'venv', 'lib', 'python3.12', 'site-packages')
    if os.path.exists(possible_venv):
        sys.path.append(possible_venv)
    
    hardcoded_venv = '/home/aditya/SkyScript/venv/lib/python3.12/site-packages'
    if os.path.exists(hardcoded_venv) and hardcoded_venv not in sys.path:
        sys.path.append(hardcoded_venv)

    import dash
    from dash import dcc, html
    from dash.dependencies import Input, Output
    import plotly.graph_objs as go

import logging

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

class VisualizerNode(Node):
    def __init__(self):
        super().__init__('visualizer_node')
        
        self.positions = {}
        self.tracked_drones = []
        
        # Restore maxlen for sliding window behavior (approx 50s at 20Hz limit)
        self.maxlen = 1000
        self.time_history = deque(maxlen=self.maxlen)
        self.dist_history = {}
        
        self.start_time = time.time()
        
        self.create_subscription(
            Int32,
            '/swarm/drone_count',
            self.drone_count_callback,
            10
        )

        self.get_logger().info('Visualizer Node Started. Web dashboard at http://127.0.0.1:8050')

    def drone_count_callback(self, msg):
        count = msg.data
        
        target_names = []
        if count >= 1:
            target_names.append('crazyflie')
        for i in range(2, count + 1):
            target_names.append(f'crazyflie{i}')
            
        for name in target_names:
            if name not in self.positions:
                self.positions[name] = None
                self.tracked_drones.append(name)
                
                self.create_subscription(
                    Point,
                    f'/{name}/position',
                    lambda msg, n=name: self.position_callback(msg, n),
                    10
                )
                
                for existing_name in self.tracked_drones:
                    if existing_name == name: continue
                    
                    pair = tuple(sorted((existing_name, name)))
                    if pair not in self.dist_history:
                        self.dist_history[pair] = deque(maxlen=self.maxlen)

    def position_callback(self, msg, name):
        self.positions[name] = msg
        self.update_data()

    def update_data(self):        
        current_time = time.time() - self.start_time
        
        if len(self.time_history) > 0 and current_time < self.time_history[-1] + 0.05:
            return

        self.time_history.append(current_time)
        
        def dist(a, b):
            if a is None or b is None: return 0.0
            return math.sqrt((a.x-b.x)**2 + (a.y-b.y)**2 + (a.z-b.z)**2)

        for pair, history in list(self.dist_history.items()):
            p1 = self.positions[pair[0]]
            p2 = self.positions[pair[1]]
            d = dist(p1, p2)
            history.append(d)

viz_node = None

def run_dash_app():
    app = dash.Dash(__name__)
    
    app.layout = html.Div([
        html.H1("SkyScript Swarm Monitor", style={'textAlign': 'center'}),
        
        dcc.Graph(id='live-distance-graph'),
        
        dcc.Interval(
            id='graph-update',
            interval=500,
            n_intervals=0
        )
    ])

    @app.callback(Output('live-distance-graph', 'figure'),
                  Input('graph-update', 'n_intervals'))
    def update_graph_scatter(n):
        if viz_node is None:
            return go.Figure()

        times = list(viz_node.time_history)
        
        data = []
        
        # Safety line
        data.append(go.Scatter(
                x=[min(times) if times else 0, max(times) if times else 60], 
                y=[0.5, 0.5], 
                mode='lines', 
                name='Safety Limit (0.5m)',
                line=dict(color='red', width=2, dash='dash')
            ))

        for pair, history in list(viz_node.dist_history.items()):
            if len(history) == 0: continue
            
            n1 = pair[0].replace('crazyflie', '').strip()
            if n1 == '': n1 = '1'
            n2 = pair[1].replace('crazyflie', '').strip()
            if n2 == '': n2 = '1'
            
            label = f"Drone {n1}-{n2}"
            
            y_data = list(history)
            
            min_len = min(len(times), len(y_data))
            
            data.append(go.Scatter(
                x=times[-min_len:], 
                y=y_data[-min_len:], 
                mode='lines', 
                name=label
            ))

        current_max_time = max(times) if times else 0
        
        current_max_dist = 0.0
        for trace in data:
            if trace['name'] == 'Safety Limit (0.5m)': continue
            if trace['y']:
                current_max_dist = max(current_max_dist, max(trace['y']))

        layout = go.Layout(
            title='Inter-Drone Distances',
            xaxis=dict(title='Time (s)', range=[max(0, current_max_time - 30), max(30, current_max_time)]),
            yaxis=dict(title='Distance (m)', range=[0, max(3.0, current_max_dist + 1.0)]),
            hovermode='closest'
        )

        return {'data': data, 'layout': layout}

    app.run(debug=False, port=8050, host='0.0.0.0')

def main(args=None):
    global viz_node
    rclpy.init(args=args)
    viz_node = VisualizerNode()
    
    dash_thread = threading.Thread(target=run_dash_app)
    dash_thread.daemon = True
    dash_thread.start()
    
    try:
        rclpy.spin(viz_node)
    except KeyboardInterrupt:
        pass
    finally:
        viz_node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
