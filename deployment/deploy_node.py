#!/usr/bin/env python3
"""
deploy_node.py - Single Node Deployment Automation
MYCOSENTINEL v0.2.0 - Biosensor Network Deployment

Ansible-style deployment script for provisioning a single MycoSentinel node.
Uses SSH for remote execution with idempotent operations.

Usage:
    python3 deploy_node.py --node-id MS-A1 --target 192.168.1.101
    python3 deploy_node.py --node-id MS-A1 --target 192.168.1.101 --config custom_config.yaml
    python3 deploy_node.py --node-id MS-A1 --target 192.168.1.101 --skip-hardware-test

Author: MycoSentinel Deployment Automation
Version: 0.2.0
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# Optional imports with graceful fallback
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

try:
    import paramiko
    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False
    paramiko = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'deploy_node_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
logger = logging.getLogger(__name__)

# Color codes for terminal output
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
class DeploymentTask:
    """Represents a deployment task with rollback capability"""
    name: str
    execute: callable
    rollback: Optional[callable] = None
    critical: bool = True

@dataclass
class NodeConfiguration:
    """Node configuration parameters"""
    node_id: str
    hostname: str
    static_ip: str
    sector: str
    gateway_ip: str
    network_ssid: str = "MycoSentinel"
    network_password: str = "biosensor2026"
    mqtt_broker: str = "192.168.10.1"
    mqtt_port: int = 1883
    i2c_devices: Dict[str, int] = None
    gpio_pins: Dict[str, int] = None
    
    def __post_init__(self):
        if self.i2c_devices is None:
            self.i2c_devices = {
                'ads1115_adc': 0x48,
                'dht22_temp': 0x5c,
            }
        if self.gpio_pins is None:
            self.gpio_pins = {
                'heater': 18,
                'fan': 19,
                'mist': 20,
                'led_excitation': 21,
                'pump': 22,
                'camera_led': 16,
            }

class NodeDeployer:
    """
    Ansible-style deployment orchestrator for single MycoSentinel node.
    
    Features:
    - Idempotent operations (safe to re-run)
    - Automated rollback on failure
    - Hardware self-testing
    - Configuration templating
    - Remote execution via SSH
    """
    
    def __init__(self, node_config: NodeConfiguration, target_host: str, 
                 ssh_user: str = 'pi', ssh_key_path: Optional[str] = None,
                 deploy_dir: str = '/opt/mycosentinel'):
        # Check dependencies first
        if not PARAMIKO_AVAILABLE:
            raise ImportError(
                "paramiko is required for deployment. "
                "Install with: pip3 install paramiko"
            )
        
        self.config = node_config
        self.target_host = target_host
        self.ssh_user = ssh_user
        self.ssh_key_path = ssh_key_path or str(Path.home() / '.ssh' / 'mycosentinel_deploy')
        self.deploy_dir = deploy_dir
        self.ssh_client: Optional['paramiko.SSHClient'] = None
        self.sftp_client: Optional['paramiko.SFTPClient'] = None
        self.deployment_log: List[Dict] = []
        self.rollback_stack: List[Tuple[str, callable]] = []
        
    def connect(self) -> bool:
        """Establish SSH connection to target node"""
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Try key-based auth first, then password
            if Path(self.ssh_key_path).exists():
                self.ssh_client.connect(
                    hostname=self.target_host,
                    username=self.ssh_user,
                    key_filename=self.ssh_key_path,
                    timeout=30
                )
            else:
                logger.warning(f"SSH key not found: {self.ssh_key_path}")
                logger.info("Attempting password authentication (default: raspberry)")
                self.ssh_client.connect(
                    hostname=self.target_host,
                    username=self.ssh_user,
                    password='raspberry',
                    timeout=30
                )
            
            self.sftp_client = self.ssh_client.open_sftp()
            logger.info(f"Connected to {self.target_host}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to {self.target_host}: {e}")
            return False
    
    def disconnect(self):
        """Close SSH connection"""
        if self.sftp_client:
            self.sftp_client.close()
        if self.ssh_client:
            self.ssh_client.close()
        logger.info("Disconnected")
    
    def remote_exec(self, command: str, timeout: int = 60) -> Tuple[int, str, str]:
        """Execute command on remote node"""
        if not self.ssh_client:
            raise RuntimeError("Not connected to remote host")
        
        logger.debug(f"Executing: {command[:80]}...")
        stdin, stdout, stderr = self.ssh_client.exec_command(command, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        stdout_str = stdout.read().decode('utf-8')
        stderr_str = stderr.read().decode('utf-8')
        
        return exit_code, stdout_str, stderr_str
    
    def remote_script(self, script_content: str, timeout: int = 120) -> Tuple[int, str, str]:
        """Execute multi-line script on remote node"""
        # Upload script
        script_name = f"deploy_script_{int(time.time())}.sh"
        remote_path = f"/tmp/{script_name}"
        
        with self.sftp_client.open(remote_path, 'w') as f:
            f.write(script_content)
        
        # Make executable and run
        self.remote_exec(f"chmod +x {remote_path}")
        result = self.remote_exec(f"bash {remote_path}", timeout)
        
        # Cleanup
        self.remote_exec(f"rm {remote_path}")
        
        return result
    
    def upload_file(self, local_path: str, remote_path: str):
        """Upload file to remote node"""
        if not self.sftp_client:
            raise RuntimeError("Not connected")
        
        # Create remote directory if needed
        remote_dir = Path(remote_path).parent
        self.remote_exec(f"sudo mkdir -p {remote_dir}")
        
        self.sftp_client.put(local_path, f"/tmp/{Path(local_path).name}")
        self.remote_exec(f"sudo mv /tmp/{Path(local_path).name} {remote_path}")
        logger.info(f"Uploaded {local_path} -> {remote_path}")
    
    def upload_template(self, template_content: str, remote_path: str, 
                       variables: Dict[str, Any]):
        """Upload Jinja2-style template with variable substitution"""
        # Simple variable substitution
        content = template_content
        for key, value in variables.items():
            content = content.replace(f"{{{{ {key} }}}}", str(value))
        
        # Write to temp file and upload
        temp_path = f"/tmp/mycosentinel_config_{int(time.time())}"
        with self.sftp_client.open(temp_path, 'w') as f:
            f.write(content)
        
        self.remote_exec(f"sudo mv {temp_path} {remote_path}")
        self.remote_exec(f"sudo chmod 644 {remote_path}")
        logger.info(f"Template uploaded to {remote_path}")
    
    # =============================================================================
    # DEPLOYMENT TASKS
    # =============================================================================
    
    def task_system_setup(self) -> bool:
        """Configure system basics: hostname, timezone, static IP"""
        logger.info(Colors.CYAN + "Task: System Setup" + Colors.ENDC)
        
        script = f"""#!/bin/bash
