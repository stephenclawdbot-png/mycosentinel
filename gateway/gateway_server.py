#!/usr/bin/env python3
"""
MycoSentinel Gateway Server
Core gateway software for 10-node biosensor network deployment.

Features:
- Node registration and management system
- MQTT broker integration for data collection
- Data aggregation from multiple nodes
- RESTful JSON API for data queries
- Real-time WebSocket streaming
- Alert threshold monitoring
- Data persistence to InfluxDB

Usage:
    python3 gateway_server.py --config config.json
    python3 gateway_server.py --simulation  # Run with simulated nodes

Author: MycoSentinel Deployment Team
Version: 1.0.0
"""

import json
import logging
import asyncio
import time
import threading
import queue
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
import argparse

# Flask/FastAPI imports
from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS

# MQTT imports
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    print("Warning: paho-mqtt not installed, MQTT features disabled")

# Data storage
try:
    from influxdb import InfluxDBClient
    INFLUX_AVAILABLE = True
except ImportError:
    INFLUX_AVAILABLE = False
    print("Warning: influxdb not installed, using in-memory storage")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('gateway.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class NodeRegistration:
    """Node registration record"""
    node_id: str
    sector: str
    ip_address: str
    mac_address: str
    registered_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    status: str = "online"
    firmware_version: str = "unknown"
    capabilities: List[str] = field(default_factory=list)
    location: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            **asdict(self),
            "uptime_seconds": time.time() - self.registered_at,
            "last_seen_seconds_ago": time.time() - self.last_seen
        }


@dataclass
class SensorData:
    """Sensor data packet"""
    node_id: str
    timestamp: float
    sequence_num: int
    bioreactor: Dict[str, Any]
    optical: Dict[str, Any]
    electrical: Dict[str, Any]
    processing: Dict[str, Any]
    meta: Dict[str, Any]
    received_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @property
    def age_seconds(self) -> float:
        return time.time() - self.timestamp


@dataclass
class Alert:
    """Alert record"""
    id: str
    node_id: str
    severity: str  # info, warning, critical
    message: str
    metric: str
    threshold: float
    value: float
    timestamp: float = field(default_factory=time.time)
    acknowledged: bool = False


# ============================================================================
# NODE REGISTRY
# ============================================================================

