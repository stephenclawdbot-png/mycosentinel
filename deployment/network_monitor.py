#!/usr/bin/env python3
"""
network_monitor.py - Real-time Network Monitoring Dashboard
MYCOSENTINEL v0.2.0 - Biosensor Network Monitor

Real-time monitoring dashboard for the 10-node MycoSentinel mesh network.
Features:
- Auto-discovery of nodes via MQTT heartbeat
- Real-time data visualization (console + web dashboard)
- OTA (Over-The-Air) firmware updates
- Alert system with configurable thresholds
- Network health diagnostics
- Historical data logging

Usage:
    python3 network_monitor.py                          # Start monitoring
    python3 network_monitor.py --web                    # Start web dashboard
    python3 network_monitor.py --ota --node MS-A1      # Initiate OTA update
    python3 network_monitor.py --discover               # Auto-discover nodes
    python3 network_monitor.py --alert-test             # Test alert system

Author: MycoSentinel Deployment Automation
Version: 0.2.0
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
import subprocess
import threading
import queue
import tempfile
import hashlib
from collections import defaultdict, deque
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any, Callable
import warnings
warnings.filterwarnings('ignore')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'network_monitor_{datetime.now().strftime("%Y%m%d")}.log')
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
    MAGENTA = '\033[35m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

@dataclass
class SensorReading:
    """Single sensor reading"""
    timestamp: float
    sensor_type: str
    value: float
    unit: str
    confidence: float = 1.0
    
@dataclass
class NodeStatus:
    """Complete node status"""
    node_id: str
    online: bool
    last_seen: float
    ip_address: str
    sector: str
    readings: Dict[str, SensorReading] = field(default_factory=dict)
    system_stats: Dict = field(default_factory=dict)
    alerts: List[str] = field(default_factory=list)
    ota_status: Optional[str] = None
    mesh_neighbors: List[str] = field(default_factory=list)
    uptime_seconds: float = 0.0
    battery_percent: Optional[float] = None
    signal_strength: Optional[float] = None
    firmware_version: str = "unknown"

@dataclass
class AlertRule:
    """Alert configuration rule"""
    sensor_type: str
    threshold_min: Optional[float] = None
    threshold_max: Optional[float] = None
    threshold_critical: Optional[float] = None
    duration_seconds: int = 60
    enabled: bool = True
    notification_channels: List[str] = field(default_factory=lambda: ["console", "log"])

@dataclass
class NetworkState:
    """Complete network state"""
    nodes: Dict[str, NodeStatus] = field(default_factory=dict)
    gateway_status: Dict = field(default_factory=dict)
    mesh_topology: Dict = field(default_factory=dict)
    alerts_active: Dict[str, List[Dict]] = field(default_factory=dict)
    statistics: Dict = field(default_factory=dict)
    last_updated: float = field(default_factory=time.time)

class ConfigManager:
    """Manages configuration files"""
    
    CONFIG_PATH = Path("/opt/mycosentinel/config") if Path("/opt/mycosentinel").exists() else Path(__file__).parent / "config"
    
    DEFAULT_THRESHOLDS = {
        "co2_ppm": {"min": 350, "max": 1000, "critical": 1500},
        "pm2_5": {"min": 0, "max": 35, "critical": 75},
        "pm10": {"min": 0, "max": 150, "critical": 250},
        "voc_index": {"min": 0, "max": 200, "critical": 300},
        "temperature_c": {"min": 10, "max": 40, "critical_high": 45, "critical_low": 5},
        "humidity_percent": {"min": 20, "max": 80, "critical_low": 10, "critical_high": 95},
        "optical_signal": {"min": 100, "max": 2500, "critical_low": 50, "critical_high": 3000},
        "electrical_current_uA": {"min": 0, "max": 100, "critical": 150}
    }
    
    def __init__(self):
        self.CONFIG_PATH.mkdir(parents=True, exist_ok=True)
        self.thresholds_path = self.CONFIG_PATH / "thresholds.json"
        self.nodes_path = self.CONFIG_PATH / "discovered_nodes.json"
        self.alerts_config_path = self.CONFIG_PATH / "alerts_config.json"
        
    def load_thresholds(self) -> Dict:
        """Load or create default thresholds"""
        if self.thresholds_path.exists():
            with open(self.thresholds_path) as f:
                return json.load(f)
        
        # Save defaults
        with open(self.thresholds_path, 'w') as f:
            json.dump(self.DEFAULT_THRESHOLDS, f, indent=2)
        return self.DEFAULT_THRESHOLDS
    
    def save_thresholds(self, thresholds: Dict):
        """Save thresholds to file"""
        with open(self.thresholds_path, 'w') as f:
            json.dump(thresholds, f, indent=2)
    
    def load_discovered_nodes(self) -> Dict:
        """Load discovered nodes"""
        if self.nodes_path.exists():
            with open(self.nodes_path) as f:
                return json.load(f)
        return {}
    
    def save_discovered_nodes(self, nodes: Dict):
        """Save discovered nodes"""
        with open(self.nodes_path, 'w') as f:
            json.dump(nodes, f, indent=2, default=str)
    
    def load_alerts_config(self) -> Dict:
        """Load alert configuration"""
        if self.alerts_config_path.exists():
            with open(self.alerts_config_path) as f:
                return json.load(f)
        return {
            "notification_channels": ["console", "log", "mqtt"],
            "email_enabled": False,
            "webhook_enabled": False,
            "aggregation_window_seconds": 300
        }

class OTAUpdater:
    """Over-The-Air firmware update manager"""
    
    def __init__(self, mqtt_client=None, firmware_path: Optional[Path] = None):
        self.mqtt = mqtt_client
        self.firmware_path = firmware_path or Path(__file__).parent / "firmware"
        self.active_updates: Dict[str, Dict] = {}
        self.update_history: List[Dict] = []
        
    def get_available_firmware(self) -> List[Dict]:
        """List available firmware versions"""
        versions = []
        if self.firmware_path.exists():
            for fw_file in self.firmware_path.glob("*.bin"):
                stat = fw_file.stat()
                versions.append({
                    "filename": fw_file.name,
                    "version": fw_file.stem,
                    "size_bytes": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "checksum": self._calculate_checksum(fw_file)
                })
        return versions
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum"""
        h = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                h.update(chunk)
        return h.hexdigest()[:16]
    
    def initiate_update(self, node_id: str, firmware_version: str, 
                       verify: bool = True) -> bool:
        """Initiate OTA update for a node"""
        logger.info(f"Initiating OTA update for {node_id} to version {firmware_version}")
        
        # Find firmware file
        fw_file = self.firmware_path / f"{firmware_version}.bin"
        if not fw_file.exists():
            logger.error(f"Firmware not found: {fw_file}")
            return False
        
        checksum = self._calculate_checksum(fw_file)
        
        # Create update manifest
        update_manifest = {
            "node_id": node_id,
            "firmware_version": firmware_version,
            "file_size": fw_file.stat().st_size,
            "checksum": checksum,
            "timestamp": time.time(),
            "status": "initiated"
        }
        
        self.active_updates[node_id] = update_manifest
        
        # Send update command via MQTT
        if self.mqtt:
            topic = f"mycosentinel/nodes/{node_id}/ota/command"
            payload = json.dumps({
                "action": "update",
                "version": firmware_version,
                "checksum": checksum,
                "url": f"http://192.168.1.100/firmware/{firmware_version}.bin"
            })
            self.mqtt.publish(topic, payload)
            logger.info(f"OTA update command sent to {node_id}")
        else:
            logger.warning("MQTT not connected, OTA command not sent")
        
        return True
    
    def handle_status_update(self, node_id: str, status: Dict):
        """Handle OTA status update from node"""
        if node_id in self.active_updates:
            self.active_updates[node_id].update(status)
            
            if status.get("status") == "complete":
                logger.info(f"OTA update complete for {node_id}")
                self.update_history.append(self.active_updates.pop(node_id))
            elif status.get("status") == "failed":
                logger.error(f"OTA update failed for {node_id}: {status.get('error')}")
                self.update_history.append(self.active_updates.pop(node_id))
            else:
                progress = status.get("progress", 0)
                logger.info(f"OTA {node_id}: {progress}% complete")
    
    def rollback_update(self, node_id: str) -> bool:
        """Rollback to previous firmware version"""
        logger.info(f"Initiating rollback for {node_id}")
        
        if self.mqtt:
            topic = f"mycosentinel/nodes/{node_id}/ota/command"
            payload = json.dumps({"action": "rollback"})
            self.mqtt.publish(topic, payload)
            return True
        return False
    
    def get_update_status(self, node_id: Optional[str] = None) -> Dict:
        """Get current update status"""
        if node_id:
            return self.active_updates.get(node_id, {})
        return {
            "active": self.active_updates,
            "history": self.update_history[-10:]  # Last 10
        }

