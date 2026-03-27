# MycoSentinel 10-Node Test Deployment Manifest

**Project:** MYCOSENTINEL-001 Biosensor Network  
**Version:** v0.2.0-test  
**Date:** 2026-03-28  
**Status:** Pre-deployment Planning Document  

---

## 1. EXECUTIVE SUMMARY

This manifest defines the comprehensive deployment strategy for a 10-node MycoSentinel biosensor test network. The deployment validates distributed sensing, network reliability, and biological sensor performance under field conditions before scaling to production deployments (100+ nodes).

**Deployment Scope:**
- 10 sensor nodes across 3 sectors (A: 3 nodes, B: 3 nodes, C: 4 nodes)
- 1 central gateway with backhaul connectivity
- 500m radius coverage area
- 30-day minimum test duration
- Target: Detect Hg²⁺ at EPA 2 ppb threshold

**Success Criteria:**
- >95% node uptime
- <5% false positive rate
- <2 hour detection latency
- Successful inter-node correlation

---

## 2. NODE PLACEMENT STRATEGY

### 2.1 Geographic Distribution

```
                         N ↑
                           │
         [MS-C3]    [MS-C4]    [MS-A3]   ~ ~ ~ Water Risk Zone
            │          │          │
     [MS-B2]─────[GATEWAY]────[MS-A2]────~ ~ ~ Monitoring Points
            │          │          │
         [MS-B1]    [MS-B3]    [MS-A1]
                           │
                     [MS-C1]    [MS-C2]
                           
    Coverage: 500m radius  │  Spacing: 75-150m between nodes
```

### 2.2 Sector Distribution

**Sector A (Upwind Reference) - 3 nodes**
- Position: Northeast quadrant
- Purpose: Establish baseline, detect incoming contamination
- MS-A1: Entry point monitoring (farthest from gateway)
- MS-A2: Mid-sector reference (moderate proximity)
- MS-A3: Edge of suspected contamination zone

**Sector B (Primary Monitoring) - 3 nodes**
- Position: Southwest quadrant (prevailing downwind)
- Purpose: High-density monitoring of contamination sources
- MS-B1: Adjacent to suspected source
- MS-B2: Cross-reference validation
- MS-B3: Discharge monitoring point (water proximity)

**Sector C (Control/Baseline) - 4 nodes**
- Position: Northwest/Southeast quadrants
- Purpose: Negative controls, spatial validation, triangulation
- MS-C1: Control reference (isolated)
- MS-C2: Secondary control
- MS-C3: Buffer zone monitor
- MS-C4: Far-field validation

### 2.3 Placement Parameters

| Parameter | Specification | Rationale |
|-----------|--------------|-----------|
| Node spacing | 75-150m | Spatial resolution for gradient mapping |
| Gateway distance | 50-200m | WiFi range + signal strength margin |
| Height above ground | 1.5-2.0m | Avoid ground moisture, accessible maintenance |
| Clearance | >5m from trees | Prevent WiFi obstruction |
| Water proximity | 10-50m for aquatic nodes | Detect runoff/contamination |
| Sun exposure | >6 hours/day | Solar panel requirements |

### 2.4 Node Coordinates (Example Site)

| Node ID | Latitude | Longitude | Sector | Purpose | Distance from Gateway |
|---------|----------|-----------|--------|---------|----------------------|
| MS-A1 | 14.5552 | 121.0248 | A | Upwind baseline | 180m |
| MS-A2 | 14.5560 | 121.0255 | A | Mid-sector | 120m |
| MS-A3 | 14.5565 | 121.0262 | A | Buffer zone | 85m |
| MS-B1 | 14.5540 | 121.0245 | B | Source proximity | 90m |
| MS-B2 | 14.5535 | 121.0250 | B | Mid-sector | 140m |
| MS-B3 | 14.5538 | 121.0260 | B | Water monitoring | 160m |
| MS-C1 | 14.5548 | 121.0235 | C | Control reference | 200m |
| MS-C2 | 14.5555 | 121.0270 | C | Validation | 175m |
| MS-C3 | 14.5570 | 121.0240 | C | Far control | 220m |
| MS-C4 | 14.5562 | 121.0232 | C | Boundary | 240m |

