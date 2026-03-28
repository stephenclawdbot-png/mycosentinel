#!/usr/bin/env python3
"""
MycoSentinel Gateway Server (FastAPI Version)
Core gateway software for 10-node biosensor network simulation.

Features:
- Node registration and management
- MQTT broker integration for data collection
- Data aggregation from multiple nodes
- RESTful JSON API for data queries
- Real-time WebSocket streaming
- Alert threshold monitoring
- InfluxDB persistence

Usage:
    python3 gateway.py

Author: MycoSentinel Deployment Team
Version: 1.0.0
"""

import json
import os
import logging
import asyncio
import time
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# MQTT imports
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    print("Warning: paho-mqtt not installed, MQTT features disabled")

# InfluxDB imports
try:
    from influxdb_client import InfluxDBClient, Point
    from influxdb_client.client.write_api import SYNCHRONOUS
    INFLUX_AVAILABLE = True
except ImportError:
    INFLUX_AVAILABLE = False
    print("Warning: influxdb-client not installed, using in-memory storage")

# Socket.io for WebSocket
try:
    import socketio
    SIO_AVAILABLE = True
except ImportError:
    SIO_AVAILABLE = False
    print("Warning: python-socketio not installed, WebSocket disabled")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/gateway.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

MQTT_HOST = os.getenv('MQTT_HOST', 'localhost')
MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))
INFLUX_HOST = os.getenv('INFLUX_HOST', 'localhost')
INFLUX_PORT = int(os.getenv('INFLUX_PORT', '8086'))
INFLUX_TOKEN = os.getenv('INFLUX_TOKEN', 'mycosentinel-sim-token')
INFLUX_ORG = os.getenv('INFLUX_ORG', 'mycosentinel')
INFLUX_BUCKET = os.getenv('INFLUX_BUCKET', 'sensor-data')
API_PORT = int(os.getenv('API_PORT', '8000'))
EXPECTED_NODES = int(os.getenv('NODE_COUNT', '10'))

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
    severity: str
    message: str
    metric: str
    threshold: float
    value: float
    timestamp: float = field(default_factory=time.time)
    acknowledged: bool = False

# Pydantic models for API
class NodeRegistrationRequest(BaseModel):
    node_id: str
    sector: str
    ip_address: str
    mac_address: str
    firmware_version: str = "0.1.0"
    capabilities: List[str] = ["optical", "electrical"]

class CommandRequest(BaseModel):
    command: str
    params: Optional[Dict] = None

class AlertAcknowledge(BaseModel):
    acknowledged: bool = True

# ============================================================================
# NODE REGISTRY
# ============================================================================

