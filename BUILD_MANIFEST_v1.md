# MYCOSENTINEL-001 BUILD MANIFEST v1.0
## Unified Build Specification & Critical Path Analysis

**Project:** MycoSentinel Biosensor Network  
**Status:** Build in Progress - All Design Docs Received  
**Date:** 2026-03-28  
**Team:** BIOSYN-01 (Synthetic Biology), BIOSYN-02 (Hardware), BIOSYN-03 (ML), BIOSYN-04 (Integration)

---

## TABLE OF CONTENTS

1. [Executive Summary](#1-executive-summary)
2. [Subsystem Specifications](#2-subsystem-specifications)
3. [Dependency Matrix](#3-dependency-matrix)
4. [Critical Path Analysis](#4-critical-path-analysis)
5. [Build Sequence Phases](#5-build-sequence-phases)
6. [Deliverables Checklist](#6-deliverables-checklist)
7. [Risk & Mitigation](#7-risk--mitigation)

---

## 1. EXECUTIVE SUMMARY

### 1.1 Project Overview

MycoSentinel is a distributed fungal biosensor network that detects mercury (Hg²⁺) at EPA drinking water limits (2 ppb) using engineered *Saccharomyces cerevisiae* with MerR/GFP genetic circuits. The system combines synthetic biology, low-cost electrochemical hardware, edge ML inference, and cloud-based distributed deployment.

### 1.2 Target Specifications

| Parameter | Target | Source Document |
|-----------|--------|-----------------|
| **Detection Limit** | ≤ 2 ppb Hg²⁺ (10 nM) | BIOSYN-01 |
| **Response Time** | ≤ 2 hours to 90% signal | BIOSYN-01 |
| **Hardware Cost** | < $60 per node | BIOSYN-02 |
| **Sampling Rate** | 1 Hz continuous | BIOSYN-03 |
| **Anomaly Detection** | TFLite LSTM autoencoder | BIOSYN-03 |
| **Deployment Scale** | 1,000+ nodes | BIOSYN-04 |
| **Bio-Chamber Life** | 30-60 days | BIOSYN-04 |

### 1.3 Cross-Subsystem Integration

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                         HIGH-LEVEL SYSTEM ARCHITECTURE                            │
├───────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│   ┌─────────────────────────────────────────────────────────────────────────┐    │
│   │                      BIOSYN-01: SYNTHETIC BIOLOGY                        │    │
│   │                   MerR/GFP Circuit + Yeast Chassis                       │    │
│   │              ┌──────────────┐     ┌──────────────┐                    │    │
│   │              │ pTEF1-MerR   │────►│ pmerT-yEGFP  │──►GFP Signal       │    │
│   │              │ (Constitutive)│     │ (Hg²⁺ Responsive)│                │    │
│   │              └──────────────┘     └──────────────┘                    │    │
│   └─────────────────────────────────┬───────────────────────────────────────┘    │
│                                     │                                             │
│                                     ▼ GFP Fluorescence                           │
│                                     OR                                           │
│   ┌─────────────────────────────────┼───────────────────────────────────────┐   │
│   │                      BIOSYN-02: HARDWARE                                 │   │
│   │                 Electrochemical Read + 3D Enclosure                     │   │
│   │    ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐    │   │
│   │    │  Graphite   │    │  LMP91000   │    │   ESP32-WROOM       │    │   │
│   │    │  Electrodes │───►│  Potentiostat│──►│  + LoRa + WiFi     │    │   │
│   │    │  (WE/CE/RE) │    │             │    │  3D Printed Vessel  │    │   │
│   │    └─────────────┘    └─────────────┘    └─────────────────────┘    │   │
│   └─────────────────────────────────┬───────────────────────────────────────┘   │
│                                     │ MQTT / HTTP                              │
│                                     ▼                                           │
│   ┌─────────────────────────────────────────────────────────────────────────┐  │
│   │                      BIOSYN-03: SOFTWARE PIPELINE                        │  │
│   │           TFLite Anomaly Detection + FastAPI Dashboard                   │  │
│   │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐        │  │
│   │  │  Optical   │  │ Electrical │  │  Temporal  │  │    ML      │        │  │
│   │  │ Processing │  │ Processing │──►│  Analysis  │──►│ Inference  │        │  │
│   │  └────────────┘  └────────────┘  └────────────┘  └─────┬──────┘        │  │
│   │                                                       │                │  │
│   │  ┌────────────────────────────────────────────────────▼────────────┐   │  │
│   │  │                    FastAPI + WebSocket Dashboard               │   │  │
│   │  │              InfluxDB + MQTT + Alert System                    │   │  │
│   │  └────────────────────────────────────────────────────────────────┘   │  │
│   └─────────────────────────────────┬───────────────────────────────────────┘  │
│                                     │ Cloud Uplink / Edge Mesh                │
│                                     ▼                                          │
│   ┌─────────────────────────────────────────────────────────────────────────┐ │
│   │                  BIOSYN-04: SYSTEM INTEGRATION                          │ │
│   │         Distributed Deployment + TSCA Compliance                         │ │
│   │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────────┐   │ │
│   │  │  Gateway   │  │   Cloud    │  │  Regulatory│  │   Field Ops    │   │ │
│   │  │  Nodes     │──│  Platform  │  │  Compliance│  │   & Maintenance│   │ │
│   │  │  (Raspberry│  │  (Kafka/   │  │  (TSCA     │  │   (Bio-Chamber│   │ │
│   │  │  Pi 5)     │  │   Influx)  │  │  PMN/TERA) │  │    Replacement)│   │ │
│   │  └────────────┘  └────────────┘  └────────────┘  └────────────────┘   │ │
│   └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. SUBSYSTEM SPECIFICATIONS

### 2.1 BIOSYN-01: Genetic Circuit Design

#### Core Genetic Architecture

| Component | Specification | Sequence ID | Provider |
|-----------|---------------|-------------|----------|
| **Chassis** | *S. cerevisiae* BY4741 (MATα his3Δ1 leu2Δ0 met15Δ0 ura3Δ0) | ATCC 201389 | ATCC |
| **Integration Locus** | HO locus (dispensable for mating) | HO_gRNA | Addgene #67638 |
| **Cas9 Plasmid** | pML104 (pFA6a-pGal-Cas9-crb) | Addgene 67638 | Addgene |
| **Promoter 1** | pTEF1 (constitutive for MerR) | Native yeast | - |
| **Promoter 2** | pmerT (Hg²⁺-responsive) | E. coli Mer operator | Synthesized |
| **Reporter** | yEGFP (yeast-enhanced GFP) | 717 bp | Synthesized |
| **Terminator 1** | tADH1 | 250 bp | Standard |
| **Terminator 2** | tCYC1 | 280 bp | Standard |

#### Complete Integration Cassette (2,960 bp)

```
[5' HO arm: 500 bp] ── [pTEF1-MerR-tADH1: 1,180 bp] ── [pmerT-yEGFP-tCYC1: 1,280 bp] ── [3' HO arm: 500 bp]
```

**MerR Coding Sequence (yeast codon-optimized, 360 bp):**
```
ATGACAGACTCTGAAGTTGAGAAAGGTCTGCTGAAGGCTATTACATCTTCTGTTCATCCAGTAGCAGGCGTTGCATCTGGTCTGCCATCTGGTAGCAAGCTGTCTGGTACCGAGAAATCTCTGTCTGGTGGTAGAAAGGCTATTGCTCACGGTCTGCTGTCTCGTTCTGGTCTGGCTAAGAAGTTGAAGAAGACTAAGGAAGCTAAGGCTCGTTCTCAATCTAAGACTCGTCGTGAATCTGGTCTGTCTGAAGGTCTGCACGGTATCGAGGGTATCGCTCACTTCTCTCACGGTAA
```

**Expected Performance:**
- Detection range: 10 nM - 100 μM Hg²⁺ (4 orders of magnitude)
- EC50: ~500 nM
- Response time (t½): ≤ 60 minutes
- Hill coefficient: 1.5-2.0 (cooperative binding)

#### Safety Features

| Feature | Implementation | Rationale |
|---------|----------------|-----------|
| **Auxotrophy** | his3Δ mutation | Requires histidine supplementation |
| **Kill Switch** | Temperature-sensitive allele | Strain dies above 37°C |
| **No AR Genes** | KanMX selection used | No antibiotic resistance transfer |
| **GRAS Chassis** | *S. cerevisiae* | FDA Generally Recognized as Safe |

---

### 2.2 BIOSYN-02: Hardware Platform

#### Microcontroller & Core Electronics

| Component | Model | Unit Cost | Qty | Supplier |
|-----------|-------|-----------|-----|----------|
| Main MCU | ESP32-WROOM-32 | $4.50 | 1 | Espressif |
| Potentiostat | LMP91000SDE/NOPB | $6.00 | 1 | TI/Digi-Key |
| Transimpedance Amp | LMP7721MF | $3.50 | 1 | TI/Digi-Key |
| LoRa Module | SX1276 433/915MHz | $4.00 | 1 | HopeRF |
| Display | 0.96" OLED SSD1306 | $3.00 | 1 | Generic |
| RTC | DS3231 I2C | $1.50 | 1 | Maxim |

#### Electrochemical Subsystem (Pencil Lead Hack)

| Component | Specification | Unit Cost |
|-----------|---------------|-----------|
| **Working Electrode** | 0.5mm HB graphite (mechanical pencil) | $2.00/12-pack |
| **Counter Electrode** | 0.7mm graphite (different diameter) | $2.00/12-pack |
| **Reference Electrode** | Ag/AgCl pellet + KCl gel | $4.00 |
| **Potential Range** | ±1.5V WE vs RE (electrolysis limit) | - |
| **Current Detection** | Down to 100 pA (with LMP7721) | - |

#### Environmental Sensors

| Sensor | Model | Accuracy | Cost |
|--------|-------|----------|------|
| Temperature | NTC 10K | ±0.5°C | $0.50 |
| Humidity | DHT22/AM2302 | ±2% RH | $3.00 |
| pH | BPH-1 analog module | ±0.1 (calibrated) | $8.00 |

#### 3D Printed Bioreactor Vessel

**STL Files Required:**
1. `vessel_main.stl` - 150mm H x 80mm OD, 3mm walls
2. `vessel_lid.stl` - M25 threaded, O-ring seal
3. `electrode_holder.stl` - 3-well array (12mm diameter each)
4. `heater_mount.stl` - 5mm channel for 12V silicone pad
5. `sensor_cap.stl` - DHT22 + pH probe mounting

**Print Settings:**
- Material: PETG (food-safe, autoclavable to 70°C)
- Nozzle: 0.4mm
- Layer height: 0.2mm
- Infill: 30% cubic
- Print time: ~6 hours total

#### Power System

| Component | Spec | Cost |
|-----------|------|------|
| Main Power | 5V 2A USB wall adapter | $3.00 |
| Battery | 2x 18650 Li-ion 3000mAh | $6.00 |
| Charger | TP4056 + DW01A protection | $1.00 |
| Buck Converter | LM2596 5V→12V for heater | $1.50 |
| Heating Pad | 12V 5W silicone | $2.50 |

**Power Budget:**
- Idle: 0.1W (200mA @ 5V)
- Measurement: 0.5W (100mA + heating)
- Battery life: 36 hours continuous (2x 18650)

---

### 2.3 BIOSYN-03: Software Stack

#### Signal Processing Pipeline

```
Raw Sensor Data → [Optical/Electrical Processors] → [Temporal Analysis] → [ML Inference] → [Dashboard + Alerts]
```

**Key Processing Modules:**

| Module | Function | Technology |
|--------|----------|------------|
| **OpticalProcessor** | Background subtraction, temp compensation, normalization | Python + OpenCV |
| **ElectricalProcessor** | ADC conversion, noise filtering, drift detection | SciPy signal |
| **TemporalAnalyzer** | State machine (Initializing→Baseline→Response→Alert) | Custom Python |
| **DriftDetector** | Long-term drift monitoring (24hr windows) | Linear regression |

#### ML Pipeline (TFLite)

**Anomaly Detection Model:**
- Architecture: LSTM Autoencoder
- Input: 60-sample sequence × 4 features
  - Feature 0: Normalized signal value
  - Feature 1: Temperature (normalized to 50°C)
  - Feature 2: Rate of change
  - Feature 3: Time of day (cyclical)
- Hidden layers: 32 → 16 → 8 (latent) → 16 → 32
- Output: Reconstructed sequence
- Anomaly threshold: 95th percentile of MSE on training data
- Model size: ~500KB TFLite (quantized float16)

**Inference Performance:**
- Raspberry Pi 4: 12ms per prediction
- Raspberry Pi 3B+: 45ms per prediction
- ESP32 (if edge-inference added later): Not supported directly

#### Backend Services

| Service | Technology | Purpose |
|---------|------------|---------|
| MQTT Broker | Mosquitto 2.0 | Sensor data ingestion |
| Time-Series DB | InfluxDB 2.7 | Data storage |
| API Server | FastAPI + Uvicorn | Dashboard + REST API |
| Real-time | WebSocket | Live dashboard updates |
| Visualization | Grafana + Custom React | Maps, charts, alerts |

**API Endpoints:**
- `GET /api/sensors` - List all sensors
- `GET /api/sensors/{id}/history` - Historical data (InfluxDB)
- `WebSocket /ws` - Real-time updates

#### Alert System

| Threshold Type | Condition | Action |
|----------------|-----------|--------|
| Anomaly | Score > 0.8 for 30s | CRITICAL alert |
| Low Confidence | Confidence < 0.5 for 60s | WARNING alert |
| Temperature | Outside 15-35°C for 120s | WARNING alert |
| Saturation | Signal at max for 10s | CRITICAL alert |
| Contamination | State = CONTAMINATION | EMERGENCY alert |

---

### 2.4 BIOSYN-04: System Integration

#### Network Architecture

```
Sensor Node (ESP32 + LoRa) 
    │
    │ LoRaWAN-Mesh (1-5km range)
    ▼
Gateway (Raspberry Pi 5 + SX1302 + LTE)
    │
    │ MQTT/TLS 1.3 over cellular/satellite
    ▼
Cloud (Kafka → InfluxDB → FastAPI → Dashboard)
```

**Communication Protocols:**
- Node → Gateway: LoRaWAN Class B/C, CBOR payload
- Gateway → Cloud: MQTT 5.0 over TLS 1.3
- Real-time: WebSocket for dashboard

#### Triple Barrier Containment

| Barrier | Implementation | Verification |
|---------|----------------|--------------|
| **Physical** | 0.22 μm PES membrane + IP67 enclosure | Pressure decay test |
| **Genetic** | his3Δ auxotrophy + temperature-sensitive allele | Viability assay |
| **Operational** | Geofencing + 60-day replacement + autoclave protocol | QR tracking |

#### Regulatory Requirements

**USA - TSCA (Toxic Substances Control Act):**
- TSCA Section 5 PMN (Pre-Manufacture Notification) - 90-day review
- TERA (TSCA Experimental Release Application) for field testing
- IBC (Institutional Biosafety Committee) approval

**Key Compliance Documents:**
- Chemical identity: *S. cerevisiae* MYCO-001
- Risk assessment: Human health + ecological
- Containment protocol: Triple barrier system
- Emergency response plan (24hr EPA notification)

#### Deployment Scaling

| Scale | Nodes | Gateways | Timeline | Use Case |
|-------|-------|----------|----------|----------|
| Pilot | 10 | 1 | 2 weeks | Lab validation |
| Field Test | 100 | 5 | 6 weeks | Watershed pilot |
| Production | 1,000+ | 20 | 12 weeks | City-wide network |

---

## 3. DEPENDENCY MATRIX

### 3.1 Cross-Subsystem Dependencies

```
                        BIOSYN-01        BIOSYN-02        BIOSYN-03        BIOSYN-04
                    ┌──────────────┬──────────────┬──────────────┬──────────────┐
    BIOSYN-01       │      X       │   HARD       │   SOFT       │   SOFT       │
    (Synthetic    │              │  Yeast can't │  Signal      │  Regulatory  │
     Biology)     │              │  integrate   │  processing  │  compliance  │
                   │              │  without     │  needs       │  depends on  │
                   │              │  bio-chamber │  bio-signal  │  GMO status  │
    ───────────────────────────────┼──────────────┼──────────────┼──────────────┤
    BIOSYN-02       │   HARD       │      X       │   HARD       │   SOFT       │
    (Hardware)      │  Bio-chamber │              │  Electrical  │  Physical    │
                    │  design      │              │  processing│  deployment  │
                    │  constrains  │              │  algo      │  specs       │
                    │  electrode   │              │  needs HW  │              │
                    │  placement   │              │  data      │              │
    ───────────────────────────────┼──────────────┼──────────────┼──────────────┤
    BIOSYN-03       │   SOFT       │   HARD       │      X       │   SOFT       │
    (ML/Dashboard)  │  Calibration │  Signal      │              │  Cloud       │
                    │  curves      │  processing│              │  deployment  │
                    │  need        │  depends   │              │  needs       │
                    │  strain      │  on ADC    │              │  scalable    │
                    │  data        │  specs     │              │  infra       │
    ───────────────────────────────┼──────────────┼──────────────┼──────────────┤
    BIOSYN-04       │   SOFT       │   SOFT       │   SOFT       │      X       │
    (Integration)   │  GMO         │  Regulatory│  Data        │              │
                    │  compliance│  filings   │  retention   │              │
                    │  needs       │  need      │  policies    │              │
                    │  strain ID   │  specs     │              │              │
    ───────────────────────────────┴──────────────┴──────────────┴──────────────┘
    
    LEGEND:
    HARD = Cannot proceed without completion
    SOFT = Can develop in parallel with some assumptions
    X = Self (diagonal)
```

### 3.2 Internal Dependencies by Subsystem

**BIOSYN-01 (Synthetic Biology):**
```
Gene Synthesis Order ─► Golden Gate Assembly ─► Yeast Transformation ─► PCR Verification ─► Strain Characterization
     (Week 1)              (Week 2)               (Week 3)                 (Week 4)              (Week 5-7)
```

**BIOSYN-02 (Hardware):**
```
PCB Design ─► PCB Order ─► Component Sourcing ───┬───► PCB Assembly ─► Firmware Flash ─► Hardware Test
 (Days 1-3)    (1 week)       (parallel)          │      (Day 10)        (Day 12)         (Day 14)
                                                  │
3D Model Design ─► STL Export ─► Print (6 hrs) ───┘
```

**BIOSYN-03 (Software):**
```
Algorithm Design ─► Python Implementation ───┬───► Docker Container ─► Cloud Deploy ─► Integration Test
    (Days 1-2)         (Days 3-7)            │       (Day 8)             (Day 9)            (Day 10)
                                               │
TFLite Model Train ─► Quantization ─► Export ─┘    ML Pipeline Setup ───┘
```

**BIOSYN-04 (Integration):**
```
TSCA PMN Filing ───► 90-Day Review ───┬───► TERA Application ───► Field Test ────► Scale Deploy
   (Early Start)                      │        (if needed)        (pending approval)
                                      │
Cloud Infra Setup ────────────────────┘
   (Parallel)
```

---

## 4. CRITICAL PATH ANALYSIS

### 4.1 Critical Path Diagram

```
CRITICAL PATH (Longest sequential chain determining minimum timeline):
═══════════════════════════════════════════════════════════════════════════════════

WEEK 1          WEEK 2          WEEK 3          WEEK 4          WEEK 5          WEEK 6          WEEK 7
│               │               │               │               │               │               │
▼               ▼               ▼               ▼               ▼               ▼               ▼
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│   TSCA   │   │  TSCA    │   │  TSCA    │   │   TSCA   │   │ PCB      │   │ Hardware │   │  FULL    │
│   PMN    │   │  REVIEW  │   │  REVIEW  │   │  REVIEW  │   │ ASSEMBLY │   │ + BIO    │   │ SYSTEM   │
│  FILED   │   │  WEEK 1  │   │  WEEK 2  │   │  WEEK 3  │   │ ┌╌╌╌╌╌╌╮ │   │ INTEGRA- │   │  TEST    │
│          │   │          │   │          │   │  (if no  │   │ ┊  Gene  ┊ │   │  TION    │   │          │
│          │   │ ┌╌╌╌╌╌╌╮ │   │ ┌╌╌╌╌╌╌╮ │   │ extension│  │ ┊ Synth  ┊ │   │          │   │          │
│          │   │ ┊3D STL ┊ │   │ ┊ PCB  ┊ │   │  needed) │  │ ┊ Arrives┊ │   │          │   │          │
│          │   │ ┊Prints ┊ │   │ ┊Order ┊ │   │          │  │ └╌╌╌╌╌╌╯ │   │          │   │          │
│          │   │ └╌╌╌╌╌╌╯ │   │ └╌╌╌╌╌╌╯ │   │          │  └─────────┘   │ ┌╌╌╌╌╌╌╮ │   │          │
│          │   │          │   │          │   │          │                │ ┊ Yeast  ┊ │   │          │
│          │   │ ┌╌╌╌╌╌╌╮ │   │ ┌╌╌╌╌╌╌╮ │   │ ┌╌╌╌╌╌╌╮ │                │ ┊  PCR   ┊ │   │          │
│          │   │ ┊Gene  ┊ │   │ ┊Cloud ┊ │   │ ┊ PCB  ┊ │                │ ┊ Verify ┊ │   │          │
│          │   │ ┊Synth ┊ │   │ ┊Setup ┊ │   │ ┊Arrives┊ │                │ └╌╌╌╌╌╌╯ │   │          │
│          │   │ └╌╌╌╌╌╌╯ │   │ └╌╌╌╌╌╌╯ │   │ └╌╌╌╌╌╌╯ │                └──────────┘   └──────────┘
│          │   │          │   │          │   │          │
│          │   │ ┌╌╌╌╌╌╌╮ │   │ ┌╌╌╌╌╌╌╮ │   │ │ ┌╌╌╌╌╌╌╮ │   │                │
│          │   │ ┊ ML   ┊ │   │ ┊ ML   ┊ │   │ ┊ ML   ┊ │   │                │
│          │   │ ┊ Train┊ │   │ ┊ Quant┊ │   │ └╌╌╌╌╌╌╯ │   │                │
│          │   │ └╌╌╌╌╌╌╯ │   │ └╌╌╌╌╌╌╯ │   │          │   │                │
└──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘

PARALLEL TRACKS (can run simultaneously with critical path):
────────────────────────────────────────────────────────────────────────────────────

FIRMWARE:      Week 1-2 (can start immediately, needs hardware for integration test)
CLOUD:         Week 2-3 (can start immediately, ready by Week 5 for integration)
SOFTWARE/MODELS: Week 2-4 (can start immediately, needs data for training)
ANALYTICS:     Week 4-5 (needs some sensor data, can use synthetic for development)

════════════════════════════════════════════════════════════════════════════════════
```

### 4.2 Critical Path Analysis Summary

**Minimum Time to Working System: 7 Weeks**

**Critical Path Items (no float):**
1. **TSCA PMN Filing** → Start immediately, 90-day regulatory clock
2. **Gene Synthesis** → 2-3 week lead time from Twist
3. **Yeast Transformation** → 1 week (depends on DNA arriving)
4. **PCR Verification** → 3 days (confirms integration)
5. **Strain Characterization** → 1 week (dose-response)
6. **Hardware Assembly** → 1 week (can parallelize with bio work)
7. **System Integration Test** → 1 week (requires both streams complete)

**Parallel Work (can proceed without blocking critical path):**
- 3D printing (complete by Week 2)
- PCB ordering (arrives Week 4)
- Cloud infrastructure setup (complete by Week 3)
- ML model training (complete by Week 4)
- Firmware development (ready by Week 5)

**Risk Factors That Could Extend Critical Path:**
- TSCA PMN extension request (+30-90 days)
- Gene synthesis delay (+1-2 weeks)
- Yeast transformation failure (restart Week 3)
- PCB defects (reorder Week 5)

---

## 5. BUILD SEQUENCE PHASES

### Phase 0: Immediate Actions (Week 0 - Start Now)

**TSCA PMN Preparation (BIOSYN-04 Lead):**
- [ ] Draft Chemical Identity section (*S. cerevisiae* MYCO-001)
- [ ] Compile Risk Assessment (human health + ecological)
- [ ] Document Triple Barrier Containment Protocol
- [ ] Prepare Exposure Assessment (release scenarios)
- [ ] File TSCA PMN with EPA (starts 90-day clock)
- **DELIVERABLE:** TSCA PMN Filing Confirmation

**Parallel Starts (All Teams):**
- [ ] BIOSYN-01: Design review, order primers
- [ ] BIOSYN-02: PCB schematic review, component sourcing
- [ ] BIOSYN-03: Algorithm design, select ML framework version
- [ ] BIOSYN-04: Cloud architecture, select CSP (AWS/GCP/Azure)

---

### Phase 1: Foundation (Weeks 1-2)

**BIOSYN-01 (Synthetic Biology):**
- [ ] Order integration cassette from Twist Bioscience (2,960 bp)
- [ ] Order pML104 from Addgene (#67638)
- [ ] Design HO gRNA oligos (Top: TAGGTGTGGTGTGTGTGTGTGTG)
- [ ] Prepare yeast competent cells (BY4741)
- **DELIVERABLE:** All DNA materials ordered, arrival confirmed

**BIOSYN-02 (Hardware):**
- [ ] Finalize PCB design (KiCad)
- [ ] Order PCB fabrication (JLCPCB, 5-day turn)
- [ ] Source components (Digi-Key/Mouser order)
- [ ] Print 3D vessel components (PETG)
- **DELIVERABLE:** PCB design files, component kit, printed vessels

**BIOSYN-03 (Software):**
- [ ] Set up development environment (Docker, Python 3.11)
- [ ] Implement OpticalProcessor module
- [ ] Implement ElectricalProcessor module
- [ ] Set up InfluxDB + Mosquitto locally
- **DELIVERABLE:** Working signal processing modules

**BIOSYN-04 (Integration):**
- [ ] Provision cloud infrastructure (VPC, subnets)
- [ ] Set up Kafka cluster (or AWS Kinesis)
- [ ] Configure InfluxDB Cloud instance
- [ ] Draft regulatory compliance documentation
- **DELIVERABLE:** Cloud environment ready for deployment

---

### Phase 2: Assembly (Weeks 3-4)

**BIOSYN-01 (Synthetic Biology) - CRITICAL PATH:**
- [ ] Receive gene synthesis from Twist
- [ ] Clone gRNA into pML104 (Golden Gate)
- [ ] Linearize integration cassette
- [ ] Yeast LiAc/PEG transformation (Day 1-3)
- [ ] Plate on SC-URA selection (Day 3-5)
- **DELIVERABLE:** Transformants growing on plates

**BIOSYN-02 (Hardware):**
- [ ] Receive PCBs from fab
- [ ] Solder LMP91000 + op-amp section (precision soldering)
- [ ] Assemble ESP32 + sensor connectors
- [ ] Assemble 5 prototype units
- **DELIVERABLE:** 5 assembled hardware prototypes

**BIOSYN-03 (Software):**
- [ ] Implement TemporalAnalyzer state machine
- [ ] Train LSTM autoencoder (synthetic data acceptable)
- [ ] Convert to TFLite format
- [ ] Implement FastAPI endpoints
- **DELIVERABLE:** Working dashboard + TFLite model

**BIOSYN-04 (Integration):**
- [ ] Deploy MQTT broker (Mosquitto)
- [ ] Set up authentication (TLS certs)
- [ ] Create Docker Compose for full stack
- [ ] Implement data retention policies
- **DELIVERABLE:** Integrated cloud platform

---

### Phase 3: Verification (Week 5)

**BIOSYN-01 (Synthetic Biology) - CRITICAL PATH:**
- [ ] Colony PCR verification (HO locus integration)
- [ ] Verify positive colonies: expect 4,200 bp band
- [ ] Expand 3-5 positive clones
- [ ] Prepare glycerol stocks
- **DELIVERABLE:** 3-5 verified integrant strains

**Cross-Team Integration:**
- [ ] Load bio-chamber with verified strain
- [ ] Install chamber in hardware prototype
- [ ] Flash firmware with strain-specific calibration
- [ ] Connect to cloud MQTT broker
- [ ] Run baseline measurements (24 hours)
- **DELIVERABLE:** Integrated biosensor node (strain + hardware + software)

**BIOSYN-03 (Validation):**
- [ ] Validate signal processing pipeline
- [ ] Test anomaly detection with synthetic data
- [ ] Verify dashboard real-time updates
- [ ] Calibrate pH/temp sensors
- **DELIVERABLE:** Validated software stack

---

### Phase 4: Characterization (Week 6)

**BIOSYN-01 (Dose-Response):**
- [ ] Prepare HgCl₂ standards (0.01 μM to 1000 μM)
- [ ] Run dose-response assay (96-well plate)
- [ ] Measure time course: 0, 0.5, 1, 2, 4, 6 hours
- [ ] Fit Hill equation, calculate LOD, EC50
- [ ] Run specificity panel (Cd²⁺, Pb²⁺, As³⁺, etc.)
- **DELIVERABLE:** Characterization report with LOD, EC50, specificity matrix

**BIOSYN-02 (Hardware Optimization):**
- [ ] Optimize electrochemical parameters
- [ ] Calibrate temperature compensation
- [ ] Test power consumption (battery life validation)
- [ ] Environmental testing (IP67, thermal)
- **DELIVERABLE:** Calibrated hardware, BOM locked

**BIOSYN-03 (ML Training):**
- [ ] Collect real biosensor data (if PMN cleared)
- [ ] OR: Continue with synthetic + lab data
- [ ] Fine-tune anomaly detection threshold
- [ ] Implement drift correction algorithm
- **DELIVERABLE:** Trained TFLite model on real/quality synthetic data

**BIOSYN-04 (Regulatory):**
- [ ] TSCA PMN Day 60 checkpoint
- [ ] Prepare TERA application (if field test planned)
- [ ] Draft field deployment SOP
- **DELIVERABLE:** Regulatory status report, TERA ready to file

---

### Phase 5: System Test (Week 7)

**Full System Integration:**
- [ ] Deploy 3-node pilot network
- [ ] Gateways online, MQTT flowing
- [ ] Run 48-hour continuous monitoring
- [ ] Inject known Hg²⁺ spike, verify detection
- [ ] Test alert system (email/SMS notifications)
- [ ] Validate cloud dashboard data accuracy
- [ ] Document end-to-end latency (< 30s target)
- **DELIVERABLE:** Validated system, test report

**Documentation:**
- [ ] Update all subsystem docs with as-built specs
- [ ] Create field deployment guide
- [ ] Finalize regulatory compliance package
- **DELIVERABLE:** Complete documentation package

---

## 6. DELIVERABLES CHECKLIST

### BIOSYN-01 Deliverables

| ID | Deliverable | Due | Status |
|----|-------------|-----|--------|
| SB-01 | Complete integration cassette DNA (2,960 bp) | Week 3 | ⬜ |
| SB-02 | Verified integrant yeast strain (PCR confirmed) | Week 5 | ⬜ |
| SB-03 | Glycerol stock (3-5 clones) | Week 5 | ⬜ |
| SB-04 | Dose-response characterization report | Week 6 | ⬜ |
| SB-05 | LOD/EC50/Specificity data | Week 6 | ⬜ |
| SB-06 | Bio-chamber SOP (inoculation to disposal) | Week 7 | ⬜ |

### BIOSYN-02 Deliverables

| ID | Deliverable | Due | Status |
|----|-------------|-----|--------|
| HW-01 | PCB design files (KiCad + Gerbers) | Week 2 | ⬜ |
| HW-02 | 5 assembled prototype units | Week 4 | ⬜ |
| HW-03 | 3D printed vessel set (5 units) | Week 2 | ⬜ |
| HW-04 | Firmware (ESP32 flashed, MQTT working) | Week 5 | ⬜ |
| HW-05 | BOM + cost analysis (<$60 confirmed) | Week 5 | ⬜ |
| HW-06 | Hardware calibration data | Week 6 | ⬜ |

### BIOSYN-03 Deliverables

| ID | Deliverable | Due | Status |
|----|-------------|-----|--------|
| SW-01 | Signal processing modules (optical + electrical) | Week 2 | ⬜ |
| SW-02 | Temporal analyzer with state machine | Week 3 | ⬜ |
| SW-03 | TFLite anomaly detection model (500KB) | Week 4 | ⬜ |
| SW-04 | FastAPI backend + WebSocket | Week 4 | ⬜ |
| SW-05 | React/Grafana dashboard | Week 4 | ⬜ |
| SW-06 | Docker Compose for full deployment | Week 5 | ⬜ |
| SW-07 | Alert system (thresholds + notifications) | Week 5 | ⬜ |

### BIOSYN-04 Deliverables

| ID | Deliverable | Due | Status |
|----|-------------|-----|--------|
| INT-01 | TSCA PMN filed | Week 0 | ⬜ |
| INT-02 | Cloud infrastructure provisioned | Week 2 | ⬜ |
| INT-03 | MQTT broker configured (TLS + auth) | Week 3 | ⬜ |
| INT-04 | InfluxDB + data retention policies | Week 3 | ⬜ |
| INT-05 | Gateway deployment package | Week 4 | ⬜ |
| INT-06 | Field deployment SOP | Week 6 | ⬜ |
| INT-07 | Regulatory compliance package | Week 7 | ⬜ |

---

## 7. RISK & MITIGATION

### 7.1 Critical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **TSCA PMN rejection** | Low | Critical | Early EPA engagement, strong containment narrative, IBC pre-review |
| **Gene synthesis delay** | Medium | High | Order from 2 providers, keep primers ready for backup PCR |
| **Yeast transformation failure** | Medium | High | Optimize LiAc protocol, maintain multiple batches of competent cells |
| **LMP91000 supply shortage** | Medium | Medium | Order 2x needed qty, identify discrete potentiostat alternative |
| **LoRa range issues** | Low | Medium | Design for mesh networking, LTE fallback in gateway |
| **Anomaly detection poor accuracy** | Low | Medium | Synthetic training data fallback, rule-based alerts as backup |

### 7.2 Contingency Plans

**If TSCA PMN extends beyond 90 days:**
- Continue all development with containment assumed
- Prepare TERA for limited field testing
- Shift focus to in-lab demonstration

**If yeast strain non-functional:**
- Pivot to E. coli chassis (faster, though BL2 requirements)
- Alternative: Cell-free system (no organism, pure protein)

**If hardware costs exceed $60:**
- Deprioritize display module (saves $3)
- Switch to discrete op-amp potentiostat (saves $6)
- Remove pH probe (savings $8, use manual calibration)

---

## APPENDIX A: Quick Reference

### Contact Directory

| Role | Team | Responsibility |
|------|------|----------------|
| Synthetic Biologist | BIOSYN-01 | Strain construction, characterization |
| Hardware Engineer | BIOSYN-02 | PCB, enclosure, electrochemical system |
| ML Engineer | BIOSYN-03 | Anomaly detection, dashboard |
| Integration Lead | BIOSYN-04 | Deployment, regulatory, system integration |

### Key Suppliers

| Item | Supplier | Lead Time | Cost |
|------|----------|-----------|------|
| Gene synthesis (3kb) | Twist Bioscience | 2-3 weeks | $300-400 |
| Cas9 plasmid | Addgene #67638 | 1 week | $65 |
| LMP91000 | Digi-Key | Stock | $6 |
| ESP32 dev kit | AliExpress | 2 weeks | $4.50 |
| PCB fabrication | JLCPCB | 5 days | $5-10 |

### Regulatory Contacts

- EPA TSCA Assistance: TSCA-Hotline@epa.gov
- USDA APHIS BRS: (301) 851-8510
- State EPA: [Lookup by state]

---

**DOCUMENT CONTROL**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| v1.0 | 2026-03-28 | BUILD AGENT | Initial unified manifest |

**NEXT REVIEW:** 2026-04-04 (1 week) or upon design change

---

*"Build fast, test early, contain carefully, deploy wisely."*
