#!/usr/bin/env python3
"""
MycoSentinel Node Simulator
Simulates 10 sensor nodes for network testing before hardware deployment.

Features:
- Simulates all 10 nodes (MS-A1 through MS-D2)
- Generates synthetic mycotoxin sensor data
- Sends data to gateway via MQTT/HTTP
- Supports anomaly injection for testing alerts
- Configurable data patterns and rates

Usage:
    python3 node_simulator.py --gateway 10.0.0.1 --nodes 10
    python3 node_simulator.py --gateway 10.0.0.1 --infect MS-A1 --toxin aflatoxin
    python3 node_simulator.py --gateway 10.0.0.1 --duration 3600

Author: MycoSentinel Deployment Team
Version: 1.0.0
"""

import json
import time
import random
import argparse
import threading
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from collections import deque
import signal
import sys

# Try to import MQTT
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False

# Try to import HTTP client
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# MYCOTOXIN SIMULATION MODELS
# ============================================================================

MYCOTOXIN_PROFILES = {
    "aflatoxin_b1": {
        "name": "Aflatoxin B1",
        "ld50_mg_kg": 0.5,
        "optical_response_pattern": "sigmoid",
        "electrical_response_pattern": "linear",
        "response_time_seconds": 120,
        "recovery_time_seconds": 3600,
    },
    "ochratoxin_a": {
        "name": "Ochratoxin A",
        "ld50_mg_kg": 20.0,
        "optical_response_pattern": "linear",
        "electrical_response_pattern": "step",
        "response_time_seconds": 300,
        "recovery_time_seconds": 7200,
    },
    "deoxynivalenol": {
        "name": "Deoxynivalenol (DON)",
        "ld50_mg_kg": 46.0,
        "optical_response_pattern": "step",
        "electrical_response_pattern": "sigmoid",
        "response_time_seconds": 180,
        "recovery_time_seconds": 5400,
    },
    "zearalenone": {
        "name": "Zearalenone",
        "ld50_mg_kg": 200.0,
        "optical_response_pattern": "linear",
        "electrical_response_pattern": "linear",
        "response_time_seconds": 240,
        "recovery_time_seconds": 4800,
    },
}


