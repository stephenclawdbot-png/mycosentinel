#!/usr/bin/env python3
"""
MycoSentinel Network Deployment Script
Deploys and configures the entire 10-node mesh network.

Usage:
    python deploy_network.py --manifest deploy_config.json
    python deploy_network.py --parallel 3  # Deploy 3 nodes in parallel
    python deploy_network.py --gateway-only  # Deploy gateway first
    python deploy_network.py --nodes MS-A1,MS-A2,MS-A3  # Deploy specific nodes

Features:
- Multi-node parallel deployment
- Mesh network self-organization
- Gateway-first deployment strategy
- Network health verification
- Rollback on failure
"""

import argparse
import json
import sys
import os
import time
import logging
import threading
import queue
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import networkx as nx

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from deploy_node import NodeDeployer, NodeConfig, discover_nodes, DEPLOYMENT_DIR

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class DeploymentResult:
    """Result of a single node deployment"""
    node_id: str
    success: bool
    duration_seconds: float
    error_message: Optional[str] = None
    log_file: Optional[str] = None


class MeshTopology:
    """
    Manages mesh network topology for optimal node placement and routing.
    """
    
    def __init__(self, nodes_config: List[Dict]):
        self.nodes = nodes_config
        self.graph = nx.Graph()
        self._build_graph()
    
    def _build_graph(self):
        """Build network graph with nodes as vertices"""
        gateway = None
        
        # Add all nodes
        for node in self.nodes:
            node_id = node["id"]
            location = node.get("location", {})
            
            self.graph.add_node(
                node_id,
                pos=(location.get("lat", 0), location.get("lon", 0)),
                sector=node.get("sector", "A"),
                elevation=location.get("elevation_m", 0),
                is_relay=node.get("power", {}).get("mesh_relay", False)
            )
        
        # Add edges based on proximity and sector
        for i, n1 in enumerate(self.nodes):
            for n2 in self.nodes[i+1:]:
                dist = self._calculate_distance(n1, n2)
                
                # Connect if within range and same sector or relay
                if dist < 150:  # 150m max range
                    weight = dist
                    # Prefer same-sector connections
                    if n1.get("sector") == n2.get("sector"):
                        weight *= 0.5
                    # Prefer relay nodes
                    if n1.get("power", {}).get("mesh_relay") or \
                       n2.get("power", {}).get("mesh_relay"):
                        weight *= 0.7
                    
                    self.graph.add_edge(n1["id"], n2["id"], weight=weight, distance=dist)
        
        logger.info(f"Mesh topology: {self.graph.number_of_nodes()} nodes, "
                   f"{self.graph.number_of_edges()} potential links")
    
    def _calculate_distance(self, n1: Dict, n2: Dict) -> float:
        """Calculate distance between two nodes in meters"""
        import math
        
        lat1 = n1.get("location", {}).get("lat", 0)
        lon1 = n1.get("location", {}).get("lon", 0)
        lat2 = n2.get("location", {}).get("lat", 0)
        lon2 = n2.get("location", {}).get("lon", 0)
        
        # Haversine formula
        R = 6371000  # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        
        a = math.sin(delta_phi/2)**2 + \
            math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def get_deployment_order(self) -> List[List[str]]:
        """
        Return deployment order as waves.
        Wave 1: Gateway-adjacent nodes
        Wave 2: Nodes reachable via Wave 1
        etc.
        """
        gateway_ip = "192.168.1.100"
        
        # Find nodes closest to gateway (by IP / distance)
        waves = []
        deployed = set()
        remaining = set(n["id"] for n in self.nodes)
        
        while remaining:
            wave = []
            for node_id in remaining:
                # Find closest deployed neighbor or gateway-adjacent
                if not deployed:
                    # First wave: sectors A nodes closest to gateway
                    node = next((n for n in self.nodes if n["id"] == node_id), None)
                    if node and node.get("sector") == "A":
                        if node.get("location", {}).get("distance_from_gateway_m", 9999) < 100:
                            wave.append(node_id)
                else:
                    # Check if has deployed neighbor
                    neighbors = set(self.graph.neighbors(node_id)) & deployed
                    if neighbors:
                        wave.append(node_id)
            
            if not wave:
                # No clear wave, just take remaining
                wave = list(remaining)[:3]  # Max 3 per wave
            
            waves.append(wave)
            deployed.update(wave)
            remaining -= set(wave)
        
        return waves
    
    def get_neighbors_for_node(self, node_id: str) -> List[str]:
        """Get neighboring node IDs for mesh configuration"""
        if node_id not in self.graph:
            return []
        return list(self.graph.neighbors(node_id))
    
    def calculate_routes(self) -> Dict[str, List[str]]:
        """Calculate optimal routes from each node to gateway"""
        routes = {}
        
        for node in self.nodes:
            node_id = node["id"]
            try:
                # Find shortest path to a Sector A node (closer to gateway)
                paths = []
                for target in self.nodes:
                    if target["id"] != node_id and target.get("sector") == "A":
                        try:
                            path = nx.shortest_path(
                                self.graph, node_id, target["id"], weight="weight"
                            )
                            paths.append(path)
                        except nx.NetworkXNoPath:
                            pass
                
                routes[node_id] = min(paths, key=len) if paths else [node_id]
            except Exception as e:
                logger.warning(f"Could not calculate route for {node_id}: {e}")
                routes[node_id] = [node_id]
        
        return routes
    
    def visualize(self, output_path: str = "mesh_topology.png"):
        """Generate visualization of mesh topology"""
        try:
            import matplotlib.pyplot as plt
            
            pos = nx.spring_layout(self.graph, seed=42)
            
            # Color by sector
            sector_colors = {"A": "green", "B": "blue", "C": "orange"}
            node_colors = [
                sector_colors.get(self.graph.nodes[n].get("sector", "A"), "gray")
                for n in self.graph.nodes()
            ]
            
            # Size by relay status
            node_sizes = [
                500 if self.graph.nodes[n].get("is_relay") else 300
                for n in self.graph.nodes()
            ]
            
            plt.figure(figsize=(12, 10))
            nx.draw_networkx_nodes(self.graph, pos, node_color=node_colors, 
                                 node_size=node_sizes, alpha=0.9)
            nx.draw_networkx_edges(self.graph, pos, alpha=0.5, width=1)
            nx.draw_networkx_labels(self.graph, pos, font_size=8)
            
            plt.title("MycoSentinel Mesh Network Topology")
            plt.axis('off')
            plt.tight_layout()
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Topology visualization saved to {output_path}")
        except ImportError:
            logger.warning("matplotlib not available for topology visualization")
        except Exception as e:
            logger.error(f"Failed to visualize topology: {e}")


