import os
from glob import glob
from setuptools import setup

from setuptools import find_packages, setup

package_name = 'SkySim'

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
    description='Crazyflie control simulation package for SkySim project built for AimBeyonD lab',
    license='MIT',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'SkySim = SkySim.SkySim:main',
            'control_services = SkySim.control_services:main',
            'llm_planner = SkySim.llm_planner_node:main',
            'swarm_controller = SkySim.swarm_controller_node:main',
            'stream_positions = SkySim.stream_positions_node:main',
            'translator = SkySim.translator_node:main',
            'visualizer = SkySim.visualizer_node:main'
        ],
    },
)