class SensorModel:
    """
    Physics-based sensor model for simulating realistic biosensor behavior.
    Models both optical (fluorescence) and electrical (impedance) responses.
    """
    
    def __init__(self, node_id: str, sector: str, seed: Optional[int] = None):
        self.node_id = node_id
        self.sector = sector
        
        # Initialize random state per node (for reproducibility)
        self.rng = random.Random(seed if seed else hash(node_id) % 10000)
        
        # Baseline characteristics (vary per node)
        self.baseline_fluorescence = self.rng.uniform(1800, 2200)
        self.baseline_impedance = self.rng.uniform(4000, 5000)
        self.baseline_noise_std = self.rng.uniform(20, 50)
        self.temperature_drift = self.rng.uniform(-0.5, 0.5)
        
        # Current state
        self.current_fluorescence = self.baseline_fluorescence
        self.current_impedance = self.baseline_impedance
        self.current_temperature = 28.0
        self.current_ph = 6.8
        
        # Contamination state
        self.contaminated = False
        self.contamination_start = None
        self.contamination_type = None
        self.contamination_concentration = 0.0
        
        # Response tracking
        self.sequence_num = 0
        self.start_time = time.time()
        
    def _calculate_temp_compensation(self, base_value: float, temp: float) -> float:
        """Calculate temperature compensation for sensor readings"""
        # GFP fluorescence decreases ~1% per degree above 25C
        temp_effect = (temp - 25.0) * -0.01
        conductivity_effect = (temp - 25.0) * 0.02  # +2% per degree
        return temp_effect, conductivity_effect
    
    def _sigmoid_response(self, t: float, t0: float, tau: float) -> float:
        """Sigmoid response function for gradual response"""
        return 1.0 / (1.0 + 2.718 ** (-(t - t0) / tau))
    
    def _step_response(self, t: float, t0: float, tau: float) -> float:
        """Step response function for immediate detection"""
        if t < t0:
            return 0.0
        return min(1.0, (t - t0) / tau)
    
    def _linear_response(self, t: float, t0: float, tau: float) -> float:
        """Linear ramp response"""
        if t < t0:
            return 0.0
        return min(1.0, (t - t0) / tau)
    
    def inject_contamination(self, toxin_type: str, concentration_ppb: float = 100.0):
        """Simulate mycotoxin contamination"""
        if toxin_type not in MYCOTOXIN_PROFILES:
            logger.error(f"Unknown toxin: {toxin_type}")
            return False
        
        self.contaminated = True
        self.contamination_start = time.time()
        self.contamination_type = toxin_type
        self.contamination_concentration = concentration_ppb
        
        logger.warning(f"[{self.node_id}] CONTAMINATION INJECTED: {toxin_type} at {concentration_ppb} ppb")
        return True
    
    def clear_contamination(self):
        """Clear contamination state"""
        if self.contaminated:
            logger.info(f"[{self.node_id}] Contamination cleared")
        self.contaminated = False
        self.contamination_start = None
        self.contamination_type = None
        self.contamination_concentration = 0.0
    
    def generate_reading(self) -> Dict[str, Any]:
        """Generate a single sensor reading"""
        self.sequence_num += 1
        timestamp = time.time()
        
        # Simulate temperature drift
        self.current_temperature = 28.0 + 2.0 * self._sinusoidal_drift(timestamp, 3600) + self.rng.gauss(0, 0.5)
        
        # Calculate base noise
        noise_optical = self.rng.gauss(0, self.baseline_noise_std)
        noise_electrical = self.rng.gauss(0, self.baseline_noise_std * 0.5)
        
        # Initialize values
        optical_raw = self.baseline_fluorescence + noise_optical
        electrical_raw = self.baseline_impedance + noise_electrical
        
        # Calculate contamination response
        mycotoxin_detected = False
        anomaly_score = 0.0
        state = "baseline"
        
        if self.contaminated and self.contamination_start:
            elapsed = timestamp - self.contamination_start
            profile = MYCOTOXIN_PROFILES[self.contamination_type]
            
            # Calculate response magnitude based on concentration
            # Typical response: 20-50% signal change per LD50 equivalent
            ld50 = profile["ld50_mg_kg"]
            concentration_factor = min(2.0, self.contamination_concentration / (ld50 * 1000))
            
            # Calculate response progress
            t0 = profile["response_time_seconds"] * 0.5  # Start response
            tau = profile["response_time_seconds"] * 0.3
            
            # Optical response
            if profile["optical_response_pattern"] == "sigmoid":
                response_progress = self._sigmoid_response(elapsed, t0, tau)
            elif profile["optical_response_pattern"] == "step":
                response_progress = self._step_response(elapsed, t0, tau)
            else:  # linear
                response_progress = self._linear_response(elapsed, t0, tau)
            
            # Apply response to optical signal (fluorescence decreases)
            optical_change = self.baseline_fluorescence * 0.3 * response_progress * concentration_factor
            optical_raw = self.baseline_fluorescence - optical_change + noise_optical
            
            # Electrical response (impedance changes)
            if profile["electrical_response_pattern"] == "sigmoid":
                elec_progress = self._sigmoid_response(elapsed, t0, tau)
            elif profile["electrical_response_pattern"] == "step":
                elec_progress = self._step_response(elapsed, t0, tau)
            else:  # linear
                elec_progress = self._linear_response(elapsed, t0, tau)
            
            elec_change = self.baseline_impedance * 0.25 * elec_progress * concentration_factor
            electrical_raw = self.baseline_impedance + elec_change + noise_electrical
            
            # Determine detection state
            if response_progress > 0.7:
                mycotoxin_detected = True
                state = "contamination"
                anomaly_score = min(1.0, response_progress * concentration_factor)
            elif response_progress > 0.3:
                state = "transient"
                anomaly_score = response_progress * 0.5
            else:
                state = "response"
                anomaly_score = response_progress * 0.3
        else:
            # Check for random anomalies (sensor error simulation)
            if self.rng.random() < 0.001:  # 0.1% chance of anomaly
                anomaly_score = self.rng.uniform(0.3, 0.6)
                state = "anomaly"
                optical_raw += self.rng.uniform(100, 300)
        
        # Temperature compensation
        temp_comp_optical, temp_comp_electrical = self._calculate_temp_compensation(0, self.current_temperature)
        
        # Build data packet
        optical_normalized = optical_raw / self.baseline_fluorescence
        electrical_normalized = electrical_raw / self.baseline_impedance
        
        # Confidence calculation
        confidence = 0.95 - (anomaly_score * 0.3) - (abs(self.current_temperature - 28) * 0.02)
        confidence = max(0.0, min(1.0, confidence))
        
        data = {
            "node_id": self.node_id,
            "timestamp": timestamp,
            "sequence_num": self.sequence_num,
            "bioreactor": {
                "temperature_c": round(self.current_temperature, 2),
                "humidity_percent": round(65.0 + self.rng.gauss(0, 5), 1),
                "ph": round(6.8 + self.rng.gauss(0, 0.1), 2),
                "stirrer_rpm": round(120 + self.rng.gauss(0, 5))
            },
            "optical": {
                "wavelength_nm": 525,
                "raw_fluorescence": round(optical_raw, 1),
                "background_subtracted": round(optical_raw - 150, 1),
                "normalized": round(optical_normalized, 3),
                "temperature_compensated": round(optical_raw * (1 + temp_comp_optical), 1)
            },
            "electrical": {
                "impedance_ohm": round(electrical_raw, 1),
                "voltage_v": round(electrical_raw / 5000.0, 4),
                "current_ua": round((electrical_raw / 5000.0) / 10000 * 1e6, 2),
                "normalized_response": round(electrical_normalized, 3)
            },
            "processing": {
                "mycotoxin_detected": mycotoxin_detected,
                "mycotoxin_type": self.contamination_type if mycotoxin_detected else None,
                "anomaly_score": round(anomaly_score, 3),
                "confidence": round(confidence, 3),
                "state": state
            },
            "meta": {
                "firmware_version": "0.1.0-sim",
                "uptime_seconds": int(timestamp - self.start_time),
                "battery_percent": round(87.5 - (self.sequence_num / 3600 * 0.1), 1),
                "rssi_dbm": round(-65 + self.rng.gauss(0, 3)),
                "sector": self.sector
            }
        }
        
        return data
    
    def _sinusoidal_drift(self, t: float, period: float) -> float:
        """Generate sinusoidal drift pattern"""
        return ((t % period) / period * 2 * 3.14159) ** 0.5 * 0.5