---

## 3. NETWORK TOPOLOGY

### 3.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           NETWORK ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────┐         │
│   │                        CLOUD DASHBOARD                         │         │
│   │                    (Grafana + Data Storage)                      │         │
│   │                         HTTPS:443                               │         │
│   └───────────────────────────────┬─────────────────────────────────┘         │
│                                   │                                          │
│                              Internet/4G                                    │
│                                   │                                          │
│   ┌───────────────────────────────▼─────────────────────────────────┐         │
│   │                      GATEWAY NODE (Hub)                          │         │
│   │              ┌───────────────────────────────────┐               │         │
│   │              │  Raspberry Pi 4/5 (4GB+)          │               │         │
│   │              │  • MQTT Broker (Mosquitto)         │               │         │
│   │              │  • InfluxDB Time-Series DB          │               │         │
│   │              │  • Node-RED Data Processing          │               │         │
│   │              │  • Grafana Dashboard (Local)        │               │         │
│   │              │  • WiFi Access Point (192.168.10.0/24)│            │         │
│   │              │  • Ethernet Backhaul                 │               │         │
│   │              └───────────────────────────────────┘               │         │
│   │                              │                                   │         │
│   └──────────────────────────────┼───────────────────────────────────┘         │
│                                  │                                           │
│                    ┌─────────────┼─────────────┐                             │
│                    │             │             │                             │
│              WiFi 2.4GHz        │        LoRa (Backup)                      │
│                    │             │             │                             │
│   ┌────────────────┴─────────────┴─────────────┴────────────────┐             │
│   │                     SENSOR NODE MESH                        │             │
│   │                                                             │             │
│   │   Sector A        Sector B        Sector C                   │             │
│   │   ┌──────┐       ┌──────┐       ┌──────┐                    │             │
│   │   │MS-A1 │◄─────►│MS-B1 │◄─────►│MS-C1 │                    │             │
│   │   │ MS01 │       │ MS04 │       │ MS07 │                    │             │
│   │   └──┬───┘       └──┬───┘       └──┬───┘                    │             │
│   │      │              │              │                       │             │
│   │   ┌──┴───┐       ┌──┴───┐       ┌──┴───┐                   │             │
│   │   │MS-A2 │◄─────►│MS-B2 │◄─────►│MS-C2 │                   │             │
│   │   │ MS02 │       │ MS05 │       │ MS08 │                   │             │
│   │   └──┬───┘       └──┬───┘       └──┬───┘                   │             │
│   │      │              │              │                       │             │
│   │   ┌──┴───┐       ┌──┴───┐       ┌──┴───┐                   │             │
│   │   │MS-A3 │◄─────►│MS-B3 │◄─────►│MS-C3 │◄───►│MS-C4 │       │             │
│   │   │ MS03 │       │ MS06 │       │ MS09 │      │ MS10 │       │             │
│   │   └──────┘       └──────┘       └──────┘      └──────┘       │             │
│   │                                                              │             │
│   │  Protocol: MQTT over TCP  Port: 1883 (TLS: 8883)            │             │
│   │  Message Rate: 1 msg/minute/node                             │             │
│   │  Topology: Star (primary) + Mesh (fallback)                 │             │
│   └──────────────────────────────────────────────────────────────┘             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Communication Protocols

**Primary: WiFi + MQTT**
- Protocol: MQTT 3.1.1 over TCP
- Port: 1883 (unencrypted local network)
- Broker: Mosquitto on gateway (192.168.10.1)
- Message format: JSON
- Keep-alive: 60 seconds
- QoS Level: 1 (at least once delivery)
- Topics:
  - `mycosentinel/{node_id}/telemetry` - Sensor readings
  - `mycosentinel/{node_id}/status` - Node health
  - `mycosentinel/{node_id}/alerts` - Anomaly detections
  - `mycosentinel/{node_id}/config` - Remote configuration

**Fallback: LoRa (optional modules)**
- Frequency: 915 MHz (US) / 868 MHz (EU)
- Range: 2-5km (depending on terrain)
- Data rate: configurable SF7-SF12
- Used when: WiFi connectivity lost >5 minutes

