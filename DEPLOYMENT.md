# MycoSentinel 10-Node Deployment Guide

## Overview

This guide covers the deployment of the MycoSentinel biosensor network - a 10-node environmental monitoring system with auto-discovery, OTA updates, and real-time alerting.

**Project ID:** MYCOSENTINEL-ENV-10NODE  
**Version:** v0.2.0  
**Status:** Deployment Ready

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Hardware Setup](#hardware-setup)
3. [Network Architecture](#network-architecture)
4. [Quick Start](#quick-start)
5. [Deployment Scripts](#deployment-scripts)
6. [Monitoring](#monitoring)
7. [OTA Updates](#ota-updates)
8. [Troubleshooting](#troubleshooting)
9. [Maintenance](#maintenance)

---

## Prerequisites

### Hardware Requirements

| Component | Quantity | Specification |
|-----------|----------|---------------|
| Gateway | 1 | Raspberry Pi 4B (4GB+) |
| Sensor Nodes | 10 | Raspberry Pi Zero 2 W |
| CO2 Sensors | 10 | Sensirion SCD30 |
| PM Sensors | 10 | Sensirion SPS30 |
| VOC Sensors | 10 | Sensirion SGP40 |
| Temp/Humidity | 10 | DHT22 |
| Solar Panels | 10 | 20W (30W for relay nodes) |
| Batteries | 10 | 10Ah LiFePO4 (15Ah for MS-C4) |

### Software Requirements

```
Python 3.9+
Git
SSH client
MQTT broker (Mosquitto)
InfluxDB (optional)
Grafana (optional)
```

### Network Requirements

- Gateway IP: `192.168.1.100`
- Node Subnet: `192.168.1.101-110`
- Mesh Protocol: B.A.T.M.A.N. or WiFi-based mesh
- MQTT Port: 1883

---

## Hardware Setup

### Gateway Assembly

1. Install Raspberry Pi OS (64-bit) on gateway
2. Connect Ethernet
3. Assign static IP: `192.168.1.100`
4. Configure WiFi AP for mesh backbone

### Node Assembly (per node)

1. **Raspberry Pi Zero 2 W Setup:**
   ```bash
   # Enable I2C
   sudo raspi-config nonint do_i2c 0
   
   # Enable SPI
   sudo raspi-config nonint do_spi 0
   ```

2. **Sensor Wiring (I2C):**
   | Sensor | Address | VCC | SDA | SCL |
   |--------|---------|-----|-----|-----|
   | SCD30 | 0x61 | 3.3V | GPIO2 | GPIO3 |
   | SPS30 | 0x69 | 3.3V | GPIO2 | GPIO3 |
   | SGP40 | 0x59 | 3.3V | GPIO2 | GPIO3 |
   | DHT22 | - | 3.3V | GPIO4 | - |

3. **Solar/Battery:**
   - Connect charge controller
   - Wire battery to Pi via buck converter (5V)

---

## Network Architecture

```
                    ┌─────────────────┐
                    │   GATEWAY       │
                    │  192.168.1.100  │
                    │  MQTT/InfluxDB  │
                    └────────┬────────┘
                             │ WiFi/Mesh
         ┌───────────────────┼───────────────────┐
         │                   │                   │
    ┌────▼────┐       ┌──────▼──────┐      ┌────▼────┐
    │ MS-A1   │◄────►│   MS-A2     │◄────►│ MS-A3   │
    │101      │ mesh  │   102       │ mesh │ 103     │
    └──┬──┬───┘       └──────┬──────┘      └──┬──┬───┘
       │  │                  │                │  │
    ┌──▼──▼───┐         ┌────▼────┐      ┌───▼──▼──┐
    │ MS-B1   │◄───────►│ MS-B2   │◄────►│ MS-B3   │
    │ 104     │  mesh   │ 105     │ mesh │ 106     │
    └────┬────┘         └────┬────┘      └────┬────┘
         │                   │                │
         │              ┌────▼────┐           │
         │              │ MS-C4 │◄──────────┘
         │              │ 110   │ relay
         │              └───┬───┘
         │                  │
    ┌────▼────┐       ┌─────▼─────┐      ┌───▼────┐
    │ MS-C1   │◄────►│   MS-C2   │◄────►│ MS-C3  │
    │ 107     │ mesh  │   108     │ mesh │ 109    │
    └─────────┘       └───────────┘      └────────┘
```

**Sectors:**
- Sector A (101-103): Gateway-adjacent primary nodes
- Sector B (104-106): Mid-range relay capable
- Sector C (107-110): Extended range (C4 is relay node)

---

## Quick Start

### 1. Gateway Setup

```bash
# On gateway (192.168.1.100)
cd /opt/mycosentinel/deployment

# Install gateway services
python3 deploy_network.py --gateway-only

# Verify services
systemctl status mosquitto
systemctl status influxdb
```

### 2. Deploy Network

```bash
# Full 10-node deployment
python3 deploy_network.py --manifest deploy_config.json

# Or deploy specific nodes
python3 deploy_network.py --nodes MS-A1,MS-A2,MS-A3
```

### 3. Start Monitoring

```bash
python3 network_monitor.py
```

---

## Deployment Scripts

### deploy_node.py

Flash and configure a single node.

```bash
# Deploy single node
python3 deploy_node.py --node-id MS-A1 --target 192.168.1.101

# Deploy with custom config
python3 deploy_node.py --node-id MS-A1 --target 192.168.1.101 --config my_config.json

# Skip hardware test (for development)
python3 deploy_node.py --node-id MS-A1 --target 192.168.1.101 --skip-hardware-test

# Dry run (see what would happen)
python3 deploy_node.py --node-id MS-A1 --target 192.168.1.101 --dry-run
```

**Deployment Steps:**
1. Check prerequisites
2. Flash firmware
3. Configure network (static IP)
4. Install dependencies
5. Deploy sensor code
6. Calibrate sensors
7. Verify deployment

### deploy_network.py

Deploy entire 10-node mesh network.

```bash
# Full deployment
python3 deploy_network.py

# Deploy nodes only (skip gateway)
python3 deploy_network.py --nodes MS-A1,MS-A2,MS-B1

# Visualize topology only
python3 deploy_network.py --visualize

# Parallel deployment (3 workers)
python3 deploy_network.py --parallel 3
```

**Features:**
- Automatic mesh topology calculation
- Wave-based deployment (gateway-adjacent first)
- Parallel node deployment
- Rollback on failure
- Network verification

---

## Monitoring

### network_monitor.py

Real-time console dashboard with alert system.

```bash
# Start live monitoring
python3 network_monitor.py

# Discover nodes
python3 network_monitor.py --discover

# Quick status check
python3 network_monitor.py --status

# Test alerts
python3 network_monitor.py --alert-test
```

**Dashboard Columns:**
- Node ID: MS-XX identifier
- Sector: A, B, or C
- Status: ● Online / ● Offline
- IP: Static IP address
- Uptime: How long online
- Last Seen: Time since last heartbeat
- Sensors: Active sensor count

### Alert Thresholds

| Sensor | Warning | Critical |
|--------|---------|----------|
| CO2 (ppm) | >1000 | >1500 |
| PM2.5 (µg/m³) | >35 | >75 |
| PM10 (µg/m³) | >150 | >250 |
| VOC Index | >200 | >300 |
| Temperature (°C) | <10 or >40 | <5 or >45 |
| Humidity (%) | <20 or >80 | <10 or >95 |

Alerts are automatically cleared when readings return to normal.

---

## OTA Updates

Over-the-air firmware updates for deployed nodes.

### Prepare Firmware

```bash
# Place firmware in deployment/firmware/
cp mycosentinel_v0.2.1.bin deployment/firmware/

# Verify checksum
sha256sum deployment/firmware/mycosentinel_v0.2.1.bin
```

### Initiate Update

```bash
# Update single node
python3 network_monitor.py --ota --node MS-A1 --version v0.2.1

# Monitor will show progress:
# OTA MS-A1: 25% complete
# OTA MS-A1: 50% complete
# OTA MS-A1: 75% complete
# OTA MS-A1: 100% complete
```

### Rollback

```bash
# Rollback to previous version
python3 network_monitor.py --rollback --node MS-A1
```

---

## Troubleshooting

### Node Not Responding

1. **Check power:**
   ```bash
   ping 192.168.1.101
   ```

2. **Check logs:**
   ```bash
   ssh pi@192.168.1.101 "sudo journalctl -u mycosentinel -f"
   ```

3. **Service status:**
   ```bash
   ssh pi@192.168.1.101 "sudo systemctl status mycosentinel"
   ```

4. **Redeploy if needed:**
   ```bash
   python3 deploy_node.py --node-id MS-A1 --target 192.168.1.101
   ```

### MQTT Connection Issues

1. **Check broker:**
   ```bash
   mosquitto_sub -h 192.168.1.100 -t "mycosentinel/#" -v
   ```

2. **Verify firewall:**
   ```bash
   sudo ufw status
   sudo ufw allow 1883
   ```

### Sensor Errors

1. **I2C scan:**
   ```bash
   ssh pi@192.168.1.101 "sudo i2cdetect -y 1"
   # Should show: 0x61 (SCD30), 0x69 (SPS30), 0x59 (SGP40)
   ```

2. **Recalibrate:**
   ```bash
   ssh pi@192.168.1.101 "sudo /opt/mycosentinel/venv/bin/python -c 'from mycosentinel.sensor import calibrate; calibrate()'"
   ```

### Alert Fatigue

If receiving too many alerts:

1. Adjust thresholds in `config/thresholds.json`
2. Increase `duration_seconds` in alert rules
3. Acknowledge alerts to suppress repeat notifications

---

## Maintenance

### Weekly Tasks

- Check monitoring dashboard for offline nodes
- Review alert history for recurring issues
- Verify MQTT broker is healthy
- Check InfluxDB disk usage

### Monthly Tasks

- Recalibrate CO2 sensors (SCD30 requires monthly cal)
- Update firmware if available
- Check solar panel cleanliness
- Verify battery health

### Calibration Schedule

| Sensor | Frequency | Command |
|--------|-----------|---------|
| SCD30 (CO2) | 30 days | Auto-drifting |
| SPS30 (PM) | 90 days | Factory calibrated |
| SGP40 (VOC) | 7 days | Dynamic baseline |
| DHT22 | N/A | Check offset |

### Backup

```bash
# Backup configuration
rsync -av /opt/mycosentinel/config/ backup/

# Backup InfluxDB
influx backup /backup/influxdb
```

---

## Configuration Files

### deploy_config.json

Main deployment manifest with all 10 node configurations:
- Node IDs and IPs
- Sensor calibrations
- Power settings
- Location coordinates

### node_configuration.json

Auto-generated during deployment. Maps discovered nodes to their current state. Updated by `network_monitor.py`.

### thresholds.json

Alert thresholds in `/opt/mycosentinel/config/thresholds.json`:

```json
{
  "co2_ppm": {
    "min": 350,
    "max": 1000,
    "critical": 1500
  },
  "temperature_c": {
    "min": 10,
    "max": 40,
    "critical_high": 45,
    "critical_low": 5
  }
}
```

---

## Support

For issues or questions:
1. Check logs: `journalctl -u mycosentinel -f`
2. Review network monitor status
3. Check mesh topology with `deploy_network.py --visualize`
4. File issue with deployment log attached

---

## Changelog

### v0.2.0
- Added network_monitor.py with real-time dashboard
- Added OTA update system
- Added auto-discovery
- Added alert system with configurable thresholds
- Enhanced deploy_network.py with wave-based deployment

### v0.1.0
- Initial biosensor implementation
- Mesh networking protocol
- Basic deployment scripts

---

**License:** MIT  
**Author:** MycoSentinel Project  
**Last Updated:** 2026-03-28
