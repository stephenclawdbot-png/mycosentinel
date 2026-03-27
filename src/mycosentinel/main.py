"""
MycoSentinel — Main Application Entry Point
Continuous biosensor monitoring system.

Usage:
    python -m mycosentinel run --config config.yaml
    python -m mycosentinel node --node-id node-01
    python -m mycosentinel gateway --gateway-id gateway-01
"""

import argparse
import yaml
import signal
import time
import logging
from pathlib import Path

from mycosentinel.bioreactor import BioreactorController
from mycosentinel.sensor import OpticalSensor, ElectricalSensor
from mycosentinel.pipeline import SignalProcessor
from mycosentinel.network import SensorNode, Gateway
from mycosentinel.dashboard import Dashboard

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration defaults
DEFAULT_CONFIG = {
    'node_id': 'myco-01',
    'sampling_rate_hz': 1.0,
    'sensors': ['optical'],  # ['optical', 'electrical']
    'use_mock': True,  # Set False for real hardware
    'dashboard': {
        'enabled': True,
        'port': 8080
    },
    'network': {
        'mode': 'standalone',  # 'standalone', 'gateway', 'mqtt'
        'mqtt_broker': None,
        'http_endpoint': None
    },
    'processing': {
        'filter_type': 'median',
        'anomaly_threshold': 2.5,
        'calibration_duration_sec': 30
    }
}

def load_config(path: str) -> dict:
    """Load configuration from YAML"""
    config_path = Path(path)
    if config_path.exists():
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    return DEFAULT_CONFIG

def save_config(config: dict, path: str):
    """Save configuration to YAML"""
    with open(path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
    logger.info(f"Configuration saved to {path}")

class MycoSentinelApp:
    """Main application controller"""
    
    def __init__(self, config: dict):
        self.config = config
        self.node: SensorNode = None
        self.gateway: Gateway = None
        self.dashboard: Dashboard = None
        self._shutdown = False
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self._shutdown = True
    
    def run_standalone(self):
        """Run single node with dashboard"""
        logger.info("Starting MycoSentinel in STANDALONE mode")
        
        # Create node
        self.node = SensorNode(
            node_id=self.config['node_id'],
            sampling_rate_hz=self.config['sampling_rate_hz'],
            use_mock=self.config['use_mock']
        )
        
        # Create dashboard
        if self.config['dashboard']['enabled']:
            self.dashboard = Dashboard(
                gateway=None,
                port=self.config['dashboard']['port']
            )
            
            # Connect node to dashboard
            def update_dashboard(packet):
                if self.dashboard:
                    self.dashboard.update_data(packet)
            
            self.node.register_callback(update_dashboard)
            
            # Start dashboard in thread
            self.dashboard.run_async()
            logger.info(f"Dashboard available at http://localhost:{self.dashboard.port}")
        
        # Start node
        self.node.start()
        logger.info(f"Node {self.config['node_id']} started")
        
        # Run until shutdown
        try:
            while not self._shutdown:
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()
    
    def run_gateway(self):
        """Run as gateway with multiple nodes"""
        logger.info("Starting MycoSentinel in GATEWAY mode")
        
        # Create gateway
        self.gateway = Gateway(
            gateway_id=self.config.get('gateway_id', 'gateway-01'),
            mqtt_broker=self.config['network'].get('mqtt_broker'),
            use_mqtt=bool(self.config['network'].get('mqtt_broker'))
        )
        
        # Create and register nodes
        nodes_config = self.config.get('nodes', [DEFAULT_CONFIG])
        for node_config in nodes_config:
            node = SensorNode(
                node_id=node_config['node_id'],
                sampling_rate_hz=node_config.get('sampling_rate_hz', 1.0),
                use_mock=node_config.get('use_mock', True)
            )
            self.gateway.register_node(node)
        
        # Start all
        self.gateway.start_all()
        logger.info(f"Gateway managing {len(self.gateway.nodes)} nodes")
        
        # Dashboard
        if self.config['dashboard']['enabled']:
            self.dashboard = Dashboard(
                gateway=self.gateway,
                port=self.config['dashboard']['port']
            )
            self.dashboard.run_async()
        
        # Run
        try:
            while not self._shutdown:
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down MycoSentinel...")
        
        if self.node:
            self.node.stop()
        
        if self.gateway:
            self.gateway.stop_all()
        
        logger.info("Shutdown complete")

def main():
    parser = argparse.ArgumentParser(
        description='MycoSentinel — Living Biosensor Network'
    )
    parser.add_argument(
        'command',
        choices=['run', 'node', 'gateway', 'init', 'calibrate'],
        help='Command to execute'
    )
    parser.add_argument(
        '--config', '-c',
        default='mycosentinel.yaml',
        help='Configuration file path'
    )
    parser.add_argument(
        '--node-id', '-n',
        type=str,
        help='Node identifier'
    )
    parser.add_argument(
        '--gateway-id', '-g',
        type=str,
        help='Gateway identifier'
    )
    parser.add_argument(
        '--mock',
        action='store_true',
        default=True,
        help='Use mock hardware (default)'
    )
    parser.add_argument(
        '--no-mock',
        action='store_false',
        dest='mock',
        help='Use real hardware'
    )
    
    args = parser.parse_args()
    
    if args.command == 'init':
        # Create default config
        if args.node_id:
            DEFAULT_CONFIG['node_id'] = args.node_id
        save_config(DEFAULT_CONFIG, args.config)
        print(f"Initialized {args.config}")
        print("Edit configuration and run: python -m mycosentinel run")
        return
    
    # Load configuration
    config = load_config(args.config)
    
    # Override with CLI args
    if args.node_id:
        config['node_id'] = args.node_id
        config['network']['mode'] = 'standalone'
    if args.gateway_id:
        config['gateway_id'] = args.gateway_id
        config['network']['mode'] = 'gateway'
    config['use_mock'] = args.mock
    
    # Create and run app
    app = MycoSentinelApp(config)
    
    if args.command in ['run', 'node']:
        app.run_standalone()
    elif args.command == 'gateway':
        app.run_gateway()
    elif args.command == 'calibrate':
        print("Calibration mode - TODO: Implement calibration wizard")

if __name__ == '__main__':
    main()