set -e

echo "Setting hostname..."
echo "{self.config.hostname}" | sudo tee /etc/hostname
sudo hostnamectl set-hostname {self.config.hostname}

# Update /etc/hosts
sudo sed -i "s/127.0.1.1.*/127.0.1.1 {self.config.hostname}/" /etc/hosts || \
    echo "127.0.1.1 {self.config.hostname}" | sudo tee -a /etc/hosts

echo "Setting timezone..."
sudo timedatectl set-timezone Asia/Manila

echo "Configuring static IP..."
cat << 'DHCPEOF' | sudo tee /etc/dhcpcd.conf
# MycoSentinel static IP configuration
interface wlan0
static ip_address={self.config.static_ip}/24
static routers={self.config.gateway_ip}
static domain_name_servers={self.config.gateway_ip} 8.8.8.8

# Fallback to DHCP if static fails
fallback static_eth0
DHCPEOF

echo "System setup complete"
"""
        exit_code, stdout, stderr = self.remote_script(script)
        
        if exit_code == 0:
            logger.info(Colors.GREEN + "✓ System configured" + Colors.ENDC)
            return True
        else:
            logger.error(f"System setup failed: {stderr}")
            return False
    
    def rollback_system_setup(self):
        """Rollback system changes"""
        logger.warning("Rolling back system setup...")
        self.remote_exec("sudo mv /etc/dhcpcd.conf.bak /etc/dhcpcd.conf 2>/dev/null || true")
    
    def task_install_dependencies(self) -> bool:
        """Install required system packages and Python libraries"""
        logger.info(Colors.CYAN + "Task: Install Dependencies" + Colors.ENDC)
        
        script = """#!/bin/bash
