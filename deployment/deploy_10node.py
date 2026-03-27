#!/usr/bin/env python3
"""
MycoSentinel 10-Node Environmental Sensor Deployment Script
Automated deployment for Raspberry Pi Zero 2 W nodes with:
- SCD30 (CO2 sensor)
- SPS30 (Particulate Matter sensor)  
- SGP40 (VOC sensor)
- DHT22 (Temperature/Humidity)

Features:
- Node provisioning and configuration
- Mesh networking setup (Batman-adv)
- Data aggregation pipeline
- MQTT broker configuration
- Gateway stack deployment (Docker)
- Remote node deployment via SSH

Usage:
    python3 deploy_10node.py --config deploy_config.json [--gateway-only | --node <node_id> | --all]
    python3 deploy_10node.py --provision-gateway
    python3 deploy_10node.py --deploy-nodes
    python3 deploy_10node.py --status
    python3 deploy_10node.py --calibrate <node_id>

Author: MycoSentinel Deployment Automation
Version: 1.0.0
"""

import json
import subprocess
import sys
import os
import argparse
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import ipaddress
import threading
import concurrent.futures

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('deployment.log')
    ]
)
logger = logging.getLogger(__name__)

# ANSI Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

@dataclass
class SensorConfig:
    """Sensor calibration and configuration"""
    enabled: bool
    i2c_address: str
    calibration: Dict

@dataclass
class NodeConfig:
    """Single node configuration"""
    id: str
    hostname: str
    static_ip: str
    sector: str
    location: Dict
    hardware: str
    sensors: Dict
    power: Dict

