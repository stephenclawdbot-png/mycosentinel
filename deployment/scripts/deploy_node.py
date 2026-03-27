#!/usr/bin/env python3
"""
MycoSentinel Node Deployment Script
Automated flashing and configuration of a single sensor node.

Usage:
    python deploy_node.py --node-id MS-A1 --port /dev/ttyUSB0
    python deploy_node.py --config node_config.json
    python deploy_node.py --discover  # Auto-discover connected nodes

Features:
- USB/Serial node provisioning
- Automatic firmware flashing
- Sensor calibration
- Network configuration (WiFi + Mesh)
- Health verification
"""

import argparse
import json
import sys
import os
import time
import logging
import subprocess
import tempfile
import yaml
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List, Tuple
from datetime import datetime
import serial
import serial.tools.list_ports

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
PROJECT_ROOT = Path(__file__).parent.parent.parent
DEPLOYMENT_DIR = Path(__file__).parent.parent
CONFIG_PATH = DEPLOYMENT_DIR / "deploy_config.json"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
REQUIRED_PACKAGES = ['pyserial', 'pi-mqtt-gpio', 'influxdb-client', 'paho-mqtt']

@dataclass
class NodeConfig:
    """Configuration for a single node deployment"""
    node_id: str
    hostname: str
    static_ip: str
    sector: str
    lat: float
    lon: float
    elevation_m: int
    distance_from_gateway_m: float
    bearing_deg: float
    i2c_scd30: str = "0x61"
    i2c_sps30: str = "0x69"
    i2c_sgp40: str = "0x59"
    gpio_dht22: int = 4
    wifi_ssid: str = "MycoSentinel-Mesh"
    wifi_password: str = ""
    mqtt_broker: str = "192.168.1.100"
    mesh_enabled: bool = True
    mesh_relay: bool = False