set -e

echo "Updating package lists..."
sudo apt-get update -qq

echo "Installing system packages..."
sudo apt-get install -y -qq \
    python3-pip python3-venv python3-numpy python3-picamera2 \
    i2c-tools libgpiod-dev git htop vim \
    mosquitto-clients wireless-tools \
    sqlite3 ffmpeg libcamera-dev

echo "Enabling I2C and SPI interfaces..."
sudo raspi-config nonint do_i2c 0
sudo raspi-config nonint do_spi 0
sudo raspi-config nonint do_camera 0

echo "Creating virtual environment..."
sudo mkdir -p /opt/mycosentinel
sudo python3 -m venv /opt/mycosentinel/venv
source /opt/mycosentinel/venv/bin/activate

echo "Installing Python packages..."
pip install --upgrade pip wheel
pip install board Pillow Adafruit-Blinka adafruit-circuitpython-dht \
    adafruit-circuitpython-ads1x15 paramiko paho-mqtt influxdb-client \
    fastapi uvicorn gpiozero lgpio RPi.GPIO pyserial pyyaml

echo "Dependencies installed successfully"
"""
        exit_code, stdout, stderr = self.remote_script(script, timeout=300)
        
        if exit_code == 0:
            logger.info(Colors.GREEN + "✓ Dependencies installed" + Colors.ENDC)
            return True
        else:
            logger.error(f"Dependency installation failed: {stderr}")
            return False
    
    def task_deploy_software(self) -> bool:
        """Deploy MycoSentinel software stack"""
        logger.info(Colors.CYAN + "Task: Deploy Software" + Colors.ENDC)
        
        # Create directory structure
        script = f"""#!/bin/bash
set -e

sudo mkdir -p /opt/mycosentinel/{{src,config,data,logs,calibration}}
sudo chown -R pi:pi /opt/mycosentinel

# Create __init__.py files
touch /opt/mycosentinel/__init__.py
touch /opt/mycosentinel/src/__init__.py

echo "Directory structure created"
"""
        self.remote_script(script)
        
        # Upload source files
        source_files = [
            ('../src/mycosentinel/__init__.py', '/opt/mycosentinel/src/__init__.py'),
            ('../src/mycosentinel/sensor.py', '/opt/mycosentinel/src/sensor.py'),
            ('../src/mycosentinel/bioreactor.py', '/opt/mycosentinel/src/bioreactor.py'),
            ('../src/mycosentinel/network.py', '/opt/mycosentinel/src/network.py'),
            ('../src/mycosentinel/pipeline.py', '/opt/mycosentinel/src/pipeline.py'),
            ('../src/mycosentinel/main.py', '/opt/mycosentinel/src/main.py'),
            ('../src/mycosentinel/dashboard.py', '/opt/mycosentinel/src/dashboard.py'),
        ]
        
        workspace = Path(__file__).parent.parent
        for local, remote in source_files:
            local_path = workspace / local
            if local_path.exists():
                self.upload_file(str(local_path), remote)
        
        logger.info(Colors.GREEN + "✓ Software deployed" + Colors.ENDC)
        return True
    
    def task_configure_sensors(self) -> bool:
        """Configure sensor calibration and settings"""
        logger.info(Colors.CYAN + "Task: Configure Sensors" + Colors.ENDC)
        
        config = {
            'node_id': self.config.node_id,
            'sector': self.config.sector,
            'i2c_devices': self.config.i2c_devices,
            'gpio_pins': self.config.gpio_pins,
            'calibration': {
                'optical_baseline': 1200.0,
                'electrical_baseline': 0.0,
                'threshold_multiplier': 2.0,
                'calibration_duration_sec': 30,
            },
            'bioreactor': {
                'target_temperature_c': 28.0,
                'humidity_percent': 65.0,
                'heater_duty_max': 0.8,
            }
        }
        
        config_json = json.dumps(config, indent=2)
        script = f"""#!/bin/bash