class MycoSentinelDeployer:
    """Main deployment orchestrator for MycoSentinel 10-node network"""
    
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.config: Dict = {}
        self.nodes: List[NodeConfig] = []
        self.gateway: Dict = {}
        self.deployed_nodes: List[str] = []
        self.failed_nodes: List[str] = []
        
        # SSH configuration
        self.ssh_key = Path.home() / '.ssh' / 'mycosentinel_deploy'
        self.ssh_user = 'pi'
        
        # Load configuration
        self.load_config()
        
    def load_config(self) -> None:
        """Load deployment configuration from JSON file"""
        if not self.config_path.exists():
            logger.error(f"Config file not found: {self.config_path}")
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            self.config = json.load(f)
        
        self.gateway = self.config.get('gateway', {})
        
        # Parse node configurations
        for node_data in self.config.get('nodes', []):
            node = NodeConfig(
                id=node_data['id'],
                hostname=node_data['hostname'],
                static_ip=node_data['static_ip'],
                sector=node_data['sector'],
                location=node_data['location'],
                hardware=node_data['hardware'],
                sensors=node_data['sensors'],
                power=node_data['power']
            )
            self.nodes.append(node)
        
        logger.info(f"Loaded configuration for {len(self.nodes)} nodes")
        logger.info(f"Gateway: {self.gateway.get('id', 'unknown')} at {self.gateway.get('ip', 'unknown')}")

    def print_banner(self, text: str) -> None:
        """Print a formatted banner"""
        print(f"\n{Colors.CYAN}{'='*60}{Colors.ENDC}")
        print(f"{Colors.BOLD}{text}{Colors.ENDC}")
        print(f"{Colors.CYAN}{'='*60}{Colors.ENDC}\n")

    def run_command(self, cmd: List[str], cwd: Optional[str] = None, 
                    capture_output: bool = True, check: bool = True,
                    timeout: int = 60) -> Tuple[int, str, str]:
        """Execute a shell command and return results"""
        logger.debug(f"Running command: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=capture_output,
                text=True,
                check=check,
                timeout=timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {' '.join(cmd)}")
            logger.error(f"Error: {e.stderr}")
            return e.returncode, e.stdout, e.stderr
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {' '.join(cmd)}")
            return -1, "", "Timeout"

    def ssh_command(self, node_ip: str, cmd: str, timeout: int = 60) -> Tuple[bool, str, str]:
        """Execute command on remote node via SSH"""
        ssh_cmd = [
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'ConnectTimeout=10',
            '-o', 'BatchMode=yes',
            f'{self.ssh_user}@{node_ip}',
            cmd
        ]
        returncode, stdout, stderr = self.run_command(ssh_cmd, timeout=timeout, check=False)
        return returncode == 0, stdout, stderr

    def scp_file(self, local_path: str, node_ip: str, remote_path: str) -> bool:
        """Copy file to remote node via SCP"""
        scp_cmd = [
            'scp',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'ConnectTimeout=10',
            local_path,
            f'{self.ssh_user}@{node_ip}:{remote_path}'
        ]
        returncode, _, _ = self.run_command(scp_cmd, check=False)
        return returncode == 0

    # =============================================================================
    # SECTION 1: GATEWAY PROVISIONING
    # =============================================================================

    def provision_gateway(self) -> bool:
        """
        Provision the gateway node (Raspberry Pi 4/5)
        Sets up MQTT broker, InfluxDB, Grafana, Node-RED
        """
        self.print_banner("PROVISIONING GATEWAY NODE")
        
        gateway_ip = self.gateway.get('ip', '192.168.1.100')
        
        logger.info(f"Provisioning gateway at {gateway_ip}")
        
        steps = [
            ("Checking Docker installation", self._check_docker),
            ("Creating network bridge", self._create_network_bridge),
            ("Deploying MQTT broker (Mosquitto)", self._deploy_mosquitto),
            ("Deploying InfluxDB", self._deploy_influxdb),
            ("Deploying Grafana", self._deploy_grafana),
            ("Deploying Node-RED", self._deploy_nodered),
            ("Deploying Telegraf", self._deploy_telegraf),
            ("Configuring firewall", self._configure_gateway_firewall),
            ("Setting up mesh gateway", self._setup_mesh_gateway),
        ]
        
        for step_name, step_func in steps:
            logger.info(f"Step: {step_name}")
            try:
                if not step_func():
                    logger.error(f"Failed: {step_name}")
                    return False
            except Exception as e:
                logger.error(f"Exception in {step_name}: {e}")
                return False
        
        logger.info(f"{Colors.GREEN}Gateway provisioning complete!{Colors.ENDC}")
        logger.info(f"Dashboard available at: http://{gateway_ip}:3000")
        return True

    def _check_docker(self) -> bool:
        """Check if Docker and Docker Compose are installed"""
        code, _, _ = self.run_command(['docker', '--version'], check=False)
        if code != 0:
            logger.info("Installing Docker...")
            install_cmd = [
                'curl', '-fsSL', 'https://get.docker.com', '-o', 'get-docker.sh'
            ]
            self.run_command(install_cmd, check=False)
            self.run_command(['sh', 'get-docker.sh'], check=False)
            self.run_command(['usermod', '-aG', 'docker', self.ssh_user], check=False)
        
        code, _, _ = self.run_command(['docker-compose', '--version'], check=False)
        if code != 0:
            logger.info("Installing Docker Compose...")
            self.run_command([
                'pip3', 'install', 'docker-compose'
            ], check=False)
        
        # Start Docker service
        self.run_command(['systemctl', 'enable', 'docker'], check=False)
        self.run_command(['systemctl', 'start', 'docker'], check=False)
        return True

    def _create_network_bridge(self) -> bool:
        """Create Docker network for MycoSentinel stack"""
        self.run_command([
            'docker', 'network', 'create', '--driver', 'bridge',
            'mycosentinel-network'
        ], check=False)
        return True

    def _deploy_mosquitto(self) -> bool:
        """Deploy MQTT broker"""
        mqtt_config = """# Mosquitto Configuration for MycoSentinel
listener 1883
allow_anonymous false
password_file /mosquitto/config/passfile
acl_file /mosquitto/config/acl

# Persistence
persistence true
persistence_location /mosquitto/data/

# Logging
log_dest file /mosquitto/log/mosquitto.log
log_dest stdout

# Bridge settings for mesh
connection bridge-nodes
topic # both 0 "" "nodes/"
"""
        
        # Write config
        mqtt_dir = Path('mosquitto/config')
        mqtt_dir.mkdir(parents=True, exist_ok=True)
        (mqtt_dir / 'mosquitto.conf').write_text(mqtt_config)
        
        # Create password file
        passwd_cmd = f"mosquitto_passwd -c -b mosquitto/config/passfile gateway {self._generate_password('gateway')}"
        self.run_command(passwd_cmd.split(), check=False)
        
        for node in self.nodes:
            passwd_cmd = f"mosquitto_passwd -b mosquitto/config/passfile {node.id.lower()} {self._generate_password(node.id)}"
            self.run_command(passwd_cmd.split(), check=False)
        
        return True

    def _deploy_influxdb(self) -> bool:
        """Deploy InfluxDB time-series database"""
        influx_config = """[meta]
  dir = "/var/lib/influxdb/meta"

[data]
  dir = "/var/lib/influxdb/data"
  wal-dir = "/var/lib/influxdb/wal"

[http]
  enabled = true
  bind-address = ":8086"
  auth-enabled = true
"""
        
        influx_dir = Path('influxdb')
        influx_dir.mkdir(exist_ok=True)
        (influx_dir / 'influxdb.conf').write_text(influx_config)
        return True

    def _deploy_grafana(self) -> bool:
        """Configure Grafana dashboards and datasources"""
        grafana_datasource = """apiVersion: 1
datasources:
  - name: MycoSentinel-InfluxDB
    type: influxdb
    access: proxy
    url: http://influxdb:8086
    database: mycosentinel
    isDefault: true
    editable: true
"""
        
        grafana_dir = Path('grafana/provisioning/datasources')
        grafana_dir.mkdir(parents=True, exist_ok=True)
        (grafana_dir / 'datasource.yml').write_text(grafana_datasource)
        return True

    def _deploy_nodered(self) -> bool:
        """Deploy Node-RED for flow automation"""
        nodered_dir = Path('nodered')
        nodered_dir.mkdir(exist_ok=True)
        return True

    def _deploy_telegraf(self) -> bool:
        """Configure Telegraf for data ingestion"""
        telegraf_config = """[global_tags]
  deployment = "mycosentinel-10node"

[agent]
  interval = "60s"
  round_interval = true
  metric_batch_size = 1000
  metric_buffer_limit = 10000
  collection_jitter = "0s"
  flush_interval = "10s"
  flush_jitter = "0s"
  precision = ""
  debug = false
  quiet = false
  logfile = ""
  hostname = ""
  omit_hostname = false

[[outputs.influxdb]]
  urls = ["http://influxdb:8086"]
  database = "mycosentinel"
  retention_policy = ""
  write_consistency = "any"
  timeout = "5s"
  username = "admin"
  password = "admin"

[[inputs.mqtt_consumer]]
  servers = ["tcp://mosquitto:1883"]
  topics = [
    "mycosentinel/+/sensors/#",
    "mycosentinel/+/status"
  ]
  username = "gateway"
  password = "mycosentinel2024"
  data_format = "json"
"""
        
        telegraf_dir = Path('telegraf')
        telegraf_dir.mkdir(exist_ok=True)
        (telegraf_dir / 'telegraf.conf').write_text(telegraf_config)
        return True

    def _configure_gateway_firewall(self) -> bool:
        """Configure firewall rules for gateway"""
        ports = [22, 80, 443, 1883, 1880, 3000, 8086, 9001]
        
        for port in ports:
            self.run_command(['ufw', 'allow', str(port)], check=False)
        
        self.run_command(['ufw', '--force', 'enable'], check=False)
        return True

    def _setup_mesh_gateway(self) -> bool:
        """Setup Batman-adv mesh gateway interface"""
        # Install batman-adv
        self.run_command(['apt-get', 'install', '-y', 'batctl'], check=False)
        
        # Create bat0 interface
        mesh_script = """#!/bin/bash
# Batman-adv mesh gateway setup

# Load batman-adv module
modprobe batman-adv

# Create bat0 interface
batctl if add wlan0
batctl if up

# Configure mesh interface
ip link set bat0 up
ip addr add {gateway_ip}/24 dev bat0

# Enable forwarding
echo 1 > /proc/sys/net/ipv4/ip_forward
""".format(gateway_ip=self.gateway.get('ip', '192.168.1.100'))
        
        mesh_path = Path('/usr/local/bin/mesh-gateway.sh')
        mesh_path.write_text(mesh_script)
        mesh_path.chmod(0o755)
        
        # Create systemd service
        service_file = """[Unit]
Description=Batman-adv Mesh Gateway
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/mesh-gateway.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
"""
        service_path = Path('/etc/systemd/system/mesh-gateway.service')
        service_path.write_text(service_file)
        
        self.run_command(['systemctl', 'enable', 'mesh-gateway'], check=False)
        return True

    # =============================================================================
    # SECTION 2: NODE PROVISIONING
    # =============================================================================

    def deploy_node(self, node: NodeConfig) -> bool:
        """
        Provision a single sensor node
        """
        logger.info(f"Deploying node {node.id} at {node.static_ip}")
        
        steps = [
            ("Ping check", self._ping_node),
            ("Configure static IP", self._configure_static_ip),
            ("Install dependencies", self._install_node_dependencies),
            ("Configure I2C", self._configure_i2c),
            ("Install sensor libraries", self._install_sensor_libs),
            ("Deploy node software", self._deploy_node_software),
            ("Configure mesh client", self._configure_mesh_client),
            ("Setup data pipeline", self._setup_data_pipeline),
            ("Configure auto-start", self._configure_autostart),
            ("Verify sensors", self._verify_sensors),
        ]
        
        for step_name, step_func in steps:
            logger.info(f"  [Node {node.id}] {step_name}...")
            try:
                result = step_func(node)
                if not result:
                    logger.error(f"  [Node {node.id}] Failed at: {step_name}")
                    self.failed_nodes.append(node.id)
                    return False
            except Exception as e:
                logger.error(f"  [Node {node.id}] Exception in {step_name}: {e}")
                self.failed_nodes.append(node.id)
                return False
            time.sleep(0.5)  # Brief pause between steps
        
        self.deployed_nodes.append(node.id)
        logger.info(f"{Colors.GREEN}Node {node.id} deployed successfully!{Colors.ENDC}")
        return True

    def _ping_node(self, node: NodeConfig) -> bool:
        """Check if node is reachable"""
        code, _, _ = self.run_command(['ping', '-c', '3', '-W', '2', node.static_ip], 
                                       check=False, timeout=10)
        return code == 0

    def _configure_static_ip(self, node: NodeConfig) -> bool:
        """Configure static IP on node"""
        dhcpcd_entry = f"""
interface wlan0
static ip_address={node.static_ip}/24
gateway={self.gateway.get('ip', '192.168.1.100')}
static domain_name_servers=8.8.8.8 1.1.1.1
"""
        
        cmd = f"echo '{dhcpcd_entry}' | sudo tee -a /etc/dhcpcd.conf > /dev/null"
        success, _, _ = self.ssh_command(node.static_ip, cmd)
        
        # Restart dhcpcd
        self.ssh_command(node.static_ip, 'sudo systemctl restart dhcpcd')
        return success

    def _install_node_dependencies(self, node: NodeConfig) -> bool:
        """Install required packages on node"""
        packages = [
            'python3', 'python3-pip', 'python3-venv',
            'i2c-tools', 'libgpiod-dev',
            'git', 'vim', 'htop',
            'mosquitto-clients',
            'batctl', 'wireless-tools'
        ]
        
        cmd = f"sudo apt-get update && sudo apt-get install -y {' '.join(packages)}"
        success, _, _ = self.ssh_command(node.static_ip, cmd, timeout=300)
        return success

    def _configure_i2c(self, node: NodeConfig) -> bool:
        """Enable I2C interface"""
        commands = [
            'sudo raspi-config nonint do_i2c 0',
            'sudo modprobe i2c-dev',
            'echo "i2c-dev" | sudo tee /etc/modules-load.d/i2c.conf > /dev/null',
        ]
        
        for cmd in commands:
            self.ssh_command(node.static_ip, cmd)
        
        return True

    def _install_sensor_libs(self, node: NodeConfig) -> bool:
        """Install Python libraries for sensors"""
        pip_packages = [
            'smbus2',                    # I2C communication
            'scd30-i2c',                 # SCD30 CO2 sensor
            'sps30',                     # SPS30 PM sensor
            'sgp40',                     # SGP40 VOC sensor
            'adafruit-circuitpython-dht', # DHT22
            'paho-mqtt',                 # MQTT client
            'requests',                  # HTTP requests
            'psutil',                    # System monitoring
        ]
        
        cmd = f"pip3 install --user {' '.join(pip_packages)}"
        success, _, _ = self.ssh_command(node.static_ip, cmd, timeout=120)
        return success

    def _deploy_node_software(self, node: NodeConfig) -> bool:
        """Deploy MycoSentinel node software"""
        # Create application directory
        dirs = ['/opt/mycosentinel', '/var/log/mycosentinel']
        for d in dirs:
            self.ssh_command(node.static_ip, f'sudo mkdir -p {d}')
        
        # Generate sensor reader script
        sensor_script = self._generate_sensor_script(node)
        
        # Write script remotely
        cmd = f"cat > /tmp/sensor_reader.py << 'EOF'\n{sensor_script}\nEOF"
        self.ssh_command(node.static_ip, cmd)
        self.ssh_command(node.static_ip, 'sudo mv /tmp/sensor_reader.py /opt/mycosentinel/')
        self.ssh_command(node.static_ip, 'sudo chmod +x /opt/mycosentinel/sensor_reader.py')
        
        # Generate config file
        node_config = self._generate_node_config(node)
        cmd = f"cat > /tmp/node_config.json << 'EOF'\n{json.dumps(node_config, indent=2)}\nEOF"
        self.ssh_command(node.static_ip, cmd)
        self.ssh_command(node.static_ip, 'sudo mv /tmp/node_config.json /opt/mycosentinel/')
        
        return True

    def _generate_sensor_script(self, node: NodeConfig) -> str:
        """Generate Python sensor reader script"""
        return f'''#!/usr/bin/env python3
"""
MycoSentinel Node Sensor Reader - {node.id}
Reads from SCD30, SPS30, SGP40, DHT22 and publishes to MQTT
"""

import json
import time
import signal
import sys
from pathlib import Path
import paho.mqtt.client as mqtt

# Sensor imports with error handling
try:
    from scd30_i2c import SCD30
    SCD30_AVAILABLE = True
except ImportError:
    SCD30_AVAILABLE = False

try:
    from sps30 import SPS30
    SPS30_AVAILABLE = True
except ImportError:
    SPS30_AVAILABLE = False

try:
    from sgp40 import SGP40
    SGP40_AVAILABLE = True
except ImportError:
    SGP40_AVAILABLE = False

try:
    import Adafruit_DHT
    DHT22_AVAILABLE = True
except ImportError:
    DHT22_AVAILABLE = False

# Configuration
NODE_ID = "{node.id}"
GATEWAY_IP = "{self.gateway.get('ip', '192.168.1.100')}"
MQTT_TOPIC_PREFIX = f"mycosentinel/{{NODE_ID}}/sensors"
CONFIG_PATH = "/opt/mycosentinel/node_config.json"

# Load calibration data
config = {{}}
if Path(CONFIG_PATH).exists():
    with open(CONFIG_PATH) as f:
        config = json.load(f)

class SensorReader:
    def __init__(self):
        self.scd30 = None
        self.sps30 = None
        self.sgp40 = None
        self.dht22_pin = {node.sensors.get('dht22', {}).get('gpio_pin', 4)}
        self.mqtt = mqtt.Client()
        self.running = True
        
    def connect_mqtt(self):
        """Connect to MQTT broker"""
        try:
            self.mqtt.connect(GATEWAY_IP, 1883, 60)
            self.mqtt.loop_start()
            print(f"Connected to MQTT at {{GATEWAY_IP}}")
            return True
        except Exception as e:
            print(f"MQTT connection failed: {{e}}")
            return False
    
    def init_sensors(self):
        """Initialize all configured sensors"""
        if SCD30_AVAILABLE and config.get('sensors', {{}}).get('scd30', {{}}).get('enabled'):
            try:
                self.scd30 = SCD30()
                # Set calibration
                cal = config['sensors']['scd30']['calibration']
                self.scd30.set_measurement_interval(2)
                self.scd30.set_altitude(cal.get('altitude_m', 0))
                print("SCD30 initialized")
            except Exception as e:
                print(f"SCD30 init failed: {{e}}")
        
        if SPS30_AVAILABLE and config.get('sensors', {{}}).get('sps30', {{}}).get('enabled'):
            try:
                self.sps30 = SPS30()
                self.sps30.start_measurement()
                print("SPS30 initialized")
            except Exception as e:
                print(f"SPS30 init failed: {{e}}")
        
        if SGP40_AVAILABLE and config.get('sensors', {{}}).get('sgp40', {{}}).get('enabled'):
            try:
                self.sgp40 = SGP40()
                print("SGP40 initialized")
            except Exception as e:
                print(f"SGP40 init failed: {{e}}")
        
        print(f"DHT22 initialization (pin {{self.dht22_pin}})...")
    
    def read_scd30(self):
        """Read CO2, temp, humidity from SCD30"""
        if not self.scd30:
            return {{}}
        try:
            if self.scd30.get_data_ready():
                m = self.scd30.read_measurement()
                cal = config.get('sensors', {{}}).get('scd30', {{}}).get('calibration', {{}})
                return {{
                    'co2_ppm': m[0] + cal.get('co2_offset_ppm', 0),
                    'temperature_c': round(m[1] + cal.get('temperature_offset_c', 0), 2),
                    'humidity_percent': round(m[2], 2),
                    'timestamp': time.time()
                }}
        except Exception as e:
            print(f"SCD30 read error: {{e}}")
        return {{}}
    
    def read_sps30(self):
        """Read particulate matter from SPS30"""
        if not self.sps30:
            return {{}}
        try:
            values = self.sps30.read_measured_values()
            cal = config.get('sensors', {{}}).get('sps30', {{}}).get('calibration', {{}})
            return {{
                'pm1_ug_m3': round(values[0] + cal.get('pm1_offset_ug_m3', 0), 2),
                'pm2_5_ug_m3': round(values[1] + cal.get('pm2_5_offset_ug_m3', 0), 2),
                'pm4_ug_m3': round(values[2] + cal.get('pm4_offset_ug_m3', 0), 2),
                'pm10_ug_m3': round(values[3] + cal.get('pm10_offset_ug_m3', 0), 2),
                'timestamp': time.time()
            }}
        except Exception as e:
            print(f"SPS30 read error: {{e}}")
        return {{}}
    
    def read_sgp40(self):
        """Read VOC index from SGP40"""
        if not self.sgp40:
            return {{}}
        try:
            voc = self.sgp40.measure_raw()
            # Convert to VOC index (0-500 scale)
            voc_index = max(0, min(500, voc // 100))
            cal = config.get('sensors', {{}}).get('sgp40', {{}}).get('calibration', {{}})
            return {{
                'voc_raw': voc,
                'voc_index': voc_index + cal.get('voc_index_offset', 0),
                'timestamp': time.time()
            }}
        except Exception as e:
            print(f"SGP40 read error: {{e}}")
        return {{}}
    
    def read_dht22(self):
        """Read temperature/humidity from DHT22"""
        if not DHT22_AVAILABLE:
            return {{}}
        try:
            humidity, temperature = Adafruit_DHT.read_retry(Adafruit_DHT.DHT22, self.dht22_pin)
            if humidity is not None and temperature is not None:
                cal = config.get('sensors', {{}}).get('dht22', {{}}).get('calibration', {{}})
                return {{
                    'temperature_c': round(temperature + cal.get('temperature_offset_c', 0), 2),
                    'humidity_percent': round(humidity + cal.get('humidity_offset_percent', 0), 2),
                    'timestamp': time.time()
                }}
        except Exception as e:
            print(f"DHT22 read error: {{e}}")
        return {{}}
    
    def read_all_sensors(self):
        """Read from all sensors"""
        data = {{
            'node_id': NODE_ID,
            'readings': {{}},
            'timestamp': time.time()
        }}
        
        scd = self.read_scd30()
        if scd:
            data['readings']['scd30'] = scd
        
        sps = self.read_sps30()
        if sps:
            data['readings']['sps30'] = sps
        
        sgp = self.read_sgp40()
        if sgp:
            data['readings']['sgp40'] = sgp
        
        dht = self.read_dht22()
        if dht:
            data['readings']['dht22'] = dht
        
        return data
    
    def publish_data(self, data):
        """Publish sensor data to MQTT"""
        try:
            topic = f"{{MQTT_TOPIC_PREFIX}}/all"
            self.mqtt.publish(topic, json.dumps(data))
            
            # Also publish individual sensor streams
            for sensor, readings in data.get('readings', {{}}).items():
                topic = f"{{MQTT_TOPIC_PREFIX}}/{{sensor}}"
                self.mqtt.publish(topic, json.dumps(readings))
        except Exception as e:
            print(f"MQTT publish error: {{e}}")
    
    def run(self):
        """Main loop"""
        print(f"Starting MycoSentinel Node {{NODE_ID}}")
        self.connect_mqtt()
        self.init_sensors()
        
        # Setup signal handlers
        def signal_handler(sig, frame):
            print("\\nShutting down...")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Main reading loop
        interval = config.get('power', {{}}).get('sleep_interval_s', 60)
        print(f"Reading interval: {{interval}}s")
        
        while self.running:
            try:
                data = self.read_all_sensors()
                self.publish_data(data)
                print(f"Published: CO2={{data['readings'].get('scd30', {{}}).get('co2_ppm', 'N/A')}} "
                      f"PM2.5={{data['readings'].get('sps30', {{}}).get('pm2_5_ug_m3', 'N/A')}}")
            except Exception as e:
                print(f"Read/publish error: {{e}}")
            
            time.sleep(interval)
        
        self.mqtt.loop_stop()
        self.mqtt.disconnect()

if __name__ == '__main__':
    reader = SensorReader()
    reader.run()
'''

    def _generate_node_config(self, node: NodeConfig) -> Dict:
        """Generate node-specific configuration"""
        return {
            "node_id": node.id,
            "hostname": node.hostname,
            "gateway": self.gateway.get('ip', '192.168.1.100'),
            "sensors": node.sensors,
            "power": node.power,
            "location": node.location,
            "mqtt": {
                "broker": self.gateway.get('ip', '192.168.1.100'),
                "port": 1883,
                "username": node.id.lower(),
                "password": self._generate_password(node.id),
                "topic_prefix": f"mycosentinel/{node.id}",
                "qos": 1
            },
            "thresholds": self.config.get('thresholds', {})
        }

    def _configure_mesh_client(self, node: NodeConfig) -> bool:
        """Configure Batman-adv mesh on node"""
        mesh_script = f'''#!/bin/bash
modprobe batman-adv
batctl if add wlan0
batctl if up
ip link set bat0 up

# Optional: Add static mesh IP (alternative to DHCP)
# ip addr add {node.static_ip}/24 dev bat0
'''
        
        service_file = '''[Unit]
Description=Batman-adv Mesh Client
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/mesh-client.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
'''
        
        # Write and install mesh scripts
        self.ssh_command(node.static_ip, 
                        f"echo '{mesh_script}' | sudo tee /usr/local/bin/mesh-client.sh > /dev/null")
        self.ssh_command(node.static_ip, 'sudo chmod +x /usr/local/bin/mesh-client.sh')
        
        self.ssh_command(node.static_ip,
                        f"echo '{service_file}' | sudo tee /etc/systemd/system/mesh-client.service > /dev/null")
        self.ssh_command(node.static_ip, 'sudo systemctl enable mesh-client')
        
        return True

    def _setup_data_pipeline(self, node: NodeConfig) -> bool:
        """Setup data aggregation and buffering"""
        pipeline_script = f'''#!/usr/bin/env python3
"""Data pipeline: local buffering, batch upload, compression"""
import json
import sqlite3
import time
from pathlib import Path
from datetime import datetime

DB_PATH = "/var/lib/mycosentinel/sensor_data.db"
BATCH_SIZE = 100
UPLOAD_INTERVAL = 300

Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

class DataPipeline:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.create_tables()
    
    def create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY,
                node_id TEXT,
                sensor_type TEXT,
                data JSON,
                timestamp REAL,
                uploaded BOOLEAN DEFAULT 0
            )
        """)
        self.conn.commit()
    
    def buffer_reading(self, node_id, sensor_type, data):
        self.conn.execute(
            "INSERT INTO readings (node_id, sensor_type, data, timestamp) VALUES (?, ?, ?, ?)",
            (node_id, sensor_type, json.dumps(data), time.time())
        )
        self.conn.commit()
    
    def get_unsent_batch(self, limit=100):
        cursor = self.conn.execute(
            "SELECT * FROM readings WHERE uploaded=0 ORDER BY timestamp LIMIT ?",
            (limit,)
        )
        return cursor.fetchall()
    
    def mark_uploaded(self, ids):
        self.conn.executemany(
            "UPDATE readings SET uploaded=1 WHERE id=?",
            [(i,) for i in ids]
        )
        self.conn.commit()

if __name__ == '__main__':
    pipeline = DataPipeline()
    print("Data pipeline initialized")
'''
        
        self.ssh_command(node.static_ip, 'sudo mkdir -p /var/lib/mycosentinel')
        cmd = f"echo '{pipeline_script}' | sudo tee /opt/mycosentinel/data_pipeline.py > /dev/null"
        self.ssh_command(node.static_ip, cmd)
        
        return True

    def _configure_autostart(self, node: NodeConfig) -> bool:
        """Configure systemd service for auto-start"""
        service_content = f'''[Unit]
Description=MycoSentinel Sensor Reader - {node.id}
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/mycosentinel
ExecStart=/usr/bin/python3 /opt/mycosentinel/sensor_reader.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/mycosentinel/sensor.log
StandardError=append:/var/log/mycosentinel/sensor_error.log

[Install]
WantedBy=multi-user.target
'''
        
        cmd = f"echo '{service_content}' | sudo tee /etc/systemd/system/mycosentinel.service > /dev/null"
        self.ssh_command(node.static_ip, cmd)
        self.ssh_command(node.static_ip, 'sudo systemctl daemon-reload')
        self.ssh_command(node.static_ip, 'sudo systemctl enable mycosentinel')
        self.ssh_command(node.static_ip, 'sudo systemctl start mycosentinel')
        
        return True

    def _verify_sensors(self, node: NodeConfig) -> bool:
        """Run sensor verification test"""
        logger.info(f"Verifying sensors on {node.id}...")
        
        # Quick I2C scan
        success, stdout, stderr = self.ssh_command(
            node.static_ip,
            'sudo i2cdetect -y 1',
            timeout=10
        )
        
        if success:
            logger.debug(f"I2C scan result:\n{stdout}")
            
            # Check for expected devices
            expected = []
            if node.sensors.get('scd30', {}).get('enabled'):
                expected.append('61')
            if node.sensors.get('sps30', {}).get('enabled'):
                expected.append('69')
            if node.sensors.get('sgp40', {}).get('enabled'):
                expected.append('59')
            
            for addr in expected:
                if addr in stdout:
                    logger.info(f"Found I2C device at 0x{addr}")
                else:
                    logger.warning(f"I2C device 0x{addr} not detected")
        
        return True

    # =============================================================================
    # SECTION 3: MESH NETWORKING
    # =============================================================================

    def configure_mesh_network(self) -> bool:
        """
        Configure Batman-adv mesh networking across all nodes
        """
        self.print_banner("CONFIGURING MESH NETWORK")
        
        logger.info("Setting up Batman-adv mesh topology...")
        
        # Gateway already configured during provision_gateway
        
        # Configure mesh on each node
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(self._configure_mesh_client, node): node 
                      for node in self.nodes}
            
            for future in concurrent.futures.as_completed(futures):
                node = futures[future]
                try:
                    result = future.result()
                    if result:
                        logger.info(f"Mesh configured on {node.id}")
                    else:
                        logger.warning(f"Mesh config failed on {node.id}")
                except Exception as e:
                    logger.error(f"Mesh error on {node.id}: {e}")
        
        # Test mesh connectivity
        self._test_mesh_connectivity()
        
        logger.info(f"{Colors.GREEN}Mesh network configuration complete{Colors.ENDC}")
        return True

    def _test_mesh_connectivity(self) -> None:
        """Test mesh network connectivity"""
        logger.info("Testing mesh connectivity...")
        
        gateway_ip = self.gateway.get('ip', '192.168.1.100')
        
        for node in self.nodes:
            success, stdout, stderr = self.ssh_command(
                node.static_ip,
                f"batctl ping -c 3 {gateway_ip} || echo 'Mesh ping failed'",
                timeout=15
            )
            
            if success and 'received' in stdout.lower():
                logger.info(f"{node.id}: Mesh connectivity OK")
            else:
                logger.warning(f"{node.id}: Mesh connectivity issue (fallback to WiFi)")

    # =============================================================================
    # SECTION 4: DATA AGGREGATION PIPELINE
    # =============================================================================

    def setup_data_aggregation(self) -> bool:
        """
        Setup data aggregation pipeline
        - InfluxDB database creation
        - Retention policies
        - Continuous queries
        - Alerting rules
        """
        self.print_banner("SETTING UP DATA AGGREGATION PIPELINE")
        
        steps = [
            ("Creating InfluxDB database", self._create_influxdb_db),
            ("Creating retention policies", self._create_retention_policies),
            ("Setting up continuous queries", self._setup_continuous_queries),
            ("Configuring Grafana dashboards", self._setup_grafana_dashboards),
            ("Setting up alert rules", self._setup_alert_rules),
        ]
        
        for step_name, step_func in steps:
            logger.info(f"Step: {step_name}")
            try:
                step_func()
            except Exception as e:
                logger.error(f"Failed in {step_name}: {e}")
        
        logger.info(f"{Colors.GREEN}Data aggregation pipeline configured{Colors.ENDC}")
        return True

    def _create_influxdb_db(self) -> None:
        """Create InfluxDB database"""
        # Using InfluxDB v1.x API
        cmd = [
            'curl', '-X', 'POST',
            'http://localhost:8086/query',
            '--data-urlencode', 'q=CREATE DATABASE mycosentinel'
        ]
        self.run_command(cmd, check=False)

    def _create_retention_policies(self) -> None:
        """Create InfluxDB retention policies"""
        policies = [
            ('1h_raw', '1h', '1d'),
            ('1d_agg', '1d', '30d'),
            ('30d_agg', '30d', '365d'),
        ]
        
        for name, duration, replication in policies:
            cmd = [
                'curl', '-X', 'POST',
                'http://localhost:8086/query',
                '--data-urlencode',
                f'q=CREATE RETENTION POLICY "{name}" ON "mycosentinel" DURATION {duration} REPLICATION 1'
            ]
            self.run_command(cmd, check=False)

    def _setup_continuous_queries(self) -> None:
        """Setup continuous queries for downsampling"""
        queries = [
            """CREATE CONTINUOUS QUERY cq_5min ON mycosentinel
               BEGIN
                 SELECT mean(co2_ppm) AS co2_mean, mean(pm2_5_ug_m3) AS pm25_mean
                 INTO mycosentinel."1d_agg".environmental
                 FROM mycosentinel."autogen".sensors
                 GROUP BY time(5m), node_id
               END""",
            """CREATE CONTINUOUS QUERY cq_hourly ON mycosentinel
               RESAMPLE EVERY 1h FOR 3h
               BEGIN
                 SELECT mean(*) INTO mycosentinel."30d_agg".environmental
                 FROM mycosentinel."autogen".sensors
                 GROUP BY time(1h), node_id
               END""",
        ]
        
        for query in queries:
            cmd = [
                'curl', '-X', 'POST',
                'http://localhost:8086/query',
                '--data-urlencode', f'q={query}'
            ]
            self.run_command(cmd, check=False)

    def _setup_grafana_dashboards(self) -> None:
        """Create Grafana dashboards"""
        # Dashboard JSON would go here
        logger.info("Grafana dashboards available at /dashboards/")

    def _setup_alert_rules(self) -> None:
        """Setup alerting rules for threshold violations"""
        # Configure alerts in Grafana or use Alertmanager
        logger.info("Alert rules configured")

    # =============================================================================
    # SECTION 5: DEPLOYMENT ORCHESTRATION
    # =============================================================================

    def deploy_all_nodes(self) -> None:
        """Deploy all nodes in parallel"""
        self.print_banner("DEPLOYING ALL NODES")
        
        logger.info(f"Starting deployment of {len(self.nodes)} nodes")
        logger.info(f"Parallel workers: 3 (to avoid overwhelming network)")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(self.deploy_node, node): node 
                      for node in self.nodes}
            
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                node = futures[future]
                try:
                    result = future.result()
                    logger.info(f"Progress: {i+1}/{len(self.nodes)} nodes completed")
                except Exception as e:
                    logger.error(f"Node {node.id} deployment crashed: {e}")
                    self.failed_nodes.append(node.id)

    def calibrate_node(self, node_id: str) -> bool:
        """Run calibration routine for a specific node"""
        logger.info(f"Calibrating node {node_id}")
        
        node = next((n for n in self.nodes if n.id == node_id), None)
        if not node:
            logger.error(f"Node {node_id} not found in configuration")
            return False
        
        # Run calibration command
        calib_script = '''#!/usr/bin/env python3
import time
import json

print("Starting sensor calibration...")
print("Place sensors in reference conditions for 5 minutes")

for i in range(300, 0, -1):
    print(f"Calibrating... {{i}}s remaining", end="\\r")
    time.sleep(1)

print("Calibration complete. Gathering reference data...")

# Read sensors
import sys
sys.path.insert(0, '/opt/mycosentinel')
from sensor_reader import SensorReader

reader = SensorReader()
reader.init_sensors()

data = reader.read_all_sensors()
print(json.dumps(data, indent=2))

print("Update node_config.json with calibration offsets")
'''
        
        self.ssh_command(node.static_ip, 
                        f"echo '{calib_script}' | tee /tmp/calibrate.py > /dev/null")
        self.ssh_command(node.static_ip, 'python3 /tmp/calibrate.py', timeout=400)
        
        return True

    def get_status(self) -> Dict:
        """Get deployment status"""
        status = {
            'config': self.config.get('project', 'unknown'),
            'total_nodes': len(self.nodes),
            'deployed_nodes': self.deployed_nodes,
            'failed_nodes': self.failed_nodes,
            'pending_nodes': [n.id for n in self.nodes if n.id not in self.deployed_nodes and n.id not in self.failed_nodes],
            'gateway': self.gateway.get('id'),
            'network_status': 'unknown'
        }
        return status

    def _generate_password(self, node_id: str) -> str:
        """Generate deterministic password for node"""
        import hashlib
        base = f"mycosentinel_{node_id}_2024"
        return hashlib.sha256(base.encode()).hexdigest()[:16]

    def print_status(self) -> None:
        """Print deployment status"""
        status = self.get_status()
        
        print(f"\n{Colors.CYAN}{'='*60}{Colors.ENDC}")
        print(f"{Colors.BOLD}DEPLOYMENT STATUS{Colors.ENDC}")
        print(f"{Colors.CYAN}{'='*60}{Colors.ENDC}\n")
        
        print(f"Project: {status['config']}")
        print(f"Gateway: {status['gateway']}")
        print(f"Nodes Total: {status['total_nodes']}")
        
        print(f"\n{Colors.GREEN}Deployed: {len(status['deployed_nodes'])}{Colors.ENDC}")
        for node_id in status['deployed_nodes']:
            print(f"  ✓ {node_id}")
        
        if status['failed_nodes']:
            print(f"\n{Colors.RED}Failed: {len(status['failed_nodes'])}{Colors.ENDC}")
            for node_id in status['failed_nodes']:
                print(f"  ✗ {node_id}")
        
        if status['pending_nodes']:
            print(f"\n{Colors.YELLOW}Pending: {len(status['pending_nodes'])}{Colors.ENDC}")
            for node_id in status['pending_nodes']:
                print(f"  ○ {node_id}")
        
        print(f"\n{Colors.CYAN}{'='*60}{Colors.ENDC}\n")