### 3.3 Network Security

```
Security Layers:
├── Network: WPA2-PSK (WiFi), Certificate-based (MQTT TLS)
├── Transport: MQTT username/password auth per node
├── Application: Signed firmware updates only
└── Physical: IP67 enclosures, tamper-evident seals
```

**Authentication:**
- Each node has unique MQTT credentials
- Credentials stored in `/opt/mycosentinel/credentials.json`
- TLS certificates rotated every 90 days
- Failed authentication attempts logged and alerted

---

## 4. DATA COLLECTION PROTOCOL

### 4.1 Sampling Strategy

| Data Type | Frequency | Resolution | Storage | Retention |
|-----------|-----------|------------|---------|-----------|
| Optical (GFP) | 1 Hz | 16-bit RAW | Local CSV + MQTT | 7 days local, indefinite cloud |
| Electrical (ADC) | 1 Hz | 12-bit ADC | Local CSV + MQTT | 7 days local, indefinite cloud |
| Temperature | 0.1 Hz | 0.1°C | MQTT only | indefinite cloud |
| Humidity | 0.1 Hz | 1% RH | MQTT only | indefinite cloud |
| Diagnostics | 0.0017 Hz (10 min) | JSON blob | MQTT only | 90 days cloud |

### 4.2 Data Transmission Schedule

**Normal Operation:**
```
Every Minute:
  ├── Send aggregated sensor telemetry (mean of 60 samples)
  ├── Send node status (CPU, memory, network RSSI)
  └── Log to local buffer

Every 5 Minutes:
  ├── Send full histogram distribution (for analysis)
  └── Send bioreactor state (heater duty cycle, misting events)

Every Hour:
  ├── Send calibration drift check
  ├── Upload log buffer to gateway
  └── Validate time sync (NTP)
```

**Alert Conditions (Immediate):**
- Contaminant detection (anomaly threshold exceeded)
- Hardware failure (sensor offline, heater fault)
- Network disconnection (failover to LoRa if available)
- Bioreactor out of tolerance (temp >45°C, <15°C)

### 4.3 Data Payload Format

**Telemetry Message (JSON):**
```json
{
  "node_id": "MS-A1",
  "timestamp": "2026-03-28T14:30:00Z",
  "version": "0.1.0",
  "sensors": {
    "optical": {
      "fluorescence_mean": 1247.3,
      "fluorescence_std": 12.4,
      "fluorescence_max": 1289,
      "baseline_reference": 1200.0,
      "delta_from_baseline": 47.3
    },
    "electrical": {
      "voltage_mv": 1250,
      "current_ua": 45.2,
      "conductivity": 3.2
    },
    "environmental": {
      "temperature_c": 28.5,
      "humidity_percent": 65.0,
      "heater_duty_cycle": 0.15
    }
  },
  "processing": {
    "anomaly_score": 0.85,
    "detection_flag": false,
    "contaminant_type": null,
    "confidence": 0.0
  },
  "system": {
    "uptime_seconds": 86400,
    "cpu_percent": 12.5,
    "memory_mb": 45.2,
    "rssi_dbm": -62,
    "battery_voltage": 4.05,
    "solar_input_watts": 0.8
  }
}
```

### 4.4 Offline Buffering

**Local Storage:**
- MicroSD card: 32GB per node
- Circular buffer: 7 days rolling
- Format: SQLite database per day
- Rotation: Auto-delete when <10% free space

**Sync Protocol:**
- When connectivity restored, upload stored data
- Prioritize: Alerts > Telemetry > Diagnostics
- Batch upload: 100 records per transaction
- Conflict resolution: Server timestamp wins

---

## 5. ALERT THRESHOLDS

### 5.1 Detection Thresholds

**Mercury (Hg²⁺) Detection:**

| Threshold | Value | Action | Priority |
|-----------|-------|--------|----------|
| Baseline | μ ± 2σ | Continuous monitoring | Normal |
| Baseline Drift | >3σ over 1 hour | Flag for calibration | Low |
| **Level 1 (Caution)** | 4σ < signal < 6σ | Log, trend analysis | Medium |
| **Level 2 (Warning)** | 6σ < signal < 8σ | Alert operators | High |
| **Level 3 (Alert)** | signal > 8σ | Immediate notification | Critical |
| **EPA Limit** | Signal = 6.5σ (calibrated to 2 ppb) | Regulatory threshold | Critical |

