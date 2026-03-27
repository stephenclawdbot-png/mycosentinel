"""
Network communication for distributed MycoSentinel nodes.
Supports MQTT and HTTP for IoT connectivity.
"""

import json
import time
import threading
from typing import Dict, List, Optional, Callable
from dataclasses import asdict
import logging
import queue

logger = logging.getLogger(__name__)

class SensorNode:
    """
    Individual sensor node controller.
    
    Manages:
    - Bioreactor conditions
    - Sensor readings (optical + electrical)
    - Signal processing
    - Data transmission to gateway
    
    Runs continuously, collecting and processing data.
    """
    
    def __init__(
        self,
        node_id: str,
        sampling_rate_hz: float = 1.0,
        use_mock: bool = True
    ):
        self.node_id = node_id
        self.sampling_rate = sampling_rate_hz
        self.interval = 1.0 / sampling_rate_hz
        self.use_mock = use_mock
        
        # Components (initialized lazily)
        self.bioreactor = None
        self.optical_sensor = None
        self.electrical_sensor = None
        self.processor = None
        
        # State
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callbacks: List[Callable] = []
        self._data_buffer: queue.Queue = queue.Queue(maxsize=1000)
        
        # Statistics
        self.readings_count = 0
        self.anomaly_count = 0
        self.start_time = None
        
        logger.info(f"SensorNode {node_id} initialized")
    
    def initialize_components(self):
        """Initialize all hardware components"""
        from .bioreactor import BioreactorController
        from .sensor import OpticalSensor, ElectricalSensor
        from .pipeline import SignalProcessor
        
        self.bioreactor = BioreactorController(use_mock=self.use_mock)
        self.optical_sensor = OpticalSensor(use_mock=self.use_mock)
        self.electrical_sensor = ElectricalSensor(use_mock=self.use_mock)
        self.processor = SignalProcessor(use_ml=False)
        
        # Start bioreactor control
        self.bioreactor.start()
        
        logger.info("All components initialized")
    
    def register_callback(self, callback: Callable):
        """Register callback for processed data"""
        self._callbacks.append(callback)
    
    def _read_loop(self):
        """Main data acquisition loop"""
        logger.info(f"Node {self.node_id}: Starting read loop")
        
        # Calibration phase
        calibration_readings = []
        logger.info(f"Node {self.node_id}: Calibrating baseline...")
        
        for i in range(30):  # 30 second calibration
            if not self._running:
                return
            
            reading = self.optical_sensor.capture()
            calibration_readings.append(reading.value)
            time.sleep(1)
        
        self.processor.calibrate_baseline(calibration_readings)
        logger.info(f"Node {self.node_id}: Calibration complete")
        
        # Main loop
        while self._running:
            try:
                # Read sensors
                optical_reading = self.optical_sensor.capture()
                electrical_reading = self.electrical_sensor.measure()
                
                # Process optical signal (primary)
                processed = self.processor.process(
                    optical_reading.value,
                    timestamp=optical_reading.timestamp
                )
                
                self.readings_count += 1
                if processed.contaminant_detected:
                    self.anomaly_count += 1
                
                # Build data packet
                packet = {
                    "node_id": self.node_id,
                    "timestamp": time.time(),
                    "bioreactor": self.bioreactor.get_conditions().__dict__ if self.bioreactor else {},
                    "optical_raw": optical_reading.value,
                    "electrical_raw": electrical_reading.value,
                    "processed": {
                        "filtered": processed.filtered_value,
                        "normalized": processed.normalized_value,
                        "anomaly_score": processed.anomaly_score,
                        "contaminant_detected": processed.contaminant_detected,
                        "confidence": processed.confidence
                    },
                    "meta": {
                        "uptime": time.time() - self.start_time if self.start_time else 0,
                        "total_readings": self.readings_count,
                        "anomaly_count": self.anomaly_count
                    }
                }
                
                # Queue for transmission
                try:
                    self._data_buffer.put_nowait(packet)
                except queue.Full:
                    logger.warning("Data buffer full, dropping oldest")
                    self._data_buffer.get()  # Remove oldest
                    self._data_buffer.put_nowait(packet)
                
                # Notify callbacks
                for cb in self._callbacks:
                    try:
                        cb(packet)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")
                
                time.sleep(self.interval)
                
            except Exception as e:
                logger.error(f"Read loop error: {e}")
                time.sleep(1)  # Brief pause on error
    
    def start(self):
        """Start sensor node"""
        if self._running:
            return
        
        self.initialize_components()
        self.start_time = time.time()
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        
        logger.info(f"Node {self.node_id}: Started")
    
    def stop(self):
        """Stop sensor node"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        if self.bioreactor:
            self.bioreactor.stop()
        logger.info(f"Node {self.node_id}: Stopped")
    
    def get_data(self, block: bool = False, timeout: Optional[float] = None) -> Optional[Dict]:
        """Get next data packet from buffer"""
        try:
            return self._data_buffer.get(block=block, timeout=timeout)
        except queue.Empty:
            return None
    
    def get_status(self) -> Dict:
        """Get current node status"""
        return {
            "node_id": self.node_id,
            "running": self._running,
            "uptime": time.time() - self.start_time if self.start_time else 0,
            "readings": self.readings_count,
            "anomalies": self.anomaly_count,
            "buffer_size": self._data_buffer.qsize()
        }

class Gateway:
    """
    Gateway for aggregating multiple sensor nodes.
    
    Sends data to cloud via MQTT or HTTP.
    """
    
    def __init__(
        self,
        gateway_id: str,
        mqtt_broker: Optional[str] = None,
        mqtt_port: int = 1883,
        http_endpoint: Optional[str] = None,
        use_mqtt: bool = False
    ):
        self.gateway_id = gateway_id
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.http_endpoint = http_endpoint
        self.use_mqtt = use_mqtt and mqtt_broker
        
        self.nodes: Dict[str, SensorNode] = {}
        self.mqtt_client = None
        self._running = False
        
        if self.use_mqtt:
            try:
                import paho.mqtt.client as mqtt
                self.mqtt_client = mqtt.Client()
                self.mqtt_client.on_connect = self._on_mqtt_connect
                self.mqtt_client.on_message = self._on_mqtt_message
            except ImportError:
                logger.warning("paho-mqtt not available")
                self.use_mqtt = False
        
        logger.info(f"Gateway {gateway_id} initialized")
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        logger.info(f"MQTT connected: {rc}")
    
    def _on_mqtt_message(self, client, userdata, msg):
        logger.debug(f"MQTT message: {msg.topic} {msg.payload}")
    
    def connect(self):
        """Connect to MQTT broker"""
        if self.mqtt_client and self.mqtt_broker:
            try:
                self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
                self.mqtt_client.loop_start()
                logger.info(f"Connected to MQTT: {self.mqtt_broker}")
            except Exception as e:
                logger.error(f"MQTT connection failed: {e}")
    
    def publish(self, topic: str, data: Dict):
        """Publish data to MQTT topic"""
        if self.mqtt_client:
            try:
                payload = json.dumps(data)
                self.mqtt_client.publish(topic, payload)
            except Exception as e:
                logger.error(f"MQTT publish failed: {e}")
    
    def register_node(self, node: SensorNode) -> Callable:
        """Register a sensor node with this gateway"""
        self.nodes[node.node_id] = node
        
        # Create callback to forward data
        def forward_callback(packet: Dict):
            # Add gateway metadata
            packet["gateway_id"] = self.gateway_id
            packet["received_time"] = time.time()
            
            # Publish
            topic = f"mycosentinel/nodes/{node.node_id}/data"
            self.publish(topic, packet)
            
            # Also HTTP post if configured
            if self.http_endpoint:
                self._http_post(packet)
        
        node.register_callback(forward_callback)
        
        logger.info(f"Registered node {node.node_id}")
        return forward_callback
    
    def _http_post(self, data: Dict):
        """POST data to HTTP endpoint"""
        if not self.http_endpoint:
            return
        
        try:
            import requests
            requests.post(
                self.http_endpoint,
                json=data,
                timeout=5
            )
        except Exception as e:
            logger.error(f"HTTP post failed: {e}")
    
    def start_all(self):
        """Start all registered nodes"""
        self.connect()
        for node in self.nodes.values():
            node.start()
        logger.info(f"Started {len(self.nodes)} nodes")
    
    def stop_all(self):
        """Stop all nodes"""
        for node in self.nodes.values():
            node.stop()
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
        logger.info("All nodes stopped")
    
    def get_all_status(self) -> Dict[str, Dict]:
        """Get status of all nodes"""
        return {nid: node.get_status() for nid, node in self.nodes.items()}

if __name__ == "__main__":
    print("Network module demo")
    
    # Single node demo
    node = SensorNode("test-01", sampling_rate_hz=2.0, use_mock=True)
    
    def print_callback(packet):
        print(f"Node {packet['node_id']}: optical={packet['optical_raw']:.1f}, "
              f"anomaly={packet['processed']['anomaly_score']:.2f}, "
              f"detected={packet['processed']['contaminant_detected']}")
    
    node.register_callback(print_callback)
    node.start()
    
    import signal
    def shutdown(sig, frame):
        print("\nStopping...")
        node.stop()
        exit(0)
    
    signal.signal(signal.SIGINT, shutdown)
    
    print("Running for 60 seconds...")
    time.sleep(60)
    node.stop()