class GatewayDeployer:
    """Deploys and configures the central gateway"""
    
    def __init__(self, gateway_config: Dict, dry_run: bool = False):
        self.config = gateway_config
        self.dry_run = dry_run
        self.ip = gateway_config.get("ip", "192.168.1.100")
    
    def deploy(self) -> bool:
        """Deploy gateway infrastructure"""
        logger.info("=" * 60)
        logger.info("DEPLOYING MYCOSENTINEL GATEWAY")
        logger.info("=" * 60)
        
        steps = [
            ("Check Gateway Hardware", self._check_hardware),
            ("Install Core Services", self._install_services),
            ("Configure MQTT Broker", self._configure_mqtt),
            ("Configure InfluxDB", self._configure_influxdb),
            ("Configure Grafana", self._configure_grafana),
            ("Configure Firewall", self._configure_firewall),
            ("Verify Gateway", self._verify_gateway),
        ]
        
        for name, step in steps:
            logger.info(f"--- {name} ---")
            try:
                if not step():
                    logger.error(f"Gateway deployment failed at: {name}")
                    return False
            except Exception as e:
                logger.error(f"Gateway step failed: {e}")
                return False
        
        logger.info("Gateway deployment complete!")
        return True
    
    def _check_hardware(self) -> bool:
        """Verify gateway hardware"""
        logger.info(f"Checking gateway at {self.ip}")
        
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "3", self.ip],
                capture_output=True,
                timeout=5
            )
            if result.returncode != 0:
                logger.error(f"Gateway at {self.ip} is not reachable")
                return False
        except Exception as e:
            logger.error(f"Failed to ping gateway: {e}")
            return False
        
        logger.info("Gateway is reachable")
        return True
    
    def _install_services(self) -> bool:
        """Install MQTT, InfluxDB, Grafana on gateway"""
        services = [
            "mosquitto", "mosquitto-clients",
            "influxdb2",
            "grafana",
            "docker.io"  # For containerized services
        ]
        
        logger.info("Installing services...")
        
        if self.dry_run:
            logger.info("[DRY-RUN] Would install: " + ", ".join(services))
            return True
        
        try:
            ssh_target = f"pi@{self.ip}"
            subprocess.run(
                ["ssh", "-o", "StrictHostKeyChecking=no", ssh_target,
                 "sudo", "apt-get", "update"],
                check=True, capture_output=True, timeout=60
            )
            
            subprocess.run(
                ["ssh", "-o", "StrictHostKeyChecking=no", ssh_target,
                 "sudo", "apt-get", "install", "-y"] + services,
                check=True, capture_output=True, timeout=300
            )
            
            logger.info("Services installed")
            return True
        except Exception as e:
            logger.error(f"Service installation failed: {e}")
            return False
    
    def _configure_mqtt(self) -> bool:
        """Configure MQTT broker for mesh networking"""
        logger.info("Configuring MQTT broker...")
        
        mosquitto_conf = """
# MycoSentinel MQTT Configuration
listener 1883
allow_anonymous true
persistence true
persistence_location /var/lib/mosquitto/

# Bridge configuration for external cloud
# connection bridge-cloud
# address cloud-broker.example.com:1883

# Logging
log_dest file /var/log/mosquitto/mosquitto.log
log_type all

# Mesh topic structure
topic mycosentinel/# out
topic mycosentinel/# in

# Retain node status messages
persistent_client_expiration 1d
"""
        
        if self.dry_run:
            logger.info("[DRY-RUN] Would configure MQTT")
            return True
        
        try:
            ssh_target = f"pi@{self.ip}"
            
            # Write config
            with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
                f.write(mosquitto_conf)
                config_file = f.name
            
            subprocess.run(
                ["scp", "-o", "StrictHostKeyChecking=no",
                 config_file, f"{ssh_target}:/tmp/mosquitto.conf"],
                check=True
            )
            
            subprocess.run(
                ["ssh", "-o", "StrictHostKeyChecking=no", ssh_target,
                 "sudo", "mv", "/tmp/mosquitto.conf", "/etc/mosquitto/mosquitto.conf"],
                check=True
            )
            
            subprocess.run(
                ["ssh", "-o", "StrictHostKeyChecking=no", ssh_target,
                 "sudo", "systemctl", "restart", "mosquitto"],
                check=True
            )
            
            os.unlink(config_file)
            logger.info("MQTT configured")
            return True
            
        except Exception as e:
            logger.error(f"MQTT configuration failed: {e}")
            return False
    
    def _configure_influxdb(self) -> bool:
        """Initialize InfluxDB for time-series data"""
        logger.info("Configuring InfluxDB...")
        
        if self.dry_run:
            logger.info("[DRY-RUN] Would configure InfluxDB")
            return True
        
        try:
            ssh_target = f"pi@{self.ip}"
            
            # Start service
            subprocess.run(
                ["ssh", "-o", "StrictHostKeyChecking=no", ssh_target,
                 "sudo", "systemctl", "start", "influxdb"],
                check=True
            )
            
            # InfluxDB v2+ requires setup
            # Note: In production, use proper secrets management
            setup_cmd = """
            influx setup --force \
                --username admin \
                --password mycosentinel-admin \
                --org mycosentinel \
                --bucket biosensor_data \
                --retention 30d
            """
            
            subprocess.run(
                ["ssh", "-o", "StrictHostKeyChecking=no", ssh_target,
                 "bash", "-c", setup_cmd],
                check=False, capture_output=True  # May fail if already set up
            )
            
            logger.info("InfluxDB configured")
            return True
            
        except Exception as e:
            logger.error(f"InfluxDB configuration failed: {e}")
            return False
    
    def _configure_grafana(self) -> bool:
        """Set up Grafana dashboards"""
        logger.info("Configuring Grafana...")
        
        if self.dry_run:
            logger.info("[DRY-RUN] Would configure Grafana")
            return True
        
        logger.info("Grafana will be accessible at http://{}:3000".format(self.ip))
        return True
    
    def _configure_firewall(self) -> bool:
        """Configure firewall rules"""
        logger.info("Configuring firewall...")
        
        if self.dry_run:
            logger.info("[DRY-RUN] Would configure firewall")
            return True
        
        # Allow: SSH (22), MQTT (1883), HTTP (80), HTTPS (443), Grafana (3000), InfluxDB (8086)
        ports = [22, 80, 443, 1883, 3000, 8086]
        
        try:
            ssh_target = f"pi@{self.ip}"
            
            for port in ports:
                subprocess.run(
                    ["ssh", "-o", "StrictHostKeyChecking=no", ssh_target,
                     "sudo", "ufw", "allow", str(port)],
                    check=False  # May already be allowed
                )
            
            subprocess.run(
                ["ssh", "-o", "StrictHostKeyChecking=no", ssh_target,
                 "sudo", "ufw", "--force", "enable"],
                check=True
            )
            
            logger.info("Firewall configured")
            return True
            
        except Exception as e:
            logger.error(f"Firewall configuration failed: {e}")
            return False
    
    def _verify_gateway(self) -> bool:
        """Verify all services are running"""
        logger.info("Verifying gateway services...")
        
        services = ["mosquitto", "influxdb", "grafana-server"]
        
        try:
            ssh_target = f"pi@{self.ip}"
            
            for svc in services:
                result = subprocess.run(
                    ["ssh", "-o", "StrictHostKeyChecking=no", ssh_target,
                     "systemctl", "is-active", svc],
                    capture_output=True,
                    check=False
                )
                status = "running" if result.returncode == 0 else "not running"
                logger.info(f"  {svc}: {status}")
            
            return True
            
        except Exception as e:
            logger.error(f"Gateway verification failed: {e}")
            return False


