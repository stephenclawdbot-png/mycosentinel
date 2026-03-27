# MycoSentinel 10-Node Network Deployment Plan

**Document Version:** 1.0.0  
**Deployment Phase:** Active Test Network  
**Target:** Raspberry Pi Zero 2 W / Pico W / ESP32-S3 Nodes  
**Last Updated:** 2026-03-28

---

## Executive Summary

This document outlines the deployment plan for the MycoSentinel 10-node biosensor network. The network consists of engineered yeast biosensors capable of detecting mycotoxins through dual-readout systems (optical fluorescence + electrical impedance).

---

## 1. Network Topology

### 1.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MYCOSENTINEL 10-NODE NETWORK                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│    ┌─────────────────────────────────────────────────────────┐              │
│    │                  GATEWAY NODE (MS-GW)                   │              │
│    │              Raspberry Pi 4B / 4GB RAM                   │              │
│    │  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌───────┐  │              │
│    │  │  MQTT    │  │  JSON API │  │  Data    │  │  Web  │  │              │
│    │  │  Broker  │  │  Server   │  │  Store   │  │  Dash │  │              │
│    │  └────┬─────┘  └────┬──────┘  └────┬─────┘  └───┬───┘  │              │
│    │       │             │              │            │       │              │
│    │       └─────────────┴──────┬───────┴────────────┘       │              │
│    │                            │                           │              │
│    │                    ┌───────┴────────┐                  │              │
│    │                    │   Aggregator    │                  │              │
│    │                    │   & Registry    │                  │              │
│    │                    └────────┬───────┘                  │              │
│    │                             │                          │              │
│    │                      WiFi Mesh / LoRa                   │              │
│    └─────────────────────────────┼──────────────────────────┘              │
│                                  │                                         │
│                    ┌─────────────┼─────────────┐                          │
│                    │             │             │                          │
│               ┌────▼────┐   ┌────▼────┐   ┌────▼────┐                      │
│               │ MS-A1   │   │ MS-A2   │   │ MS-A3   │   Sector A: Area 1   │
│               │ Sector A│   │ Sector A│   │ Sector A│   (Warehouse A)        │
│               └────┬────┘   └────┬────┘   └────┬────┘                      │
│                    │             │             │                          │
│               ┌────▼────┐   ┌────▼────┐   ┌────▼────┐                      │
│               │ MS-B1   │   │ MS-B2   │   │ MS-B3   │   Sector B: Area 2   │
│               │ Sector B│   │ Sector B│   │ Sector B│   (Warehouse B)      │
│               └────┬────┘   └────┬────┘   └────┬────┘                      │
│                    │             │             │                          │
│               ┌────▼────┐   ┌────▼────┐   ┌────▼────┐                      │
│               │ MS-C1   │   │ MS-C2   │   │ MS-C3   │   Sector C: Area 3   │
│               │ Sector C│   │ Sector C│   │ Sector C│   (Processing)       │
│               └────┬────┘   └────┬────┘   └────┬────┘                      │
│                    │             │             │                          │
│               ┌────▼────┐   ┌────▼────┐   ┌────▼────┐                      │
│               │ MS-D1   │   │ MS-D2   │   │         │   Sector D: Area 4   │
│               │ Sector D│   │ Sector D│   │ (spare) │   (Shipping/Entry)   │
│               └─────────┘   └─────────┘   └─────────┘                      │
│                                                                             │
│    Node Naming Convention: MS-{SECTOR}{INDEX}                                │
│    - MS: MycoSentinel                                                       │
│    - Sector: A, B, C, D (geographic area)                                  │
│    - Index: 1, 2, 3 (node counter per sector)                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Network Topology Type: Hybrid Mesh

**Primary Communication:** WiFi Mesh (IEEE 802.11s / BATMAN-adv)  
**Fallback Communication:** LoRa (Long Range, low power)  
**Range:** ~50-100m between nodes in mesh, ~1km LoRa  
**Topology:** Partial Mesh with Gateway as Root

