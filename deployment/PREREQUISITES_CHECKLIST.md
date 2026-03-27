# MycoSentinel Deployment - Prerequisites Checklist

**Project:** MycoSentinel Environmental Sensor Network  
**Version:** v0.2.0  
**Last Updated:** 2026-03-28  

---

> **⚠️ IMPORTANT:** Complete ALL items in this checklist before initiating live deployment. This checklist ensures a smooth, error-free deployment process.

---

## Section 1: Hardware Prerequisites

### 1.1 Gateway Hardware (1 unit)

| Item | Required | Verified | Notes |
|------|----------|----------|-------|
| Raspberry Pi 4B (4GB+ RAM) | ✅ | ☐ | 8GB recommended |
| 32GB MicroSD Card (Class 10) | ✅ | ☐ | SanDisk/Kingston recommended |
| 5V/3A USB-C Power Supply | ✅ | ☐ | Official RPi supply preferred |
| Ethernet Cable | ✅ | ☐ | For initial setup |
| WiFi Antenna (optional) | ☐ | ☐ | For improved mesh range |

### 1.2 Node Hardware (10 units each)

| Item | Quantity | Verified | Notes |
|------|----------|----------|-------|
| Raspberry Pi Zero 2 W | 10 | ☐ | With headers if possible |
| 32GB MicroSD Card | 10 | ☐ | Class 10, bootable |
| 2.5A Micro-USB Power Supply | 10 | ☐ | Per-Node power |
| **SENSORS (per node):** | | | |
| Sensirion SCD30 (CO2) | 10 | ☐ | I2C address 0x61 |
| Sensirion SPS30 (PM) | 10 | ☐ | I2C address 0x69 |
| Sensirion SGP40 (VOC) | 10 | ☐ | I2C address 0x59 |
| DHT22 (Temp/Humidity) | 10 | ☐ | GPIO4 |
| **POWER (per node):** | | | |
| 20W Solar Panel | 10 | ☐ | 30W for MS-C4 |
| 10Ah LiFePO4 Battery | 9 | ☐ | 15Ah for MS-C4 |
| Charge Controller | 10 | ☐ | MPPT type preferred |
| 5V Buck Converter | 10 | ☐ | 3A minimum |
| **WIRING:** | | | |
| Jumper Wires (F-F, M-F, M-M) | Bundle | ☐ | 65+ piece kit per node |
| Solderless Breadboard | 10 | ☐ | Half-size |
| Weatherproof Enclosure | 10 | ☐ | IP65 rated minimum |
| Cable Glands | 20 | ☐ | For sensor entry |

### 1.3 Tools & Equipment

| Item | Required | Verified | Notes |
|------|----------|----------|-------|
| Multimeter | ✅ | ☐ | Voltage/current testing |
| Soldering Iron | ☐ | ☐ | If hardwiring sensors |
| Crimping Tool | ☐ | ☐ | For weatherproof connectors |
| Laptop/Workstation | ✅ | ☐ | Deployment machine |
| SD Card Reader | ✅ | ☐ | USB 3.0 preferred |
| Network Switch | ☐ | ☐ | Initial testing |
| Portable Power Bank | ☐ | ☐ | Field testing nodes |

---

## Section 2: Software Prerequisites

### 2.1 Workstation Software

| Software | Version | Install Command | Verified |
|----------|---------|-----------------|----------|
| Python | 3.9+ | `brew install python3` | ☐ |
| pip | Latest | Included with Python | ☐ |
| git | Latest | `brew install git` | ☐ |
| ssh | OpenSSH 8+ | Built-in | ☐ |
| scp | OpenSSH 8+ | Built-in | ☐ |
| Raspberry Pi Imager | Latest | Download | ☐ |
| nmap | Latest | `brew install nmap` | ☐ |
| **Python Dependencies:** | | | |
| pyyaml | 5.4+ | `pip3 install pyyaml` | ☐ |
| paramiko | 2.11+ | `pip3 install paramiko` | ☐ |

### 2.2 Gateway Software Stack

| Software | Purpose | Port | Verified |
|----------|---------|------|----------|
| Raspberry Pi OS (64-bit Lite) | Base OS | - | ☐ |
| Docker CE | Containerization | - | ☐ |
| Docker Compose | Orchestration | - | ☐ |
| Mosquitto | MQTT Broker | 1883 | ☐ |
| InfluxDB | Time-series DB | 8086 | ☐ |
| Grafana | Visualization | 3000 | ☐ |
| Node-RED | Automation | 1880 | ☐ |
| Telegraf | Data Agent | - | ☐ |
| Batman-adv | Mesh Protocol | - | ☐ |

### 2.3 Node Software Stack