class NodeRegistry:
    """Central registry for managing sensor nodes"""
    
    def __init__(self, expected_nodes: int = 10):
        self.nodes: Dict[str, NodeRegistration] = {}
        self.expected_count = expected_nodes
        self._lock = threading.RLock()
        
    def register_node(self, node_id: str, sector: str, ip_address: str,
                     mac_address: str, firmware_version: str = "0.1.0",
                     capabilities: List[str] = None) -> NodeRegistration:
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
        with self._lock:
            if node_id in self.nodes:
                del self.nodes[node_id]
                logger.info(f"Node unregistered: {node_id}")
                return True
            return False
    
    def update_heartbeat(self, node_id: str) -> bool:
        with self._lock:
            if node_id in self.nodes:
                self.nodes[node_id].last_seen = time.time()
                if self.nodes[node_id].status != "online":
                    self.nodes[node_id].status = "online"
                    logger.info(f"Node came online: {node_id}")
                return True
            return False
    
    def set_node_status(self, node_id: str, status: str) -> bool:
        with self._lock:
            if node_id in self.nodes:
                old_status = self.nodes[node_id].status
                self.nodes[node_id].status = status
                if old_status != status:
                    logger.info(f"Node {node_id} status: {old_status} -> {status}")
                return True
            return False
    
    def get_node(self, node_id: str) -> Optional[NodeRegistration]:
        with self._lock:
            return self.nodes.get(node_id)
    
    def get_all_nodes(self) -> List[NodeRegistration]:
        with self._lock:
            return list(self.nodes.values())
    
    def get_nodes_by_sector(self, sector: str) -> List[NodeRegistration]:
        with self._lock:
            return [n for n in self.nodes.values() if n.sector == sector]
    
    def get_online_nodes(self) -> List[NodeRegistration]:
        with self._lock:
            return [n for n in self.nodes.values() if n.status == "online"]
    
    def check_offline_nodes(self, timeout_seconds: float = 120) -> List[str]:
        offline_nodes = []
        with self._lock:
            now = time.time()
            for node_id, node in self.nodes.items():
                if now - node.last_seen > timeout_seconds and node.status == "online":
                    node.status = "offline"
                    offline_nodes.append(node_id)
                    logger.warning(f"Node offline: {node_id}")
        return offline_nodes
    
    def get_registry_status(self) -> Dict:
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
    """Aggregates data from multiple sensor nodes"""
    
    def __init__(self, max_buffer_size: int = 10000):
        self.node_buffers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_buffer_size))
        self.latest_data: Dict[str, SensorData] = {}
        self.statistics: Dict[str, Dict] = defaultdict(lambda: defaultdict(float))
        self._data_callbacks: List[Callable[[SensorData], None]] = []
        self._lock = threading.RLock()
    
    def add_data_callback(self, callback: Callable[[SensorData], None]):
        self._data_callbacks.append(callback)
    
    def process_data(self, data: SensorData) -> bool:
        with self._lock:
            self.node_buffers[data.node_id].append(data)
            self.latest_data[data.node_id] = data
            self._update_statistics(data)
            
            for callback in self._data_callbacks:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"Data callback error: {e}")
            return True
    
    def _update_statistics(self, data: SensorData):
        node_stats = self.statistics[data.node_id]
        optical_norm = data.optical.get("normalized", 0)
        electrical_norm = data.electrical.get("normalized_response", 0)
        anomaly_score = data.processing.get("anomaly_score", 0)
        
        n = node_stats.get("count", 0) + 1
        node_stats["count"] = n
        node_stats["optical_avg"] = (node_stats.get("optical_avg", 0) * (n-1) + optical_norm) / n
        node_stats["electrical_avg"] = (node_stats.get("electrical_avg", 0) * (n-1) + electrical_norm) / n
        node_stats["anomaly_max"] = max(node_stats.get("anomaly_max", 0), anomaly_score)
    
    def get_latest_data(self, node_id: Optional[str] = None) -> Optional[SensorData]:
        with self._lock:
            if node_id:
                return self.latest_data.get(node_id)
            return None
    
    def get_all_latest(self) -> Dict[str, SensorData]:
        with self._lock:
            return dict(self.latest_data)
    
    def get_node_history(self, node_id: str, limit: int = 100) -> List[Dict]:
        with self._lock:
            buffer = self.node_buffers.get(node_id, deque())
            return [d.to_dict() for d in list(buffer)[-limit:]]
    
    def get_aggregate_stats(self, node_id: Optional[str] = None) -> Dict:
        with self._lock:
            if node_id:
                return dict(self.statistics.get(node_id, {}))
            
            all_stats = {
                "total_readings": 0,
                "nodes_reporting": len(self.latest_data),
                "anomaly_detected_count": 0,
                "avg_optical": 0,
                "avg_electrical": 0
            }
            
            optical_sum = electrical_sum = count = 0
            
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
        cutoff = time.time() - max_age_seconds
        with self._lock:
            for node_id, buffer in self.node_buffers.items():
                while buffer and buffer[0].timestamp < cutoff:
                    buffer.popleft()

# ============================================================================
# ALERT MANAGER
# ============================================================================