class NodeRegistry:
    """
    Central registry for managing sensor nodes in the network.
    Handles node registration, status tracking, and lifecycle management.
    """
    
    def __init__(self, expected_nodes: int = 10):
        self.nodes: Dict[str, NodeRegistration] = {}
        self.expected_count = expected_nodes
        self._lock = threading.RLock()
        
    def register_node(self, node_id: str, sector: str, ip_address: str,
                     mac_address: str, firmware_version: str = "0.1.0",
                     capabilities: List[str] = None) -> NodeRegistration:
        """Register a new node or update existing registration"""
        with self._lock:
            node = NodeRegistration(
                node_id=node_id,
                sector=sector,
                ip_address=ip_address,
                mac_address=mac_address,
                firmware_version=firmware_version,
                capabilities=capabilities or ["optical", "electrical"],
                status="online"
            )
            self.nodes[node_id] = node
            logger.info(f"Node registered: {node_id} at {ip_address}")
            return node
    
    def unregister_node(self, node_id: str) -> bool:
        """Remove a node from the registry"""
        with self._lock:
            if node_id in self.nodes:
                del self.nodes[node_id]
                logger.info(f"Node unregistered: {node_id}")
                return True
            return False
    
    def update_heartbeat(self, node_id: str) -> bool:
        """Update last seen timestamp for a node"""
        with self._lock:
            if node_id in self.nodes:
                self.nodes[node_id].last_seen = time.time()
                if self.nodes[node_id].status != "online":
                    self.nodes[node_id].status = "online"
                    logger.info(f"Node came online: {node_id}")
                return True
            return False
    
    def set_node_status(self, node_id: str, status: str) -> bool:
        """Set node status (online, offline, error, calibrating)"""
        with self._lock:
            if node_id in self.nodes:
                old_status = self.nodes[node_id].status
                self.nodes[node_id].status = status
                if old_status != status:
                    logger.info(f"Node {node_id} status: {old_status} -> {status}")
                return True
            return False
    
    def get_node(self, node_id: str) -> Optional[NodeRegistration]:
        """Get node registration by ID"""
        with self._lock:
            return self.nodes.get(node_id)
    
    def get_all_nodes(self) -> List[NodeRegistration]:
        """Get all registered nodes"""
        with self._lock:
            return list(self.nodes.values())
    
    def get_nodes_by_sector(self, sector: str) -> List[NodeRegistration]:
        """Get all nodes in a specific sector"""
        with self._lock:
            return [n for n in self.nodes.values() if n.sector == sector]
    
    def get_online_nodes(self) -> List[NodeRegistration]:
        """Get all online nodes"""
        with self._lock:
            return [n for n in self.nodes.values() if n.status == "online"]
    
    def check_offline_nodes(self, timeout_seconds: float = 120) -> List[str]:
        """Check for nodes that haven't sent heartbeat recently"""
        offline_nodes = []
        with self._lock:
            now = time.time()
            for node_id, node in self.nodes.items():
                if now - node.last_seen > timeout_seconds and node.status == "online":
                    node.status = "offline"
                    offline_nodes.append(node_id)
                    logger.warning(f"Node offline: {node_id} (no heartbeat for {timeout_seconds}s)")
        return offline_nodes
    
    def get_registry_status(self) -> Dict:
        """Get overall registry status"""
        with self._lock:
            total = len(self.nodes)
            online = len([n for n in self.nodes.values() if n.status == "online"])
            offline = len([n for n in self.nodes.values() if n.status == "offline"])
            
            return {
                "total_nodes": total,
                "expected_nodes": self.expected_count,
                "online_nodes": online,
                "offline_nodes": offline,
                "registration_percent": (total / self.expected_count * 100) if self.expected_count else 0,
                "health_percent": (online / total * 100) if total else 0
            }


# ============================================================================
# DATA AGGREGATOR
# ============================================================================