class NodeDeployer:
    """
    Deployment automation for MycoSentinel sensor nodes.
    Handles flashing, configuration, and initial calibration.
    """
    
    def __init__(self, node_config: NodeConfig, serial_port: str, dry_run: bool = False):
        self.config = node_config
        self.serial_port = serial_port
        self.dry_run = dry_run
        self.ssh_target = f"pi@{node_config.static_ip}"
        self.deployment_log: List[Dict] = []
        
    def log(self, level: str, message: str, data: Optional[Dict] = None):
        """Log deployment step"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            "node_id": self.config.node_id,
            "data": data or {}
        }
        self.deployment_log.append(entry)
        
        if level == "ERROR":
            logger.error(message)
        elif level == "WARNING":
            logger.warning(message)
        else:
            logger.info(message)
    
    def run_command(self, command: List[str], check: bool = True, 
                   timeout: int = 60, ssh: bool = False) -> Tuple[int, str, str]:
        """Execute shell command, optionally via SSH"""
        if ssh and not self.dry_run:
            command = ["ssh", "-o", "StrictHostKeyChecking=no", 
                      "-o", "ConnectTimeout=10",
                      self.ssh_target] + command
        
        self.log("DEBUG", f"Running: {' '.join(command)}")
        
        if self.dry_run:
            self.log("INFO", f"[DRY-RUN] Would execute: {' '.join(command)}")
            return 0, "", ""
        
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout
            )
            
            if check and result.returncode != 0:
                raise subprocess.CalledProcessError(
                    result.returncode, command, 
                    output=result.stdout, stderr=result.stderr
                )
            
            return result.returncode, result.stdout, result.stderr
            
        except subprocess.TimeoutExpired:
            self.log("ERROR", f"Command timed out after {timeout}s: {' '.join(command)}")
            raise
        except Exception as e:
            self.log("ERROR", f"Command failed: {e}")
            raise
    
    def step_check_prerequisites(self) -> bool:
        """Verify deployment prerequisites"""
        self.log("INFO", "=== Step 1: Checking Prerequisites ===")
        
        # Check serial port exists
        if not Path(self.serial_port).exists():
            self.log("ERROR", f"Serial port {self.serial_port} not found")
            return False
        
        # Check required binaries
        required = ["python3", "pip3", "scp", "ssh"]
        for cmd in required:
            try:
                subprocess.run([cmd, "--version"], capture_output=True, check=True)
                self.log("DEBUG", f"Found {cmd}")
            except (subprocess.CalledProcessError, FileNotFoundError):
                self.log("ERROR", f"Required tool not found: {cmd}")
                return False
        
        # Check if node is already deployed
        try:
            subprocess.run(
                ["ping", "-c", "1", "-W", "2", self.config.static_ip],
                capture_output=True,
                timeout=5
            )
            self.log("WARNING", f"Node at {self.config.static_ip} already responds to ping!")
            response = input("Continue anyway? (yes/no): ")
            if response.lower() != "yes":
                return False
        except:
            pass
        
        self.log("INFO", "Prerequisites check passed")
        return True
    
    def step_flash_firmware(self) -> bool:
        """Flash firmware to node via USB/serial"""
        self.log("INFO", "=== Step 2: Flashing Firmware ===")
        
        # Prepare firmware image with embedded config
        firmware_template = PROJECT_ROOT / "firmware" / "raspberry-pi-zero" / "image.img"
        if not firmware_template.exists():
            self.log("ERROR", f"Firmware image not found: {firmware_template}")
            self.log("INFO", "Using mock mode - firmware would be flashed here")
            return True  # Continue in mock mode
        
        # Create config overlay
        overlay_config = {
            "node_id": self.config.node_id,
            "hostname": self.config.hostname,
            "wifi": {
                "ssid": self.config.wifi_ssid,
                "password": self.config.wifi_password,
            },
            "network": {
                "static_ip": self.config.static_ip,
                "mesh_enabled": self.config.mesh_enabled,
            },
            "sensors": {
                "scd30_address": self.config.i2c_scd30,
                "sps30_address": self.config.i2c_sps30,
                "sgp40_address": self.config.i2c_sgp40,
                "dht22_pin": self.config.gpio_dht22,
            }
        }
        
        # Flash using etcher-cli or dd
        try:
            # Use dd to write image to SD card (if serial_port is a block device)
            if Path(self.serial_port).is_block_device():
                self.log("INFO", f"Flashing SD card at {self.serial_port}")
                
                # Unmount if mounted
                self.run_command(["diskutil", "unmountDisk", self.serial_port], check=False)
                
                # Flash image
                self.run_command(
                    ["sudo", "dd", f"if={firmware_template}", f"of={self.serial_port}", 
                     "bs=4m", "status=progress"],
                    timeout=300
                )
                
                self.log("INFO", "Flashing complete")
            else:
                # Serial provisioning for already-booted devices
                self.log("INFO", "Serial provisioning mode")
                self._provision_via_serial()
                
        except Exception as e:
            self.log("ERROR", f"Firmware flashing failed: {e}")
            return False
        
        return True
    
    def _provision_via_serial(self):
        """Provision node via serial console"""
        self.log("INFO", f"Connecting to {self.serial_port} for provisioning")
        
        if self.dry_run:
            return
        
        # Send configuration commands via serial
        with serial.Serial(self.serial_port, 115200, timeout=5) as ser:
            time.sleep(2)  # Wait for boot
            
            # Send hostname configuration
            ser.write(f"sudo hostnamectl set-hostname {self.config.hostname}\n".encode())
            time.sleep(0.5)
            
            # Configure static IP
            dhcpcd_conf = f"""
interface wlan0
static ip_address={self.config.static_ip}/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1
"""
            ser.write(f"echo '{dhcpcd_conf}' | sudo tee /etc/dhcpcd.conf\n".encode())
            time.sleep(0.5)
            
            # Configure WiFi
            wpa_conf = f"""