| Software | Purpose | Verified |
|----------|---------|----------|
| Raspberry Pi OS Lite | Base OS | ☐ |
| Python 3.9+ | Runtime | ☐ |
| smbus2 | I2C Communication | ☐ |
| scd30-i2c | CO2 Sensor | ☐ |
| sps30 | PM Sensor | ☐ |
| sgp40 | VOC Sensor | ☐ |
| adafruit-circuitpython-dht | DHT22 | ☐ |
| paho-mqtt | MQTT Client | ☐ |
| batctl | Mesh Tools | ☐ |

---

## Section 3: Network Prerequisites

### 3.1 Physical Network

| Requirement | Specification | Verified | Notes |
|-------------|---------------|----------|-------|
| Gateway IP | 192.168.1.100 | ☐ | Static reservation |
| Node IP Range | 192.168.1.101-110 | ☐ | DHCP static leases |
| Gateway Router | 192.168.1.1 | ☐ | Internet access |
| DNS Servers | 8.8.8.8, 1.1.1.1 | ☐ | Primary + backup |
| WiFi Channel | 1, 6, or 11 | ☐ | Minimize interference |

### 3.2 Mesh Network

| Requirement | Specification | Verified | Notes |
|-------------|---------------|----------|-------|
| Mesh SSID | mycosentinel-mesh | ☐ | Hidden OK |
| Mesh Password | Strong passphrase | ☐ | WPA2-PSK |
| Mesh Subnet | 10.0.0.0/24 | ☐ | Overlay network |
| Gateway Bridge | Enabled | ☐ | bat0 interface |

### 3.3 Firewall Rules

| Port | Service | Direction | Action | Verified |
|------|---------|-----------|--------|----------|
| 22 | SSH | Inbound | Allow | ☐ |
| 1883 | MQTT | Inbound | Allow | ☐ |
| 1883 | MQTT | Outbound | Allow | ☐ |
| 8086 | InfluxDB | Inbound | Allow | ☐ |
| 3000 | Grafana | Inbound | Allow | ☐ |
| 9001 | MQTT WS | Inbound | Allow | ☐ |

---

## Section 4: Configuration Prerequisites

### 4.1 Deployment Configuration

| File | Path | Status | Notes |
|------|------|--------|-------|
| Main Config | `deployment/deploy_config.json` | ✅ | Validated |
| Node Config | Auto-generated | ☐ | Created at deploy |
| SSH Keys | `~/.ssh/mycosentinel_deploy` | ☐ | Generate before deploy |

### 4.2 Gateway Configuration

| Setting | Value | Verified | Notes |
|---------|-------|----------|-------|
| Hostname | mycosentinel-gw | ☐ | Set in raspi-config |
| Timezone | Asia/Manila | ☐ | Match local time |
| WiFi Country | PH | ☐ | For regulation compliance |
| Static IP | 192.168.1.100/24 | ☐ | In /etc/dhcpcd.conf |

### 4.3 Node Configuration

| Setting | Value Pattern | Verified | Notes |
|---------|---------------|----------|-------|
| Hostname | mycosentinel-{id} | ☐ | e.g., mycosentinel-a1 |
| SSH User | pi | ☐ | Default |
| Initial Password | raspberry | ☐ | Change after deploy |
| Static IP | 192.168.1.{101-110} | ☐ | Per-node unique |

---

## Section 5: Sensor Prerequisites

### 5.1 Sensor Testing

| Sensor | Address | Test Command | Verified |
|--------|---------|--------------|----------|
| SCD30 | 0x61 | `i2cdetect -y 1` | ☐ |
| SPS30 | 0x69 | `i2cdetect -y 1` | ☐ |
| SGP40 | 0x59 | `i2cdetect -y 1` | ☐ |
| DHT22 | GPIO4 | Check /sys/bus/gpio | ☐ |

### 5.2 Calibration Requirements

| Sensor | Calibration | Reference Equipment | Verified |
|--------|-------------|-------------------|----------|
| SCD30 | Initial + 30 days | Sensirion Dev Kit | ☐ |
| SPS30 | Factory calibrated | PM Monitor (BAM1020) | ☐ |
| SGP40 | 7-day baseline | VOC Reference | ☐ |
| DHT22 | Offset check | Calibrated hygrometer | ☐ |

---

## Section 6: Power Prerequisites

### 6.1 Solar Sizing

| Component | Specification | Calculated | Verified |
|-------------|---------------|------------|----------|
| Node Power Draw | ~2.5W avg | - | ☐ |
| Daily Consumption | 60Wh | 2.5W × 24h | ☐ |
| Solar Panel | 20W | >3× consumption | ☐ |
| Battery | 10Ah @ 12V | 120Wh capacity | ☐ |
| Backup Duration | 48h | No sun days | ☐ |

### 6.2 Power Verification

