import os
from glob import glob
from setuptools import setup

from setuptools import find_packages, setup

package_name = 'skyscript_sim'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),

        (os.path.join('share', package_name, 'launch'), 
         glob(os.path.join('launch', '*.py'))),
        
        (os.path.join('share', package_name, 'config'), 
         glob(os.path.join('config', '*.yaml'))),
    ],
    install_requires=['setuptools', 'dash', 'pandas', 'plotly'],
    zip_safe=True,
    maintainer='Aditya',
    maintainer_email='as2397@hw.ac.uk',
    description='Crazyflie control simulation package for SkyScript project built for AimBeyonD lab',
    license='MIT',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'skyscript_sim = skyscript_sim.skyscript_sim:main',
            'control_services = skyscript_sim.control_services:main',
            'llm_planner = skyscript_sim.llm_planner_node:main',
            'swarm_controller = skyscript_sim.swarm_controller_node:main',
            'stream_positions = skyscript_sim.stream_positions_node:main',
            'translator = skyscript_sim.translator_node:main',
            'visualizer = skyscript_sim.visualizer_node:main'
        ],
    },
)