```
                    ┌─────────────┐
                    │    MS-GW    │
                    │   Gateway   │
                    │  10.0.0.1   │
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
     ┌────▼────┐      ┌────▼────┐      ┌────▼────┐
     │ MS-A1   │◄────►│ MS-A2   │◄────►│ MS-A3   │
     │10.0.0.11│      │10.0.0.12│      │10.0.0.13│
     └────┬────┘      └────┬────┘      └────┬────┘
          │                │                │
     ┌────▼────┐      ┌────▼────┐      ┌────▼────┐
     │ MS-B1   │◄────►│ MS-B2   │◄────►│ MS-B3   │
     │10.0.0.21│      │10.0.0.22│      │10.0.0.23│
     └────┬────┘      └─────────┘      └────┬────┘
          │                                   │
     ┌────▼────┐      ┌─────────┐      ┌────▼────┐
     │ MS-C1   │◄────►│ MS-C2   │◄────►│ MS-C3   │
     │10.0.0.31│      │10.0.0.32│      │10.0.0.33│
     └────┬────┘      └─────────┘      └─────────┘
          │
     ┌────▼────┐      ┌─────────┐
     │ MS-D1   │◄────►│ MS-D2   │
     │10.0.0.41│      │10.0.0.42│
     └─────────┘      └─────────┘
```

### 1.3 IP Address Allocation

| Node | Role | Static IP | MAC Reservation | Notes |
|------|------|-----------|-----------------|-------|
| MS-GW | Gateway | 10.0.0.1 | b8:27:eb:xx:xx:01 | Raspberry Pi 4B |
| MS-A1 | Sensor | 10.0.0.11 | b8:27:eb:xx:xx:11 | Sector A |
| MS-A2 | Sensor | 10.0.0.12 | b8:27:eb:xx:xx:12 | Sector A |
| MS-A3 | Sensor | 10.0.0.13 | b8:27:eb:xx:xx:13 | Sector A |
| MS-B1 | Sensor | 10.0.0.21 | b8:27:eb:xx:xx:21 | Sector B |
| MS-B2 | Sensor | 10.0.0.22 | b8:27:eb:xx:xx:22 | Sector B |
| MS-B3 | Sensor | 10.0.0.23 | b8:27:eb:xx:xx:23 | Sector B |
| MS-C1 | Sensor | 10.0.0.31 | b8:27:eb:xx:xx:31 | Sector C |
| MS-C2 | Sensor | 10.0.0.32 | b8:27:eb:xx:xx:32 | Sector C |
| MS-C3 | Sensor | 10.0.0.33 | b8:27:eb:xx:xx:33 | Sector C |
| MS-D1 | Sensor | 10.0.0.41 | b8:27:eb:xx:xx:41 | Sector D |
| MS-D2 | Sensor | 10.0.0.42 | b8:27:eb:xx:xx:42 | Sector D |

---

## 2. Communication Protocol

### 2.1 Protocol Stack

| Layer | Protocol | Purpose |
|-------|----------|---------|
| Application | Custom JSON/MQTT | Sensor data, commands |
| Transport | TCP (MQTT) / UDP (Discovery) | Reliable messaging |
| Network | IP v4 | Static addressing |
| Data Link | WiFi (802.11s) or LoRa | Mesh connectivity |
| Physical | WiFi 2.4GHz / LoRa 868MHz | Radio transmission |

### 2.2 MQTT Topic Structure

```
mycosentinel/
├── nodes/
│   ├── MS-A1/
│   │   ├── data          # Sensor readings (JSON, 1 Hz)
│   │   ├── status        # Node health (every 60s)
│   │   └── events        # Alerts, calibration events
│   ├── MS-A2/
│   │   └── ...
│   └── ...
├── gateway/
│   ├── status            # Gateway health
│   ├── commands          # Broadcast commands
│   └── aggregated        # Processed data streams
└── system/
    ├── alerts            # Critical alerts
    ├── calibration       # Calibration updates
    └── config            # Configuration updates
```