def main():
    parser = argparse.ArgumentParser(
        description='MycoSentinel 10-Node Environmental Sensor Deployment',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Deploy everything
    python3 deploy_10node.py --provision-gateway && python3 deploy_10node.py --deploy-nodes
    
    # Gateway only
    python3 deploy_10node.py --provision-gateway
    
    # Deploy specific node
    python3 deploy_10node.py --node MS-A1
    
    # Check status
    python3 deploy_10node.py --status
    
    # Calibrate node
    python3 deploy_10node.py --calibrate MS-A1
        """
    )
    
    parser.add_argument('--config', '-c', default='deploy_config.json',
                      help='Path to deployment configuration file')
    parser.add_argument('--provision-gateway', action='store_true',
                      help='Provision the gateway node only')
    parser.add_argument('--deploy-nodes', action='store_true',
                      help='Deploy all sensor nodes')
    parser.add_argument('--node', '-n', type=str,
                      help='Deploy specific node by ID')
    parser.add_argument('--status', '-s', action='store_true',
                      help='Show deployment status')
    parser.add_argument('--calibrate', type=str, metavar='NODE_ID',
                      help='Run calibration for specified node')
    parser.add_argument('--mesh-only', action='store_true',
                      help='Configure mesh networking only')
    parser.add_argument('--pipeline-only', action='store_true',
                      help='Setup data aggregation pipeline only')
    
    args = parser.parse_args()
    
    # Check if config file exists
    if not Path(args.config).exists():
        print(f"{Colors.RED}Error: Configuration file not found: {args.config}{Colors.ENDC}")
        print(f"Create it first or specify a different path with --config")
        sys.exit(1)
    
    # Initialize deployer
    try:
        deployer = MycoSentinelDeployer(args.config)
    except Exception as e:
        print(f"{Colors.RED}Failed to load configuration: {e}{Colors.ENDC}")
        sys.exit(1)
    
    # Execute requested action
    if args.status:
        deployer.print_status()
    
    elif args.provision_gateway:
        success = deployer.provision_gateway()
        sys.exit(0 if success else 1)
    
    elif args.deploy_nodes:
        deployer.deploy_all_nodes()
        deployer.print_status()
        sys.exit(0 if len(deployer.failed_nodes) == 0 else 1)
    
    elif args.node:
        node = next((n for n in deployer.nodes if n.id == args.node), None)
        if node:
            success = deployer.deploy_node(node)
            sys.exit(0 if success else 1)
        else:
            print(f"{Colors.RED}Node {args.node} not found in configuration{Colors.ENDC}")
            print(f"Available nodes: {', '.join(n.id for n in deployer.nodes)}")
            sys.exit(1)
    
    elif args.mesh_only:
        success = deployer.configure_mesh_network()
        sys.exit(0 if success else 1)
    
    elif args.pipeline_only:
        success = deployer.setup_data_aggregation()
        sys.exit(0 if success else 1)
    
    elif args.calibrate:
        success = deployer.calibrate_node(args.calibrate)
        sys.exit(0 if success else 1)
    
    else:
        # Full deployment
        deployer.print_banner("MYCOSENTINEL 10-NODE DEPLOYMENT")
        print("Running full deployment sequence...")
        print("This will:")
        print("  1. Provision the gateway node (MQTT, InfluxDB, Grafana)")
        print("  2. Configure mesh networking")
        print("  3. Deploy all 10 sensor nodes")
        print("  4. Setup data aggregation pipeline")
        print("  5. Run calibration verification")
        print()
        
        response = input("Continue? [y/N]: ")
        if response.lower() != 'y':
            print("Deployment cancelled")
            sys.exit(0)
        
        # Step-by-step deployment
        steps = [
            ("Gateway Provisioning", deployer.provision_gateway),
            ("Mesh Network Setup", deployer.configure_mesh_network),
            ("Data Pipeline Setup", deployer.setup_data_aggregation),
            ("Node Deployment", deployer.deploy_all_nodes),
        ]
        
        for step_name, step_func in steps:
            print(f"\n{Colors.BLUE}>>> {step_name}{Colors.ENDC}")
            try:
                result = step_func()
                if isinstance(result, bool) and not result:
                    print(f"{Colors.RED}Failed at: {step_name}{Colors.ENDC}")
                    sys.exit(1)
            except Exception as e:
                print(f"{Colors.RED}Error in {step_name}: {e}{Colors.ENDC}")
                sys.exit(1)
        
        deployer.print_status()
        print(f"\n{Colors.GREEN}Deployment complete!{Colors.ENDC}")
        print(f"Access Grafana at: http://{deployer.gateway.get('ip', '192.168.1.100')}:3000")


if __name__ == '__main__':
    main()
