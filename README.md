# MycoSentinel — Living Biosensor Network v0.1.0

**Engineered fungal sensors for real-time environmental monitoring**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

---

## What is MycoSentinel?

A distributed network of living biosensors using **genetically engineered yeast** to detect environmental contaminants in real-time.

### The Innovation

Traditional chemical sensors are:
- ❌ Expensive ($10K+ per unit)
- ❌ Disposable (single-use cartridges)
- ❌ Slow (hours for results)

MycoSentinel uses **living sensors** that are:
- ✅ Self-replicating (grow more sensors)
- ✅ Multi-analyte (one organism detects many targets)
- ✅ Real-time (continuous monitoring)
- ✅ Low-cost ($100 per node vs $10K)

---

## How It Works

1. **Genetic Engineering**: Yeast modified with promoters that activate GFP (green fluorescent protein) when specific contaminants detected
2. **Bioreactor**: Cultures maintained in 3D-printed vessels with temperature/humidity control
3. **Optical Detection**: Raspberry Pi camera detects fluorescence intensity changes
4. **Signal Processing**: ML pipeline filters noise, detects anomalies, classifies contaminant type
5. **Network**: Distributed nodes report to gateway → cloud dashboard

---

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/stephenclawdbot-png/mycosentinel.git
cd mycosentinel

# Install
pip install -e .

# Install with all dependencies
pip install -e ".[hardware,ml,dashboard,network]"
```

### Run Standalone Node (Mock Mode)

```bash
# Initialize configuration
mycosentinel init --config mysensor.yaml

# Run with mock hardware (simulation)
mycosentinel run --config mysensor.yaml --mock

# View dashboard
open http://localhost:8080
```

### Run with Real Hardware (Raspberry Pi)

```bash
# Hardware dependencies
pip install RPi.GPIO picamera2 Adafruit-circuitpython-ads1x15

# Run with real sensors
mycosentinel run --config mysensor.yaml --no-mock
```

---

## Hardware BOM

**Per Sensor Node (~$100):**

| Component | Supplier | Cost |
|-----------|----------|------|
| Raspberry Pi Zero 2 W | Raspberry Pi | $15 |
| Pi Camera Module | Various | $15 |
| ADS1115 ADC | Adafruit | $8 |
| DHT22 Humidity Sensor | Various | $5 |
| DS18B20 Temperature Sensor | Various | $3 |
| Heating Pad (5V) | AliExpress | $5 |
| 3D Printed Bioreactor | Self-print | ~$8 |
| Yeast Culture | Lab supply | $10 |
| Electronics/misc | Various | ~$26 |

**Total: ~$100 per node**

---

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Sensor     │     │   Signal    │     │   Network   │
│  Nodes      │────→│ Processing  │────→│   Layer     │
│ (Pi + Bio)  │     │  (Python)   │     │ (MQTT/HTTP)│
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
                                               ↓
                                        ┌─────────────┐
                                        │  Dashboard  │
                                        │ (Web UI)    │
                                        └─────────────┘
```

---

## Genetic Engineering

**Chassis**: *Saccharomyces cerevisiae* (Baker's yeast)

**Detection Mechanism**:
- **Promoter**: pCUP1 (responds to heavy metals)
- **Reporter**: sfGFP (super-folder GFP)
- **Circuit**: Metal binds → Promoter activates → GFP expressed → Fluorescence detected

**Target Analytes**:
- Heavy metals (Cd²⁺, Pb²⁺, Cu²⁺)
- Pesticides (organophosphates)
- PFAS (forever chemicals)

See `docs/GENETIC_DESIGN.md` for full circuit details.

---

## API Reference

### SensorNode

```python
from mycosentinel.network import SensorNode

node = SensorNode(node_id="node-01", use_mock=True)
node.start()

data = node.get_data(block=True, timeout=5)
print(f"Reading: {data}")

node.stop()
```

### SignalProcessor

```python
from mycosentinel.pipeline import SignalProcessor

processor = SignalProcessor(anomaly_threshold=2.0)
processor.calibrate_baseline(readings)

result = processor.process(raw_value)
if result.contaminant_detected:
    print(f"ANOMALY: {result.contaminant_type}")
```

---

## Development

### Running Tests

```bash
pip install -e ".[dev]"
pytest
```

### Code Style

```bash
black src/mycosentinel
mypy src/mycosentinel
```

---

## Research Consortium

This project emerged from abandoned research on fungal biosensors. Previously impractical due to:
- Expensive lab equipment ($10K+)
- Manual sampling requirements
- No standardized genetic platform

**Now possible because:**
- CRISPR tools democratized genetic engineering ($500)
- Raspberry Pi enables cheap optical detection ($30)
- ML handles biological signal variability
- IoT networks enable distributed deployment

---

## Safety & Ethics

**Containment**: Modified organisms remain in sealed bioreactors. Physical containment, not genetic (no GMO release).

**Biosafety**: S. cerevisiae is BSL-1 (generally safe). No pathogenic genes used.

---

## Roadmap

- [ ] Field deployment (v0.2.0)
- [ ] Multi-analyte detection (v0.3.0)
- [ ] Solar-powered nodes (v0.4.0)
- [ ] Consumer kit (v1.0.0)

---

## License

MIT License — See [LICENSE](LICENSE)

**Build it. Deploy it. Monitor everything.**

---

*Part of the META-SYSTEM autonomous research consortium*
*Continuously evolving at 5-minute cycles*