### 2.3 Data Packet Format

**Sensor Data Packet (JSON):**
```json
{
  "node_id": "MS-A1",
  "timestamp": 1704067200.123,
  "sequence_num": 15234,
  "bioreactor": {
    "temperature_c": 28.5,
    "humidity_percent": 65.0,
    "ph": 6.8,
    "stirrer_rpm": 120
  },
  "optical": {
    "wavelength_nm": 525,
    "raw_fluorescence": 2048,
    "background_subtracted": 1842,
    "normalized": 1.15
  },
  "electrical": {
    "impedance_ohm": 4500,
    "voltage_v": 0.85,
    "current_ua": 12.3,
    "normalized_response": 0.93
  },
  "processing": {
    "mycotoxin_detected": false,
    "anomaly_score": 0.12,
    "confidence": 0.89,
    "state": "baseline"
  },
  "meta": {
    "firmware_version": "0.1.0",
    "uptime_seconds": 86400,
    "battery_percent": 87.5,
    "rssi_dbm": -65
  }
}
```

### 2.4 Communication Schedule

| Traffic Type | Frequency | Payload Size | MQTT QoS |
|--------------|-----------|--------------|----------|
| Sensor Data | 1 Hz | ~500 bytes | 1 (at least once) |
| Status Update | 60 s | ~200 bytes | 0 (at most once) |
| Alert/Event | Immediate | ~300 bytes | 2 (exactly once) |
| Discovery Beacon | 30 s | ~100 bytes | 0 |
| Command Response | On request | Varies | 1 |

---

## 3. Gateway Setup Requirements

### 3.1 Hardware Requirements

| Component | Specification | Purpose |
|-----------|---------------|---------|
| Gateway Host | Raspberry Pi 4B (4GB) | Data aggregation, API |
| Storage | 32GB+ microSD (Class 10) | Data logging |
| Network | Ethernet + WiFi dual-stack | External + mesh connectivity |
| Power | 5V/3A USB-C PSU | Continuous operation |
| Cooling | Passive heatsink case | Thermal management |
| Optional | UPS HAT (PiJuice) | Power backup |

### 3.2 Service Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     MS-GW Services                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────┐           │
│  │              Docker Compose                  │           │
│  ├─────────────────────────────────────────────┤           │
│  │                                             │           │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐ │           │
│  │  │ Mosquitto│  │ InfluxDB │  │  FastAPI │ │           │
│  │  │ (MQTT)   │  │(TSDB)    │  │ (JSON)   │ │           │
│  │  │  1883    │  │ 8086     │  │ 8000     │ │           │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘ │           │
│  │       │             │             │       │           │
│  │       └─────────────┼─────────────┘       │           │
│  │                     │                      │           │
│  │              ┌──────┴──────┐             │           │
│  │              │  Gateway     │             │           │
│  │              │  Core        │             │           │
│  │              │              │             │           │
│  │              │ • Registry   │             │           │
│  │              │ • Aggregator │             │           │
│  │              │ • Scheduler  │             │           │
│  │              └─────────────┘             │           │
│  │                                             │           │
│  └─────────────────────────────────────────────┘           │
│                                                              │
│  Network Interfaces:                                          │
│  - eth0: 192.168.1.100 (external LAN)                        │
│  - wlan0: 10.0.0.1 (mesh AP)                                 │
│  - bat0: 10.0.0.1 (BATMAN mesh)                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 Software Stack

| Service | Version | Purpose | Port |
|---------|---------|---------|------|
| Mosquitto MQTT | 2.x | Message broker | 1883 (TCP), 9001 (WS) |
| InfluxDB | 2.7 | Time-series database | 8086 |
| FastAPI | 0.100+ | REST API server | 8000 |
| Python | 3.11 | Runtime environment | - |
| Docker | 24.x | Containerization | - |
| Docker Compose | 2.x | Service orchestration | - |

### 3.4 Gateway Capabilities