class DataAggregator:
    """
    Aggregates data from multiple sensor nodes.
    Provides real-time buffers, statistics, and data persistence.
    """
    
    def __init__(self, max_buffer_size: int = 10000):
        self.node_buffers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_buffer_size))
        self.latest_data: Dict[str, SensorData] = {}
        self.statistics: Dict[str, Dict] = defaultdict(lambda: defaultdict(float))
        self._data_callbacks: List[Callable[[SensorData], None]] = []
        self._lock = threading.RLock()
        
    def add_data_callback(self, callback: Callable[[SensorData], None]):
        """Register a callback for new data"""
        self._data_callbacks.append(callback)
    
    def process_data(self, data: SensorData) -> bool:
        """Process incoming sensor data"""
        with self._lock:
            # Store in node buffer
            self.node_buffers[data.node_id].append(data)
            self.latest_data[data.node_id] = data
            
            # Update statistics
            self._update_statistics(data)
            
            # Notify callbacks
            for callback in self._data_callbacks:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"Data callback error: {e}")
            
            return True
    
    def _update_statistics(self, data: SensorData):
        """Update running statistics for a node"""
        node_stats = self.statistics[data.node_id]
        
        optical_norm = data.optical.get("normalized", 0)
        electrical_norm = data.electrical.get("normalized_response", 0)
        anomaly_score = data.processing.get("anomaly_score", 0)
        
        # Running averages
        n = node_stats.get("count", 0) + 1
        node_stats["count"] = n
        node_stats["optical_avg"] = (node_stats.get("optical_avg", 0) * (n-1) + optical_norm) / n
        node_stats["electrical_avg"] = (node_stats.get("electrical_avg", 0) * (n-1) + electrical_norm) / n
        node_stats["anomaly_max"] = max(node_stats.get("anomaly_max", 0), anomaly_score)
        
        # Hourly buckets
        hour = datetime.fromtimestamp(data.timestamp).strftime("%Y-%m-%d-%H")
        hour_key = f"hour_{hour}"
        if hour_key not in node_stats:
            node_stats[hour_key] = {"count": 0, "optical_sum": 0, "electrical_sum": 0}
        node_stats[hour_key]["count"] += 1
        node_stats[hour_key]["optical_sum"] += optical_norm
        node_stats[hour_key]["electrical_sum"] += electrical_norm
    
    def get_latest_data(self, node_id: Optional[str] = None) -> Optional[SensorData]:
        """Get most recent data for a node or all nodes"""
        with self._lock:
            if node_id:
                return self.latest_data.get(node_id)
            return None
    
    def get_all_latest(self) -> Dict[str, SensorData]:
        """Get latest data from all nodes"""
        with self._lock:
            return dict(self.latest_data)
    
    def get_node_history(self, node_id: str, limit: int = 100) -> List[Dict]:
        """Get historical data for a node"""
        with self._lock:
            buffer = self.node_buffers.get(node_id, deque())
            return [d.to_dict() for d in list(buffer)[-limit:]]
    
    def get_aggregate_stats(self, node_id: Optional[str] = None) -> Dict:
        """Get aggregated statistics"""
        with self._lock:
            if node_id:
                return dict(self.statistics.get(node_id, {}))
            
            # Aggregate across all nodes
            all_stats = {
                "total_readings": 0,
                "nodes_reporting": len(self.latest_data),
                "anomaly_detected_count": 0,
                "avg_optical": 0,
                "avg_electrical": 0
            }
            
            optical_sum = electrical_sum = 0
            count = 0
            
            for nid, stats in self.statistics.items():
                all_stats["total_readings"] += stats.get("count", 0)
                optical_sum += stats.get("optical_avg", 0)
                electrical_sum += stats.get("electrical_avg", 0)
                count += 1
                
                latest = self.latest_data.get(nid)
                if latest and latest.processing.get("mycotoxin_detected"):
                    all_stats["anomaly_detected_count"] += 1
            
            if count > 0:
                all_stats["avg_optical"] = optical_sum / count
                all_stats["avg_electrical"] = electrical_sum / count
            
            return all_stats
    
    def clear_old_data(self, max_age_seconds: float = 86400):
        """Clear data older than specified age"""
        cutoff = time.time() - max_age_seconds
        with self._lock:
            for node_id, buffer in self.node_buffers.items():
                while buffer and buffer[0].timestamp < cutoff:
                    buffer.popleft()


# ============================================================================
# ALERT MANAGER
# ============================================================================

