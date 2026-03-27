#!/usr/bin/env python3
"""
MycoSentinel Simulation Runner
Runs the complete 10-node simulation and captures results.

This script:
1. Starts the gateway server in the background
2. Initializes 10 simulated sensor nodes
3. Runs various contamination scenarios
4. Captures and logs results
5. Generates a simulation report

Usage:
    python3 run_simulation.py
    python3 run_simulation.py --duration 600
    python3 run_simulation.py --output results/

Author: MycoSentinel Deployment Team
Version: 1.0.0
"""

import os
import sys
import json
import time
import signal
import logging
import argparse
import subprocess
import threading
import queue
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from simulation.node_simulator import NodeSimulatorOrchestrator, MYCOTOXIN_PROFILES

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('simulation_run.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SimulationRunner:
    """
    Manages the full simulation lifecycle.
    Starts gateway, runs nodes, captures results.
    """
    
    def __init__(self, output_dir: str = "simulation_results", duration: int = 300):
        self.output_dir = Path(output_dir)
        self.duration = duration
        self.gateway_process = None
        self.nodes_started = False
        self.results = {
            "start_time": None,
            "end_time": None,
            "duration_seconds": 0,
            "gateway_pid": None,
            "nodes": [],
            "scenarios_run": [],
            "alerts_generated": [],
            "data_statistics": {},
            "errors": []
        }
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def start_gateway(self) -> bool:
        """Start the gateway server"""
        logger.info("Starting gateway server...")
        
        try:
            gateway_script = Path(__file__).parent.parent / "gateway" / "gateway_server.py"
            
            # Start gateway as subprocess
            self.gateway_process = subprocess.Popen(
                [sys.executable, str(gateway_script), "--port", "8000"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.output_dir)
            )
            
            # Wait for gateway to start
            time.sleep(2)
            
            if self.gateway_process.poll() is None:
                self.results["gateway_pid"] = self.gateway_process.pid
                logger.info(f"Gateway started (PID: {self.gateway_process.pid})")
                return True
            else:
                logger.error("Gateway failed to start")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start gateway: {e}")
            return False
    
    def stop_gateway(self):
        """Stop the gateway server"""
        if self.gateway_process and self.gateway_process.poll() is None:
            logger.info("Stopping gateway...")
            self.gateway_process.terminate()
            try:
                self.gateway_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.gateway_process.kill()
            logger.info("Gateway stopped")
    
    def run_simulation(self) -> Dict:
        """Run the full simulation"""
        self.results["start_time"] = datetime.now().isoformat()
        
        try:
            # Create node simulator
            logger.info("Creating node simulator...")
            simulator = NodeSimulatorOrchestrator(
                gateway_host="localhost",
                gateway_port=8000,
                mqtt_port=1883,
                data_rate_hz=1.0,
                node_count=10
            )
            
            # Initialize and connect nodes
            simulator.initialize_nodes()
            time.sleep(1)
            simulator.connect_all()
            time.sleep(1)
            
            # Start all nodes
            simulator.start_all()
            self.nodes_started = True
            
            # Wait for nodes to stabilize
            logger.info("Waiting for nodes to stabilize (5s)...")
            time.sleep(5)
            
            # Run scenarios
            logger.info("Running simulation scenarios...")
            scenarios = ["baseline", "single_contamination", "multi_contamination"]
            
            for scenario in scenarios:
                logger.info(f"\n{'='*60}")
                logger.info(f"Running scenario: {scenario}")
                logger.info(f"{'='*60}")
                
                events = simulator.run_simulation_scenario(scenario, int(self.duration / len(scenarios)))
                self.results["scenarios_run"].append({
                    "scenario": scenario,
                    "events": events if events else []
                })
                
                # Clear contamination between scenarios
                simulator.clear_all_contamination()
                time.sleep(5)
            
            # Get final status
            final_status = simulator.get_status()
            self.results["nodes"] = [
                {
                    "node_id": nid,
                    **node_info
                }
                for nid, node_info in final_status["nodes"].items()
            ]
            
            # Get data statistics from gateway
            try:
                import requests
                response = requests.get("http://localhost:8000/api/v1/aggregate/all", timeout=5)
                if response.status_code == 200:
                    self.results["data_statistics"] = response.json().get("statistics", {})
                
                # Get alerts
                response = requests.get("http://localhost:8000/api/v1/alerts", timeout=5)
                if response.status_code == 200:
                    self.results["alerts_generated"] = response.json().get("alerts", [])
                    
            except Exception as e:
                logger.warning(f"Could not fetch final statistics: {e}")
            
            # Stop nodes
            logger.info("Stopping nodes...")
            simulator.stop_all()
            self.nodes_started = False
            
        except Exception as e:
            logger.error(f"Simulation error: {e}")
            self.results["errors"].append(str(e))
        
        self.results["end_time"] = datetime.now().isoformat()
        
        return self.results
    
    def generate_report(self) -> str:
        """Generate simulation report"""
        report_file = self.output_dir / "SIMULATION_REPORT.md"
        
        with open(report_file, 'w') as f:
            f.write("# MycoSentinel 10-Node Simulation Report\n\n")
            
            f.write("## Summary\n\n")
            f.write(f"- **Start Time:** {self.results['start_time']}\n")
            f.write(f"- **End Time:** {self.results['end_time']}\n")
            f.write(f"- **Gateway PID:** {self.results.get('gateway_pid', 'N/A')}\n")
            f.write(f"- **Nodes Simulated:** 10\n")
            f.write(f"- **Scenarios Run:** {len(self.results['scenarios_run'])}\n")
            f.write(f"- **Alerts Generated:** {len(self.results.get('alerts_generated', []))}\n")
            
            f.write("\n## Node Status\n\n")
            f.write("| Node ID | Sector | Status | Sequence # | Contaminated |\n")
            f.write("|---------|--------|--------|------------|-------------|\n")
            for node in self.results.get("nodes", []):
                f.write(f"| {node.get('node_id', 'N/A')} | {node.get('sector', 'N/A')} | "
                       f"{'Online' if node.get('registered') else 'Offline'} | "
                       f"{node.get('sequence_num', 0)} | "
                       f"{'Yes' if node.get('contaminated') else 'No'} |\n")
            
            f.write("\n## Scenarios Executed\n\n")
            for scenario in self.results.get("scenarios_run", []):
                f.write(f"### {scenario['scenario'].replace('_', ' ').title()}\n\n")
                if scenario.get('events'):
                    f.write("Events:\n")
                    for event in scenario['events']:
                        f.write(f"- {event}\n")
                else:
                    f.write("_No specific events triggered_\n")
                f.write("\n")
            
            f.write("\n## Data Statistics\n\n")
            stats = self.results.get("data_statistics", {})
            if stats:
                f.write(f"- Total Readings: {stats.get('total_readings', 'N/A')}\n")
                f.write(f"- Nodes Reporting: {stats.get('nodes_reporting', 'N/A')}\n")
                f.write(f"- Average Optical Response: {stats.get('avg_optical', 'N/A')}\n")
                f.write(f"- Average Electrical Response: {stats.get('avg_electrical', 'N/A')}\n")
                f.write(f"- Anomalies Detected: {stats.get('anomaly_detected_count', 'N/A')}\n")
            else:
                f.write("_Statistics not available_\n")
            
            f.write("\n## Alerts\n\n")
            alerts = self.results.get("alerts_generated", [])
            if alerts:
                for alert in alerts:
                    f.write(f"- **{alert.get('severity', 'info').upper()}**: "
                           f"{alert.get('message', 'N/A')} "
                           f"({alert.get('node_id', 'N/A')})\n")
            else:
                f.write("_No alerts generated_\n")
            
            f.write("\n## Errors\n\n")
            errors = self.results.get("errors", [])
            if errors:
                for error in errors:
                    f.write(f"- {error}\n")
            else:
                f.write("_No errors during simulation_\n")
            
            f.write("\n---\n\n")
            f.write("\n*Report generated by MycoSentinel Simulation Runner*\n")
        
        logger.info(f"Report saved to: {report_file}")
        return str(report_file)
    
    def cleanup(self):
        """Cleanup resources"""
        if self.nodes_started:
            logger.info("Emergency cleanup: stopping nodes...")
        
        self.stop_gateway()
    
    def run(self) -> Dict:
        """Run complete simulation workflow"""
        try:
            # Start gateway
            if not self.start_gateway():
                self.results["errors"].append("Failed to start gateway")
                return self.results
            
            # Run simulation
            logger.info("\n" + "="*60)
            logger.info("SIMULATION STARTING")
            logger.info("="*60 + "\n")
            
            self.run_simulation()
            
            # Generate report
            self.generate_report()
            
        finally:
            self.cleanup()
        
        return self.results


def main():
    parser = argparse.ArgumentParser(description='Run MycoSentinel 10-Node Simulation')
    parser.add_argument('--output', '-o', default='simulation_results',
                       help='Output directory for results')
    parser.add_argument('--duration', '-d', type=int, default=300,
                       help='Simulation duration in seconds (default: 300)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    print("="*70)
    print("  🍄 MYCOSENTINEL 10-NODE DEPLOYMENT SIMULATION")
    print("="*70)
    print()
    print(f"  Output Directory: {args.output}")
    print(f"  Duration: {args.duration} seconds")
    print()
    print("  This will:")
    print("    1. Start the Gateway Server")
    print("    2. Simulate 10 sensor nodes")
    print("    3. Run contamination scenarios")
    print("    4. Generate results report")
    print()
    print("="*70)
    print()
    
    runner = SimulationRunner(
        output_dir=args.output,
        duration=args.duration
    )
    
    results = runner.run()
    
    print("\n" + "="*70)
    print("  SIMULATION COMPLETE")
    print("="*70)
    print(f"\n  Results saved to: {args.output}/")
    print(f"  Report: {args.output}/SIMULATION_REPORT.md")
    print()
    print(f"  Nodes simulated: {len(results.get('nodes', []))}")
    print(f"  Scenarios run: {len(results.get('scenarios_run', []))}")
    print(f"  Alerts: {len(results.get('alerts_generated', []))}")
    print(f"  Errors: {len(results.get('errors', []))}")
    print()
    print("="*70)


if __name__ == '__main__':
    main()