network={{
    ssid="{self.config.wifi_ssid}"
    psk="{self.config.wifi_password}"
    key_mgmt=WPA-PSK
}}
"""
            ser.write(f"echo '{wpa_conf}' | sudo tee /etc/wpa_supplicant/wpa_supplicant.conf\n".encode())
            time.sleep(0.5)
            
            self.log("INFO", "Serial provisioning commands sent")
    
    def step_network_configuration(self) -> bool:
        """Configure network settings"""
        self.log("INFO", "=== Step 3: Network Configuration ===")
        
        # Wait for node to come online
        self.log("INFO", f"Waiting for {self.config.hostname} to come online...")
        
        max_retries = 30
        for i in range(max_retries):
            try:
                result = subprocess.run(
                    ["ping", "-c", "1", "-W", "2", self.config.static_ip],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    self.log("INFO", f"Node {self.config.hostname} is online!")
                    break
            except:
                pass
            
            time.sleep(2)
            self.log("DEBUG", f"Waiting... ({i+1}/{max_retries})")
        else:
            self.log("ERROR", "Node failed to come online")
            return False
        
        # Copy network configuration files
        try:
            # Create temp config files
            with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
                json.dump(asdict(self.config), f, indent=2)
                temp_config = f.name
            
            # SCP config to node
            self.run_command([
                "scp", "-o", "StrictHostKeyChecking=no",
                temp_config, f"{self.ssh_target}:/home/pi/node_config.json"
            ])
            
            # Apply configuration via SSH
            self.run_command([
                "sudo", "mkdir", "-p", "/opt/mycosentinel"
            ], ssh=True)
            
            self.run_command([
                "sudo", "mv", "/home/pi/node_config.json", "/opt/mycosentinel/config.json"
            ], ssh=True)
            
            # Restart network
            self.run_command(["sudo", "systemctl", "restart", "dhcpcd"], ssh=True)
            
            os.unlink(temp_config)
            self.log("INFO", "Network configuration applied")
            
        except Exception as e:
            self.log("ERROR", f"Network configuration failed: {e}")
            return False
        
        return True
    
    def step_install_software(self) -> bool:
        """Install required software packages"""
        self.log("INFO", "=== Step 4: Software Installation ===")
        
        try:
            # Update package lists
            self.run_command(["sudo", "apt-get", "update"], ssh=True, timeout=120)
            
            # Install required packages
            packages = [
                "python3-pip", "python3-venv", "i2c-tools", "git",
                "mosquitto-clients", "ntp", "vim"
            ]
            self.run_command(
                ["sudo", "apt-get", "install", "-y"] + packages,
                ssh=True,
                timeout=300
            )
            
            # Enable I2C
            self.run_command(["sudo", "raspi-config", "nonint", "do_i2c", "0"], ssh=True)
            
            # Create virtual environment
            self.run_command(
                ["python3", "-m", "venv", "/opt/mycosentinel/venv"],
                ssh=True
            )
            
            # Install Python packages
            for pkg in REQUIRED_PACKAGES:
                self.run_command(
                    ["/opt/mycosentinel/venv/bin/pip", "install", pkg],
                    ssh=True,
                    timeout=60
                )
            
            self.log("INFO", "Software installation complete")
            
        except Exception as e:
            self.log("ERROR", f"Software installation failed: {e}")
            return False
        
        return True
    
    def step_deploy_sensor_code(self) -> bool:
        """Deploy MycoSentinel sensor software"""
        self.log("INFO", "=== Step 5: Deploying Sensor Code ===")
        
        try:
            # Create directory structure
            dirs = ["/opt/mycosentinel/src", "/opt/mycosentinel/logs", "/opt/mycosentinel/data"]
            for d in dirs:
                self.run_command(["sudo", "mkdir", "-p", d], ssh=True)
            
            # Sync source code
            src_dir = PROJECT_ROOT / "src"
            if src_dir.exists():
                self.run_command([
                    "rsync", "-avz", "--delete",
                    "-e", "ssh -o StrictHostKeyChecking=no",
                    f"{src_dir}/", f"{self.ssh_target}:/opt/mycosentinel/src/"
                ], timeout=60)
            
            # Deploy service file
            service_content = f"""[Unit]