- **Data Aggregation**: Real-time collection from 10+ nodes
- **Persistence**: 30-day rolling data storage with compression
- **API**: RESTful JSON API for external integrations
- **Dashboard**: Web-based visualization (optional Grafana)
- **Alerts**: Threshold-based alerting system
- **OTA**: Over-the-air firmware updates for nodes
- **Health Monitoring**: Node heartbeat and status tracking

---

## 4. Data Collection & Visualization

### 4.1 Data Flow

```
┌─────────┐    MQTT     ┌─────────────────────────────────────────┐
│  Sensor │────────────►│  Gateway Core                         │
│ Node    │             │  • Parse JSON                         │
│         │             │  • Basic validation                   │
└─────────┘             │  • Node registry                      │
                        │  • Data buffering                     │
                        └──────┬────────────────────────────────┘
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
            ▼                  ▼                  ▼
     ┌────────────┐    ┌────────────┐    ┌────────────┐
     │ InfluxDB   │    │  REST API  │    │  Real-time │
     │ (Storage)  │    │  (Query)   │    │  WebSocket │
     └────────────┘    └────────────┘    └────────────┘
            │                  │                  │
            │                  │                  │
       ┌────▼────┐       ┌────▼────┐       ┌────▼────┐
       │Grafana  │       │External │       │Dashboard│
       │(Viz)    │       │Systems  │       │(Live)   │
       └─────────┘       └─────────┘       └─────────┘
```

### 4.2 Data Retention Policy

| Data Type | Storage | Retention | Compression |
|-----------|---------|-----------|-------------|
| Raw sensor data | InfluxDB | 7 days | None |
| 1-minute aggregated | InfluxDB | 30 days | Basic |
| 1-hour aggregated | InfluxDB | 1 year | High |
| Alert history | InfluxDB | 5 years | None |
| System logs | Files | 30 days | Gzip |

### 4.3 API Endpoints

| Endpoint | Method | Description | Response |
|----------|--------|-------------|----------|
| `/api/v1/health` | GET | Gateway health status | JSON |
| `/api/v1/nodes` | GET | List all registered nodes | JSON array |
| `/api/v1/nodes/{id}` | GET | Node details and status | JSON |
| `/api/v1/nodes/{id}/data` | GET | Latest sensor data | JSON |
| `/api/v1/nodes/{id}/history` | GET | Historical data (time range) | JSON array |
| `/api/v1/aggregate/all` | GET | Aggregated data from all nodes | JSON |
| `/api/v1/alerts` | GET | Active alerts | JSON array |
| `/api/v1/config` | GET/POST | Configuration management | JSON |

### 4.4 Visualization Dashboard

**Real-time Views:**
- Network topology map (all 10 nodes)
- Node status grid (online/offline)
- Sensor reading gauges (current values)
- Time-series charts (trends)
- Alert panel (critical notifications)

**Historical Views:**
- Heat maps (sector contamination levels)
- Trend analysis (hourly/daily/weekly)
- Export functionality (CSV, JSON)

---

## 5. Deployment Timeline

### Phase 1: Gateway Setup (Day 1)
- [ ] Flash SD card with Raspberry Pi OS Lite
- [ ] Configure static IP and network
- [ ] Install Docker and Docker Compose
- [ ] Deploy MQTT broker
- [ ] Deploy data store (InfluxDB)
- [ ] Deploy API server (FastAPI)
- [ ] Verify gateway services running

### Phase 2: Network Configuration (Day 2)
- [ ] Configure WiFi mesh / BATMAN-adv
- [ ] Set up DHCP reservations
- [ ] Configure firewall rules
- [ ] Test mesh connectivity
- [ ] Document network topology

### Phase 3: Node Provisioning (Days 3-5)
- [ ] Flash firmware to all 10 nodes
- [ ] Configure node IDs and static IPs
- [ ] Calibrate sensors (if hardware available)
- [ ] Register nodes with gateway
- [ ] Test data transmission