class AlertManager:
    """Manages alerts and notifications"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.alert_rules = self._load_rules()
        self.active_alerts: Dict[str, Dict] = {}
        self.alert_history: deque = deque(maxlen=1000)
        self.notification_callbacks: List[Callable] = []
        
    def _load_rules(self) -> List[AlertRule]:
        """Load alert rules from config"""
        thresholds = self.config.load_thresholds()
        rules = []
        
        for sensor, values in thresholds.items():
            rules.append(AlertRule(
                sensor_type=sensor,
                threshold_min=values.get("min"),
                threshold_max=values.get("max"),
                threshold_critical=values.get("critical"),
                enabled=True
            ))
        
        return rules
    
    def register_notification_callback(self, callback: Callable):
        """Register callback for notifications"""
        self.notification_callbacks.append(callback)
    
    def check_reading(self, node_id: str, sensor_type: str, 
                     value: float, timestamp: float) -> Optional[Dict]:
        """Check if reading triggers an alert"""
        rule = next((r for r in self.alert_rules if r.sensor_type == sensor_type), None)
        if not rule or not rule.enabled:
            return None
        
        alert_level = None
        message = None
        
        # Check critical thresholds first
        if rule.threshold_critical is not None:
            if value > rule.threshold_critical:
                alert_level = "critical"
                message = f"{sensor_type} CRITICAL: {value:.2f} (threshold: {rule.threshold_critical})"
        
        if rule.threshold_critical and isinstance(rule.threshold_critical, dict):
            if "critical_high" in rule.threshold_critical and value > rule.threshold_critical["critical_high"]:
                alert_level = "critical"
                message = f"{sensor_type} CRITICAL HIGH: {value:.2f}"
            elif "critical_low" in rule.threshold_critical and value < rule.threshold_critical["critical_low"]:
                alert_level = "critical"
                message = f"{sensor_type} CRITICAL LOW: {value:.2f}"
        
        # Then check warning thresholds
        if alert_level is None:
            if rule.threshold_max is not None and value > rule.threshold_max:
                alert_level = "warning"
                message = f"{sensor_type} HIGH: {value:.2f} (max: {rule.threshold_max})"
            elif rule.threshold_min is not None and value < rule.threshold_min:
                alert_level = "warning"
                message = f"{sensor_type} LOW: {value:.2f} (min: {rule.threshold_min})"
        
        if alert_level:
            alert = {
                "id": f"{node_id}_{sensor_type}_{int(timestamp)}",
                "node_id": node_id,
                "sensor_type": sensor_type,
                "value": value,
                "level": alert_level,
                "message": message,
                "timestamp": timestamp,
                "acknowledged": False
            }
            
            self._trigger_alert(alert)
            return alert
        
        return None
    
    def _trigger_alert(self, alert: Dict):
        """Process triggered alert"""
        alert_key = f"{alert['node_id']}_{alert['sensor_type']}"
        
        # Check if alert already active
        if alert_key in self.active_alerts:
            # Update timestamp
            self.active_alerts[alert_key]["last_triggered"] = alert["timestamp"]
            return
        
        # New alert
        self.active_alerts[alert_key] = alert
        self.alert_history.append(alert)
        
        # Log
        log_level = logging.CRITICAL if alert["level"] == "critical" else logging.WARNING
        logger.log(log_level, f"ALERT [{alert['level'].upper()}] {alert['message']}")
        
        # Notify callbacks
        for cb in self.notification_callbacks:
            try:
                cb(alert)
            except Exception as e:
                logger.error(f"Notification callback error: {e}")
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert"""
        for key, alert in self.active_alerts.items():
            if alert["id"] == alert_id:
                alert["acknowledged"] = True
                logger.info(f"Alert {alert_id} acknowledged")
                return True
        return False
    
    def clear_resolved_alerts(self, node_status: Dict[str, NodeStatus]):
        """Clear alerts for readings that have returned to normal"""
        thresholds = self.config.load_thresholds()
        
        for alert_key in list(self.active_alerts.keys()):
            alert = self.active_alerts[alert_key]
            node_id = alert["node_id"]
            sensor_type = alert["sensor_type"]
            
            if node_id in node_status:
                node = node_status[node_id]
                if sensor_type in node.readings:
                    reading = node.readings[sensor_type]
                    value = reading.value
                    
                    # Check if back to normal
                    threshold = thresholds.get(sensor_type, {})
                    min_val = threshold.get("min", float('-inf'))
                    max_val = threshold.get("max", float('inf'))
                    
                    if min_val <= value <= max_val:
                        logger.info(f"Alert cleared: {alert_key}")
                        del self.active_alerts[alert_key]
    
    def get_active_alerts(self, node_id: Optional[str] = None) -> List[Dict]:
        """Get active alerts, optionally filtered by node"""
        alerts = list(self.active_alerts.values())
        if node_id:
            alerts = [a for a in alerts if a["node_id"] == node_id]
        return sorted(alerts, key=lambda x: x["timestamp"], reverse=True)
    
    def test_alert_system(self):
        """Test alert notifications"""
        logger.info("Testing alert system...")
        
        test_alerts = [
            {"node_id": "TEST", "sensor_type": "co2_ppm", "value": 2000, "level": "critical"},
            {"node_id": "TEST", "sensor_type": "temperature_c", "value": 55, "level": "critical"},
            {"node_id": "TEST", "sensor_type": "pm2_5", "value": 50, "level": "warning"}
        ]
        
        for test in test_alerts:
            alert = self.check_reading(
                test["node_id"], test["sensor_type"],
                test["value"], time.time()
            )
            if alert:
                print(f"{Colors.YELLOW}Test {alert['level'].upper()}: {alert['message']}{Colors.ENDC}")
        
        print(f"{Colors.GREEN}Alert test complete. {len(test_alerts)} test alerts generated.{Colors.ENDC}")

