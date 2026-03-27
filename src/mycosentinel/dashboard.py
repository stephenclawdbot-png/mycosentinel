"""
Web dashboard for MycoSentinel using Flask/FastAPI.
Real-time sensor monitoring with WebSocket support.
"""

import json
import time
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

# Try to import FastAPI, fall back to Flask
try:
    from fastapi import FastAPI, WebSocket
    from fastapi.responses import HTMLResponse
    from fastapi.staticfiles import StaticFiles
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    try:
        from flask import Flask, jsonify, render_template_string, request
        from flask_socketio import SocketIO
        FLASK_AVAILABLE = True
    except ImportError:
        FLASK_AVAILABLE = False
        logger.warning("No web framework available, dashboard disabled")

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>MycoSentinel Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            background: #0a0a0a;
            color: #00ff00;
            padding: 20px;
        }
        .header { 
            border-bottom: 2px solid #00ff00;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        .header h1 { font-size: 2em; margin-bottom: 10px; }
        .header p { color: #666; }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .card {
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 20px;
        }
        .card h3 {
            color: #00ff00;
            margin-bottom: 15px;
            font-size: 1.2em;
        }
        .metric {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #333;
        }
        .metric:last-child { border-bottom: none; }
        .metric-label { color: #888; }
        .metric-value { font-family: monospace; }
        .status-good { color: #00ff00; }
        .status-warning { color: #ffaa00; }
        .status-critical { color: #ff0000; }
        #chart-container {
            height: 300px;
            margin-top: 30px;
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 8px;
        }
        .log {
            font-family: monospace;
            font-size: 0.8em;
            max-height: 200px;
            overflow-y: auto;
            background: #000;
            padding: 10px;
            border-radius: 4px;
        }
        .log-entry { margin-bottom: 4px; }
        .anomaly {
            animation: pulse 2s infinite;
            background: rgba(255, 0, 0, 0.1);
        }
        @keyframes pulse {
            0% { border-color: #ff0000; }
            50% { border-color: #ff6666; }
            100% { border-color: #ff0000; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🍄 MycoSentinel</h1>
        <p>Living Biosensor Network — Real-time Environmental Monitoring</p>
    </div>
    
    <div class="grid">
        <div class="card" id="nodes-card">
            <h3>Active Nodes</h3>
            <div id="nodes-list">
                <div class="metric">
                    <span class="metric-label">Loading...</span>
                </div>
            </div>
        </div>
        
        <div class="card" id="latest-card">
            <h3>Latest Reading</h3>
            <div id="latest-data">
                <div class="metric">
                    <span class="metric-label">Waiting for data...</span>
                </div>
            </div>
        </div>
        
        <div class="card" id="anomalies-card">
            <h3>Anomaly Statistics</h3>
            <div id="anomaly-stats">
                <div class="metric">
                    <span class="metric-label">Total Detections:</span>
                    <span class="metric-value" id="total-anomalies">0</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Detection Rate:</span>
                    <span class="metric-value" id="detection-rate">0%</span>
                </div>
            </div>
        </div>
        
        <div class="card" id="system-card">
            <h3>System Status</h3>
            <div id="system-metrics">
                <div class="metric">
                    <span class="metric-label">Uptime:</span>
                    <span class="metric-value">0h 0m</span>
                </div>
            </div>
        </div>
    </div>
    
    <div class="card" style="margin-top: 20px;">
        <h3>Event Log</h3>
        <div class="log" id="event-log"></div>
    </div>
    
    <script>
        const eventLog = document.getElementById('event-log');
        const nodesList = document.getElementById('nodes-list');
        const latestData = document.getElementById('latest-data');
        
        function addLog(message, type = 'info') {
            const entry = document.createElement('div');
            entry.className = 'log-entry';
            entry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
            eventLog.prepend(entry);
            
            if (eventLog.children.length > 50) {
                eventLog.removeChild(eventLog.lastChild);
            }
        }
        
        function updateDisplay(data) {
            // Update latest reading
            if (data.processed) {
                const p = data.processed;
                latestData.innerHTML = `
                    <div class="metric ${p.contaminant_detected ? 'anomaly' : ''}">
                        <span class="metric-label">Node:</span>
                        <span class="metric-value">${data.node_id}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Raw Signal:</span>
                        <span class="metric-value">${p.filtered?.toFixed(2) || 'N/A'}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Anomaly Score:</span>
                        <span class="metric-value ${p.anomaly_score > 2 ? 'status-warning' : 'status-good'}">
                            ${p.anomaly_score?.toFixed(2) || 'N/A'}
                        </span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Detection:</span>
                        <span class="metric-value ${p.contaminant_detected ? 'status-critical' : 'status-good'}">
                            ${p.contaminant_detected ? '⚠️ CONTAMINANT DETECTED' : 'Normal'}
                        </span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Confidence:</span>
                        <span class="metric-value">${(p.confidence * 100).toFixed(1)}%</span>
                    </div>
                `;
            }
            
            if (p.contaminant_detected) {
                addLog(`ANOMALY: Node ${data.node_id}, score ${p.anomaly_score.toFixed(2)}`, 'warning');
            }
        }
        
        // Poll for updates
        setInterval(async () => {
            try {
                const response = await fetch('/api/latest');
                const data = await response.json();
                if (data) updateDisplay(data);
            } catch (e) {
                // Connection issue
            }
        }, 1000);
        
        // Poll for status
        setInterval(async () => {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                nodesList.innerHTML = Object.entries(data.nodes || {}).map(([id, status]) => `
                    <div class="metric">
                        <span class="metric-label">${id}</span>
                        <span class="metric-value ${status.running ? 'status-good' : 'status-warning'}">
                            ${status.running ? '●' : '○'} ${status.readings} readings
                        </span>
                    </div>
                `).join('');
                
                document.getElementById('total-anomalies').textContent = 
                    Object.values(data.nodes).reduce((sum, n) => sum + n.anomalies, 0);
                
            } catch (e) {}
        }, 5000);
        
        addLog('Dashboard connected');
    </script>
</body>
</html>
"""

class Dashboard:
    """Web dashboard for MycoSentinel monitoring"""
    
    def __init__(self, gateway: 'Gateway' = None, port: int = 8080):
        self.gateway = gateway
        self.port = port
        self.app = None
        self._latest_data = None
        
        if FASTAPI_AVAILABLE:
            self._init_fastapi()
        elif FLASK_AVAILABLE:
            self._init_flask()
        else:
            logger.warning("No web framework available for dashboard")
    
    def _init_fastapi(self):
        """Initialize FastAPI app"""
        self.app = FastAPI(title="MycoSentinel API")
        
        @self.app.get("/", response_class=HTMLResponse)
        async def index():
            return DASHBOARD_HTML
        
        @self.app.get("/api/status")
        async def status():
            return {
                "nodes": self.gateway.get_all_status() if self.gateway else {},
                "timestamp": time.time()
            }
        
        @self.app.get("/api/latest")
        async def latest():
            return self._latest_data or {}
        
        @self.app.websocket("/ws")
        async def websocket(websocket: WebSocket):
            await websocket.accept()
            while True:
                try:
                    if self._latest_data:
                        await websocket.send_json(self._latest_data)
                    await asyncio.sleep(1)
                except:
                    break
    
    def _init_flask(self):
        """Initialize Flask app"""
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        @self.app.route("/")
        def index():
            return render_template_string(DASHBOARD_HTML)
        
        @self.app.route("/api/status")
        def status():
            return jsonify({
                "nodes": self.gateway.get_all_status() if self.gateway else {},
                "timestamp": time.time()
            })
        
        @self.app.route("/api/latest")
        def latest():
            return jsonify(self._latest_data or {})
        
        @self.socketio.on('connect')
        def handle_connect():
            logger.info("Client connected to dashboard")
    
    def update_data(self, data: Dict):
        """Update latest data"""
        self._latest_data = data
        if FLASK_AVAILABLE and hasattr(self, 'socketio'):
            self.socketio.emit('data', data, broadcast=True)
    
    def run(self, host: str = "0.0.0.0"):
        """Run dashboard server"""
        if self.app is None:
            logger.error("No web framework available")
            return
        
        try:
            if FASTAPI_AVAILABLE:
                uvicorn.run(self.app, host=host, port=self.port)
            elif FLASK_AVAILABLE:
                self.socketio.run(self.app, host=host, port=self.port, debug=False)
        except Exception as e:
            logger.error(f"Dashboard failed: {e}")
    
    def run_async(self, host: str = "0.0.0.0"):
        """Run in thread"""
        import threading
        thread = threading.Thread(target=self.run, args=(host,), daemon=True)
        thread.start()
        return thread

if __name__ == "__main__":
    # Standalone demo
    dash = Dashboard(port=8080)
    if dash.app:
        print("Starting dashboard on http://localhost:8080")
        dash.run()
    else:
        print("Web framework not available. Install: pip install fastapi uvicorn")
