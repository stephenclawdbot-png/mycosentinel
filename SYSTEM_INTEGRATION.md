# MycoSentinel System Integration Architecture
## Field-Deployable Biosensor Network for Environmental Monitoring

**Version:** 1.0.0  
**Date:** March 2026  
**Classification:** Field Deployment Ready

---

## Executive Summary

MycoSentinel is a distributed fungal biosensor network designed for large-scale environmental monitoring. This document provides the complete end-to-end architecture, deployment playbook, and operational framework required to deploy **1,000+ sensor nodes** across cities, farms, or watersheds.

**Key Innovation:** Genetically engineered *Saccharomyces cerevisiae* (yeast) or *Aspergillus nidulans* (filamentous fungus) strains that emit measurable signals (fluorescence, bioluminescence, electrochemical) in response to target analytes including heavy metals, endocrine disruptors, pathogens, and agricultural chemicals.

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Sensor Node Design](#2-sensor-node-design)
3. [Gateway & Edge Infrastructure](#3-gateway--edge-infrastructure)
4. [Cloud Platform & Analytics](#4-cloud-platform--analytics)
5. [Deployment Strategy](#5-deployment-strategy)
6. [Calibration & Ground-Truthing](#6-calibration--ground-truthing)
7. [Safety & Containment Protocols](#7-safety--containment-protocols)
8. [Regulatory Framework](#8-regulatory-framework)
9. [Business & Operational Models](#9-business--operational-models)
10. [Success Metrics & Benchmarking](#10-success-metrics--benchmarking)
11. [Risk Management](#11-risk-management)
12. [Appendices](#12-appendices)

---

## 1. System Architecture Overview

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    FIELD DEPLOYMENT                                      │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐      │
│  │  SENSOR      │     │  SENSOR      │     │  SENSOR      │     │  SENSOR      │      │
│  │  NODE 001    │     │  NODE 002    │     │  NODE 003    │     │  NODE...     │      │
│  │  (Biological │     │  (Biological │     │  (Biological │     │  (Biological │      │
│  │   Core)      │     │   Core)      │     │   Core)      │     │   Core)      │      │
│  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘     └──────┬───────┘      │
│         │                      │                      │                      │         │
│         └──────────────────────┼──────────────────────┼──────────────────────┘         │
│                                  │                      │                               │
│                                  ▼                      ▼                               │
│                           ┌──────────────┐       ┌──────────────┐                      │
│                           │   GATEWAY    │◄──────►│   GATEWAY    │                      │
│                           │   NODE A     │ LoRa  │   NODE B     │                      │
│                           │  (Edge Hub)  │  Mesh │  (Edge Hub)  │                      │
│                           └──────┬───────┘       └──────┬───────┘                      │
│                                  │                      │                               │
└──────────────────────────────────┼──────────────────────┼───────────────────────────────┘
                                   │                      │
                                   │   LTE/5G/WiFi/       │
                                   │   Satellite          │
                                   │                      │
                                   ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    CLOUD PLATFORM                                        │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐        │
│   │   INGESTION  │───►│   STREAM     │───►│  ANALYTICS   │───►│  DASHBOARD   │        │
│   │   LAYER      │    │   PROCESSING │    │   ENGINE     │    │   & VIZ      │        │
│   │   (Kafka/    │    │   (Flink/    │    │   (ML/       │    │   (Grafana/  │        │
│   │    MQTT)     │    │    Spark)    │    │   Stats)     │    │    Custom)   │        │
│   └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘        │
│                                                                                         │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                               │
│   │   ALERT      │    │   DATA       │    │   MODEL      │                               │
│   │   SYSTEM     │    │   WAREHOUSE  │    │   TRAINING   │                               │
│   │              │    │   (Time-     │    │   PIPELINE   │                               │
│   │              │    │   Series DB) │    │              │                               │
│   └──────────────┘    └──────────────┘    └──────────────┘                               │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Component Summary

| Layer | Component | Technology | Purpose |
|-------|-----------|------------|---------|
| **Edge** | Sensor Node | Custom PCB + Bio-Chamber | Analyte detection & signal transduction |
| **Edge** | Gateway | Raspberry Pi 5 / NUC + LoRa | Local aggregation & uplink |
| **Transport** | Connectivity | LoRaWAN-Mesh, LTE-M, NB-IoT, Starlink | Field-to-cloud communication |
| **Cloud** | Data Ingestion | Apache Kafka, MQTT brokers | High-throughput data streaming |
| **Cloud** | Processing | Apache Flink, AWS Kinesis | Real-time stream analytics |
| **Cloud** | Storage | InfluxDB/TimescaleDB + S3 | Time-series + blob storage |
| **Cloud** | Analytics | Python/Spark ML, TensorFlow | Anomaly detection, predictive models |
| **Cloud** | Dashboard | Grafana + Custom React App | Visualization & control |

### 1.3 Scalability Targets

| Metric | Target | Architecture Support |
|--------|--------|---------------------|
| Max Nodes per Deployment | 10,000+ | Hierarchical gateway clustering |
| Data Points/Day | 100M+ | Kafka partitioning, horizontal scaling |
| Latency (Alert) | < 30 seconds | Edge pre-processing + priority queuing |
| Latency (Dashboard) | < 5 seconds | Time-series DB optimization |
| Uptime SLA | 99.5% | Multi-region cloud, redundant gateways |

---

## 2. Sensor Node Design

### 2.1 Biological Core Specifications

#### Engineered Organism Options

| Organism | Advantages | Challenges | Best For |
|----------|-----------|------------|----------|
| **S. cerevisiae** (Yeast) | Fast growth, well-characterized, GRAS status | Limited metabolic diversity | Heavy metals, pH, simple organics |
| **A. nidulans** (Filamentous) | Secretion capability, robust hyphae | Slower growth, complex genetics | Complex organics, antibiotics, fungal pathogens |
| **E. coli** (Modified) | Fastest response, extensive toolkit | Biosafety concerns (BL1/BL2) | Research/controlled environments |

#### Detection Mechanisms

```
┌─────────────────────────────────────────────────────────────────┐
│                    BIOSENSOR SIGNAL PATHWAY                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Analyte ──► ┌──────────────┐                                │
│   (e.g.,     │  PROMOTER    │ ──► Transcription Activation   │
│    Cd²⁺)     │  (zinc/cad   │                                │
│              │   responsive)│                                │
│              └──────┬───────┘                                │
│                     │                                         │
│                     ▼                                         │
│              ┌──────────────┐                                │
│              │  REPORTER    │ ──► Signal Output              │
│              │  GENE        │                                │
│              │              │                                │
│              │ Options:     │                                │
│              │ • GFP/YFP    │ → Fluorometer (495/509 nm)   │
│              │ • Luciferase │ → Luminometer                  │
│              │ • Uricase    │ → Electrochemical              │
│              │   pathway    │   (uric acid detection)        │
│              └──────┬───────┘                                │
│                     │                                         │
│                     ▼                                         │
│              ┌──────────────┐                                │
│              │  SIGNAL      │ ──► Raspberry Pi Pico ADC      │
│              │  OUTPUT      │                                │
│              └──────────────┘                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Hardware Specifications

#### Sensor Node BOM (Bill of Materials)

| Component | Part Number | Unit Cost | Function |
|-----------|-------------|-----------|----------|
| Microcontroller | Raspberry Pi Pico W | $6.00 | Processing + WiFi |
| Optical Detector | Adafruit TSL2561 | $8.00 | Light-to-digital (fluorescence) |
| Temperature Sensor | DS18B20 | $3.00 | Thermal calibration |
| pH Probe | Atlas Scientific EZO-pH | $45.00 | Reference measurement |
| Battery | 18650 Li-Ion 3000mAh | $8.00 | 7-day autonomous operation |
| Solar Panel | 5V 2W | $6.00 | Trickle charging |
| LoRa Module | RFM95W (433/915MHz) | $12.00 | Long-range communication |
| Enclosure | IP67 Polycarbonate | $15.00 | Environmental protection |
| Bio-Chamber | Custom PDMS/glass | $25.00 | Organism containment |
| **Total Hardware** | | **~$128** | **Per node at 1K scale** |

#### Bio-Chamber Design (CRITICAL for Containment)

```
┌──────────────────────────────────────────────────────────────────┐
│                    BIO-CHAMBER CROSS-SECTION                     │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │  OUTER SHELL (IP67 Polycarbonate)                        │  │
│   │  ┌────────────────────────────────────────────────────┐  │  │
│   │  │  PHYSICAL BARRIER (0.22 μm PES membrane)          │  │  │
│   │  │  ┌──────────────────────────────────────────────┐  │  │  │
│   │  │  │  PRIMARY CHAMBER (Media + Organism)        │  │  │  │
│   │  │  │  ┌────────────────────────────────────┐      │  │  │  │
│   │  │  │  │  OPTICAL WINDOW (Glass viewing    │      │  │  │  │
│   │  │  │  │  port for fluorescence detection)  │      │  │  │  │
│   │  │  │  └────────────────────────────────────┘      │  │  │  │
│   │  │  │                                              │  │  │  │
│   │  │  │  MEDIA INLET (with check valve) ─────────►   │  │  │  │
│   │  │  │  SAMPLE INLET (0.45 μm filter) ──────────►    │  │  │  │
│   │  │  │  WASTE OUTLET (sterile, heat-sealed) ◄────── │  │  │  │
│   │  │  └──────────────────────────────────────────────┘  │  │  │
│   │  └────────────────────────────────────────────────────┘  │  │
│   └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│   KEY FEATURES:                                                   │
│   • Dual physical barriers (shell + 0.22 μm membrane)          │
│   • Optical window for non-contact measurement                   │
│   • Sterilizable inlets/outlets                                │
│   • UV-C LED for chamber sterilization cycle                   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 2.3 Sensor Operating Parameters

| Parameter | Specification | Notes |
|-----------|--------------|-------|
| Detection Range | 0.1 μg/L - 10 mg/L | Analyte-dependent |
| Response Time | 15-60 minutes | Faster for toxic response, slower for metabolic |
| Operational Lifespan | 30-60 days | Bio-chamber replacement cycle |
| Operating Temperature | 5°C - 40°C | Insulated housing extends range |
| Data Transmission | Every 15 min (standard) / Real-time (alert) | LoRaWAN Class B/C |
| Power Consumption | 0.1W (idle) / 0.5W (measurement) | Solar-sustainable |

---

## 3. Gateway & Edge Infrastructure

### 3.1 Gateway Node Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     GATEWAY NODE (1 per 50 sensors)                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                   COMPUTE UNIT                                │ │
│  │  Raspberry Pi 5 (8GB) or Intel NUC i3                        │ │
│  │  • Local SQLite buffer for offline storage                      │ │
│  │  • Edge ML for anomaly detection                              │ │
│  │  • Firmware OTA updates for sensor nodes                     │ │
│  └───────────────────────────────────────────────────────────────┘ │
│         ▲                  ▲                  ▲                    │
│         │                  │                  │                    │
│  ┌──────┴──────┐    ┌──────┴──────┐    ┌──────┴──────┐            │
│  │ LoRaWAN    │    │ LTE/5G     │    │ WiFi/Eth   │            │
│  │ Concentrator│    │ Modem      │    │ Backup     │            │
│  │ (SX1302)   │    │ (Quectel)  │    │ (OpenWRT)  │            │
│  └─────────────┘    └─────────────┘    └─────────────┘            │
│         ▲                  │                  │                    │
│  ═══════╪══════════════════╪══════════════════╪══════════════      │
│         │                  │                  │                    │
│  ┌──────┴──────────────────┴──────────────────┴──────┐            │
│  │                  CLOUD UPLINK                     │            │
│  │  MQTT/TLS 1.3 over cellular/satellite/wired       │            │
│  └───────────────────────────────────────────────────┘            │
│                                                                     │
│  Power: Solar + 20Ah LiFePO4 battery (3-day autonomy)              │
│  Enclosure: IP66 rated, vented with desiccant                      │
│  Security: TPM 2.0 for secure boot, encrypted storage              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Network Topology

```
                    ┌─────────────────┐
                    │   CLOUD         │
                    │   PLATFORM      │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
        ┌─────────┐   ┌─────────┐   ┌─────────┐
        │ GATEWAY │◄──│ GATEWAY │◄──│ GATEWAY │
        │   A     │   │   B     │   │   C     │
        │ (City)  │   │ (Farm)  │   │ (Water) │
        └────┬────┘   └────┬────┘   └────┬────┘
             │             │             │
      ┌──────┼──────┐  ┌───┼───┐  ┌────┼──────┐
      │      │      │  │   │   │  │    │      │
      ▼      ▼      ▼  ▼   ▼   ▼  ▼    ▼      ▼
    ┌───┐  ┌───┐  ┌───┐ ┌┐ ┌┐ ┌┐ └─┐ ┌──┐   ┌──┐
    │S1 │  │S2 │  │S3 │ │S│ │S│ │S│  │S4│   │S5│
    └───┘  └───┘  └───┘ └┘ └┘ └┘ └─┘ └──┘   └──┘
   (50 nodes per gateway typical; max 100)
```

### 3.3 Communication Protocol Stack

| Layer | Protocol | Purpose |
|-------|----------|---------|
| Application | MQTT 5.0 | Pub/sub messaging |
| Payload | CBOR/JSON | Efficient data encoding |
| Security | TLS 1.3 + X.509 | End-to-end encryption |
| Network | LoRaWAN 1.1 | Long-range, low-power |
| Backup | NB-IoT / LTE-M | Cellular fallback |
| Emergency | Iridium SBD | Satellite (remote areas) |

### 3.4 Message Format (CBOR Example)

```c
{
  "msg_type": "sensor_reading",
  "node_id": "MS-2026-001247",
  "timestamp": 1711593600,
  "geo": {
    "lat": 40.7128,
    "lon": -74.0060
  },
  "readings": {
    "bio_signal": 2847,       // Arbitrary units (fluorescence)
    "temperature": 22.4,      // °C
    "ph": 7.2,
    "battery_v": 3.71,        // Volts
    "uptime_sec": 2592000     // ~30 days
  },
  "flags": {
    "chamber_status": "active",
    "containment_check": "pass",
    "alert_state": false
  },
  "sig": "base64-ed25519-signature..."  // Tamper detection
}
```

---

## 4. Cloud Platform & Analytics

### 4.1 Data Pipeline Architecture

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│                           CLOUD DATA PIPELINE                                        │
├────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│   ┌────────┐   TLS 1.3   ┌────────────┐                                            │
│   │Sensor  │──────────────►│ MQTT       │                                            │
│   │Gateway │               │ Broker     │                                            │
│   └────────┘               │ (HiveMQ/  │                                            │
│                            │  EMQX)     │                                            │
│                            └─────┬──────┘                                            │
│                                  │                                                   │
│                         ┌────────┴────────┐                                         │
│                         │ Topic Routing:   │                                         │
│                         │ • raw/{node_id}  │                                         │
│                         │ • alerts/high    │                                         │
│                         │ • alerts/critical│                                         │
│                         │ • calibration    │                                         │
│                         └────────┬────────┘                                         │
│                                  │                                                   │
│              ┌───────────────────┼───────────────────┐                              │
│              │                   │                   │                              │
│              ▼                   ▼                   ▼                              │
│   ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                     │
│   │ STREAM         │  │ ALERT          │  │ ARCHIVE        │                     │
│   │ PROCESSING     │  │ PROCESSOR      │  │ S3             │                     │
│   │ (Apache Flink) │  │ (Real-time)    │  │ (Cold storage) │                     │
│   └───────┬────────┘  └───────┬────────┘  └────────────────┘                     │
│           │                   │                                                      │
│           ▼                   ▼                                                      │
│   ┌────────────────┐  ┌────────────────┐                                           │
│   │ TIME-SERIES DB │  │ NOTIFICATION   │                                           │
│   │ (InfluxDB 3.0) │  │ (SNS/PagerDuty │                                           │
│   │                │  │ /Telegram)     │                                           │
│   │ ┌────────────┐ │  └────────────────┘                                           │
│   │ │ Hot Data   │ │                                                                │
│   │ │ (30 days)  │ │                                                                │
│   │ └────────────┘ │                                                                │
│   │ ┌────────────┐ │                                                                │
│   │ │ Warm Data  │ │                                                                │
│   │ │ (1 year)   │ │                                                                │
│   │ └────────────┘ │                                                                │
│   └───────┬────────┘                                                                │
│           │                                                                         │
│           ▼                                                                         │
│   ┌────────────────┐                                                                 │
│   │ ANALYTICS      │                                                                 │
│   │ ENGINE         │                                                                 │
│   │ • Anomaly      │                                                                 │
│   │   Detection    │                                                                 │
│   │ • Predictive   │                                                                 │
│   │   Models       │                                                                 │
│   │ • Source       │                                                                 │
│   │   Attribution  │                                                                 │
│   └───────┬────────┘                                                                │
│           │                                                                         │
│           ▼                                                                         │
│   ┌────────────────────────────────────────────────────┐                           │
│   │                    API LAYER                         │                           │
│   │  REST API + GraphQL + WebSocket for real-time       │                           │
│   └────────────────────────────────────────────────────┘                           │
│           │                                                                          │
│           ▼                                                                          │
│   ┌────────────────────────────────────────────────────┐                           │
│   │                  DASHBOARD                         │                           │
│   │  React + Mapbox + Grafana + Custom Visualizations │                           │
│   └────────────────────────────────────────────────────┘                           │
│                                                                                      │
└────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Analytics Capabilities

| Feature | Technology | Description |
|---------|-----------|-------------|
| **Anomaly Detection** | Isolation Forest + LSTM | Detect unexpected biological signal patterns |
| **Source Attribution** | Bayesian inference | Estimate pollution source location from sensor array |
| **Predictive Alerting** | Prophet / ARIMA | Forecast contamination events |
| **Bio-Drift Correction** | Multi-variate regression | Account for organism signal degradation |
| **Spatial Visualization** | Mapbox + heatmaps | Real-time + historical pollution maps |

### 4.3 Dashboard Wireframe

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│  MYCOSENTINEL COMMAND CENTER                                    [User] [Alerts ▼]  │
├────────────────────────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────────────────────────────┐│
│  │                     INTERACTIVE MAP (Real-Time Heatmap)                        ││
│  │     ● MS-001 [GREEN]    ● MS-002 [GREEN]     ● MS-003 [YELLOW - ALERT]        ││
│  │                              ● MS-004 [GREEN]    ● MS-005 [GREEN]              ││
│  │  Legend: 🟢 Active  🟡 Alert  🔴 Critical  ⚫ Offline                          ││
│  └───────────────────────────────────────────────────────────────────────────────┘│
│  ┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐              │
│  │   OVERVIEW        │ │  ACTIVE ALERTS    │ │  SYSTEM HEALTH    │              │
│  │   ─────────       │ │  ─────────────    │ │  ─────────────    │              │
│  │   Nodes: 1,247    │ │  • MS-003: Pb²⁺  │ │  Nodes Online: 94% │              │
│  │   Active: 1,172   │ │    (Farm Sector B)│ │  Avg Battery: 72% │              │
│  │   Alerts: 3       │ │    > Threshold    │ │  Last Sync: 2m    │              │
│  │   Offline: 75     │ │  • MS-089: Low pH │ │                   │              │
│  │                   │ │    (River Section 3)│                   │              │
│  │   [View Details]  │ │  • MS-412: Chamber│ │  [View Health]    │              │
│  │                   │ │    Replace Due    │ │                   │              │
│  └───────────────────┘ └───────────────────┘ └───────────────────┘              │
│  ┌───────────────────────────────────────────────────────────────────────────────┐│
│  │                        TREND ANALYSIS (Last 30 Days)                           ││
│  │  ┌────────────────────────────────────────────────────────────────────────┐   ││
│  │  │  [Heavy Metals] [Endocrine Disruptors] [Antibiotics] [Custom...]    │   ││
│  │  │                                                                        │   ││
│  │  │    ╱╲                           ╱╲                                   │   ││
│  │  │   ╱  ╲    ╱╲                   ╱  ╲    ╱╲                            │   ││
│  │  │  ╱    ╲──╱  ╲──────────────────╱    ╲──╱  ╲── Rain Event              │   ││
│  │  │ ╱                                    ╲                               │   ││
│  │  │╱                                      ╲____________________          │   ││
│  │  │                                                                        │   ││
│  │  └────────────────────────────────────────────────────────────────────────┘   ││
│  └───────────────────────────────────────────────────────────────────────────────┘│
└────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Deployment Strategy

### 5.1 Deployment Playbooks

#### Scenario A: Urban Watershed Deployment (1,000 nodes)

**Timeline:** 12 weeks  
**Coverage:** 50 km² metropolitan area

| Phase | Weeks | Activities | Deliverables |
|-------|-------|------------|--------------|
| **1. Site Survey** | 1-2 | GIS analysis, permission acquisition, power/connectivity assessment | Site map with 1,000 GPS coordinates |
| **2. Gateway Installation** | 3-4 | Install 20 gateway nodes (50 sensors each) on existing infrastructure | Gateway network live |
| **3. Sensor Deployment** | 5-8 | Deploy sensors in batches of 250, pairing to nearest gateway | 1,000 sensors online |
| **4. Calibration** | 9-10 | Run reference standards, collect parallel lab samples | Calibration curves verified |
| **5. Validation** | 11-12 | Compare with commercial sensors, stress-test alerts | Validation report |

#### Scenario B: Agricultural Deployment (500 nodes)

**Timeline:** 8 weeks  
**Coverage:** 10,000-acre farm

| Phase | Weeks | Activities |
|-------|-------|------------|
| **1. Grid Planning** | 1 | 100m grid pattern for runoff monitoring |
| **2. Gateway Placement** | 2 | 10 gateways on farm buildings and silos |
| **3. Sensor Installation** | 3-6 | Focus on drainage channels, irrigation points |
| **4. Seasonal Calibration** | 7-8 | Pre-growing season baseline establishment |

#### Scenario C: Remote Watershed (200 nodes)

**Timeline:** 6 weeks  
**Coverage:** 100 km river system

| Phase | Weeks | Activities |
|-------|-------|------------|
| **1. Access Survey** | 1 | Helicopter/drone scouting for installation points |
| **2. Solar-Gateway Setup** | 2 | Self-contained gateway units with solar + satellite |
| **3. Float Deployment** | 3-5 | Buoy-mounted sensors anchored at strategic points |
| **4. Remote Validation** | 6 | Mobile lab for field verification |

### 5.2 Inoculation Protocol

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│                      BIO-CHAMBER INOCULATION PROTOCOL                              │
├────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  STEP 1: Sterile Preparation (Class II Biosafety Cabinet)                          │
│  ───────────────────────────────────────────────────────                           │
│  • Pre-fill chamber with 50mL sterile minimal media                                   │
│  • Verify 0.22 μm membrane integrity (bubble point test)                            │
│  • UV-C sterilize chamber interior (254nm, 30 min)                                  │
│                                                                                     │
│  STEP 2: Organism Inoculation                                                        │
│  ─────────────────────────────                                                       │
│  • Thaw cryo-stock of engineered strain (1mL @ -80°C)                              │
│  • Inoculate chamber aseptically via septum port                                    │
│  • Initial density: 1×10⁶ cells/mL                                                  │
│  • Seal all ports with heat-seal                                                     │
│                                                                                     │
│  STEP 3: Quality Control                                                             │
│  ─────────────────────────                                                           │
│  • Baseline fluorescence reading (dark control)                                       │
│  • Positive control with known inducer concentration                                  │
│  • Verify containment (pressure decay test)                                         │
│  • Apply tamper-evident seal with QR code traceability                              │
│                                                                                     │
│  STEP 4: Field Activation                                                            │
│  ─────────────────────────                                                           │
│  • Transport at 4°C (maximum 48 hours)                                               │
│  • Allow to equilibrate to ambient temperature (2 hours)                           │
│  • Scan QR code to activate in cloud system                                          │
│  • Begin 24-hour baseline calibration period                                         │
│                                                                                     │
│  STEP 5: Chain of Custody                                                            │
│  ─────────────────────────                                                           │
│  • Each chamber: Unique ID, preparation date, technician, QC pass/fail           │
│  • Blockchain ledger entry for GMO traceability                                      │
│  • Geofenced activation (chamber only activates within 100m of deployment site)    │
│                                                                                     │
└────────────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Maintenance Schedule

| Interval | Activity | Labor per 100 Nodes |
|----------|----------|---------------------|
| **Daily** | Remote health check (automated) | 0 hrs |
| **Weekly** | Battery voltage review, alert investigation | 2 hrs |
| **Monthly** | Physical inspection, debris clearing, photo documentation | 8 hrs |
| **Quarterly** | Sensor cleaning, exterior seal check, firmware update | 16 hrs |
| **Bi-Annually** | Bio-chamber replacement, full calibration cycle | 24 hrs |
| **Annually** | Hardware refurbishment, gateway deep maintenance | 40 hrs |

### 5.4 Bio-Chamber Replacement Workflow

```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│   ALERT:    │──►│  DISPATCH   │──►│   FIELD     │──►│  REMOVAL    │──►│  DISPOSAL   │
│   Chamber   │   │  Technician │   │   Arrival   │   │   & SWAP  │   │   & LOG    │
│   Expiring  │   │  (with spare)│  │  Verify ID  │   │   (30 min)  │   │  Autoclave  │
└─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘
                                                                              │
                                                                              ▼
                                                                       ┌─────────────┐
                                                                       │   LOG ENTRY │
                                                                       │  QR Code +  │
                                                                       │ Blockchain  │
                                                                       │  Autoclave  │
                                                                       │ Certificate │
                                                                       └─────────────┘
```

---

## 6. Calibration & Ground-Truthing

### 6.1 Calibration Hierarchy

```
Tier 1: PRIMARY STANDARDS (NIST-traceable)
        ├─ Certified reference materials (CRMs)
        ├─ Example: NIST SRM 1643e (trace elements in water)
        └─ Validated in ISO 17025 laboratory
        
        ▼
        
Tier 2: SECONDARY STANDARDS (Field lab)
        ├─ Working solutions prepared weekly
        ├─ Concentration range: 0.1× to 10× expected
        └─ Run in triplicate on 3 biological replicates
        
        ▼
        
TIER 3: SENSOR CALIBRATION (In-node)
        ├─ Response curve: Signal vs Concentration
        ├─ Dynamic range determination
        ├─ LOD/LOQ calculation
        └─ Drift correction factors
        
        ▼
        
TIER 4: FIELD VALIDATION (Ground-truthing)
        ├─ Parallel grab samples → certified lab
        ├─ Commercial sensor comparison (YSI, Hach)
        ├─ Regulatory lab analysis (EPA 200.8, etc.)
        └─ Statistical agreement analysis
```

### 6.2 Calibration Procedure

For each sensor node:

```python
# Pseudocode for calibration

def calibrate_sensor(node_id, standards):
    """
    Run calibration curve on fresh bio-chamber
    """
    readings = []
    
    for concentration in [0, 0.1, 1, 10, 100, 1000]:  # μg/L
        # Inject standard via sample port
        inject_standard(node_id, concentration)
        
        # Wait for equilibrium (organism-dependent)
        wait(response_time * 3)
        
        # Record stable reading
        signal = read_optical(node_id)
        readings.append((concentration, signal))
    
    # Fit calibration model (typically Hill or linear)
    model = fit_dose_response(readings)
    
    # Calculate performance metrics
    lod = calculate_lod(readings)        # Limit of detection
    loq = calculate_loq(readings)        # Limit of quantification
    r_squared = model.r_squared
    
    # Store to node memory + cloud
    upload_calibration(node_id, model, lod, loq, r_squared)
    
    return model
```

### 6.3 Ground-Truthing Protocol

| Frequency | Samples | Analysis | Comparison Target |
|-----------|---------|----------|-------------------|
| Weekly (first month) | 10% of sensors | ICP-MS, LCMS | ± 20% agreement |
| Monthly (months 2-6) | 5% of sensors | ICP-MS | ± 30% agreement |
| Quarterly (ongoing) | 2% of sensors | ICP-MS | ± 30% agreement |
| Event-triggered | All sensors in zone | Full panel | Immediate verification |

### 6.4 Statistical Validation

**Key Metrics:**

- **Pearson r**: > 0.85 (correlation with reference)
- **Mean Absolute Error (MAE)**: < 25% of measured value
- **Bland-Altman Agreement**: 95% of points within ± 1.96 SD
- **Kappa Statistic**: > 0.7 (categorical agreement: alert vs no-alert)

---

## 7. Safety & Containment Protocols

### 7.1 GMO Risk Assessment

| Factor | Assessment | Mitigation |
|--------|-----------|------------|
| **Organism** | *S. cerevisiae* (GRAS) or *A. nidulans* | Non-pathogenic, no environmental persistence |
| **Modification** | Promoter-reporter only, no antibiotic resistance | No selective advantage in wild |
| **Release Scenario** | Membrane breach + organism escape | Triple barrier system (see below) |
| **Ecological Impact** | Competition with native yeasts | Engineered strain has fitness cost |
| **Human Health** | No toxigenic products | Non-infectious, no allergenic proteins |

**Biosafety Level:** BL1 (standard microbiological practices sufficient)

### 7.2 Triple Barrier Containment System

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│                      TRIPLE BARRIER CONTAINMENT                                     │
├────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌───────────────────────────────────────────────────────────────────────────────┐ │
│  │  BARRIER 1: PHYSICAL (Unconditional)                                           │ │
│  │  ───────────────────────────────────                                           │ │
│  │  • 0.22 μm PES membrane (bacteria/vast majority of fungi cannot pass)       │ │
│  │  • Heat-sealed chamber with no penetrations                                     │ │
│  │  • IP67-rated outer enclosure                                                   │ │
│  │  • Mechanical tamper-evidence (break-away tabs)                              │ │
│  └───────────────────────────────────────────────────────────────────────────────┘ │
│                                   ▼                                                │
│  ┌───────────────────────────────────────────────────────────────────────────────┐ │
│  │  BARRIER 2: GENETIC (Conditional Kill Switch)                                  │ │
│  │  ────────────────────────────────────────────                                   │ │
│  │  • Auxotrophy: Engineered strain requires histidine supplement                  │ │
│  │    (his3Δ mutation - cannot survive without supplementation)                 │ │
│  │  • Temperature sensitivity: Strain dies above 37°C                             │ │
│  │  • UV-C vulnerability: Engineered reduced DNA repair                            │ │
│  │  • Competitive disadvantage: Slower growth than wild-type                       │ │
│  └───────────────────────────────────────────────────────────────────────────────┘ │
│                                   ▼                                                │
│  ┌───────────────────────────────────────────────────────────────────────────────┐ │
│  │  BARRIER 3: OPERATIONAL (Procedural)                                            │ │
│  │  ────────────────────────────────────                                          │ │
│  │  • Bi-annual chamber replacement (before degradation)                            │ │
│  │  • Autoclaving of all returned chambers (121°C, 15 min minimum)               │ │
│  │  • Geofencing: Chamber deactivates if moved > 100m from deployment site      │ │
│  │  • Real-time containment monitoring (pressure + integrity sensors)          │ │
│  │  • Emergency response protocol for breach detection                           │ │
│  └───────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                     │
│  VERIFICATION: Independent third-party containment testing annually                │
│                                                                                     │
└────────────────────────────────────────────────────────────────────────────────────┘
```

### 7.3 Breach Detection & Response

**Detection Methods:**

1. **Pressure Decay Sensors:** Monitor for membrane compromise
2. **UV-C Dosimeter:** Confirms sterilization cycle completion
3. **Tamper Detection:** Accelerometer logs physical disturbance
4. **Fluorescence Anomaly:** Sudden signal drop may indicate organism death/release

**Response Protocol:**

| Level | Trigger | Response |
|-------|---------|----------|
| **Level 1** | Sensor anomaly | Remote diagnostic, schedule inspection |
| **Level 2** | Tamper detected | Immediate dispatch, isolate chamber |
| **Level 3** | Containment breach confirmed | Emergency protocol: autoclave on-site, environmental sampling |
| **Level 4** | Suspected environmental release | Notify EPA/state agencies, activate remediation |

### 7.4 End-of-Life Disposal

All bio-chambers MUST be:

1. **Autoclaved** at 121°C for 15 minutes minimum
2. **Documented** with QR code scan + blockchain entry
3. **Certificate generated** for regulatory compliance
4. **Disposed as biohazardous waste** per local regulations
5. **Or recycled** after incineration (metals recovery)

---

## 8. Regulatory Framework

### 8.1 Applicable Regulations (USA)

| Agency | Regulation | Applicability | Requirements |
|--------|-----------|---------------|--------------|
| **EPA** | TSCA Section 5 | New microorganisms | PMN filing 90 days prior |
| **EPA** | FIFRA | Pesticidal claims | Registration if used for pest control |
| **USDA-APHIS** | 7 CFR 340 | Plant pests | Permit if organism on plant pest list |
| **FDA** | GRAS | Food contact | Self-affirmation or notification |
| **State** | Varied | Environmental release | California, NY, others have additional requirements |

### 8.2 TSCA Pre-Manufacture Notification (PMN)

**Required for:** Intergeneric microorganisms (new combinations of DNA)

**Timeline:** 90-day review + potential extension

**Key Components:**

1. **Chemical Identity:** Genus, species, strain, introduced genes
2. **Production/Use:** Intended monitoring application, containment
3. **Exposure Assessment:** Release scenarios, environmental fate
4. **Risk Assessment:** Human health and ecological impacts
5. **Test Data:** Toxicity, pathogenicity, environmental persistence

**Exemptions:**

- Research and development in contained facility (no PMN)
- Specific regulatory exemptions for certain organisms

### 8.3 TSCA Experimental Release Application (TERA)

For field testing under controlled conditions:

- **Containment:** Similar to commercial system
- **Monitoring:** Enhanced environmental surveillance
- **Reporting:** Quarterly to EPA
- **Duration:** Typically 1-2 years

### 8.4 International Considerations

| Region | Framework | Key Requirements |
|--------|-----------|----------------|
| **EU** | Directive 2009/41/EC (contained use) | Class I-IV notification based on risk |
| **EU** | Directive 2001/18/EC (deliberate release) | Case-by-case authorization |
| **Canada** | Canadian Environmental Protection Act | New Substances Notification |
| **Australia** | Gene Technology Act 2000 | OGTR approval for release |
| **Brazil** | CTNBio | Case-by-case risk assessment |

### 8.5 Compliance Checklist

```
□ TSCA PMN filed and approved (or exemption confirmed)
□ State environmental permits obtained
□ Institutional Biosafety Committee (IBC) approval
□ Material Transfer Agreements (if academic collaboration)
□ Emergency response plan filed with local authorities
□ Insurance coverage for environmental liability
□ Public notification (where required by ordinance)
□ Worker safety training documentation
□ Annual compliance audit scheduled
```

---

## 9. Business & Operational Models

### 9.1 Model Options Comparison

| Model | Description | Revenue Stream | Best For |
|-------|-------------|---------------|----------|
| **A. Open Source Kit** | Sell hardware kits at cost + support | Hardware margin, support contracts | Research, DIY communities |
| **B. SaaS Monitoring** | Full deployment as service | Monthly/annual subscription | Municipalities, NGOs |
| **C. Hybrid Community** | Open core + premium services | Consulting, analytics upgrades | Watershed groups, citizen science |
| **D. Data Marketplace** | Aggregate and sell insights | Data licensing | Agribusiness, insurers |

### 9.2 Recommended: Hybrid Community Model

**Core Philosophy:** Open hardware/schematics + fee-for-service deployment

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│                        HYBRID COMMUNITY MODEL                                       │
├────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  OPEN SOURCE (GitHub)                    PAID SERVICES                            │
│  ───────────────────                     ───────────────                           │
│                                                                                     │
│  • PCB schematics (KiCad)               • Full turn-key deployments                │
│  • Bio-protocols (wet lab)              • Bio-chamber supply chain               │
│  • Firmware (open source)               • Cloud hosting + analytics              │
│  • 3D printable enclosures            • Calibration lab services                │
│  • Deployment guides                    • Regulatory compliance support          │
│  • Training curriculum                  • Priority support                         │
│                                                                                     │
│  COMMUNITY CONTRIBUTIONS                                              │
│  ────────────────────────                                             │
│  • Local assembly groups (makerspaces)                                │
│  • Academic research partnerships                                     │
│  • Data sharing (anonymized)                                        │
│  • Protocol improvements                                              │
│                                                                                     │
│  REVENUE: $50K-500K/year (consulting/services) + grants                           │
│  IMPACT: Unlimited deployment scale                                                 │
│                                                                                     │
└────────────────────────────────────────────────────────────────────────────────────┘
```

### 9.3 Pricing Structure (SaaS Model Reference)

| Tier | Nodes | Monthly Cost/Node | Includes |
|------|-------|-------------------|----------|
| **Basic** | 1-50 | $25 | Hardware lease, cloud dashboard, email alerts |
| **Standard** | 51-500 | $18 | + API access, phone alerts, quarterly calibration |
| **Enterprise** | 500+ | $12 | + Custom analytics, dedicated support, regulatory docs |

**Bio-Chamber Replacement:** $35/chamber (included in Enterprise)

### 9.4 Value Proposition vs Alternatives

| Solution | Upfront Cost | Annual Operating | Detection Capability | Deployment Scale |
|----------|-------------|------------------|---------------------|------------------|
| **MycoSentinel** | $150/node | $200/node | Biological specificity | Unlimited |
| **Water Rangers** (commercial) | $500/node | $100/node | Physical/chemical only | Limited |
| **YSI EXO** | $15,000/node | $500/node | Comprehensive chemistry | < 100 nodes |
| **Hach WIMS** | $20,000/node | $800/node | Lab-grade accuracy | < 20 nodes |
| **DIY (Arduino + sensors)** | $50/node | $50/node | Basic (temperature, conductivity) | Limited by labor |

---

## 10. Success Metrics & Benchmarking

### 10.1 Technical Performance Metrics

| Metric | Target | Measurement Method |
|--------|--------|---------------------|
| **Detection Limit (LOD)** | < 1 μg/L for heavy metals | 3× standard deviation of blank |
| **Dynamic Range** | 3 orders of magnitude | Calibration curve verification |
| **Response Time** | < 60 min for 90% of signal | Time-series analysis |
| **Shelf Life (Chamber)** | > 60 days from preparation | Accelerated aging study |
| **False Positive Rate** | < 5% | Comparison with certified lab |
| **False Negative Rate** | < 1% | Spike recovery studies |
| **Uptime** | > 95% | Node heartbeat logs |
| **Data Yield** | > 90% of expected transmissions | Message queue analysis |

### 10.2 Comparison with Water Rangers

| Feature | Water Rangers | MycoSentinel | Advantage |
|---------|--------------|--------------|-----------|
| **Cost per node** | ~$400 | ~$150 | 2.7× cheaper |
| **Bio-specific detection** | No | Yes | Detects what chemistry can't |
| **Maintenance frequency** | Monthly | Bi-annual | 6× less labor |
| **Deployment scale** | 10-100 nodes | 100-10,000 nodes | 100× larger |
| **Data latency** | Manual upload | Real-time | Instant alerts |
| **Customization** | Limited | Fully programmable | Any analyte |
| **Community building** | Moderate | Open-source enabled | Full transparency |
| **Regulatory acceptance** | Established | Emerging | MycoSentinel: growing |

### 10.3 Economic Benchmarking

**Cost per Data Point:**

| Method | Cost/Data Point | Annual Cost (100 nodes) |
|--------|-----------------|------------------------|
| Lab analysis (grab samples) | $50 | $1,825,000 (daily samples) |
| Commercial multi-probes | $2 | $73,000 |
| MycoSentinel | $0.05 | $1,825 |

**Return on Investment:**

- **Break-even:** 18 months vs commercial probes
- **Cost avoidance:** Early detection of contamination events
- **Grant eligibility:** Enhanced data for water quality projects

### 10.4 Key Performance Indicators (KPIs)

**Operational KPIs (Dashboard):**

```python
KPIs = {
    "deployment_coverage": "95%",          # Target areas with sensors
    "data_completeness": "92%",            # Expected vs received readings
    "time_to_repair": "< 48 hours",        # Failed node resolution
    "chamber_utilization": "85%",          # Days active vs max lifespan
    "false_alert_rate": "< 3%",            # Verified vs unverified alerts
}
```

**Scientific KPIs (Quarterly Report):**

```python
Scientific_KPIs = {
    "correlation_with_icp_ms": "r = 0.89",   # Heavy metals accuracy
    "sensitivity_vs_hach": "comparable",     # Detection limits
    "spatial_resolution": "100m",            # Average node spacing
    "temporal_resolution": "15 min",         # Standard reading interval
    "new_analytes_deployed": "2/year",       # R&D progress
}
```

---

## 11. Risk Management

### 11.1 Risk Matrix

| Risk | Likelihood | Impact | Mitigation | Owner |
|------|-----------|--------|------------|-------|
| **Chamber membrane failure** | Medium | High | Triple barrier, pressure monitoring, 60-day replacement | Operations |
| **Organism escape** | Low | Critical | Kill switches, autoclave protocol, insurance | Regulatory |
| **Data communication loss** | Medium | Medium | LTE fallback, local storage, mesh networking | Engineering |
| **Regulatory denial** | Medium | High | Early EPA engagement, legal counsel, TERA pilot | Regulatory |
| **Public opposition** | Medium | Medium | Transparency, community science model, education | Outreach |
| **Biological drift** | High | Medium | Regular calibration, drift correction algorithms | Science |
| **Hardware supply chain** | Medium | Medium | Dual sourcing, strategic stockpile | Operations |
| **Cybersecurity breach** | Low | High | TLS 1.3, certificate pinning, penetration testing | Security |

### 11.2 Contingency Plans

**Bio-Containment Breach:**

1. Immediate node isolation (remote shutdown)
2. Dispatch containment team with PPE
3. On-site autoclaving of chamber
4. Environmental sampling (100m radius)
5. EPA notification within 24 hours
6. Root cause analysis and public report

**Mass Sensor Failure:**

1. Identify common cause (firmware, batch defect)
2. Activate backup manual sampling protocol
3. Emergency bio-chamber shipment to affected sites
4. Root cause remediation
5. Lessons learned documentation

---

## 12. Appendices

### Appendix A: Bill of Materials (Complete System)

#### Per-Node BOM (1,000x Scale)

| Item | Qty | Unit Cost | Extended |
|------|-----|-----------|----------|
| Raspberry Pi Pico W | 1 | $6.00 | $6,000 |
| TSL2561 Light Sensor | 1 | $8.00 | $8,000 |
| RFM95W LoRa Module | 1 | $12.00 | $12,000 |
| DS18B20 Temp Sensor | 1 | $3.00 | $3,000 |
| 18650 Battery | 2 | $8.00 | $16,000 |
| Solar Panel 2W | 1 | $6.00 | $6,000 |
| PCB Manufacturing | 1 | $4.00 | $4,000 |
| IP67 Enclosure | 1 | $15.00 | $15,000 |
| Custom Bio-Chamber | 1 | $25.00 | $25,000 |
| Misc (cables, connectors) | 1 | $9.00 | $9,000 |
| **Subtotal** | | **$96** | **$96,000** |
| Assembly Labor (30 min @ $30/hr) | | $15 | $15,000 |
| Testing/QC (15 min @ $40/hr) | | $10 | $10,000 |
| Shipping/Logistics | | $7 | $7,000 |
| **TOTAL PER NODE** | | **$128** | **$128,000** |

#### Gateway BOM (20 Units)

| Item | Qty | Unit Cost | Extended |
|------|-----|-----------|----------|
| Raspberry Pi 5 8GB | 1 | $80 | $1,600 |
| LoRa Concentrator (SX1302) | 1 | $120 | $2,400 |
| LTE Modem (Quectel) | 1 | $60 | $1,200 |
| Solar Charge Controller | 1 | $25 | $500 |
| LiFePO4 20Ah Battery | 1 | $150 | $3,000 |
| Solar Panel 20W | 1 | $40 | $800 |
| IP66 Enclosure | 1 | $80 | $1,600 |
| **TOTAL PER GATEWAY** | | **$555** | **$11,100** |

#### Cloud Infrastructure (Annual)

| Service | Provider | Monthly | Annual |
|---------|----------|---------|--------|
| MQTT Broker (managed) | HiveMQ | $500 | $6,000 |
| Stream Processing | AWS Kinesis | $800 | $9,600 |
| Time-Series DB | InfluxDB Cloud | $300 | $3,600 |
| Object Storage | AWS S3 | $150 | $1,800 |
| Compute (EKS) | AWS | $1,200 | $14,400 |
| Monitoring | Datadog | $400 | $4,800 |
| **TOTAL** | | **$3,350** | **$40,200** |

**1,000-Node System Total: $179,300 (hardware) + $40,200 (cloud/year) + $200,000 (deployment)** = **~$420,000 first year**

### Appendix B: Regulatory Filing Templates

**TSCA PMN Cover Sheet Information:**

| Field | Content |
|-------|---------|
| Chemical Substance | *Saccharomyces cerevisiae* strain MYCO-001 |
| Generic Name | Engineered yeast biosensor |
| Trade Name | MycoSentinel Bio-Chamber |
| Use | Environmental monitoring of heavy metals |
| Production Volume | < 1 kg/year (estimated) |
| Test Data | Attached: Pathogenicity study, environmental fate |

### Appendix C: Installation Checklist

```
□ Site survey complete (GPS coordinates, photos)
□ Landowner permission obtained (documented)
□ Gateway location identified (power/connectivity)
□ Sensor mounting hardware secured
□ Gateway installed and connectivity verified
□ Sensor nodes deployed and paired to gateway
□ Baseline readings established (24 hours)
□ Calibration verification complete
□ Dashboard access granted to stakeholders
□ Maintenance schedule communicated
□ Emergency contact information posted
□ Photo documentation archived
```

### Appendix D: Acronyms & Definitions

| Term | Definition |
|------|------------|
| **BL1** | Biosafety Level 1 (lowest risk) |
| **CBOR** | Concise Binary Object Representation |
| **EPA** | Environmental Protection Agency |
| **FIFRA** | Federal Insecticide, Fungicide, and Rodenticide Act |
| **GRAS** | Generally Recognized As Safe |
| **ICP-MS** | Inductively Coupled Plasma Mass Spectrometry |
| **LCMS** | Liquid Chromatography Mass Spectrometry |
| **LOD/LOQ** | Limit of Detection / Limit of Quantification |
| **LoRaWAN** | Long Range Wide Area Network |
| **MQTT** | Message Queuing Telemetry Transport |
| **NB-IoT** | Narrowband Internet of Things |
| **PDMS** | Polydimethylsiloxane |
| **PES** | Polyethersulfone (membrane material) |
| **PMN** | Pre-Manufacture Notification |
| **TSCA** | Toxic Substances Control Act |
| **TERA** | TSCA Experimental Release Application |

### Appendix E: Integration with Existing Systems

**Data Export Formats:**

- **WQP (Water Quality Portal):** EPA-compatible XML
- **SOS (Sensor Observation Service):** OGC-compliant
- **CSV/JSON:** Bulk historical export
- **REST API:** Real-time integration
- **Webhook:** Event-driven notifications

**Third-Party Integrations:**

| System | Integration Method | Use Case |
|--------|-------------------|----------|
| **Water Rangers** | API bridge | Data sharing with existing networks |
| **USGS Water Services** | WQP export | Regulatory reporting |
| **Tableau/Power BI** | Connector | Executive dashboards |
| **Slack/Teams** | Webhook | Alert notifications |
| **GIS Systems** | GeoJSON API | Spatial analysis |

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2026-03-20 | BIOSYN-04 | Initial draft |
| 1.0 | 2026-03-28 | BIOSYN-04 | Field deployment ready |

**Next Review:** 2026-09-28 (6-month cycle)

**Approval:**
- Technical Lead: ____________________ Date: __________
- Regulatory Lead: ____________________ Date: __________
- Safety Officer: ____________________ Date: __________

---

*"Not just a lab curiosity — a complete field-deployable system for environmental monitoring at scale."*

**MycoSentinel: Biology meets infrastructure. Nature as a sensor.**