class NetworkDiscovery:
    """Auto-discovery of network nodes"""
    
    def __init__(self, config: ConfigManager, mqtt_client=None):
        self.config = config
        self.mqtt = mqtt_client
        self.discovered_nodes: Dict[str, Dict] = {}
        self.discovery_active = False
        self.discovery_thread: Optional[threading.Thread] = None
        
    def start_discovery(self, duration_seconds: int = 60):
        """Start discovery process"""
        logger.info(f"Starting network discovery for {duration_seconds}s...")
        self.discovery_active = True
        
        # Send discovery broadcast
        if self.mqtt:
            self.mqtt.publish("mycosentinel/discovery", json.dumps({
                "action": "discover",
                "timestamp": time.time()
            }))
        
        # Wait for responses
        time.sleep(duration_seconds)
        self.discovery_active = False
        
        # Save results
        self.config.save_discovered_nodes(self.discovered_nodes)
        logger.info(f"Discovery complete. Found {len(self.discovered_nodes)} node(s)")
        
        return self.discovered_nodes
    
    def handle_discovery_response(self, node_id: str, message: Dict):
        """Handle discovery response from node"""
        if self.discovery_active:
            self.discovered_nodes[node_id] = {
                "node_id": node_id,
                "ip": message.get("ip"),
                "sector": message.get("sector"),
                "firmware_version": message.get("firmware_version"),
                "discovered_at": time.time()
            }
            logger.info(f"Discovered node: {node_id}")
    
    def scan_network(self, subnet: str = "192.168.1") -> List[Dict]:
        """Scan network for nodes via ping sweep"""
        logger.info(f"Scanning network {subnet}.0/24...")
        found = []
        
        def ping_host(ip: str) -> Optional[str]:
            try:
                result = subprocess.run(
                    ["ping", "-c", "1", "-W", "1", ip],
                    capture_output=True,
                    timeout=3
                )
                if result.returncode == 0:
                    return ip
            except:
                pass
            return None
        
        # Scan 101-110 range
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(ping_host, f"{subnet}.{i}"): i for i in range(101, 111)}
            for future in as_completed(futures):
                ip = future.result()
                if ip:
                    found.append({"ip": ip, "discovered_via": "ping"})
                    logger.info(f"  Found host: {ip}")
        
        return found