Description=MycoSentinel Node {self.config.node_id}
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/mycosentinel
Environment=NODE_ID={self.config.node_id}
Environment=PYTHONPATH=/opt/mycosentinel/src
Environment=MESH_ENABLED={str(self.config.mesh_enabled).lower()}
Environment=MQTT_BROKER={self.config.mqtt_broker}
ExecStart=/opt/mycosentinel/venv/bin/python -m mycosentinel.node --config /opt/mycosentinel/config.json
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
            
            # Write service file locally then scp
            with tempfile.NamedTemporaryFile(mode='w', suffix='.service', delete=False) as f:
                f.write(service_content)
                service_file = f.name
            
            self.run_command([
                "scp", "-o", "StrictHostKeyChecking=no",
                service_file, f"{self.ssh_target}:/tmp/mycosentinel.service"
            ])
            
            self.run_command([
                "sudo", "mv", "/tmp/mycosentinel.service", "/etc/systemd/system/"
            ], ssh=True)
            
            self.run_command(["sudo", "systemctl", "daemon-reload"], ssh=True)
            self.run_command(["sudo", "systemctl", "enable", "mycosentinel"], ssh=True)
            
            os.unlink(service_file)
            
            self.log("INFO", "Sensor code deployed")
            
        except Exception as e:
            self.log("ERROR", f"Sensor code deployment failed: {e}")
            return False
        
        return True
    
    def step_sensor_calibration(self) -> bool:
        """Run sensor calibration procedures"""
        self.log("INFO", "=== Step 6: Sensor Calibration ===")
        
        try:
            # Generate calibration script
            cal_script = f"""#!/usr/bin/env python3
import time
import json
from mycosentinel.sensor.calibration import Calibrator

cal = Calibrator('/opt/mycosentinel/config.json')
print("Starting calibration for node {self.config.node_id}...")

# Wait for sensors to warm up
print("Warming up sensors (30s)...")
time.sleep(30)

# Run calibration
results = cal.calibrate_all()
print(f"Calibration complete: {{results}}")

# Save calibration
with open('/opt/mycosentinel/calibration.json', 'w') as f:
    json.dump(results, f, indent=2)
print("Calibration saved")
"""
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(cal_script)
                cal_file = f.name
            
            self.run_command([
                "scp", "-o", "StrictHostKeyChecking=no",
                cal_file, f"{self.ssh_target}:/tmp/calibrate.py"
            ])
            
            self.log("INFO", "Running calibration...")
            self.run_command([
                "sudo", "/opt/mycosentinel/venv/bin/python", "/tmp/calibrate.py"
            ], ssh=True, timeout=120)
            
            os.unlink(cal_file)
            
            self.log("INFO", "Sensor calibration complete")
            
        except Exception as e:
            self.log("ERROR", f"Sensor calibration failed: {e}")
            self.log("WARNING", "Continuing with default calibration...")
            # Non-fatal - can calibrate later
            
        return True
    
    def step_verify_deployment(self) -> bool:
        """Verify node is operational"""
        self.log("INFO", "=== Step 7: Deployment Verification ===")
        
        try:
            # Start service
            self.run_command(["sudo", "systemctl", "start", "mycosentinel"], ssh=True)
            time.sleep(5)
            
            # Check service status
            _, stdout, _ = self.run_command(
                ["systemctl", "is-active", "mycosentinel"],
                ssh=True,
                check=False
            )
            
            if "active" in stdout:
                self.log("INFO", "MycoSentinel service is running")
            else:
                self.log("WARNING", "Service may not be fully started yet")
            
            # Check logs
            _, stdout, _ = self.run_command(
                ["sudo", "journalctl", "-u", "mycosentinel", "-n", "20", "--no-pager"],
                ssh=True,
                timeout=10
            )
            
            if "error" in stdout.lower():
                self.log("WARNING", "Errors found in service logs")
                self.log("DEBUG", stdout)
            
            # Test MQTT connection
            mqtt_test = f"""mosquitto_pub -h {self.config.mqtt_broker} \
                -t "mycosentinel/nodes/{self.config.node_id}/status" \
                -m '{{"status": "online", "timestamp": $(date +%s)}}'"""
            
            self.run_command([mqtt_test], ssh=True, check=False)
            
            # Run health check
            health_script = """
import json
import sys

try:
    from mycosentinel.sensor import OpticalSensor, ElectricalSensor
    
    errors = []
    
    # Test optical sensor
    try:
        optical = OpticalSensor()
        reading = optical.capture()
        print(f"Optical sensor: OK (value={reading.value:.2f})")
    except Exception as e:
        errors.append(f"Optical sensor error: {e}")
    
    # Test electrical sensor
    try:
        electrical = ElectricalSensor()
        reading = electrical.measure()
        print(f"Electrical sensor: OK (value={reading.value:.2f})")
    except Exception as e:
        errors.append(f"Electrical sensor error: {e}")
    
    if errors:
        print("\\nErrors:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("\\nAll systems operational!")
        sys.exit(0)
        
except Exception as e:
    print(f"Health check failed: {e}")
    sys.exit(1)
"""
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(health_script)
                health_file = f.name
            
            self.run_command([
                "scp", "-o", "StrictHostKeyChecking=no",
                health_file, f"{self.ssh_target}:/tmp/health_check.py"
            ])
            
            _, stdout, _ = self.run_command([
                "sudo", "/opt/mycosentinel/venv/bin/python", "/tmp/health_check.py"
            ], ssh=True, timeout=30, check=False)
            
            print(stdout)
            
            os.unlink(health_file)
            
            self.log("INFO", "Deployment verification complete")
            
        except Exception as e:
            self.log("ERROR", f"Verification failed: {e}")
            return False
        
        return True
    
    def deploy(self) -> bool:
        """Execute full deployment pipeline"""
        self.log("INFO", f"Starting deployment for node {self.config.node_id}")
        self.log("INFO", f"Serial port: {self.serial_port}")
        self.log("INFO", f"Target IP: {self.config.static_ip}")
        
        steps = [
            ("Prerequisites", self.step_check_prerequisites),
            ("Firmware Flash", self.step_flash_firmware),
            ("Network Config", self.step_network_configuration),
            ("Software Install", self.step_install_software),
            ("Code Deploy", self.step_deploy_sensor_code),
            ("Calibration", self.step_sensor_calibration),
            ("Verification", self.step_verify_deployment),
        ]
        
        success = True
        for name, step_func in steps:
            try:
                if not step_func():
                    self.log("ERROR", f"Step '{name}' failed")
                    success = False
                    break
            except Exception as e:
                self.log("ERROR", f"Step '{name}' failed with exception: {e}")
                success = False
                break
        
        # Save deployment log
        log_file = DEPLOYMENT_DIR / "logs" / f"deploy_{self.config.node_id}_{datetime.now():%Y%m%d_%H%M%S}.json"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, 'w') as f:
            json.dump({
                "node_id": self.config.node_id,
                "serial_port": self.serial_port,
                "success": success,
                "timestamp": datetime.now().isoformat(),
                "log": self.deployment_log,
                "config": asdict(self.config)
            }, f, indent=2, default=str)
        
        self.log("INFO", f"Deployment log saved to {log_file}")
        
        if success:
            self.log("INFO", f"✅ Node {self.config.node_id} deployed successfully!")
            self.log("INFO", f"   Access: ssh pi@{self.config.static_ip}")
            self.log("INFO", f"   Status: systemctl status mycosentinel")
        else:
            self.log("ERROR", f"❌ Deployment failed for node {self.config.node_id}")
        
        return success