| Test | Method | Passed | Notes |
|------|--------|--------|-------|
| Voltage at Pi | 5.0V ± 0.25V | ☐ | Use multimeter |
| Under Load | 4.8V minimum | ☐ | All sensors active |
| Battery Protection | BMS active | ☐ | Over/under voltage |
| Solar Charging | 13.5V @ battery | ☐ | Full sun |

---

## Section 7: Testing Prerequisites

### 7.1 Pre-Deployment Tests

| Test | Command | Expected Result | Passed |
|------|---------|-----------------|--------|
| Gateway Connectivity | `ping 192.168.1.100` | <10ms reply | ☐ |
| MQTT Broker Reachable | `telnet 192.168.1.100 1883` | Connection | ☐ |
| SSH Key Authentication | `ssh -i key pi@192.168.1.100` | Login without password | ☐ |
| Config File Valid | `python3 -c "import json; json.load(open('deploy_config.json'))"` | No errors | ☐ |
| Deploy Script Works | `python3 deploy_10node.py --status` | Status displayed | ☐ |

### 7.2 Post-Flash Tests (per SD card)

| Test | Method | Passed | Notes |
|------|--------|--------|-------|
| SD Card Boots | Visual LED check | ☐ | LED blinks |
| Network Discovery | `nmap -sn 192.168.1.0/24` | Appears in scan | ☐ |
| SSH Accessible | `ssh pi@<ip>` | Login prompt | ☐ |
| I2C Enabled | `ls /dev/i2c*` | Shows i2c-1 | ☐ |

---

## Section 8: Documentation Prerequisites

### 8.1 Required Documents

| Document | Location | Reviewed | Notes |
|----------|----------|----------|-------|
| DEPLOYMENT.md | Project root | ☐ | Full guide |
| GATEWAY_SETUP.md | deployment/ | ☐ | Gateway config |
| TEST_DEPLOYMENT_EXECUTION.md | deployment/ | ☐ | Test results |
| Sensor Datasheets | Hardware folder | ☐ | SCD30, SPS30, SGP40 |
| Wiring Diagrams | Hardware folder | ☐ | Per-sensor wiring |
| Calibration Procedures | Config folder | ☐ | Step-by-step |

### 8.2 Emergency Contacts

| Role | Contact | Phone | Verified |
|------|---------|-------|----------|
| Project Lead | _________ | _________ | ☐ |
| Network Admin | _________ | _________ | ☐ |
| Hardware Support | _________ | _________ | ☐ |

---

## Section 9: Deployment Day Checklist

### Morning Before (T-2 hours)

- [ ] Weather check (no rain/lightning)
- [ ] Backup battery levels verified
- [ ] All tools arranged and accessible
- [ ] Deployment machine charged
- [ ] Network access verified
- [ ] Emergency contacts available

### Hour Before (T-1 hour)

- [ ] Gateway booted and updated
- [ ] SSH keys tested
- [ ] Deploy scripts downloaded
- [ ] Monitoring dashboard open
- [ ] Log files initialized
- [ ] Coffee/tea prepared ☕

### During Deployment

- [ ] ☐ Phase 1: Gateway setup complete
- [ ] ☐ Phase 2: Node deployment started
- [ ] ☐ Phase 3: Mesh configuration
- [ ] ☐ Phase 4: Data pipeline verification

### Post-Deployment

- [ ] ☐ All 10 nodes online
- [ ] ☐ Sensor data flowing
- [ ] ☐ Alerts configured
- [ ] ☐ Documentation complete
- [ ] ☐ Backup created

---

## Quick Reference: Command Summary

```bash
# Install dependencies
pip3 install pyyaml paramiko

# Generate SSH key
ssh-keygen -t ed25519 -f ~/.ssh/mycosentinel_deploy

# Copy key to gateway
ssh-copy-id -i ~/.ssh/mycosentinel_deploy pi@192.168.1.100

# Check deployment status
cd deployment && python3 deploy_10node.py --status

# Deploy single node (dry run)
python3 deploy_node.py --node-id MS-A1 --target 192.168.1.101 --dry-run

# Deploy full network
python3 deploy_10node.py --provision-gateway
python3 deploy_10node.py --deploy-nodes

# Monitor network
python3 network_monitor.py
```

---

## Sign-Off

**I confirm that all prerequisites have been verified and the deployment is ready to proceed:**

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Technical Lead | ____________ | ____________ | ________ |
| Network Admin | ____________ | ____________ | ________ |
| Project Manager | ____________ | ____________ | ________ |

---

**Next Step:** Upon completion of this checklist, proceed to `DEPLOYMENT.md` Section 4 (Quick Start) and Section 5 (Deployment Scripts).

---

*Document generated: 2026-03-28*  
*Version: 1.0*  
*Status: Ready for Production Deployment*