**Sensor Health Thresholds:**

| Parameter | Normal Range | Warning | Critical |
|-----------|-------------|---------|----------|
| Bioreactor Temp | 25-35°C | 20-25°C, 35-40°C | <20°C, >40°C |
| Humidity | 40-80% | 30-40%, 80-90% | <30%, >90% |
| Optical Baseline | 1100-1300 | 900-1100, 1300-1500 | <900, >1500 |
| Battery | >3.7V | 3.5-3.7V | <3.5V |
| WiFi RSSI | >-70 dBm | -70 to -80 dBm | <-80 dBm |

### 5.2 Alert Routing

```
Alert Escalation Matrix:
├─ Level 1 (Informational)
│  └─ Log to dashboard only
│     
├─ Level 2 (Medium)
│  ├─ Dashboard alert
│  ├─ MQTT alert topic
│  └─ Daily digest email
│     
├─ Level 3 (High)
│  ├─ Immediate dashboard notification
│  ├─ MQTT alert topic
│  ├─ Email to operators
│  └─ SMS to on-call (if configured)
│     
└─ Critical
   ├─ All Level 3 actions
   ├─ Automatic node status broadcast
   └─ Emergency protocol activation
```

### 5.3 Correlation Rules

**Multi-Node Validation:**
- Single node alert > warning → Monitor
- Adjacent nodes both alert > warning → Escalate to Alert
- 3+ nodes in same sector alert → Sector Alert
- All sectors showing similar patterns → Event Alert

**Temporal Rules:**
- Sustained elevation >5 minutes → Reduce false positives
- Rapid rise (>2σ/min for 3 min) → Accelerated response
- Correlated with rainfall (if weather station) → Runoff event

---

## 6. FUNGAL SPECIES DETECTION TARGETS

### 6.1 Primary Targets (Genetically Engineered)

**Saccharomyces cerevisiae BY4741 - Mercury (Hg²⁺)**

| Parameter | Specification |
|-----------|--------------|
| Detection Mechanism | MerR promoter → sfGFP expression |
| Detection Limit | 0.5 ppb (0.25× EPA limit) |
| Dynamic Range | 0.5 - 500 ppb |
| Response Time | <2 hours (to 90% signal) |
| Specificity | >1000× vs other metals |
| False Positive Rate | <2% (trained classifier) |
| Bioreactor lifespan | 30 days (continuous) |
| Refill interval | Every 14 days (culture maintenance) |

**Expected Signal Response:**
```
Hg²⁺ Concentration (ppb) │ Fluorescence Response
─────────────────────────┼──────────────────────
0 (control)              │ Baseline (1000-1200)
0.5                      │ 1.5× baseline
2 (EPA limit)            │ 3× baseline ← TARGET
10                       │ 7× baseline
50                       │ 12× baseline
100                      │ Saturation
```

### 6.2 Secondary Targets (Planned Expansion)

| Target | Organism | Promoter System | Detection Limit | Status |
|--------|----------|-------------------|-----------------|--------|
| Cadmium (Cd²⁺) | S. cerevisiae BY4741 | CadC/Pcad | 5 ppb | Circuit ready |
| Arsenic (As³⁺) | S. cerevisiae BY4741 | ArsR/Pars | 10 ppb | Design phase |
| Lead (Pb²⁺) | S. cerevisiae BY4741 | PbrR/Ppbr | 15 ppb | Research |
| Organophosphates | S. cerevisiae BY4741 | OpdH-based | 0.1 ppm | Development |
| PFAS | S. cerevisiae BY4741 | Custom | Unknown | Research |

### 6.3 Detection Verification

**Cross-Validation Protocol:**
1. **Optical Detection:** Pi Camera measures GFP fluorescence
2. **Electrical Detection:** Impedance spectroscopy confirmation
3. **Correlation Match:** Signals from both sensors must align (r > 0.85)
4. **Temporal Consistency:** Signal must persist >5 minutes
5. **Spatial Correlation:** Adjacent nodes must show similar trends