class AlertManager:
    """Manages alerts based on thresholds from sensor data"""
    
    def __init__(self):
        self.alerts: deque = deque(maxlen=1000)
        self.thresholds: Dict[str, Dict] = {}
        self._lock = threading.RLock()
        self._alert_counter = 0
        self.set_default_thresholds()
        self._callbacks: List[Callable[[Alert], None]] = []
    
    def set_default_thresholds(self):
        self.thresholds = {
            "anomaly_score": {"warning": 0.5, "critical": 0.8},
            "confidence_low": {"warning": 0.5},
            "battery_low": {"warning": 20.0, "critical": 10.0},
            "rssi_weak": {"warning": -80, "critical": -90},
            "mycotoxin_detected": {"critical": True}
        }
    
    def add_callback(self, callback: Callable[[Alert], None]):
        self._callbacks.append(callback)
    
    def evaluate_data(self, data: SensorData) -> List[Alert]:
        triggered = []
        anomaly_score = data.processing.get("anomaly_score", 0)
        confidence = data.processing.get("confidence", 1)
        battery = data.meta.get("battery_percent", 100)
        rssi = data.meta.get("rssi_dbm", -50)
        detected = data.processing.get("mycotoxin_detected", False)
        
        with self._lock:
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
            
            if detected:
                triggered.append(self._create_alert(
                    data.node_id, "critical", "mycotoxin_detected",
                    "MYCOTOXIN DETECTED - Immediate action required",
                    True, True
                ))
            
            if confidence < self.thresholds["confidence_low"].get("warning", 0.5):
                triggered.append(self._create_alert(
                    data.node_id, "warning", "confidence_low",
                    f"Low confidence reading: {confidence:.2%}",
                    self.thresholds["confidence_low"]["warning"], confidence
                ))
            
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
            
            for alert in triggered:
                for callback in self._callbacks:
                    try:
                        callback(alert)
                    except Exception as e:
                        logger.error(f"Alert callback error: {e}")
        
        return triggered
    
    def _create_alert(self, node_id: str, severity: str, metric: str,
                     message: str, threshold: float, value: float) -> Alert:
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
        with self._lock:
            for alert in self.alerts:
                if alert.id == alert_id:
                    alert.acknowledged = True
                    return True
        return False
    
    def get_alerts(self, severity: Optional[str] = None,
                   acknowledged: Optional[bool] = None,
                   limit: int = 100) -> List[Dict]:
        with self._lock:
            filtered = list(self.alerts)
        
        if severity:
            filtered = [a for a in filtered if a.severity == severity]
        if acknowledged is not None:
            filtered = [a for a in filtered if a.acknowledged == acknowledged]
        
        return [asdict(a) for a in filtered[-limit:]]
    
    def get_active_alerts(self) -> List[Dict]:
        return self.get_alerts(acknowledged=False)

# ============================================================================
# INFLUXDB HANDLER
# ============================================================================

class InfluxDBHandler:
    """Handles InfluxDB persistence"""
    
    def __init__(self, host: str, port: int, token: str, org: str, bucket: str):
        self.host = host
        self.port = port
        self.token = token
        self.org = org
        self.bucket = bucket
        self.client: Optional[InfluxDBClient] = None
        self.write_api = None
        self._connected = False
    
    def connect(self) -> bool:
        if not INFLUX_AVAILABLE:
            logger.warning("InfluxDB client not available")
            return False
        
        try:
            url = f"http://{self.host}:{self.port}"
            self.client = InfluxDBClient(url=url, token=self.token, org=self.org)
            self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
            self._connected = True
            logger.info(f"Connected to InfluxDB at {url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to InfluxDB: {e}")
            return False
    
    def write_data(self, data: SensorData):
        if not self._connected or not self.write_api:
            return
        
        try:
            point = Point("sensor_data") \
                .tag("node_id", data.node_id) \
                .tag("sector", data.meta.get("sector", "unknown")) \
                .field("optical_normalized", data.optical.get("normalized", 0)) \
                .field("electrical_normalized", data.electrical.get("normalized_response", 0)) \
                .field("anomaly_score", data.processing.get("anomaly_score", 0)) \
                .field("confidence", data.processing.get("confidence", 0)) \
                .field("temperature", data.bioreactor.get("temperature_c", 0)) \
                .field("battery_percent", data.meta.get("battery_percent", 0)) \
                .time(datetime.utcfromtimestamp(data.timestamp))
            
            self.write_api.write(bucket=self.bucket, org=self.org, record=point)
        except Exception as e:
            logger.error(f"Failed to write to InfluxDB: {e}")

# ============================================================================
# MQTT HANDLER
# ============================================================================