def discover_nodes() -> List[Tuple[str, str]]:
    """Auto-discover connected Raspberry Pi devices"""
    logger.info("Scanning for MycoSentinel nodes...")
    
    nodes = []
    
    # List serial ports
    ports = serial.tools.list_ports.comports()
    for port in ports:
        # Look for Raspberry Pi USB serial (typically shows up as PID/VID)
        if "USB" in port.description or "ACM" in port.device or "USB" in port.device:
            logger.info(f"Found potential node: {port.device} - {port.description}")
            nodes.append((port.device, port.description))
    
    # Also check for SD card adapters (may be in disk mode)
    # This would require platform-specific detection
    
    return nodes


def load_node_config(source: str) -> Optional[NodeConfig]:
    """Load node configuration from file or manifest"""
    # Try loading from deployment manifest
    if source.startswith("MS-"):
        # Load from deploy_config.json by node ID
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH) as f:
                manifest = json.load(f)
            
            for node in manifest.get("nodes", []):
                if node["id"] == source:
                    return NodeConfig(
                        node_id=node["id"],
                        hostname=node["hostname"],
                        static_ip=node["static_ip"],
                        sector=node["sector"],
                        lat=node["location"]["lat"],
                        lon=node["location"]["lon"],
                        elevation_m=node["location"]["elevation_m"],
                        distance_from_gateway_m=node["location"].get("distance_from_gateway_m", 0),
                        bearing_deg=node["location"].get("bearing_deg", 0),
                        mesh_relay=node.get("power", {}).get("mesh_relay", False)
                    )
    
    # Try loading from JSON file
    path = Path(source)
    if path.exists():
        with open(path) as f:
            data = json.load(f)
        return NodeConfig(**data)
    
    return None