# ============================================================================
# SIMULATED NODE
# ============================================================================

class SimulatedNode:
    """
    Individual simulated sensor node.
    Runs in a separate thread to simulate independent operation.
    """
    
    def __init__(self, node_id: str, sector: str, gateway_host: str,
                 gateway_port: int = 8000, mqtt_port: int = 1883,
                 data_rate_hz: float = 1.0):
        self.node_id = node_id
        self.sector = sector
        self.gateway_host = gateway_host
        self.gateway_port = gateway_port
        self.mqtt_port = mqtt_port
        self.data_rate_hz = data_rate_hz
        self.interval = 1.0 / data_rate_hz
        
        # Sensor model
        self.sensor = SensorModel(node_id, sector)
        
        # Communication
        self.mqtt_client = None
        self.registered = False
        
        # Threading
        self._running = False
        self._thread = None
        
    def connect(self) -> bool:
        """Connect to MQTT broker"""
        if not MQTT_AVAILABLE:
            logger.warning(f"[{self.node_id}] MQTT not available, using HTTP mode")
            return self._register_http()
        
        try:
            self.mqtt_client = mqtt.Client()
            
            def on_connect(client, userdata, flags, rc):
                if rc == 0:
                    logger.info(f"[{self.node_id}] MQTT connected")
                else:
                    logger.error(f"[{self.node_id}] MQTT connection failed: {rc}")
            
            self.mqtt_client.on_connect = on_connect
            self.mqtt_client.connect(self.gateway_host, self.mqtt_port, 60)
            self.mqtt_client.loop_start()
            
            # Register with gateway
            self._register_mqtt()
            return True
            
        except Exception as e:
            logger.error(f"[{self.node_id}] Connection failed: {e}")
            return False
    
    def _register_mqtt(self):
        """Register node via MQTT"""
        if self.mqtt_client:
            registration = {
                "node_id": self.node_id,
                "sector": self.sector,
                "ip_address": f"10.0.0.{hash(self.node_id) % 100 + 10}",
                "mac_address": f"b8:27:eb:{hash(self.node_id) % 256:02x}:{hash(self.node_id) % 65536 // 256:02x}:{hash(self.node_id) % 256:02x}",
                "firmware_version": "0.1.0-sim",
                "capabilities": ["optical", "electrical"]
            }
            self.mqtt_client.publish(
                f"mycosentinel/nodes/{self.node_id}/register",
                json.dumps(registration)
            )
            self.registered = True
    
    def _register_http(self) -> bool:
        """Register node via HTTP API"""
        if not REQUESTS_AVAILABLE:
            return True  # Skip registration
        
        try:
            url = f"http://{self.gateway_host}:{self.gateway_port}/api/v1/nodes"
            data = {
                "node_id": self.node_id,
                "sector": self.sector,
                "ip_address": f"10.0.0.{hash(self.node_id) % 100 + 10}",
                "mac_address": f"b8:27:eb:{hash(self.node_id) % 256:02x}:00:00",
                "firmware_version": "0.1.0-sim",
                "capabilities": ["optical", "electrical"]
            }
            response = requests.post(url, json=data, timeout=5)
            if response.status_code in [200, 201]:
                self.registered = True
                return True
        except Exception as e:
            logger.warning(f"[{self.node_id}] HTTP registration failed: {e}")
        return False
    
    def _send_data_mqtt(self, data: Dict):
        """Send data via MQTT"""
        if self.mqtt_client:
            topic = f"mycosentinel/nodes/{self.node_id}/data"
            self.mqtt_client.publish(topic, json.dumps(data))
    
    def _send_data_http(self, data: Dict):
        """Send data via HTTP"""
        if REQUESTS_AVAILABLE:
            try:
                url = f"http://{self.gateway_host}:{self.gateway_port}/api/v1/aggregate/all"
                requests.post(url, json=data, timeout=2)
            except:
                pass  # Fail silently in simulation
    
    def _run_loop(self):
        """Main data generation loop"""
        logger.info(f"[{self.node_id}] Starting data generator at {self.data_rate_hz} Hz")
        
        while self._running:
            try:
                # Generate reading
                data = self.sensor.generate_reading()
                
                # Send to gateway
                if self.mqtt_client:
                    self._send_data_mqtt(data)
                else:
                    self._send_data_http(data)
                
                # Log occasionally
                if self.sensor.sequence_num % 60 == 0:
                    logger.debug(f"[{self.node_id}] Sent reading #{self.sensor.sequence_num}")
                
                # Check for detected mycotoxin
                if data["processing"]["mycotoxin_detected"]:
                    logger.warning(f"[{self.node_id}] 🚨 MYCOTOXIN DETECTED: {self.sensor.contamination_type}")
                
                time.sleep(self.interval)
                
            except Exception as e:
                logger.error(f"[{self.node_id}] Loop error: {e}")
                time.sleep(1)
    
    def start(self):
        """Start the simulated node"""
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        
    def stop(self):
        """Stop the simulated node"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
    
    def inject_contamination(self, toxin_type: str, concentration_ppb: float = 100.0):
        """Inject mycotoxin contamination"""
        return self.sensor.inject_contamination(toxin_type, concentration_ppb)
    
    def clear_contamination(self):
        """Clear contamination"""
        self.sensor.clear_contamination()


# ============================================================================
# NODE SIMULATOR ORCHESTRATOR
# ============================================================================

class NodeSimulatorOrchestrator:
    """
    Orchestrates 10 simulated sensor nodes.
    Manages simulation lifecycle and scenario injection.
    """
    
    NODE_CONFIG = [
        # Sector A - Warehouse A
        {"id": "MS-A1", "sector": "A"},
        {"id": "MS-A2", "sector": "A"},
        {"id": "MS-A3", "sector": "A"},
        # Sector B - Warehouse B
        {"id": "MS-B1", "sector": "B"},
        {"id": "MS-B2", "sector": "B"},
        {"id": "MS-B3", "sector": "B"},
        # Sector C - Processing
        {"id": "MS-C1", "sector": "C"},
        {"id": "MS-C2", "sector": "C"},
        {"id": "MS-C3", "sector": "C"},
        # Sector D - Shipping/Entry
        {"id": "MS-D1", "sector": "D"},
        {"id": "MS-D2", "sector": "D"},
    ]
    
    def __init__(self, gateway_host: str, gateway_port: int = 8000,
                 mqtt_port: int = 1883, data_rate_hz: float = 1.0,
                 node_count: int = 10):
        self.gateway_host = gateway_host
        self.gateway_port = gateway_port
        self.mqtt_port = mqtt_port
        self.data_rate_hz = data_rate_hz
        self.node_count = min(node_count, len(self.NODE_CONFIG))
        
        self.nodes: Dict[str, SimulatedNode] = {}
        self._running = False
        
    def initialize_nodes(self):
        """Create simulated nodes"""
        logger.info(f"Initializing {self.node_count} simulated nodes...")
        
        for i, config in enumerate(self.NODE_CONFIG[:self.node_count]):
            node = SimulatedNode(
                node_id=config["id"],
                sector=config["sector"],
                gateway_host=self.gateway_host,
                gateway_port=self.gateway_port,
                mqtt_port=self.mqtt_port,
                data_rate_hz=self.data_rate_hz
            )
            self.nodes[config["id"]] = node
            logger.info(f"  ✓ Created {config['id']} (Sector {config['sector']})")
        
        logger.info(f"All {self.node_count} nodes initialized")
    
    def connect_all(self):
        """Connect all nodes to gateway"""
        logger.info("Connecting nodes to gateway...")
        
        connected = 0
        for node_id, node in self.nodes.items():
            if node.connect():
                connected += 1
                time.sleep(0.1)  # Stagger connections
        
        logger.info(f"Connected {connected}/{self.node_count} nodes")
        return connected
    
    def start_all(self):
        """Start all simulated nodes"""
        logger.info("Starting all nodes...")
        
        for node in self.nodes.values():
            node.start()
            time.sleep(0.05)  # Stagger starts
        
        self._running = True
        logger.info("All nodes started and sending data")
    
    def stop_all(self):
        """Stop all simulated nodes"""
        logger.info("Stopping all nodes...")
        self._running = False
        
        for node in self.nodes.values():
            node.stop()
        
        logger.info("All nodes stopped")
    
    def inject_contamination(self, node_id: Optional[str] = None,
                            toxin_type: str = "aflatoxin_b1",
                            concentration_ppb: float = 100.0):
        """Inject contamination into a node or random node"""
        if node_id and node_id in self.nodes:
            target = self.nodes[node_id]
        elif node_id is None:
            target = random.choice(list(self.nodes.values()))
        else:
            logger.error(f"Node {node_id} not found")
            return None
        
        success = target.inject_contamination(toxin_type, concentration_ppb)
        if success:
            return target.node_id
        return None
    
    def clear_all_contamination(self):
        """Clear contamination from all nodes"""
        for node in self.nodes.values():
            node.clear_contamination()
    
    def get_status(self) -> Dict:
        """Get overall simulation status"""
        return {
            "total_nodes": len(self.nodes),
            "running": self._running,
            "gateway": f"{self.gateway_host}:{self.gateway_port}",
            "data_rate_hz": self.data_rate_hz,
            "nodes": {
                nid: {
                    "sector": node.sector,
                    "registered": node.registered,
                    "sequence_num": node.sensor.sequence_num,
                    "contaminated": node.sensor.contaminated,
                    "toxin": node.sensor.contamination_type
                }
                for nid, node in self.nodes.items()
            }
        }
    
    def run_simulation_scenario(self, scenario: str, duration: int = 300):
        """
        Run a predefined simulation scenario.
        
        Scenarios:
        - baseline: Normal operation, no contamination
        - single_contamination: One node gets contaminated
        - multi_contamination: Multiple nodes contaminated
        - spreading: Contamination spreads between nodes
        - random_events: Random contamination events
        """
        logger.info(f"Starting scenario: {scenario} (duration: {duration}s)")
        
        start_time = time.time()
        events = []
        
        if scenario == "baseline":
            # Just baseline, no events
            pass
        
        elif scenario == "single_contamination":
            # Contaminate one node at 30 seconds
            def event1():
                node = self.inject_contamination(
                    toxin_type="aflatoxin_b1",
                    concentration_ppb=150
                )
                events.append(f"Contaminated {node} with Aflatoxin B1")
            
            threading.Timer(30, event1).start()
            
            # Clear at 180 seconds
            def event2():
                self.clear_all_contamination()
                events.append("Cleared all contamination")
            
            threading.Timer(180, event2).start()
        
        elif scenario == "multi_contamination":
            # Multiple sequential contaminations
            toxin_types = ["aflatoxin_b1", "ochratoxin_a", "deoxynivalenol"]
            
            for i, toxin in enumerate(toxin_types):
                def make_event(t):
                    return lambda: events.append(
                        f"Contaminated {self.inject_contamination(toxin_type=t)} with {t}"
                    )
                
                threading.Timer(30 + i * 60, make_event(toxin)).start()
            
            threading.Timer(300, self.clear_all_contamination).start()
        
        elif scenario == "spreading":
            # Start with one node, "spread" to neighbors
            sector_nodes = [n for n in self.nodes.keys() if n.startswith("MS-A")]
            
            for i, node_id in enumerate(sector_nodes):
                def make_spread_event(nid):
                    return lambda: self.nodes[nid].inject_contamination("zearalenone", 200)
                
                threading.Timer(30 + i * 45, make_spread_event(node_id)).start()
            
            threading.Timer(300, self.clear_all_contamination).start()
        
        elif scenario == "random_events":
            # Random contamination events
            def random_event():
                if self._running and random.random() < 0.3:
                    toxin = random.choice(list(MYCOTOXIN_PROFILES.keys()))
                    node = self.inject_contamination(toxin_type=toxin)
                    events.append(f"Random event: {node} contaminated with {toxin}")
            
            for i in range(10):
                threading.Timer(30 + i * 25, random_event).start()
        
        # Wait for duration
        while self._running and time.time() - start_time < duration:
            time.sleep(1)
            
            # Print occasional status
            elapsed = int(time.time() - start_time)
            if elapsed % 30 == 0:
                active_contaminated = sum(1 for n in self.nodes.values() if n.sensor.contaminated)
                logger.info(f"Scenario progress: {elapsed}s/{duration}s | Active contaminations: {active_contaminated}")
        
        logger.info(f"Scenario '{scenario}' completed")
        if events:
            logger.info(f"Events logged: {len(events)}")
        
        return events


# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='MycoSentinel Node Simulator - Simulates 10 sensor nodes'
    )
    parser.add_argument('--gateway', '-g', default='localhost',
                       help='Gateway host (default: localhost)')
    parser.add_argument('--port', '-p', type=int, default=8000,
                       help='Gateway API port (default: 8000)')
    parser.add_argument('--mqtt-port', type=int, default=1883,
                       help='MQTT broker port (default: 1883)')
    parser.add_argument('--nodes', '-n', type=int, default=10,
                       help='Number of nodes to simulate (default: 10)')
    parser.add_argument('--rate', '-r', type=float, default=1.0,
                       help='Data transmission rate in Hz (default: 1.0)')
    parser.add_argument('--duration', '-d', type=int, default=0,
                       help='Simulation duration in seconds (0 = run forever)')
    parser.add_argument('--scenario', '-s', default='baseline',
                       choices=['baseline', 'single_contamination', 'multi_contamination', 
                               'spreading', 'random_events'],
                       help='Simulation scenario')
    parser.add_argument('--infect', '-i', help='Infect specific node with toxin')
    parser.add_argument('--toxin', '-t', default='aflatoxin_b1',
                       choices=list(MYCOTOXIN_PROFILES.keys()),
                       help='Toxin type for infection')
    parser.add_argument('--concentration', '-c', type=float, default=100.0,
                       help='Toxin concentration in ppb (default: 100)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Print header
    print("=" * 70)
    print("  🍄 MYCOSENTINEL NODE SIMULATOR")
    print("  10-Node Biosensor Network Simulation")
    print("=" * 70)
    print(f"  Gateway: {args.gateway}:{args.port}")
    print(f"  Nodes: {args.nodes}")
    print(f"  Data Rate: {args.rate} Hz")
    print(f"  Scenario: {args.scenario}")
    print("=" * 70)
    print()
    
    # Create simulator
    simulator = NodeSimulatorOrchestrator(
        gateway_host=args.gateway,
        gateway_port=args.port,
        mqtt_port=args.mqtt_port,
        data_rate_hz=args.rate,
        node_count=args.nodes
    )
    
    # Initialize and connect
    simulator.initialize_nodes()
    simulator.connect_all()
    
    # Start simulation
    simulator.start_all()
    
    # Handle specific infection
    if args.infect:
        time.sleep(2)  # Let nodes stabilize
        result = simulator.inject_contamination(
            args.infect,
            args.toxin,
            args.concentration
        )
        if result:
            print(f"\n>> Injected {args.toxin} into {result} at {args.concentration} ppb\n")
    
    # Run scenario or wait
    try:
        if args.duration > 0:
            simulator.run_simulation_scenario(args.scenario, args.duration)
        else:
            print("Running indefinitely. Press Ctrl+C to stop.")
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    finally:
        print("\nStopping simulation...")
        simulator.stop_all()
        
        # Print summary
        status = simulator.get_status()
        print("\n" + "=" * 70)
        print("  SIMULATION SUMMARY")
        print("=" * 70)
        print(f"  Total readings sent: {sum(n['sequence_num'] for n in status['nodes'].values())}")
        print(f"  Nodes reporting: {len(status['nodes'])}")
        
        contaminated = [nid for nid, n in status['nodes'].items() if n['contaminated']]
        if contaminated:
            print(f"  Nodes with contamination: {', '.join(contaminated)}")
        
        print("=" * 70)


if __name__ == '__main__':
    main()