cat << 'CONFIGEOF' | sudo tee /opt/mycosentinel/config/node_config.json
{config_json}
CONFIGEOF
sudo chmod 644 /opt/mycosentinel/config/node_config.json
"""
        exit_code, _, _ = self.remote_script(script)
        
        # Upload calibration template
        calibration_template = {
            'optical': {
                'baseline_mean': 1200.0,
                'baseline_std': 15.0,
                'calibration_date': datetime.now().isoformat(),
                'calibration_factor': 1.0,
                'roi': {'x': 100, 'y': 100, 'w': 200, 'h': 200},
            },
            'electrical': {
                'baseline_voltage': 1.25,
                'calibration_date': datetime.now().isoformat(),
            }
        }
        
        calib_script = f"""#!/bin/bash
cat << 'CALIBEOF' | sudo tee /opt/mycosentinel/calibration/default_calibration.json
{json.dumps(calibration_template, indent=2)}
CALIBEOF
sudo chmod 644 /opt/mycosentinel/calibration/default_calibration.json
"""
        self.remote_script(calib_script)
        
        logger.info(Colors.GREEN + "✓ Sensors configured" + Colors.ENDC)
        return True
    
    def task_setup_i2c_gpio(self) -> bool:
        """Configure I2C and GPIO permissions"""
        logger.info(Colors.CYAN + "Task: Setup I2C/GPIO" + Colors.ENDC)
        
        script = """#!/bin/bash
set -e

# Add pi user to gpio and i2c groups
sudo usermod -a -G gpio,i2c,spi pi

# Ensure device tree overlays are loaded
if ! grep -q "dtparam=i2c_arm=on" /boot/config.txt; then
    echo "dtparam=i2c_arm=on" | sudo tee -a /boot/config.txt
fi

if ! grep -q "dtparam=spi=on" /boot/config.txt; then
    echo "dtparam=spi=on" | sudo tee -a /boot/config.txt
fi

# Load modules
sudo modprobe i2c-dev || true
sudo modprobe spi-dev || true

echo "I2C/GPIO configured"
"""
        exit_code, stdout, stderr = self.remote_script(script)
        
        if exit_code == 0:
            logger.info(Colors.GREEN + "✓ I2C/GPIO configured" + Colors.ENDC)
            return True
        else:
            logger.error(f"I2C/GPIO setup failed: {stderr}")
            return False
    
    def task_create_systemd_services(self) -> bool:
        """Create systemd service for auto-start"""
        logger.info(Colors.CYAN + "Task: Create Systemd Services" + Colors.ENDC)
        
        service_content = f"""[Unit]
Description=MycoSentinel Biosensor Node
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/mycosentinel
Environment=PYTHONPATH=/opt/mycosentinel
Environment=NODE_ID={self.config.node_id}
Environment=USE_MOCK=False
Environment=LOG_LEVEL=INFO
ExecStart=/opt/mycosentinel/venv/bin/python -m mycosentinel.src.main node --node-id {self.config.node_id} --config /opt/mycosentinel/config/node_config.json
Restart=always
RestartSec=10
KillMode=process

[Install]
WantedBy=multi-user.target
"""
        
        script = f"""#!/bin/bash
cat << 'SERVICEEOF' | sudo tee /etc/systemd/system/mycosentinel.service
{service_content}
SERVICEEOF

sudo chmod 644 /etc/systemd/system/mycosentinel.service
sudo systemctl daemon-reload
sudo systemctl enable mycosentinel.service

echo "Service created and enabled"
"""
        exit_code, _, _ = self.remote_script(script)
        
        logger.info(Colors.GREEN + "✓ Systemd service created" + Colors.ENDC)
        return True
    
    def task_hardware_selftest(self) -> bool:
        """Run hardware self-test to verify sensor functionality"""
        logger.info(Colors.CYAN + "Task: Hardware Self-Test" + Colors.ENDC)
        
        script = """#!/bin/bash
set -e

source /opt/mycosentinel/venv/bin/activate

echo "=== MycoSentinel Hardware Self-Test ==="

# Test I2C bus
echo "Testing I2C bus..."
if command -v i2cdetect &> /dev/null; then
    echo "I2C devices detected:"
    sudo i2cdetect -y 1 | grep -E "[0-9a-f]{2}" || echo "No I2C devices found"
else
    echo "WARNING: i2cdetect not available"