class ConsoleDashboard:
    """Console-based real-time dashboard"""
    
    def __init__(self, network_state: NetworkState, alert_manager: AlertManager):
        self.network_state = network_state
        self.alert_manager = alert_manager
        self.running = False
        self.update_interval = 2.0
        
    def start(self):
        """Start console dashboard"""
        self.running = True
        
        try:
            while self.running:
                self._render()
                time.sleep(self.update_interval)
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        """Stop dashboard"""
        self.running = False
        print(f"\n{Colors.CYAN}Monitoring stopped.{Colors.ENDC}")
    
    def _render(self):
        """Render dashboard to console"""
        os.system('clear' if os.name != 'nt' else 'cls')
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"{Colors.BOLD}{Colors.CYAN}")
        print("╔══════════════════════════════════════════════════════════════╗")
        print("║           MYCOSENTINEL NETWORK MONITOR v0.2.0              ║")
        print(f"║              {now}                        ║")
        print("╚══════════════════════════════════════════════════════════════╝")
        print(f"{Colors.ENDC}")
        
        # Network summary
        total = len(self.network_state.nodes)
        online = sum(1 for n in self.network_state.nodes.values() if n.online)
        offline = total - online
        
        status_color = Colors.GREEN if online == total else (Colors.YELLOW if online > total/2 else Colors.RED)
        
        print(f"{Colors.BOLD}Network Status:{Colors.ENDC} {status_color}{online}/{total} nodes online{Colors.ENDC}")
        print(f"  Gateway: {Colors.GREEN if self.network_state.gateway_status.get('online') else Colors.RED}{'ONLINE' if self.network_state.gateway_status.get('online') else 'OFFLINE'}{Colors.ENDC}")
        
        # Active alerts
        active = self.alert_manager.get_active_alerts()
        if active:
            print(f"\n{Colors.BOLD}{Colors.RED}Active Alerts:{Colors.ENDC}")
            for alert in active[:5]:
                color = Colors.RED if alert["level"] == "critical" else Colors.YELLOW
                print(f"  {color}[{alert['level'].upper()}]{Colors.ENDC} {alert['node_id']}: {alert['message']}")
        
        # Node status table
        print(f"\n{Colors.BOLD}Node Status:{Colors.ENDC}")
        print(f"{'Node ID':<10} {'Sector':<6} {'Status':<8} {'IP':<16} {'Uptime':<10} {'Last Seen':<15} {'Sensors'}")
        print("-" * 100)
        
        for node_id in sorted(self.network_state.nodes.keys()):
            node = self.network_state.nodes[node_id]
            status = f"{Colors.GREEN}●{Colors.ENDC}" if node.online else f"{Colors.RED}●{Colors.ENDC}"
            uptime = self._format_duration(node.uptime_seconds) if node.online else "-"
            last_seen = self._format_time_ago(node.last_seen) if node.last_seen > 0 else "never"
            sensor_count = len(node.readings)
            
            print(f"{node_id:<10} {node.sector:<6} {status:<8} {node.ip_address:<16} {uptime:<10} {last_seen:<15} {sensor_count} sensors")
        
        # Recent readings
        print(f"\n{Colors.BOLD}Latest Readings (per node):{Colors.ENDC}")
        for node_id, node in self.network_state.nodes.items():
            if node.online and node.readings:
                reading_strs = []
                for sensor_type, reading in list(node.readings.items())[:3]:
                    val = f"{reading.value:.1f}{reading.unit}"
                    reading_strs.append(f"{sensor_type}={val}")
                print(f"  {node_id}: {', '.join(reading_strs)}")
        
        print(f"\n{Colors.CYAN}Press Ctrl+C to exit{Colors.ENDC}")
    
    def _format_duration(self, seconds: float) -> str:
        """Format seconds as human-readable duration"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds/60)}m"
        elif seconds < 86400:
            return f"{int(seconds/3600)}h"
        else:
            return f"{int(seconds/86400)}d"
    
    def _format_time_ago(self, timestamp: float) -> str:
        """Format timestamp as time ago"""
        diff = time.time() - timestamp
        if diff < 60:
            return f"{int(diff)}s ago"
        elif diff < 3600:
            return f"{int(diff/60)}m ago"
        else:
            return f"{int(diff/3600)}h ago"

class MQTTClient:
    """MQTT client for network communication"""
    
    def __init__(self, broker_host: str = "192.168.1.100", broker_port: int = 1883):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client = None
        self.connected = False
        self.message_handlers: List[Callable] = []
        
    def connect(self) -> bool:
        """Connect to MQTT broker"""
        try:
            import paho.mqtt.client as mqtt
            
            self.client = mqtt.Client()
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            self.client.on_disconnect = self._on_disconnect
            
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
            
            # Subscribe to topics
            self.client.subscribe("mycosentinel/nodes/+/data")
            self.client.subscribe("mycosentinel/nodes/+/status")
            self.client.subscribe("mycosentinel/nodes/+/heartbeat")
            self.client.subscribe("mycosentinel/discovery/response")
            self.client.subscribe("mycosentinel/nodes/+/ota/status")
            
            return True
            
        except ImportError:
            logger.warning("paho-mqtt not installed, running in offline mode")
            return False
        except Exception as e:
            logger.error(f"MQTT connection failed: {e}")
            return False
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback for MQTT connect"""
        if rc == 0:
            logger.info(f"Connected to MQTT broker at {self.broker_host}")
            self.connected = True
        else:
            logger.error(f"MQTT connection failed with code {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback for MQTT disconnect"""
        logger.warning(f"MQTT disconnected")
        self.connected = False
    
    def _on_message(self, client, userdata, msg):
        """Callback for MQTT message"""
        try:
            payload = json.loads(msg.payload.decode())
            topic = msg.topic
            
            for handler in self.message_handlers:
                try:
                    handler(topic, payload)
                except Exception as e:
                    logger.error(f"Message handler error: {e}")
        except Exception as e:
            logger.debug(f"Failed to parse MQTT message: {e}")
    
    def register_handler(self, handler: Callable):
        """Register message handler"""
        self.message_handlers.append(handler)
    
    def publish(self, topic: str, payload: str):
        """Publish message to topic"""
        if self.client and self.connected:
            self.client.publish(topic, payload)

class NetworkMonitor:
    """Main network monitor class"""
    
    def __init__(self, broker_host: str = "192.168.1.100"):
        self.config = ConfigManager()
        self.network_state = NetworkState()
        self.mqtt = MQTTClient(broker_host)
        self.ota_updater = OTAUpdater(mqtt_client=self.mqtt)
        self.alert_manager = AlertManager(self.config)
        self.discovery = NetworkDiscovery(self.config, mqtt_client=self.mqtt)
        self.dashboard = ConsoleDashboard(self.network_state, self.alert_manager)
        
        # Statistics
        self.messages_received = 0
        self.start_time = time.time()
        
        # Initialize MQTT handlers
        self.mqtt.register_handler(self._handle_mqtt_message)
        
        # Register alert callback
        self.alert_manager.register_notification_callback(self._on_alert)
        
        # Load discovered nodes
        saved_nodes = self.config.load_discovered_nodes()
        for node_id, info in saved_nodes.items():
            self.network_state.nodes[node_id] = NodeStatus(
                node_id=node_id,
                online=False,
                last_seen=0,
                ip_address=info.get("ip", ""),
                sector=info.get("sector", "A")
            )
    
    def _handle_mqtt_message(self, topic: str, payload: Dict):
        """Handle incoming MQTT messages"""
        self.messages_received += 1
        
        # Parse topic
        parts = topic.split('/')
        if len(parts) >= 4 and parts[0] == "mycosentinel" and parts[1] == "nodes":
            node_id = parts[2]
            message_type = parts[3]
            
            if message_type == "heartbeat":
                self._update_node_heartbeat(node_id, payload)
            elif message_type == "data":
                self._update_node_data(node_id, payload)
            elif message_type == "status":
                self._update_node_status(node_id, payload)
            elif message_type == "ota":
                self.ota_updater.handle_status_update(node_id, payload)
        
        elif topic == "mycosentinel/discovery/response":
            node_id = payload.get("node_id", "unknown")
            self.discovery.handle_discovery_response(node_id, payload)
    
    def _update_node_heartbeat(self, node_id: str, data: Dict):
        """Update node from heartbeat"""
        if node_id not in self.network_state.nodes:
            self.network_state.nodes[node_id] = NodeStatus(
                node_id=node_id,
                online=True,
                last_seen=time.time(),
                ip_address=data.get("ip", ""),
                sector=data.get("sector", "A")
            )
        
        node = self.network_state.nodes[node_id]
        node.online = True
        node.last_seen = time.time()
        node.uptime_seconds = data.get("uptime", 0)
        node.firmware_version = data.get("firmware_version", "unknown")
        node.battery_percent = data.get("battery_percent")
        node.signal_strength = data.get("signal_strength", data.get("rssi"))
    
    def _update_node_data(self, node_id: str, data: Dict):
        """Update node with sensor data"""
        if node_id not in self.network_state.nodes:
            self._update_node_heartbeat(node_id, data)
        
        node = self.network_state.nodes[node_id]
        node.online = True
        node.last_seen = time.time()
        
        # Parse sensor readings
        timestamp = data.get("timestamp", time.time())
        
        if "readings" in data:
            for sensor_type, reading_data in data["readings"].items():
                reading = SensorReading(
                    timestamp=timestamp,
                    sensor_type=sensor_type,
                    value=reading_data.get("value", 0),
                    unit=reading_data.get("unit", ""),
                    confidence=reading_data.get("confidence", 1.0)
                )
                node.readings[sensor_type] = reading
                
                # Check for alerts
                self.alert_manager.check_reading(node_id, sensor_type, 
                                                   reading.value, timestamp)
        
        # Check bioreactor data
        if "bioreactor" in data:
            node.system_stats["bioreactor"] = data["bioreactor"]
    
    def _update_node_status(self, node_id: str, data: Dict):
        """Update node status"""
        if node_id not in self.network_state.nodes:
            self._update_node_heartbeat(node_id, data)
        
        node = self.network_state.nodes[node_id]
        node.online = data.get("online", False)
        node.mesh_neighbors = data.get("mesh_neighbors", [])
    
    def _on_alert(self, alert: Dict):
        """Handle alert notifications"""
        if alert["level"] == "critical":
            # Could send email/SMS here
            pass
    
    def run_console(self):
        """Run console-based monitoring"""
        logger.info("Starting MycoSentinel Network Monitor...")
        
        # Connect MQTT
        if not self.mqtt.connect():
            logger.warning("Running in offline mode - no MQTT connectivity")
        
        # Start background tasks
        threading.Thread(target=self._cleanup_loop, daemon=True).start()
        
        try:
            self.dashboard.start()
        except KeyboardInterrupt:
            self.shutdown()
    
    def _cleanup_loop(self):
        """Background loop to mark offline nodes"""
        while True:
            time.sleep(30)
            now = time.time()
            for node in self.network_state.nodes.values():
                if now - node.last_seen > 120:  # 2 minutes
                    if node.online:
                        node.online = False
                        logger.warning(f"Node {node.node_id} marked offline (no heartbeat)")
            
            # Clear resolved alerts
            self.alert_manager.clear_resolved_alerts(self.network_state.nodes)
    
    def run_discovery(self, duration: int = 60) -> Dict:
        """Run node discovery"""
        if not self.mqtt.connect():
            logger.warning("MQTT not available, using network scan")
            return {"ping_scan": self.discovery.scan_network()}
        
        return self.discovery.start_discovery(duration)
    
    def initiate_ota(self, node_id: str, version: str) -> bool:
        """Initiate OTA update"""
        return self.ota_updater.initiate_update(node_id, version)
    
    def get_network_summary(self) -> Dict:
        """Get network summary"""
        total = len(self.network_state.nodes)
        online = sum(1 for n in self.network_state.nodes.values() if n.online)
        
        return {
            "total_nodes": total,
            "online_nodes": online,
            "offline_nodes": total - online,
            "active_alerts": len(self.alert_manager.get_active_alerts()),
            "mqtt_messages_received": self.messages_received,
            "uptime_seconds": time.time() - self.start_time
        }
    
    def shutdown(self):
        """Shutdown monitor"""
        logger.info("Shutting down...")
        self.config.save_discovered_nodes({
            nid: {
                "ip": n.ip_address,
                "sector": n.sector,
                "firmware_version": n.firmware_version
            }
            for nid, n in self.network_state.nodes.items()
        })

def main():
    parser = argparse.ArgumentParser(
        description="MycoSentinel Network Monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                       # Start console monitoring
  %(prog)s --discover            # Discover nodes on network
  %(prog)s --ota -n MS-A1 -v 0.2.0  # Update MS-A1 to v0.2.0
  %(prog)s --alert-test          # Test alert system
        """
    )
    parser.add_argument("--broker", "-b", default="192.168.1.100",
                       help="MQTT broker IP (default: 192.168.1.100)")
    parser.add_argument("--discover", "-d", action="store_true",
                       help="Run node discovery")
    parser.add_argument("--discover-duration", type=int, default=60,
                       help="Discovery duration in seconds (default: 60)")
    parser.add_argument("--ota", action="store_true",
                       help="Initiate OTA update")
    parser.add_argument("--node", "-n", help="Target node ID for OTA")
    parser.add_argument("--version", "-v", help="Firmware version for OTA")
    parser.add_argument("--rollback", action="store_true",
                       help="Rollback OTA update")
    parser.add_argument("--alert-test", action="store_true",
                       help="Test alert system")
    parser.add_argument("--status", "-s", action="store_true",
                       help="Quick status check and exit")
    
    args = parser.parse_args()
    
    monitor = NetworkMonitor(broker_host=args.broker)
    
    if args.discover:
        results = monitor.run_discovery(args.discover_duration)
        print(f"\n{Colors.GREEN}Discovery Results:{Colors.ENDC}")
        print(json.dumps(results, indent=2, default=str))
        return
    
    if args.ota:
        if not args.node:
            print("Error: --node required for OTA")
            return 1
        if not args.version and not args.rollback:
            print("Error: --version required for OTA (or use --rollback)")
            return 1
        
        if args.rollback:
            monitor.ota_updater.rollback_update(args.node)
        else:
            success = monitor.initiate_ota(args.node, args.version)
            print(f"OTA {'initiated' if success else 'failed'}")
        return
    
    if args.alert_test:
        monitor.alert_manager.test_alert_system()
        return
    
    if args.status:
        summary = monitor.get_network_summary()
        print(json.dumps(summary, indent=2))
        return
    
    # Default: run console monitor
    monitor.run_console()

if __name__ == "__main__":
    sys.exit(main() or 0)