class MQTTHandler:
    """Handles MQTT communication"""
    
    def __init__(self, broker_host: str, broker_port: int,
                 registry: NodeRegistry, aggregator: DataAggregator,
                 alert_manager: AlertManager, influx: Optional[InfluxDBHandler] = None):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.registry = registry
        self.aggregator = aggregator
        self.alert_manager = alert_manager
        self.influx = influx
        self.client: Optional[mqtt.Client] = None
        self.connected = False
        self._running = False
    
    def start(self):
        if not MQTT_AVAILABLE:
            logger.warning("MQTT not available")
            return False
        
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        
        try:
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
            self._running = True
            logger.info(f"MQTT connected to {self.broker_host}:{self.broker_port}")
            return True
        except Exception as e:
            logger.error(f"MQTT connection failed: {e}")
            return False
    
    def stop(self):
        self._running = False
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("MQTT disconnected")
    
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            logger.info("MQTT subscribed to node topics")
            client.subscribe("mycosentinel/nodes/+/data")
            client.subscribe("mycosentinel/nodes/+/status")
            client.subscribe("mycosentinel/nodes/+/register")
        else:
            logger.error(f"MQTT connection failed: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        logger.warning(f"MQTT disconnected: {rc}")
    
    def _on_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            parts = topic.split('/')
            
            if len(parts) >= 3:
                node_id = parts[2]
                msg_type = parts[3] if len(parts) > 3 else "unknown"
                
                if msg_type == "data":
                    self._handle_data(node_id, payload)
                elif msg_type == "status":
                    self._handle_status(node_id, payload)
                elif msg_type == "register":
                    self._handle_registration(node_id, payload)
                    
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON on {msg.topic}")
        except Exception as e:
            logger.error(f"MQTT message error: {e}")
    
    def _handle_data(self, node_id: str, payload: Dict):
        try:
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
            
            self.registry.update_heartbeat(node_id)
            self.aggregator.process_data(data)
            
            if self.influx:
                self.influx.write_data(data)
            
            alerts = self.alert_manager.evaluate_data(data)
            for alert in alerts:
                logger.warning(f"ALERT: {alert.message}")
                
        except Exception as e:
            logger.error(f"Data handling error: {e}")
    
    def _handle_status(self, node_id: str, payload: Dict):
        status = payload.get("status", "unknown")
        self.registry.set_node_status(node_id, status)
        self.registry.update_heartbeat(node_id)
    
    def _handle_registration(self, node_id: str, payload: Dict):
        self.registry.register_node(
            node_id=node_id,
            sector=payload.get("sector", "unknown"),
            ip_address=payload.get("ip_address", "0.0.0.0"),
            mac_address=payload.get("mac_address", "00:00:00:00:00:00"),
            firmware_version=payload.get("firmware_version", "0.1.0"),
            capabilities=payload.get("capabilities", ["optical", "electrical"])
        )

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(title="MycoSentinel Gateway", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Global state
registry = NodeRegistry(expected_nodes=EXPECTED_NODES)
aggregator = DataAggregator()
alert_manager = AlertManager()
influx = InfluxDBHandler(INFLUX_HOST, INFLUX_PORT, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET)
mqtt = MQTTHandler(MQTT_HOST, MQTT_PORT, registry, aggregator, alert_manager, influx)

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    return {"message": "MycoSentinel Gateway API", "version": "1.0.0"}

@app.get("/api/v1/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "registry": registry.get_registry_status(),
        "aggregation": aggregator.get_aggregate_stats(),
        "mqtt_connected": mqtt.connected
    }

@app.get("/api/v1/nodes")
async def get_nodes():
    nodes = [n.to_dict() for n in registry.get_all_nodes()]
    return {"count": len(nodes), "nodes": nodes}

@app.post("/api/v1/nodes")
async def register_node(req: NodeRegistrationRequest):
    node = registry.register_node(
        node_id=req.node_id,
        sector=req.sector,
        ip_address=req.ip_address,
        mac_address=req.mac_address,
        firmware_version=req.firmware_version,
        capabilities=req.capabilities
    )
    return {"status": "registered", "node": node.to_dict()}

@app.get("/api/v1/nodes/{node_id}")
async def get_node(node_id: str):
    node = registry.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    latest = aggregator.get_latest_data(node_id)
    return {
        "node": node.to_dict(),
        "latest_data": latest.to_dict() if latest else None,
        "statistics": aggregator.get_aggregate_stats(node_id)
    }

@app.get("/api/v1/nodes/{node_id}/data")
async def get_node_data(node_id: str, limit: int = 100):
    history = aggregator.get_node_history(node_id, limit)
    return {"node_id": node_id, "count": len(history), "data": history}

@app.post("/api/v1/nodes/{node_id}/command")
async def send_command(node_id: str, cmd: CommandRequest):
    return {"sent": True, "command": cmd.command, "params": cmd.params}

@app.get("/api/v1/aggregate/all")
async def get_aggregate():
    stats = aggregator.get_aggregate_stats()
    latest = {nid: d.to_dict() for nid, d in aggregator.get_all_latest().items()}
    return {"statistics": stats, "latest_data": latest}

@app.get("/api/v1/alerts")
async def get_alerts(severity: Optional[str] = None, acknowledged: Optional[bool] = None, limit: int = 100):
    alerts = alert_manager.get_alerts(severity, acknowledged, limit)
    return {"count": len(alerts), "alerts": alerts}

@app.post("/api/v1/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, ack: AlertAcknowledge):
    success = alert_manager.acknowledge_alert(alert_id)
    return {"acknowledged": success}

# ============================================================================
# WEBSOCKET ENDPOINT
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    def send_alert(alert: Alert):
        asyncio.create_task(websocket.send_json({
            "type": "alert",
            "data": asdict(alert)
        }))
    
    def send_data(data: SensorData):
        asyncio.create_task(websocket.send_json({
            "type": "data",
            "data": data.to_dict()
        }))
    
    alert_manager.add_callback(send_alert)
    aggregator.add_data_callback(send_data)
    
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back for keepalive
            await websocket.send_json({"type": "ping", "timestamp": time.time()})
    except WebSocketDisconnect:
        pass

# ============================================================================
# DASHBOARD HTML
# ============================================================================

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>MycoSentinel Gateway Dashboard</title>
    <style>
        body { font-family: sans-serif; margin: 0; background: #1a1a2e; color: #eee; }
        .header { background: #16213e; padding: 20px; text-align: center; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; padding: 20px; }
        .card { background: #0f3460; padding: 20px; border-radius: 10px; }
        .metric { font-size: 2.5em; color: #e94560; }
        .online { color: #16c79a; }
        .offline { color: #e94560; }
        .warning { color: #f9a825; }
        .critical { color: #e94560; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #333; }
        th { background: #16213e; }
        tr:hover { background: #1a4a7a; }
        #alerts { max-height: 300px; overflow-y: auto; }
        .alert-item { padding: 10px; margin: 5px 0; border-radius: 5px; }
        .alert-critical { background: #e94560; }
        .alert-warning { background: #f9a825; }
        .alert-info { background: #16c79a; }
        .sector-grid { display: flex; justify-content: space-around; padding: 20px; }
        .sector { width: 150px; height: 150px; border-radius: 10px; display: flex; flex-direction: column; align-items: center; justify-content: center; background: #0f3460; }
        .sector.active { border: 2px solid #16c79a; }
        .sector.alert { border: 2px solid #e94560; }
        h1 { margin: 0; }
        .status-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin-right: 5px; }
        .status-online { background: #16c79a; }
        .status-offline { background: #e94560; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🍄 MycoSentinel Gateway Dashboard</h1>
        <p>10-Node Biosensor Network Simulation</p>
    </div>
    
    <div class="grid">
        <div class="card">
            <h3>Network Health</h3>
            <div class="metric" id="registered-count">0/10</div>
            <p>Nodes Registered</p>
            <div class="metric online" id="online-count">0</div>
            <p>Nodes Online</p>
            <div class="metric offline" id="offline-count">0</div>
            <p>Nodes Offline</p>
        </div>
        
        <div class="card">
            <h3>Sensor Data</h3>
            <div class="metric" id="total-readings">0</div>
            <p>Total Readings</p>
            <div class="metric" id="avg-optical">0.00</div>
            <p>Avg Optical Response</p>
            <div class="metric" id="avg-electrical">0.00</div>
            <p>Avg Electrical Response</p>
        </div>
        
        <div class="card">
            <h3>Active Alerts</h3>
            <div class="metric critical" id="alert-count">0</div>
            <p>Unhandled Alerts</p>
            <div id="alerts"></div>
        </div>
    </div>
    
    <div class="card" style="margin: 0 20px;">
        <h3>Sector Heat Map</h3>
        <div class="sector-grid">
            <div class="sector" id="sector-A">
                <h2>Sector A</h2>
                <span id="sector-a-nodes">0 nodes</span>
            </div>
            <div class="sector" id="sector-B">
                <h2>Sector B</h2>
                <span id="sector-b-nodes">0 nodes</span>
            </div>
            <div class="sector" id="sector-C">
                <h2>Sector C</h2>
                <span id="sector-c-nodes">0 nodes</span>
            </div>
            <div class="sector" id="sector-D">
                <h2>Sector D</h2>
                <span id="sector-d-nodes">0 nodes</span>
            </div>
        </div>
    </div>
    
    <div class="card" style="margin: 20px;">
        <h3>Node Status</h3>
        <table id="node-table">
            <tr>
                <th>Node ID</th>
                <th>Sector</th>
                <th>Status</th>
                <th>Last Seen</th>
                <th>Anomaly</th>
            </tr>
        </table>
    </div>
    
    <script>
        const ws = new WebSocket(`ws://${window.location.host}/ws`);
        let alerts = [];
        
        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            if (msg.type === 'alert') {
                alerts.unshift(msg.data);
                updateAlerts();
            }
        };
        
        async function fetchData() {
            try {
                const [health, nodes, agg, alertList] = await Promise.all([
                    fetch('/api/v1/health').then(r => r.json()),
                    fetch('/api/v1/nodes').then(r => r.json()),
                    fetch('/api/v1/aggregate/all').then(r => r.json()),
                    fetch('/api/v1/alerts').then(r => r.json())
                ]);
                
                updateHealth(health);
                updateNodes(nodes);
                updateAggregation(agg);
                alerts = alertList.alerts.filter(a => !a.acknowledged);
                updateAlerts();
            } catch (e) {
                console.error('Fetch error:', e);
            }
        }
        
        function updateHealth(data) {
            document.getElementById('registered-count').textContent = 
                `${data.registry.online_nodes + data.registry.offline_nodes}/${data.registry.expected_nodes}`;
            document.getElementById('online-count').textContent = data.registry.online_nodes;
            document.getElementById('offline-count').textContent = data.registry.offline_nodes;
        }
        
        function updateNodes(data) {
            const tbody = document.getElementById('node-table');
            tbody.innerHTML = `<tr><th>Node ID</th><th>Sector</th><th>Status</th><th>Last Seen</th><th>Anomaly</th></tr>`;
            
            const sectors = {A: 0, B: 0, C: 0, D: 0};
            
            data.nodes.forEach(node => {
                sectors[node.sector] = (sectors[node.sector] || 0) + 1;
                const statusClass = node.status === 'online' ? 'online' : 'offline';
                const lastSeen = Math.floor(node.last_seen_seconds_ago);
                tbody.innerHTML += `<tr>
                    <td>${node.node_id}</td>
                    <td>${node.sector}</td>
                    <td class="${statusClass}">
                        <span class="status-dot status-${node.status}"></span>${node.status}
                    </td>
                    <td>${lastSeen}s ago</td>
                    <td>-</td>
                </tr>`;
            });
            
            document.getElementById('sector-a-nodes').textContent = `${sectors.A} nodes`;
            document.getElementById('sector-b-nodes').textContent = `${sectors.B} nodes`;
            document.getElementById('sector-c-nodes').textContent = `${sectors.C} nodes`;
            document.getElementById('sector-d-nodes').textContent = `${sectors.D} nodes`;
        }
        
        function updateAggregation(data) {
            document.getElementById('total-readings').textContent = data.statistics.total_readings.toLocaleString();
            document.getElementById('avg-optical').textContent = data.statistics.avg_optical.toFixed(3);
            document.getElementById('avg-electrical').textContent = data.statistics.avg_electrical.toFixed(3);
        }
        
        function updateAlerts() {
            document.getElementById('alert-count').textContent = alerts.length;
            const container = document.getElementById('alerts');
            container.innerHTML = alerts.slice(0, 10).map(alert => 
                `<div class="alert-item alert-${alert.severity}">${alert.message}</div>`
            ).join('');
        }
        
        setInterval(fetchData, 1000);
        fetchData();
    </script>
</body>
</html>
"""

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    return DASHBOARD_HTML

# ============================================================================
# BACKGROUND TASKS
# ============================================================================

async def heartbeat_monitor():
    """Background task to check node heartbeats"""
    while True:
        await asyncio.sleep(30)
        offline = registry.check_offline_nodes(120)
        if offline:
            logger.warning(f"Nodes offline: {', '.join(offline)}")

# ============================================================================
# STARTUP
# ============================================================================

@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info("Starting MycoSentinel Gateway")
    logger.info("=" * 60)
    
    # Connect to InfluxDB
    if influx.connect():
        logger.info("InfluxDB connected")
    
    # Start MQTT
    if mqtt.start():
        logger.info("MQTT started")
    
    # Start background tasks
    asyncio.create_task(heartbeat_monitor())

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down gateway...")
    mqtt.stop()

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=API_PORT)