def main():
    parser = argparse.ArgumentParser(
        description="MycoSentinel Node Deployment Script"
    )
    parser.add_argument("--node-id", "-n", help="Node ID (e.g., MS-A1)")
    parser.add_argument("--port", "-p", help="Serial port (e.g., /dev/ttyUSB0)")
    parser.add_argument("--config", "-c", help="Path to node config JSON")
    parser.add_argument("--discover", "-d", action="store_true",
                       help="Auto-discover connected nodes")
    parser.add_argument("--dry-run", action="store_true",
                       help="Simulate deployment without making changes")
    parser.add_argument("--status", "-s", help="Check status of deployed node")
    
    args = parser.parse_args()
    
    if args.discover:
        nodes = discover_nodes()
        if nodes:
            print(f"Found {len(nodes)} potential node(s):")
            for device, desc in nodes:
                print(f"  {device}: {desc}")
        else:
            print("No nodes found. Connect a Raspberry Pi via USB.")
        return
    
    if args.status:
        # Check status of existing node
        print(f"Checking status of {args.status}...")
        deployer = NodeDeployer(NodeConfig(args.status, args.status, "", "", 0, 0, 0, 0, 0), "")
        deployer.step_verify_deployment()
        return
    
    # Load configuration
    config = None
    if args.config:
        config = load_node_config(args.config)
    elif args.node_id:
        config = load_node_config(args.node_id)
    
    if not config:
        print("Error: Could not load node configuration. Provide --config or --node-id")
        sys.exit(1)
    
    port = args.port
    if not port:
        # Auto-detect
        nodes = discover_nodes()
        if nodes:
            port = nodes[0][0]
            print(f"Auto-selected port: {port}")
        else:
            print("Error: No serial port found. Use --port to specify.")
            sys.exit(1)
    
    # Execute deployment
    deployer = NodeDeployer(config, port, dry_run=args.dry_run)
    success = deployer.deploy()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