class AlertManager:
    """
    Manages alerts based on thresholds from sensor data.
    Supports multiple notification channels.
    """
    
    def __init__(self):
        self.alerts: deque = deque(maxlen=1000)
        self.thresholds: Dict[str, Dict] = {}
        self._lock = threading.RLock()
        self._alert_counter = 0
        
        # Default thresholds
        self.set_default_thresholds()
    
    def set_default_thresholds(self):
        """Set default alert thresholds"""
        self.thresholds = {
            "anomaly_score": {
                "warning": 0.5,
                "critical": 0.8
            },
            "confidence_low": {
                "warning": 0.5
            },
            "battery_low": {
                "warning": 20.0,
                "critical": 10.0
            },
            "rssi_weak": {
                "warning": -80,
                "critical": -90
            },
            "mycotoxin_detected": {
                "critical": True
            }
        }
    
    def set_threshold(self, metric: str, level: str, value: Any):
        """Set a threshold value"""
        with self._lock:
            if metric not in self.thresholds:
                self.thresholds[metric] = {}
            self.thresholds[metric][level] = value
    
    def evaluate_data(self, data: SensorData) -> List[Alert]:
        """Evaluate data against thresholds and generate alerts"""
        triggered = []
        
        # Extract values
        anomaly_score = data.processing.get("anomaly_score", 0)
        confidence = data.processing.get("confidence", 1)
        battery = data.meta.get("battery_percent", 100)
        rssi = data.meta.get("rssi_dbm", -50)
        detected = data.processing.get("mycotoxin_detected", False)
        
        with self._lock:
            # Check anomaly score
            if anomaly_score > self.thresholds["anomaly_score"].get("critical", 0.8):
                triggered.append(self._create_alert(
                    data.node_id, "critical", "anomaly_score",
                    f"Critical anomaly detected: {anomaly_score:.2f}",
                    self.thresholds["anomaly_score"]["critical"], anomaly_score
                ))
            elif anomaly_score > self.thresholds["anomaly_score"].get("warning", 0.5):
                triggered.append(self._create_alert(
                    data.node_id, "warning", "anomaly_score",
                    f"Elevated anomaly score: {anomaly_score:.2f}",
                    self.thresholds["anomaly_score"]["warning"], anomaly_score
                ))
            
            # Check mycotoxin detection
            if detected:
                triggered.append(self._create_alert(
                    data.node_id, "critical", "mycotoxin_detected",
                    "MYCOTOXIN DETECTED - Immediate action required",
                    True, True
                ))
            
            # Check low confidence
            if confidence < self.thresholds["confidence_low"].get("warning", 0.5):
                triggered.append(self._create_alert(
                    data.node_id, "warning", "confidence_low",
                    f"Low confidence reading: {confidence:.2%}",
                    self.thresholds["confidence_low"]["warning"], confidence
                ))
            
            # Check battery
            if battery < self.thresholds["battery_low"].get("critical", 10):
                triggered.append(self._create_alert(
                    data.node_id, "critical", "battery_low",
                    f"Critical battery level: {battery:.1f}%",
                    self.thresholds["battery_low"]["critical"], battery
                ))
            elif battery < self.thresholds["battery_low"].get("warning", 20):
                triggered.append(self._create_alert(
                    data.node_id, "warning", "battery_low",
                    f"Low battery: {battery:.1f}%",
                    self.thresholds["battery_low"]["warning"], battery
                ))
        
        return triggered
    
    def _create_alert(self, node_id: str, severity: str, metric: str,
                     message: str, threshold: float, value: float) -> Alert:
        """Create a new alert"""
        self._alert_counter += 1
        return Alert(
            id=f"ALT-{self._alert_counter:06d}",
            node_id=node_id,
            severity=severity,
            message=message,
            metric=metric,
            threshold=threshold,
            value=value
        )
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert"""
        with self._lock:
            for alert in self.alerts:
                if alert.id == alert_id:
                    alert.acknowledged = True
                    return True
        return False
    
    def get_alerts(self, severity: Optional[str] = None,
                   acknowledged: Optional[bool] = None,
                   limit: int = 100) -> List[Dict]:
        """Get filtered alerts"""
        with self._lock:
            filtered = list(self.alerts)
        
        if severity:
            filtered = [a for a in filtered if a.severity == severity]
        if acknowledged is not None:
            filtered = [a for a in filtered if a.acknowledged == acknowledged]
        
        return [asdict(a) for a in filtered[-limit:]]
    
    def get_active_alerts(self) -> List[Dict]:
        """Get non-acknowledged alerts"""
        return self.get_alerts(acknowledged=False)


# ============================================================================
# MQTT HANDLER
# ============================================================================

class MQTTHandler:
    """
    Handles MQTT communication with sensor nodes.
    Subscribes to data topics and publishes commands.
    """
    
    def __init__(self, broker_host: str, broker_port: int = 1883,
                 registry: NodeRegistry = None, aggregator: DataAggregator = None,
                 alert_manager: AlertManager = None):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.registry = registry
        self.aggregator = aggregator
        self.alert_manager = alert_manager
        self.client: Optional[mqtt.Client] = None
        self.connected = False
        self._running = False
        
    def start(self):
        """Start MQTT client"""
        if not MQTT_AVAILABLE:
            logger.warning("MQTT not available, skipping MQTT startup")
            return False
        
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        
        try:
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
            self._running = True
            logger.info(f"MQTT client started, connecting to {self.broker_host}:{self.broker_port}")
            return True
        except Exception as e:
            logger.error(f"MQTT connection failed: {e}")
            return False
    
    def stop(self):
        """Stop MQTT client"""
        self._running = False
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("MQTT client stopped")
    
    def _on_connect(self, client, userdata, flags, rc):
        """MQTT connect callback"""
        if rc == 0:
            self.connected = True
            logger.info("MQTT connected")
            
            # Subscribe to node data topics
            client.subscribe("mycosentinel/nodes/+/data")
            client.subscribe("mycosentinel/nodes/+/status")
            client.subscribe("mycosentinel/nodes/+/register")
            logger.info("Subscribed to mycosentinel/nodes/+/+")
        else:
            logger.error(f"MQTT connection failed, code: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """MQTT disconnect callback"""
        self.connected = False
        logger.warning(f"MQTT disconnected, code: {rc}")
    
    def _on_message(self, client, userdata, msg):
        """MQTT message callback"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            
            # Extract node_id from topic
            parts = topic.split('/')
            if len(parts) >= 3:
                node_id = parts[2]
                msg_type = parts[3] if len(parts) > 3 else "unknown"
                
                if msg_type == "data":
                    self._handle_data_message(node_id, payload)
                elif msg_type == "status":
                    self._handle_status_message(node_id, payload)
                elif msg_type == "register":
                    self._handle_registration_message(node_id, payload)
                    
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in MQTT message on {msg.topic}")
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
    
    def _handle_data_message(self, node_id: str, payload: Dict):
        """Process incoming sensor data"""
        try:
            # Create SensorData object
            data = SensorData(
                node_id=node_id,
                timestamp=payload.get("timestamp", time.time()),
                sequence_num=payload.get("sequence_num", 0),
                bioreactor=payload.get("bioreactor", {}),
                optical=payload.get("optical", {}),
                electrical=payload.get("electrical", {}),
                processing=payload.get("processing", {}),
                meta=payload.get("meta", {})
            )
            
            # Update registry
            if self.registry:
                self.registry.update_heartbeat(node_id)
            
            # Process in aggregator
            if self.aggregator:
                self.aggregator.process_data(data)
            
            # Check for alerts
            if self.alert_manager:
                alerts = self.alert_manager.evaluate_data(data)
                for alert in alerts:
                    logger.warning(f"ALERT: {alert.message}")
                    
        except Exception as e:
            logger.error(f"Error handling data message: {e}")
    
    def _handle_status_message(self, node_id: str, payload: Dict):
        """Process status update"""
        status = payload.get("status", "unknown")
        if self.registry:
            self.registry.set_node_status(node_id, status)
            self.registry.update_heartbeat(node_id)
    
    def _handle_registration_message(self, node_id: str, payload: Dict):
        """Process registration request"""
        if self.registry:
            self.registry.register_node(
                node_id=node_id,
                sector=payload.get("sector", "unknown"),
                ip_address=payload.get("ip_address", "0.0.0.0"),
                mac_address=payload.get("mac_address", "00:00:00:00:00:00"),
                firmware_version=payload.get("firmware_version", "0.1.0"),
                capabilities=payload.get("capabilities", ["optical", "electrical"]),
            )
    
    def publish_command(self, node_id: str, command: Dict):
        """Send command to a node"""
        if self.client and self.connected:
            topic = f"mycosentinel/commands/{node_id}"
            self.client.publish(topic, json.dumps(command))
            return True
        return False
    
    def broadcast_command(self, command: Dict):
        """Broadcast command to all nodes"""
        if self.client and self.connected:
            self.client.publish("mycosentinel/gateway/commands", json.dumps(command))
            return True
        return False