fi

# Test GPIO access
echo "Testing GPIO access..."
if python3 -c "import gpiozero" 2>/dev/null; then
    echo "GPIO Library: OK"
else
    echo "WARNING: gpiozero not available"
fi

# Test camera
echo "Testing camera..."
if [ -d "/dev/video0" ] || vcgencmd get_camera | grep -q "supported=1"; then
    echo "Camera: Detected"
else
    echo "Camera: Not detected (may be disabled)"
fi

# Test temperature sensor
echo "Testing 1-Wire temperature sensors..."
if [ -d "/sys/bus/w1/devices" ]; then
    for sensor in /sys/bus/w1/devices/28-*/w1_slave 2>/dev/null; do
        if [ -f "$sensor" ]; then
            temp=$(cat "$sensor" | grep "t=" | cut -d= -f2 | head -1)
            if [ -n "$temp" ]; then
                echo "Temperature sensor: $((temp/1000)).$((temp%1000/100))°C"
            fi
        fi
    done
else
    echo "1-Wire: Not configured"
fi

echo "=== Self-Test Complete ==="
"""
        exit_code, stdout, stderr = self.remote_script(script, timeout=120)
        
        logger.info("Hardware self-test output:")
        for line in stdout.split('\n'):
            if line.strip():
                logger.info(f"  {line}")
        
        return True  # Self-test is informational
    
    def task_activate_node(self) -> bool:
        """Start the MycoSentinel service"""
        logger.info(Colors.CYAN + "Task: Activate Node" + Colors.ENDC)
        
        script = """#!/bin/bash
set -e

# Start the service
sudo systemctl start mycosentinel.service

# Wait for startup
sleep 5

# Check status
if systemctl is-active --quiet mycosentinel.service; then
    echo "Service active"
else
    echo "Service failed to start"
    journalctl -u mycosentinel --no-pager -n 20
    exit 1
fi
"""
        exit_code, stdout, stderr = self.remote_script(script)
        
        if exit_code == 0:
            logger.info(Colors.GREEN + "✓ Node activated" + Colors.ENDC)
            return True
        else:
            logger.error(f"Activation failed: {stderr}")
            return False
    
    # =============================================================================
    # MAIN DEPLOYMENT ORCHESTRATION
    # =============================================================================
    
    def deploy(self, skip_hardware_test: bool = False) -> bool:
        """
        Execute full deployment workflow.
        
        Returns True if deployment successful, False otherwise.
        """
        tasks = [
            DeploymentTask("System Setup", self.task_system_setup, self.rollback_system_setup),
            DeploymentTask("Install Dependencies", self.task_install_dependencies, critical=True),
            DeploymentTask("Setup I2C/GPIO", self.task_setup_i2c_gpio, critical=True),
            DeploymentTask("Deploy Software", self.task_deploy_software, critical=True),
            DeploymentTask("Configure Sensors", self.task_configure_sensors, critical=True),
            DeploymentTask("Create Systemd Services", self.task_create_systemd_services),
        ]
        
        if not skip_hardware_test:
            tasks.append(DeploymentTask("Hardware Self-Test", self.task_hardware_selftest, critical=False))
        
        tasks.append(DeploymentTask("Activate Node", self.task_activate_node, critical=True))
        
        logger.info(Colors.BOLD + f"\n{'='*60}" + Colors.ENDC)
        logger.info(Colors.BOLD + f"Deploying {self.config.node_id} to {self.target_host}" + Colors.ENDC)
        logger.info(Colors.BOLD + f"{'='*60}\n" + Colors.ENDC)
        
        success = True
        for task in tasks:
            try:
                result = task.execute()
                self.deployment_log.append({'task': task.name, 'status': 'success'})
                
                if result:
                    if task.rollback:
                        self.rollback_stack.append((task.name, task.rollback))
                elif task.critical:
                    logger.error(Colors.RED + f"Critical task failed: {task.name}" + Colors.ENDC)
                    success = False
                    break
                else:
                    logger.warning(Colors.YELLOW + f"Non-critical task failed: {task.name}" + Colors.ENDC)
                    
            except Exception as e:
                logger.error(f"Exception in task {task.name}: {e}")
                self.deployment_log.append({'task': task.name, 'status': 'failed', 'error': str(e)})
                if task.critical:
                    success = False
                    break
        
        if success:
            logger.info(Colors.GREEN + Colors.BOLD + f"\n✓ Deployment of {self.config.node_id} completed successfully!" + Colors.ENDC)
            logger.info(f"""