**Quality Control:**
- Daily: Check baseline stability
- Weekly: Run positive control (calibration standard)
- Bi-weekly: Culture replacement, sensor cleaning

---

## 7. NODE HARDWARE REQUIREMENTS

### 7.1 Bill of Materials Per Node

| Category | Component | Model/Spec | Qty | Unit Cost | Total |
|----------|-----------|------------|-----|-----------|-------|
| **Compute** | Raspberry Pi Zero 2 W | RPi Zero 2 W + Headers | 1 | $15.00 | $15.00 |
| **Camera** | Pi Camera Module v2 | 8MP, ribbon cable | 1 | $15.00 | $15.00 |
| **Storage** | MicroSD Card | 32GB Class 10 | 1 | $8.00 | $8.00 |
| **Power** | Solar Panel | 20W, 12V | 1 | $25.00 | $25.00 |
| **Power** | Charge Controller | PWM, 10A, USB 5V out | 1 | $12.00 | $12.00 |
| **Power** | LiPo Battery | 3S 3000mAh | 1 | $25.00 | $25.00 |
| **Sensors** | ADS1115 ADC | 4-channel, 16-bit, I2C | 1 | $8.00 | $8.00 |
| **Sensors** | DHT22/AM2301 | Temp/Humidity sensor | 1 | $5.00 | $5.00 |
| **Sensors** | DS18B20 | Waterproof temp probe | 1 | $3.00 | $3.00 |
| **Bioreactor** | 3D Printed Chamber | PETG, bio-compatible | 1 | $8.00 | $8.00 |
| **Bioreactor** | Heater Pad | 5V, 10W silicone | 1 | $5.00 | $5.00 |
| **Bioreactor** | Misting Nozzle | Piezo mist generator | 1 | $4.00 | $4.00 |
| **Bioreactor** | LED Array | 470nm excitation + white | 1 | $3.00 | $3.00 |
| **Networking** | USB WiFi Dongle | 2.4GHz, external antenna | 1 | $8.00 | $8.00 |
| **Enclosure** | IP67 Project Box | 200×150×100mm, clear lid | 1 | $15.00 | $15.00 |
| **Mounting** | Ground Stake | 1.5m galvanized steel | 1 | $5.00 | $5.00 |
| **Electronics** | PCB/Proto Board | Custom HAT or perfboard | 1 | $5.00 | $5.00 |
| **Electronics** | Misc Components | Resistors, caps, connectors | 1 | $10.00 | $10.00 |
| **Biological** | Yeast Culture | S. cerevisiae modified | - | $10.00 | $10.00 |
| | | | | **Total per Node** | **$184.00** |

**10-Node Total: $1,840**  
(+ Gateway: $200, + Contingency 10%: $204)  
**Grand Total: ~$2,244**

### 7.2 Gateway Hardware Requirements

| Component | Model | Qty | Cost |
|-----------|-------|-----|------|
| Raspberry Pi 4/5 | 4GB RAM | 1 | $55 |
| SSD Storage | 256GB NVMe via USB | 1 | $40 |
| 4G/LTE Modem | USB cellular modem | 1 | $35 |
| UPS Battery | PiJuice or similar | 1 | $45 |
| Enclosure | Metal case with fan | 1 | $25 |
| | | **Total** | **$200** |

### 7.3 Node Hardware Checklist

See `NODE_HARDWARE_CHECKLIST.md` for detailed per-station checklist.

---

## 8. GO/NO-GO CRITERIA

### 8.1 Pre-Deployment Checklist

**Site Preparation:**
- [ ] Site survey completed (WiFi coverage verified)
- [ ] Landowner permissions secured
- [ ] Installation locations marked and GPS-logged
- [ ] Site photographed (before deployment)
- [ ] Weather forecast reviewed (48h window)
- [ ] Emergency contact list distributed

**Equipment Verification:**
- [ ] All 10 nodes assembled and tested (bench test)
- [ ] Gateway configured and online
- [ ] Solar charging verified (sunlight test)
- [ ] Bioreactors inoculated and growing
- [ ] Spare parts kit prepared (2 nodes worth)
- [ ] Tool kit complete
- [ ] Vehicles fueled and ready