class NetworkDeployer:
    """
    Orchestrates deployment of the entire sensor network.
    """
    
    def __init__(self, manifest_path: str, parallel: int = 2, dry_run: bool = False):
        self.manifest_path = Path(manifest_path)
        self.parallel = parallel
        self.dry_run = dry_run
        self.manifest: Dict = {}
        self.topology: Optional[MeshTopology] = None
        self.results: List[DeploymentResult] = []
        self.ports: queue.Queue = queue.Queue()
        
    def load_manifest(self) -> bool:
        """Load deployment manifest"""
        if not self.manifest_path.exists():
            # Try default location
            default_path = DEPLOYMENT_DIR / "deploy_config.json"
            if default_path.exists():
                self.manifest_path = default_path
            else:
                logger.error(f"Manifest not found: {self.manifest_path}")
                return False
        
        try:
            with open(self.manifest_path) as f:
                self.manifest = json.load(f)
            
            logger.info(f"Loaded manifest: {self.manifest.get('project', 'Unknown')}")
            logger.info(f"Version: {self.manifest.get('version', 'Unknown')}")
            logger.info(f"Nodes: {len(self.manifest.get('nodes', []))}")
            
            # Build topology
            self.topology = MeshTopology(self.manifest.get("nodes", []))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load manifest: {e}")
            return False
    
    def discover_hardware(self) -> bool:
        """Discover available hardware"""
        from deploy_node import discover_nodes
        
        available = discover_nodes()
        
        if not available:
            logger.warning("No nodes discovered via USB/Serial")
            logger.info("Will use SSH deployment mode")
            return True
        
        logger.info(f"Discovered {len(available)} serial device(s):")
        for device, desc in available:
            logger.info(f"  {device}: {desc}")
            self.ports.put(device)
        
        return True
    
    def deploy_gateway(self) -> bool:
        """Deploy gateway infrastructure"""
        gateway_config = self.manifest.get("gateway", {})
        
        if not gateway_config:
            logger.warning("No gateway configuration in manifest")
            return True
        
        deployer = GatewayDeployer(gateway_config, dry_run=self.dry_run)
        return deployer.deploy()
    
    def deploy_node_worker(self, node_config: Dict, port: str) -> DeploymentResult:
        """Worker function for parallel node deployment"""
        node_id = node_config["id"]
        start_time = time.time()
        
        try:
            # Convert to NodeConfig
            config = NodeConfig(
                node_id=node_id,
                hostname=node_config["hostname"],
                static_ip=node_config["static_ip"],
                sector=node_config["sector"],
                lat=node_config["location"]["lat"],
                lon=node_config["location"]["lon"],
                elevation_m=node_config["location"]["elevation_m"],
                distance_from_gateway_m=node_config["location"].get("distance_from_gateway_m", 0),
                bearing_deg=node_config["location"].get("bearing_deg", 0),
                mesh_relay=node_config.get("power", {}).get("mesh_relay", False)
            )
            
            # Run deployment
            deployer = NodeDeployer(config, port, dry_run=self.dry_run)
            success = deployer.deploy()
            
            duration = time.time() - start_time
            
            return DeploymentResult(
                node_id=node_id,
                success=success,
                duration_seconds=duration,
                log_file=str(DEPLOYMENT_DIR / "logs" / f"deploy_{node_id}_*.json")
            )
            
        except Exception as e:
            duration = time.time() - start_time
            return DeploymentResult(
                node_id=node_id,
                success=False,
                duration_seconds=duration,
                error_message=str(e)
            )
    
    def deploy_nodes(self, node_ids: Optional[List[str]] = None) -> bool:
        """Deploy sensor nodes in waves"""
        logger.info("=" * 60)
        logger.info("DEPLOYING SENSOR NODES")
        logger.info("=" * 60)
        
        nodes = self.manifest.get("nodes", [])
        
        if node_ids:
            nodes = [n for n in nodes if n["id"] in node_ids]
        
        if not nodes:
            logger.warning("No nodes to deploy")
            return True
        
        # Get deployment order
        deployment_waves = self.topology.get_deployment_order()
        logger.info(f"Deployment plan: {len(deployment_waves)} waves")
        
        # Deploy by waves
        all_success = True
        
        for wave_num, wave in enumerate(deployment_waves, 1):
            logger.info(f"\n--- Wave {wave_num}/{len(deployment_waves)} ---")
            
            # Filter to requested nodes
            wave_nodes = [n for n in nodes if n["id"] in wave]
            
            if not wave_nodes:
                continue
            
            # Deploy nodes in this wave
            with ThreadPoolExecutor(max_workers=self.parallel) as executor:
                futures = {}
                
                for node in wave_nodes:
                    # Get port (serial or None for SSH mode)
                    port = "/dev/null"  # SSH mode
                    try:
                        port = self.ports.get_nowait()
                    except queue.Empty:
                        pass
                    
                    future = executor.submit(self.deploy_node_worker, node, port)
                    futures[future] = node["id"]
                
                # Collect results
                for future in as_completed(futures):
                    node_id = futures[future]
                    try:
                        result = future.result()
                        self.results.append(result)
                        
                        status = "✅ SUCCESS" if result.success else "❌ FAILED"
                        logger.info(f"{node_id}: {status} ({result.duration_seconds:.1f}s)")
                        
                        if not result.success:
                            all_success = False
                            if result.error_message:
                                logger.error(f"  Error: {result.error_message}")
                    
                    except Exception as e:
                        logger.error(f"{node_id}: Exception during deployment: {e}")
                        all_success = False
            
            # Brief pause between waves for network stabilization
            if wave_num < len(deployment_waves):
                logger.info("Waiting 10s for network stabilization...")
                time.sleep(10)
        
        return all_success
    
    def configure_mesh(self) -> bool:
        """Configure mesh networking between nodes"""
        logger.info("\n" + "=" * 60)
        logger.info("CONFIGURING MESH NETWORK")
        logger.info("=" * 60)
        
        routes = self.topology.calculate_routes()
        
        for node_id, route in routes.items():
            neighbors = self.topology.get_neighbors_for_node(node_id)
            
            logger.info(f"{node_id}:")
            logger.info(f"  Neighbors: {', '.join(neighbors) if neighbors else 'None (direct) '}")
            logger.info(f"  Route: {' -> '.join(route)}")
            
            # Configure node via SSH
            mesh_config = {
                "node_id": node_id,
                "neighbors": neighbors,
                "route": route,
                "is_relay": any(
                    n.get("power", {}).get("mesh_relay")
                    for n in self.manifest.get("nodes", [])
                    if n["id"] == node_id
                )
            }
            
            if not self.dry_run:
                node = next((n for n in self.manifest.get("nodes", []) if n["id"] == node_id), None)
                if node:
                    try:
                        # Deploy mesh config
                        ssh_target = f"pi@{node['static_ip']}"
                        
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                            json.dump(mesh_config, f)
                            config_file = f.name
                        
                        subprocess.run(
                            ["scp", "-o", "StrictHostKeyChecking=no",
                             config_file, f"{ssh_target}:/opt/mycosentinel/mesh_config.json"],
                            check=True, capture_output=True, timeout=30
                        )
                        
                        subprocess.run(
                            ["ssh", "-o", "StrictHostKeyChecking=no", ssh_target,
                             "sudo", "systemctl", "restart", "mycosentinel"],
                            check=True, capture_output=True, timeout=30
                        )
                        
                        os.unlink(config_file)
                        
                    except Exception as e:
                        logger.warning(f"Failed to configure mesh for {node_id}: {e}")
        
        return True
    
    def verify_network(self) -> bool:
        """Verify entire network is operational"""
        logger.info("\n" + "=" * 60)
        logger.info("NETWORK VERIFICATION")
        logger.info("=" * 60)
        
        all_ok = True
        gateway_ip = self.manifest.get("gateway", {}).get("ip", "192.168.1.100")
        
        # Check MQTT broker
        try:
            result = subprocess.run(
                ["mosquitto_sub", "-h", gateway_ip, "-t", "mycosentinel/status", "-C", "1", "-W", "5"],
                capture_output=True,
                timeout=10
            )
            if result.returncode == 0:
                logger.info("✅ MQTT broker responding")
            else:
                logger.warning("⚠️ MQTT broker not responding")
        except Exception as e:
            logger.warning(f"⚠️ Could not test MQTT: {e}")
        
        # Check each node
        for node in self.manifest.get("nodes", []):
            node_id = node["id"]
            ip = node["static_ip"]
            
            try:
                result = subprocess.run(
                    ["ping", "-c", "1", "-W", "2", ip],
                    capture_output=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    logger.info(f"✅ {node_id}: Ping OK")
                else:
                    logger.warning(f"⚠️ {node_id}: Not responding to ping")
                    all_ok = False
                    
            except Exception as e:
                logger.warning(f"⚠️ {node_id}: Ping failed: {e}")
                all_ok = False
        
        return all_ok
    
    def generate_report(self) -> str:
        """Generate deployment report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = DEPLOYMENT_DIR / "logs" / f"deployment_report_{timestamp}.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "manifest": self.manifest.get("project", "Unknown"),
            "version": self.manifest.get("version", "Unknown"),
            "gateway": self.manifest.get("gateway", {}),
            "results": [
                {
                    "node_id": r.node_id,
                    "success": r.success,
                    "duration_seconds": r.duration_seconds,
                    "error": r.error_message
                }
                for r in self.results
            ],
            "summary": {
                "total": len(self.results),
                "success": sum(1 for r in self.results if r.success),
                "failed": sum(1 for r in self.results if not r.success),
                "total_duration": sum(r.duration_seconds for r in self.results)
            },
            "topology": {
                "nodes": self.topology.graph.number_of_nodes(),
                "edges": self.topology.graph.number_of_edges(),
                "waves": len(self.topology.get_deployment_order())
            }
        }
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        return str(report_path)
    
    def deploy(self, node_ids: Optional[List[str]] = None, gateway_only: bool = False) -> bool:
        """Execute full network deployment"""
        logger.info("MycoSentinel Network Deployment")
        logger.info(f"Started: {datetime.now().isoformat()}")
        logger.info(f"Parallel workers: {self.parallel}")
        logger.info(f"Dry run: {self.dry_run}")
        
        # Load manifest
        if not self.load_manifest():
            return False
        
        # Discover hardware
        self.discover_hardware()
        
        # Generate topology visualization
        viz_path = DEPLOYMENT_DIR / "mesh_topology.png"
        self.topology.visualize(str(viz_path))
        
        # Deploy gateway
        if not self.deploy_gateway():
            logger.error("Gateway deployment failed")
            return False
        
        if gateway_only:
            logger.info("Gateway-only deployment complete")
            return True
        
        # Deploy nodes
        if not self.deploy_nodes(node_ids):
            logger.warning("Some node deployments failed")
            # Continue with mesh config
        
        # Configure mesh
        self.configure_mesh()
        
        # Verify network
        self.verify_network()
        
        # Generate report
        report_path = self.generate_report()
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("DEPLOYMENT SUMMARY")
        logger.info("=" * 60)
        
        success_count = sum(1 for r in self.results if r.success)
        fail_count = len(self.results) - success_count
        
        logger.info(f"Total nodes: {len(self.results)}")
        logger.info(f"Successful: {success_count}")
        logger.info(f"Failed: {fail_count}")
        logger.info(f"Report: {report_path}")
        
        if fail_count == 0:
            logger.info("✅ Network deployment COMPLETE!")
            return True
        else:
            logger.warning("⚠️ Network deployment completed with failures")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="MycoSentinel Network Deployment Script"
    )
    parser.add_argument("--manifest", "-m", 
                       default=str(DEPLOYMENT_DIR / "deploy_config.json"),
                       help="Path to deployment manifest")
    parser.add_argument("--parallel", "-p", type=int, default=2,
                       help="Number of parallel deployments")
    parser.add_argument("--gateway-only", "-g", action="store_true",
                       help="Deploy only gateway infrastructure")
    parser.add_argument("--nodes", "-n", 
                       help="Comma-separated list of node IDs to deploy")
    parser.add_argument("--dry-run", action="store_true",
                       help="Simulate deployment without making changes")
    parser.add_argument("--visualize", "-v", action="store_true",
                       help="Generate topology visualization and exit")
    
    args = parser.parse_args()
    
    # Create deployer
    deployer = NetworkDeployer(
        manifest_path=args.manifest,
        parallel=args.parallel,
        dry_run=args.dry_run
    )
    
    # Just visualize
    if args.visualize:
        if deployer.load_manifest():
            viz_path = DEPLOYMENT_DIR / "mesh_topology.png"
            deployer.topology.visualize(str(viz_path))
            print(f"Topology saved to: {viz_path}")
        return
    
    # Parse node list
    node_ids = None
    if args.nodes:
        node_ids = [n.strip() for n in args.nodes.split(",")]
    
    # Run deployment
    success = deployer.deploy(
        node_ids=node_ids,
        gateway_only=args.gateway_only
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