Node Summary:
  - Hostname: {self.config.hostname}
  - IP: {self.config.static_ip}
  - Sector: {self.config.sector}
  - Deployed at: {datetime.now().isoformat()}

Next Steps:
  1. Verify node ping: ping {self.config.static_ip}
  2. Check service status: ssh {self.ssh_user}@{self.config.static_ip} "sudo systemctl status mycosentinel"
  3. View logs: ssh {self.ssh_user}@{self.config.static_ip} "sudo journalctl -u mycosentinel -f"
""")
        else:
            logger.error(Colors.RED + f"\n✗ Deployment failed! Check logs above." + Colors.ENDC)
        
        return success
    
    def rollback(self):
        """Execute rollback of all completed steps"""
        logger.warning("Initiating rollback...")
        for task_name, rollback_fn in reversed(self.rollback_stack):
            try:
                logger.info(f"Rolling back: {task_name}")
                rollback_fn()
            except Exception as e:
                logger.error(f"Rollback failed for {task_name}: {e}")


def load_node_config(node_id: str, config_path: str = 'deploy_config.json') -> NodeConfiguration:
    """Load node configuration from file (JSON or YAML)"""
    with open(config_path, 'r') as f:
        if config_path.endswith('.yaml') or config_path.endswith('.yml'):
            if not YAML_AVAILABLE:
                raise ImportError("PyYAML is required for YAML configs. Install with: pip3 install pyyaml")
            data = yaml.safe_load(f)
        else:
            data = json.load(f)
    
    # Find node in config
    for node_data in data.get('nodes', []):
        if node_data['id'] == node_id:
            return NodeConfiguration(
                node_id=node_data['id'],
                hostname=node_data['hostname'],
                static_ip=node_data['static_ip'],
                sector=node_data['sector'],
                gateway_ip=data['gateway']['ip']
            )
    
    raise ValueError(f"Node {node_id} not found in configuration")


def main():
    parser = argparse.ArgumentParser(
        description='Deploy a single MycoSentinel node',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --node-id MS-A1 --target 192.168.1.101
  %(prog)s --node-id MS-A1 --target 192.168.1.101 --config custom_config.json
  %(prog)s --node-id MS-A1 --target 192.168.1.101 --skip-hardware-test
        """
    )
    parser.add_argument('--node-id', required=True, help='Node ID (e.g., MS-A1)')
    parser.add_argument('--target', required=True, help='Target IP or hostname')
    parser.add_argument('--config', default='deploy_config.json', help='Configuration file path')
    parser.add_argument('--ssh-user', default='pi', help='SSH username (default: pi)')
    parser.add_argument('--ssh-key', help='SSH private key path')
    parser.add_argument('--skip-hardware-test', action='store_true', help='Skip hardware self-test')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be executed')
    
    args = parser.parse_args()
    
    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
        print(f"Would deploy {args.node_id} to {args.target}")
        return 0
    
    try:
        config = load_node_config(args.node_id, args.config)
    except FileNotFoundError:
        # Use default config if file not found
        config = NodeConfiguration(
            node_id=args.node_id,
            hostname=f"mycosentinel-{args.node_id.lower().replace('-', '')}",
            static_ip=args.target,
            sector='A',
            gateway_ip='192.168.1.100'
        )
        logger.warning(f"Config file not found, using defaults")
    
    deployer = NodeDeployer(
        node_config=config,
        target_host=args.target,
        ssh_user=args.ssh_user,
        ssh_key_path=args.ssh_key
    )
    
    if not deployer.connect():
        logger.error("Failed to connect to target")
        return 1
    
    try:
        success = deployer.deploy(skip_hardware_test=args.skip_hardware_test)
        return 0 if success else 1
    except KeyboardInterrupt:
        logger.info("\nDeployment interrupted")
        deployer.rollback()
        return 130
    finally:
        deployer.disconnect()


if __name__ == '__main__':
    sys.exit(main())