**Personnel:**
- [ ] Team briefed on deployment plan
- [ ] Roles assigned (installer, QA, safety)
- [ ] Communication plan established
- [ ] Return time established

### 8.2 Deployment Day Go/No-Go

**🟢 GO Conditions:**
- All 10 nodes pass bench test (24h run)
- Gateway online and accessible remotely
- At least 6 hours of daylight remaining
- Weather: <70% precipitation chance
- Team rested, safety equipment on-site

**🟡 DELAY Conditions:**
- 1-2 nodes failing bench test (use spares)
- Gateway connectivity issues
- Incoming severe weather
- Insufficient team availability

**🔴 NO-GO Conditions:**
- <8 nodes operational
- Gateway cannot establish internet backhaul
- Severe weather warning (thunderstorms, >40kph wind)
- Missing critical safety equipment
- Site access denied

### 8.3 Post-Deployment Success Criteria

**48-Hour Check:**
- [ ] 10/10 nodes reporting to dashboard
- [ ] <5% packet loss per node
- [ ] All sensors within calibration range
- [ ] Bioreactor temperatures stable (25-35°C)
- [ ] No critical alerts

**7-Day Check:**
- [ ] >95% uptime for all nodes
- [ ] Baseline established for each sensor
- [ ] First cross-node correlation data available
- [ ] No hardware failures
- [ ] Data logging continuously

**30-Day Evaluation:**
- [ ] >95% average uptime
- [ ] Detection algorithm validated (field test)
- [ ] Spatial mapping shows expected patterns
- [ ] Network reliability meets specs
- [ ] Ready for full deployment recommendation

**Full Deployment Go Criteria:**
- 10-node test achieves >95% success on all metrics
- Detection sensitivity verified (lab correlation)
- False positive rate <5%
- Team trained on maintenance procedures
- Budget and funding secured for scale-up
- Deployment team identified

---

## 9. OPERATIONAL PROCEDURES

### 9.1 Daily Operations

**Automated (No Human Action):**
- Sensor data collection and transmission
- Health monitoring and logging
- Alert generation and routing
- Bioreactor temperature control

**Manual (Daily):**
- Dashboard review (5 minutes)
- Check for alerts/critical notifications
- Verify all nodes online

### 9.2 Weekly Operations

- Node inspection visit (if required)
- Solar panel cleaning (if dusty)
- Data download verification
- System log review

### 9.3 Bi-Weekly Operations (14 Days)

- Bioreactor culture replacement
- Sensor cleaning/calibration check
- Physical inspection of enclosures
- Battery voltage logging

---

## 10. RISK MITIGATION

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| WiFi connectivity loss | Medium | High | LoRa backup, local buffering |
| Bioreactor contamination | Low | High | Sealed design, weekly inspection |
| Power failure | Low | Medium | Adequate battery sizing, solar |
| Hardware failure | Medium | Low | Spares on-site, modular design |
| False positives | Medium | Medium | Multi-node correlation required |
| Theft/vandalism | Low | Medium | Secure mounting, rural locations |
| Extreme weather | Low | High | Weatherproof IP67, monitoring |
| Data breach | Low | High | TLS encryption, local network |

---

## 11. APPENDICES

### Appendix A: Network Topology Diagram
See `diagrams/network_topology_10node.png` (generated from PlantUML)

### Appendix B: Node Hardware Checklist
See `NODE_HARDWARE_CHECKLIST.md`

### Appendix C: Data Collection Protocol
See `protocols/DATA_COLLECTION_PROTOCOL.md`

### Appendix D: Go/No-Go Decision Matrix
See `GO_NOGO_CRITERIA.md` (condensed checklist)

---

**Document Control:**
- Author: MycoSentinel Deployment Team
- Reviewer: TBD
- Approval: TBD
- Version: 0.1.0
- Date: 2026-03-28
- Next Review: Upon deployment completion

**Related Documents:**
- BUILD_MANIFEST.md
- HARDWARE_DESIGN.md
- SYNTHETIC_BIOLOGY_DESIGN.md
- SYSTEM_INTEGRATION.md
- DEPLOYMENT_GUIDE.md