# ============================================================================
# FLASK API SERVER
# ============================================================================

class GatewayAPIServer:
    """
    Flask-based REST API for the gateway.
    Provides endpoints for node management, data queries, and configuration.
    """
    
    def __init__(self, registry: NodeRegistry, aggregator: DataAggregator,
                 alert_manager: AlertManager, mqtt_handler: MQTTHandler,
                 port: int = 8000):
        self.registry = registry
        self.aggregator = aggregator
        self.alert_manager = alert_manager
        self.mqtt = mqtt_handler
        self.port = port
        self.app = Flask(__name__)
        CORS(self.app)
        self._setup_routes()
    
    def _setup_routes(self):
        """Configure Flask routes"""
        
        @self.app.route('/')
        def index():
            return """<h1>MycoSentinel Gateway API</h1>
            <p>Status: Running</p>
            <p>Endpoints: /api/v1/...</p>"""
        
        @self.app.route('/api/v1/health')
        def health():
            registry_status = self.registry.get_registry_status()
            aggregate_stats = self.aggregator.get_aggregate_stats()
            
            return jsonify({
                "status": "healthy",
                "timestamp": time.time(),
                "registry": registry_status,
                "aggregation": aggregate_stats,
                "mqtt_connected": self.mqtt.connected if self.mqtt else False
            })
        
        @self.app.route('/api/v1/nodes', methods=['GET'])
        def get_nodes():
            nodes = [n.to_dict() for n in self.registry.get_all_nodes()]
            return jsonify({
                "count": len(nodes),
                "nodes": nodes
            })
        
        @self.app.route('/api/v1/nodes', methods=['POST'])
        def register_node():
            data = request.json
            if not data or 'node_id' not in data:
                return jsonify({"error": "node_id required"}), 400
            
            node = self.registry.register_node(
                node_id=data['node_id'],
                sector=data.get('sector', 'unknown'),
                ip_address=data.get('ip_address', request.remote_addr),
                mac_address=data.get('mac_address', '00:00:00:00:00:00'),
                firmware_version=data.get('firmware_version', '0.1.0'),
                capabilities=data.get('capabilities', ['optical', 'electrical'])
            )
            
            return jsonify({"status": "registered", "node": node.to_dict()}), 201
        
        @self.app.route('/api/v1/nodes/<node_id>', methods=['GET'])
        def get_node(node_id):
            node = self.registry.get_node(node_id)
            if not node:
                return jsonify({"error": "Node not found"}), 404
            
            # Get latest data
            latest_data = self.aggregator.get_latest_data(node_id)
            data_dict = latest_data.to_dict() if latest_data else None
            
            # Get statistics
            stats = self.aggregator.get_aggregate_stats(node_id)
            
            return jsonify({
                "node": node.to_dict(),
                "latest_data": data_dict,
                "statistics": stats
            })
        
        @self.app.route('/api/v1/nodes/<node_id>/data', methods=['GET'])
        def get_node_data(node_id):
            limit = request.args.get('limit', 100, type=int)
            history = self.aggregator.get_node_history(node_id, limit)
            
            return jsonify({
                "node_id": node_id,
                "count": len(history),
                "data": history
            })
        
        @self.app.route('/api/v1/nodes/<node_id>/command', methods=['POST'])
        def send_command(node_id):
            cmd = request.json
            if not cmd:
                return jsonify({"error": "Command body required"}), 400
            
            success = self.mqtt.publish_command(node_id, cmd)
            return jsonify({"sent": success, "command": cmd})
        
        @self.app.route('/api/v1/aggregate/all', methods=['GET'])
        def get_aggregate():
            stats = self.aggregator.get_aggregate_stats()
            latest = {nid: d.to_dict() for nid, d in self.aggregator.get_all_latest().items()}
            
            return jsonify({
                "statistics": stats,
                "latest_data": latest
            })
        
        @self.app.route('/api/v1/alerts', methods=['GET'])
        def get_alerts():
            severity = request.args.get('severity')
            acknowledged = request.args.get('acknowledged', type=bool)
            limit = request.args.get('limit', 100, type=int)
            
            alerts = self.alert_manager.get_alerts(severity, acknowledged, limit)
            return jsonify({
                "count": len(alerts),
                "alerts": alerts
            })
        
        @self.app.route('/api/v1/alerts/<alert_id>/acknowledge', methods=['POST'])
        def acknowledge_alert(alert_id):
            success = self.alert_manager.acknowledge_alert(alert_id)
            return jsonify({"acknowledged": success})
        
        @self.app.route('/dashboard')
        def dashboard():
            # Simple HTML dashboard
            registry_status = self.registry.get_registry_status()
            nodes = self.registry.get_all_nodes()
            alerts = self.alert_manager.get_active_alerts()
            
            html = '''
            <!DOCTYPE html>
            <html>
            <head>
                <title>MycoSentinel Gateway Dashboard</title>
                <style>
                    body { font-family: sans-serif; margin: 20px; background: #1a1a2e; color: #eee; }
                    .header { background: #16213e; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
                    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
                    .card { background: #0f3460; padding: 15px; border-radius: 10px; }
                    .metric { font-size: 2em; color: #e94560; }
                    .online { color: #16c79a; }
                    .offline { color: #e94560; }
                    .warning { color: #f9a825; }
                    .critical { color: #e94560; }
                    table { width: 100%; border-collapse: collapse; margin-top: 10px; }
                    th, td { padding: 10px; text-align: left; border-bottom: 1px solid #333; }
                    th { background: #16213e; }
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>🍄 MycoSentinel Gateway Dashboard</h1>
                    <p>10-Node Biosensor Network Status</p>
                </div>
                
                <div class="grid">
                    <div class="card">
                        <h3>Network Health</h3>
                        <div class="metric">{total}/{expected}</div>
                        <p>Nodes Registered</p>
                        <div class="metric online">{online}</div>
                        <p>Nodes Online</p>
                        <div class="metric offline">{offline}</div>
                        <p>Nodes Offline</p>
                    </div>
                    
                    <div class="card">
                        <h3>Data Statistics</h3>
                        <div class="metric">{readings:,}</div>
                        <p>Total Readings</p>
                        <div class="metric">{avg_optical:.3f}</div>
                        <p>Avg Optical Response</p>
                        <div class="metric">{avg_electrical:.3f}</div>
                        <p>Avg Electrical Response</p>
                    </div>
                    
                    <div class="card">
                        <h3>Active Alerts</h3>
                        <div class="metric {alert_class}">{alert_count}</div>
                        <p>Unhandled Alerts</p>
                    </div>
                </div>
                
                <div class="card" style="margin-top: 20px;">
                    <h3>Node Status</h3>
                    <table>
                        <tr>
                            <th>Node ID</th>
                            <th>Sector</th>
                            <th>Status</th>
                            <th>Last Seen</th>
                            <th>Battery</th>
                        </tr>
                        {node_rows}
                    </table>
                </div>
            </body>
            </html>
            '''
            
            agg_stats = self.aggregator.get_aggregate_stats()
            
            node_rows = ""
            for node in nodes:
                status_class = "online" if node.status == "online" else "offline"
                last_seen = f"{int(time.time() - node.last_seen)}s ago"
                node_rows += f'''<tr>
                    <td>{node.node_id}</td>
                    <td>{node.sector}</td>
                    <td class="{status_class}">{node.status}</td>
                    <td>{last_seen}</td>
                    <td>-</td>
                </tr>'''
            
            alert_class = "critical" if len(alerts) > 0 else "online"
            
            return render_template_string(
                html,
                total=registry_status['total_nodes'],
                expected=registry_status['expected_nodes'],
                online=registry_status['online_nodes'],
                offline=registry_status['offline_nodes'],
                readings=agg_stats.get('total_readings', 0),
                avg_optical=agg_stats.get('avg_optical', 0),
                avg_electrical=agg_stats.get('avg_electrical', 0),
                node_rows=node_rows,
                alert_count=len(alerts),
                alert_class=alert_class
            )
    
    def run(self, debug=False):
        """Start the Flask server"""
        logger.info(f"Starting API server on port {self.port}")
        self.app.run(host='0.0.0.0', port=self.port, debug=debug, threaded=True)