### Phase 4: Simulation & Validation (Day 6)
- [ ] Run synthetic data simulation
- [ ] Verify data aggregation working
- [ ] Test API endpoints
- [ ] Validate alert system
- [ ] Generate deployment report

### Phase 5: Production Deployment (Day 7+)
- [ ] Deploy to physical locations
- [ ] Final calibration
- [ ] Monitoring handover
- [ ] Documentation update

---

## 6. Hardware Bill of Materials

### Per Node (x10)

| Component | Model | Unit Cost | Qty | Total |
|-----------|-------|-----------|-----|-------|
| Controller | Raspberry Pi Zero 2 W | $15 | 10 | $150 |
| WiFi | Onboard | - | - | - |
| Power | 5V/2.5A PSU | $8 | 10 | $80 |
| Case | Waterproof enclosure | $12 | 10 | $120 |
| Optical Sensor | AS7341 (11-channel) | $20 | 10 | $200 |
| Electrical Sensor | Custom PCB | $25 | 10 | $250 |
| Bioreactor | 3D printed + consumables | $30 | 10 | $300 |
| Yeast Strain | BIOSYN-03 | $50 | 1 | $50 |
| Misc | Cables, connectors | $15 | 10 | $150 |
| **Node Subtotal** | | | | **$1,300** |

### Gateway (x1)

| Component | Model | Cost |
|-----------|-------|------|
| Gateway | Raspberry Pi 4B (4GB) | $55 |
| Power | 5V/3A PSU | $10 |
| Case | Metal heatsink case | $20 |
| MicroSD | 64GB Class 10 | $15 |
| **Gateway Subtotal** | | **$100** |

### Network Infrastructure

| Component | Model | Cost |
|-----------|-------|------|
| Ethernet Switch | 8-port managed | $40 |
| Cables | Cat6 patch cables | $25 |
| UPS | APC Back-UPS 650VA | $80 |
| **Infrastructure Subtotal** | | **$145** |

### Total Deployment Cost: **$1,545**

---

## 7. Risk Management

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Node hardware failure | Medium | Medium | Spare nodes available (2 extra) |
| Network connectivity loss | Low | High | Local buffering on nodes + LoRa fallback |
| Gateway failure | Low | Critical | Automated backups, quick-restore procedure |
| Sensor drift | High | Medium | Automated calibration alerts, 24h recalibration |
| False positives | Medium | Medium | Dual-sensor confirmation + ML validation |
| Power outage | Medium | High | UPS on gateway, battery backups on nodes |

---

## 8. Success Criteria

- [ ] All 10 nodes successfully register with gateway
- [ ] Data collection at 1 Hz from all nodes, 99%+ uptime
- [ ] API responding within 100ms for queries
- [ ] Mesh network self-healing (automatic rerouting on node failure)
- [ ] Alert system working (threshold detection < 5 seconds)
- [ ] Data visualization dashboard accessible
- [ ] 7-day continuous operation without manual intervention

---

## Appendix A: Network Commands Reference

```bash
# Check node status
curl http://10.0.0.1:8000/api/v1/nodes

# Get node data
curl http://10.0.0.1:8000/api/v1/nodes/MS-A1/data

# MQTT test publish
mosquitto_pub -h 10.0.0.1 -t mycosentinel/test -m "hello"

# MQTT subscribe to all
docker exec -it mycosentinel-mosquitto mosquitto_sub -t 'mycosentinel/#' -v
```

## Appendix B: Node Registration Process

1. **Discovery**: Node broadcasts presence on mesh
2. **Authentication**: Gateway validates node certificate/ID
3. **Registration**: Gateway adds node to registry
4. **Config Sync**: Gateway pushes configuration to node
5. **Data Flow**: Node begins transmitting sensor data
6. **Monitoring**: Gateway tracks node health and connectivity

---

**Document Owner:** Deployment Team  
**Review Cycle:** Weekly during deployment  
**Distribution:** Core Team, Facilities