# ============================================================================
# MAIN GATEWAY CLASS
# ============================================================================

class MycoSentinelGateway:
    """
    Main gateway controller class.
    Orchestrates registry, aggregator, alerts, MQTT, and API.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        
        # Initialize components
        self.registry = NodeRegistry(expected_nodes=10)
        self.aggregator = DataAggregator(max_buffer_size=10000)
        self.alert_manager = AlertManager()
        self.mqtt = MQTTHandler(
            broker_host=self.config.get('mqtt_host', 'localhost'),
            broker_port=self.config.get('mqtt_port', 1883),
            registry=self.registry,
            aggregator=self.aggregator,
            alert_manager=self.alert_manager
        )
        self.api = GatewayAPIServer(
            registry=self.registry,
            aggregator=self.aggregator,
            alert_manager=self.alert_manager,
            mqtt_handler=self.mqtt,
            port=self.config.get('api_port', 8000)
        )
        
        # Background tasks
        self._running = False
        self._threads = []
    
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """Load configuration from file"""
        default_config = {
            "mqtt_host": "localhost",
            "mqtt_port": 1883,
            "api_port": 8000,
            "heartbeat_timeout": 120,
            "expected_nodes": 10
        }
        
        if config_path and Path(config_path).exists():
            with open(config_path) as f:
                loaded = json.load(f)
                default_config.update(loaded)
        
        return default_config
    
    def _start_heartbeat_monitor(self):
        """Start background thread to check node heartbeats"""
        def monitor():
            while self._running:
                offline = self.registry.check_offline_nodes(
                    self.config.get('heartbeat_timeout', 120)
                )
                if offline:
                    logger.warning(f"Nodes offline: {', '.join(offline)}")
                time.sleep(30)
        
        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
        self._threads.append(thread)
        logger.info("Heartbeat monitor started")
    
    def _start_data_cleanup(self):
        """Start background thread to clean old data"""
        def cleanup():
            while self._running:
                self.aggregator.clear_old_data(max_age_seconds=86400)
                time.sleep(3600)  # Run once per hour
        
        thread = threading.Thread(target=cleanup, daemon=True)
        thread.start()
        self._threads.append(thread)
        logger.info("Data cleanup task started")
    
    def start(self):
        """Start all gateway services"""
        logger.info("=" * 60)
        logger.info("Starting MycoSentinel Gateway Server")
        logger.info("=" * 60)
        
        self._running = True
        
        # Start MQTT
        self.mqtt.start()
        
        # Start background tasks
        self._start_heartbeat_monitor()
        self._start_data_cleanup()
        
        # Start API server (blocking)
        self.api.run(debug=False)
    
    def stop(self):
        """Stop all gateway services"""
        logger.info("Stopping gateway...")
        self._running = False
        self.mqtt.stop()


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='MycoSentinel Gateway Server')
    parser.add_argument('--config', '-c', help='Path to config file')
    parser.add_argument('--port', '-p', type=int, default=8000, help='API port')
    parser.add_argument('--mqtt-host', default='localhost', help='MQTT broker host')
    parser.add_argument('--mqtt-port', type=int, default=1883, help='MQTT broker port')
    
    args = parser.parse_args()
    
    # Create config dict from args
    config = {
        "api_port": args.port,
        "mqtt_host": args.mqtt_host,
        "mqtt_port": args.mqtt_port
    }
    
    # Write temp config if file not provided
    config_path = args.config
    if not config_path:
        config_path = "/tmp/mycosentinel_gateway_config.json"
        with open(config_path, 'w') as f:
            json.dump(config, f)
    
    # Start gateway
    gateway = MycoSentinelGateway(config_path)
    
    try:
        gateway.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        gateway.stop()


if __name__ == '__main__':
    main()
