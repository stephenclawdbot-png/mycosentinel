# MycoSentinel Deployment Guide v0.1.0
## Field Deployment - 10-Node Network

**Goal:** Deploy a working 10-node biosensor network in 1 day  
**Hardware Cost:** ~$1,000 ($100/node) + $200 (gateway)  
**Prerequisites:** Raspberry Pi Zero 2 W running Raspberry Pi OS Lite

---

## 📡 Network Topology Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         10-NODE FIELD DEPLOYMENT                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   Range: ~500m radius from gateway                                              │
│   Frequency: 2.4 GHz WiFi (Mesh/Star) OR LoRa (if equipped)                   │
│   Power: Solar + Battery (autonomous)                                           │
│                                                                                  │
│   ┌────────────────────────────────────────────────────────────┐                 │
│   │                    ☀️ GATEWAY NODE                        │                 │
│   │              Raspberry Pi 4/5 + SSD + MQTT Broker          │                 │
│   │              192.168.1.100 (static IP)                      │                 │
│   │              mosquitto + grafana + node-red               │                 │
│   └──────────────────┬───────────────────────────────────────┘                 │
│                      │                                                           │
│        ══════════════╪═══════════════════════════════════════                  │
│         WiFi/LoRa   │                                                          │
│                     │                                                           │
│    ┌────────────────┼────────────────┐                                          │
│    │                │                │                                          │
│    ▼                ▼                ▼                                          │
│ ┌──────┐      ┌──────┐      ┌──────┐                                          │
│ │NODE 1│◄────►│NODE 2│◄────►│NODE 3│  Sector A (0-120°)                      │
│ │ MS01 │      │ MS02 │      │ MS03 │  Distance: 50-150m from gateway          │
│ └──────┘      └──────┘      └──────┘                                          │
│    │                │                │                                          │
│    ▼                ▼                ▼                                          │
│ ┌──────┐      ┌──────┐      ┌──────┐                                          │
│ │NODE 4│      │NODE 5│      │NODE 6│  Sector B (120-240°)                    │
│ │ MS04 │      │ MS05 │      │ MS06 │  Distance: 100-200m from gateway        │
│ └──────┘      └──────┘      └──────┘                                          │
│    │                │                │                                          │
│    ▼                ▼                ▼                                          │
│ ┌──────┐      ┌──────┐      ┌──────┐      ┌──────┐                              │
│ │NODE 7│      │NODE 8│      │NODE 9│      │NODE 10│  Sector C (240-360°)        │
│ │ MS07 │      │ MS08 │      │ MS09 │      │ MS10  │  Distance: 50-150m         │
│ └──────┘      └──────┘      └──────┘      └──────┘                              │
│                                                                                  │
│   Node Naming: MS-{SECTOR}{NUMBER}                                               │
│   • MS-A1, MS-A2, MS-A3 (Sector A)                                              │
│   • MS-B1, MS-B2, MS-B3 (Sector B)                                              │
│   • MS-C1, MS-C2, MS-C3, MS-C4 (Sector C)                                       │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                         PHYSICAL DEPLOYMENT MAP                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│      [Gateway] = Home Base (shed, building, vehicle)                           │
│      ◯ = Sensor Node on stake/pole                                               │
│      ~ = Water body (river, pond, monitoring site)                              │
│                                                                                  │
│                     N ↑                                                          │
│                       │                                                          │
│         ◯ MS-C3    ◯ MS-C4    ~ ~ ~ River                                     │
│                       │                                                          │
│     ◯ MS-B2    [GATEWAY]    ◯ MS-A3                                           │
│                       │                                                          │
│         ◯ MS-C2    ◯ MS-C1    ~ ~ ~                                           │
│                       │                                                          │
│     ◯ MS-B1        ◯ MS-A2    ◯ MS-A1                                         │
│                       │                                                          │
│         ◯ MS-B3              Field/Farm                                         │
│                                                                                  │
│   Spacing: 50-100m between nodes for spatial coverage                           │
│   Height: Nodes at 1-2m above ground                                            │
│   Protection: IP67 enclosures, UV-resistant                                     │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔧 Physical Assembly Instructions

### Pre-Deployment Checklist (Day Before)

**Per Node (×10):**
- [ ] Raspberry Pi Zero 2 W flashed with OS
- [ ] Pi Camera Module connected and tested
- [ ] ADS1115 ADC wired and addressed (0x48, 0x49, etc.)
- [ ] DHT22/DS18B20 temperature sensors working
- [ ] Heating pad controller functional
- [ ] Misting solenoid responds to GPIO
- [ ] LEDs (growth + detection) working
- [ ] Bioreactor 3D-printed and sterilized
- [ ] Bio-chamber inoculated with S. cerevisiae
- [ ] Solar panel + charge controller + battery tested
- [ ] IP67 enclosure sealed and wired
- [ ] Antenna connected (WiFi or LoRa)

**Gateway (×1):**
- [ ] Raspberry Pi 4/5 with 4GB+ RAM
- [ ] SSD for data storage (128GB minimum)
- [ ] Ethernet connection OR cellular modem
- [ ] mosquitto MQTT broker installed
- [ ] Static IP configured (192.168.1.100)
- [ ] Docker + docker-compose installed
- [ ] Firewall rules for ports 1883, 9001, 3000, 8080

---

### Step-by-Step Node Assembly

#### Step 1: Electronics Assembly (30 min/node)

```
┌─────────────────────────────────────────────────────────────────┐
│                    NODE ELECTRONICS LAYOUT                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                PI ZERO 2 W  (40-pin GPIO)              │   │
│   │                                                         │   │
│   │  3V3  [ 1] [ 2]  5V                                     │   │
│   │  GPIO2 [ 3] [ 4]  5V   ──► DHT22 DATA                   │   │
│   │  GPIO3 [ 5] [ 6]  GND  ──► GND BUS                       │   │
│   │  GPIO4 [ 7] [ 8]  GPIO14 ──► UART TX (optional)         │   │
│   │  GND   [ 9] [10]  GPIO15 ──► UART RX (optional)         │   │
│   │  GPIO17[11] [12]  GPIO18 ──► HEATER PWM (GPIO 18)       │   │
│   │  GPIO27[13] [14]  GND                                   │   │
│   │  GPIO22[15] [16]  GPIO23 ──► MIST SOLENOID              │   │
│   │  3V3   [17] [18]  GPIO24 ──► GROWTH LED                 │   │
│   │  GPIO10[19] [20]  GND                                   │   │
│   │  GPIO9 [21] [22]  GPIO25 ──► UV LED / DETECTION LED     │   │
│   │  GPIO11[23] [24]  GPIO8  ──► SPI CE0 (ADC)              │   │
│   │  GND   [25] [26]  GPIO7  ──► SPI CE1 (ADC2)             │   │
│   │  GPIO0 [27] [28]  GPIO1  ──► ID EEPROM (HAT)            │   │
│   │  GPIO5 [29] [30]  GND                                   │   │
│   │  GPIO6 [31] [32]  GPIO12 ──► PWM2 (Fan)                 │   │
│   │  GPIO13[33] [34]  GND                                   │   │
│   │  GPIO19[35] [36]  GPIO16 ──► 1-Wire Temp (DS18B20)      │   │
│   │  GPIO26[37] [38]  GPIO20                                  │   │
│   │  GND   [39] [40]  GPIO21 ──► Camera LED                 │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│   ┌───────────┐      ┌───────────┐      ┌───────────┐          │
│   │ ADS1115   │      │ ADS1115   │      │ DHT22     │          │
│   │ (0x48)    │      │ (0x49)    │      │           │          │
│   │           │      │           │      │ VCC ── 3V3│          │
│   │ VCC ── 3V3│      │ VCC ── 3V3│      │ GND ── GND│          │
│   │ GND ── GND│      │ GND ── GND│      │ DATA ─►GPIO2│         │
│   │ SCL ── SCL│      │ SCL ── SCL│      │           │          │
│   │ SDA ── SDA│      │ SDA ── SDA│      │ 10K to 3V3│          │
│   │ ADDR─ GND │      │ ADDR─ VCC │      └───────────┘          │
│   └───────────┘      └───────────┘                               │
│        │                    │                                    │
│        └────────────────────┬────────────────────┐             │
│                             ▼                    ▼             │
│                      ┌─────────────┐      ┌─────────────┐       │
│                      │ I2C Bus     │      │ HEATER      │       │
│                      │ SDA: GPIO2  │      │ Controller│       │
│                      │ SCL: GPIO3  │      │ 5V Input  │       │
│                      └─────────────┘      │ PWM: GPIO18│       │
│                                            └─────────────┘       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Wiring Instructions:**

1. **Power Distribution:**
   ```bash
   # 5V Rail (from battery/charge controller)
   5V ──┬──► Pi Zero 5V pin (pin 2 or 4)
        ├──► ADS1115 VCC
        ├──► Heater controller VCC
        ├──► Misting solenoid VCC (via transistor)
        └──► LED drivers VCC (via transistors)
   
   # 3V3 Rail (from Pi)
   3V3 ──┬──► DHT22 VCC
         ├──► ADS1115 VCC (if 3V3 version)
         └──► Pull-up resistors
   
   # Ground (common)
   GND ──┬──► All components
         └──► Battery ground
   ```

2. **I2C Bus (GPIO 2 & 3):**
   ```
   GPIO 2 (SDA) ──► ADS1115 SDA ──► DHT22 DATA
   GPIO 3 (SCL) ──► ADS1115 SCL
   ```
   Add 4.7kΩ pull-ups to 3V3 on SDA and SCL lines

3. **Control Outputs:**
   ```
   GPIO 18 (PWM) ──► MOSFET Gate ──► Heating Pad
   GPIO 23 ──► 2N2222 Base ──► Misting Solenoid
   GPIO 24 ──► 2N2222 Base ──► Growth LED
   GPIO 25 ──► 2N2222 Base ──► Detection LED
   ```

4. **Sensor Inputs:**
   ```
   ADC0 (0x48) ──► Photodiode/Optical sensor
   ADC1 (0x48) ──► pH probe
   ADC0 (0x49) ──► Conductivity (optional)
   GPIO 16 ──► 1-Wire bus ──► DS18B20 temperature
   ```

#### Step 2: Bioreactor Integration (20 min/node)

```
┌─────────────────────────────────────────────────────────────────┐
│                    BIOREACTOR ASSEMBLY                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              3D PRINTED BIOREACTOR VESSEL               │   │
│   │                      (PETG, 100% infill)               │   │
│   │                                                         │   │
│   │     ┌───────────────────────────────────────────┐      │   │
│   │     │                 LID                      │      │   │
│   │     │  ┌─────┐    ┌─────────┐    ┌─────┐       │      │   │
│   │     │  │Mist │    │ Camera  │    │Vent │       │      │   │
│   │     │  │Nozzle│    │  Port   │    │Port │       │      │   │
│   │     │  └──┬──┘    └────┬────┘    └──┬──┘       │      │   │
│   │     └─────┼────────────┼────────────┼───────────┘      │   │
│   │           │            │            │                 │   │
│   │     ══════╪════════════╪════════════╪══════════════    │   │
│   │           │            │            │                 │   │
│   │     ┌─────┴────────────┴────────────┴─────┐          │   │
│   │     │        CHAMBER VOLUME: 50mL        │          │   │
│   │     │  ┌─────────────────────────────┐   │          │   │
│   │     │  │  ═══════════════════════    │   │          │   │
│   │     │  │   Yeast Culture + Media      │   │          │   │
│   │     │  │   (S. cerevisiae + YPD)     │   │          │   │
│   │     │  │                              │   │          │   │
│   │     │  │   • Heating Pad (under)    │   │          │   │
│   │     │  │   • Temp Sensor (side)      │   │          │   │
│   │     │  │   • LED Ring (top)          │   │          │   │
│   │     │  └─────────────────────────────┘   │          │   │
│   │     └─────────────────────────────────────┘          │   │
│   │                                                         │   │
│   │  • O-ring seal (Viton, 2mm)                           │   │
│   │  • Threaded connections (BSP or NPT)                  │   │
│   │  • UV-C transparent window (quartz or fused silica)   │   │
│   │  • Sample port (luer lock, sterile)                     │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Assembly Steps:**

1. **Install Heating Element:**
   - Apply thermal paste to heating pad
   - Press into channel on vessel bottom
   - Secure with RTV silicone (food-grade)

2. **Route Temperature Sensor:**
   - Insert DS18B20 into 3mm well on vessel side
   - Seal with thermal epoxy
   - Connect to 1-Wire bus

3. **Install LED Ring:**
   - Solder LED ring (WS2812B or similar) to PCB
   - Position above viewing window
   - Connect to GPIO 24 (growth) and GPIO 25 (detection)

4. **Seal Chamber:**
   - Install O-ring in lid groove
   - Apply thin layer of silicone grease
   - Hand-tighten lid (don't overtighten)

5. **Camera Alignment:**
   - Mount Pi Camera above viewing window
   - Adjust focus (twist lens until sharp)
   - Secure with hot glue or bracket

#### Step 3: Solar Power Integration (15 min/node)

```
┌─────────────────────────────────────────────────────────────────┐
│                     SOLAR POWER SYSTEM                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌──────────┐     ┌──────────────┐     ┌──────────────┐       │
│   │ SOLAR    │     │ CHARGE       │     │ BATTERY      │       │
│   │ PANEL    │────►│ CONTROLLER   │────►│ 18650 Li-Ion │       │
│   │ 5W 6V    │     │ (TP4056 or   │     │ 2S 7.4V      │       │
│   │          │     │  CN3791)     │     │ 3000mAh×2    │       │
│   └──────────┘     └──────────────┘     └──────┬───────┘       │
│        │                                       │                │
│        │                                       ▼                │
│        │                                ┌──────────────┐       │
│        │                                │ BOOST CONV   │       │
│        │                                │ (XL6009)     │       │
│        │                                │ 7.4V → 5V    │       │
│        │                                └──────┬───────┘       │
│        │                                       │                │
│        └───────────────────────────────────────┘                │
│                  (Daytime charging path)                         │
│                                                                 │
│   Calculations for 24h autonomy:                                │
│   ───────────────────────────────                                │
│   • Pi Zero 2 W + sensors: ~200mA @ 5V = 1W                    │
│   • Heater (cycling): ~500mA @ 5V = 2.5W (25% duty = 0.6W)    │
│   • LED (intermittent): ~100mA = 0.5W                         │
│   Total: ~2W average                                          │
│   Daily: 48Wh                                                │
│   Battery: 7.4V × 3Ah = 22.2Wh                                │
│   Need: 2 days autonomy = 96Wh → 48Ah @ 2S (or 24Ah @ 4S)    │
│                                                                 │
│   Recommended: 4S 14.8V 10Ah LiFePO4 (148Wh) → 3 days       │
│   Solar: 20W panel minimum for winter charging                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Wiring:**
```
Solar Panel (+/-) ──► Charge Controller (Solar +/-)
Battery (+/-) ──► Charge Controller (Battery +/-)
Charge Controller (Load +/-) ──► Boost Converter ──► Pi Zero USB or GPIO 5V
```

---

## 📊 MQTT Broker Setup (Mosquitto)

### Gateway Configuration

Create `mosquitto.conf`:

```conf
# /etc/mosquitto/mosquitto.conf

# Basic settings
listener 1883
protocol mqtt

# WebSocket for dashboard
listener 9001
protocol websockets

# Persistence
persistence true
persistence_location /var/lib/mosquitto/
log_dest file /var/log/mosquitto/mosquitto.log

# Security (for field deployment - set passwords!)
allow_anonymous false
password_file /etc/mosquitto/passwd

# ACL for node/gateway separation
acl_file /etc/mosquitto/acl

# Message size (for image data)
max_packet_size 1048576
max_inflight_messages 100
max_keepalive 1200

# Bridge to cloud (optional)
# connection cloud
# address cloud.mycosentinel.io:8883
# remote_username cloud_user
# remote_password cloud_pass
# topic # both 0
```

Create password file:
```bash
# On gateway
sudo mosquitto_passwd -c /etc/mosquitto/passwd gateway
sudo mosquitto_passwd /etc/mosquitto/passwd node01
sudo mosquitto_passwd /etc/mosquitto/passwd node02
# ... etc for all nodes
```

Create ACL file:
```conf
# /etc/mosquitto/acl

# Gateway can read/write everything
user gateway
topic readwrite #

# Nodes can only publish to their own topic and read commands
user node01
topic write mycosentinel/nodes/node01/data
topic write mycosentinel/nodes/node01/status
topic read mycosentinel/nodes/node01/cmd

user node02
topic write mycosentinel/nodes/node02/data
topic write mycosentinel/nodes/node02/status
topic read mycosentinel/nodes/node02/cmd

# Pattern for all nodes (if using node01-node10 naming)
pattern write mycosentinel/nodes/%u/data
pattern write mycosentinel/nodes/%u/status
pattern read mycosentinel/nodes/%u/cmd
```

### Topic Structure

```
mycosentinel/
├── nodes/
│   ├── node01/
│   │   ├── data          # Sensor readings (JSON)
│   │   ├── status        # Online/offline, battery
│   │   └── cmd           # Commands from gateway
│   ├── node02/
│   │   └── ...
│   └── ...
├── gateway/
│   ├── status            # Gateway health
│   └── alerts            # Aggregated alerts
└── system/
    ├── calibration       # Calibration events
    └── firmware          # OTA updates
```

### Message Format (JSON)

**Data Packet:**
```json
{
  "node_id": "node01",
  "timestamp": 1711593600.123,
  "geo": {
    "lat": 40.7128,
    "lon": -74.0060,
    "accuracy": 5
  },
  "readings": {
    "optical_raw": 2847,
    "optical_filtered": 2834,
    "fluorescence_intensity": 145.2,
    "temperature_c": 28.5,
    "humidity_pct": 65.0,
    "heater_duty": 0.35,
    "battery_v": 3.85
  },
  "detection": {
    "contaminant_detected": false,
    "anomaly_score": 1.23,
    "confidence": 0.85,
    "candidates": ["none"]
  },
  "meta": {
    "uptime_sec": 86400,
    "firmware": "0.1.0",
    "calibration_age_days": 3
  }
}
```

---

## 🔬 Field Calibration Procedure

### Pre-Deployment Calibration (Lab)

**Step 1: Optical Baseline** (30 min)
```python
# Run on each node before field deployment
from mycosentinel.sensor import OpticalSensor
from mycosentinel.pipeline import SignalProcessor

sensor = OpticalSensor(use_mock=False)
processor = SignalProcessor()

# Collect 30 min baseline with sterile media
baseline_readings = []
for i in range(1800):  # 30 min @ 1Hz
    reading = sensor.capture()
    baseline_readings.append(reading.value)
    time.sleep(1)

# Calculate statistics
mean_baseline = np.mean(baseline_readings)
std_baseline = np.std(baseline_readings)

processor.calibrate_baseline(baseline_readings)

# Save to node
with open('/opt/mycosentinel/calibration.json', 'w') as f:
    json.dump({
        'baseline_mean': mean_baseline,
        'baseline_std': std_baseline,
        'timestamp': time.time()
    }, f)
```

**Step 2: Temperature Calibration** (15 min)
```python
# Use external thermometer for reference
import subprocess

reference_temps = [15, 20, 25, 30, 35]  # °C (use water bath)
calibration_points = []

for temp in reference_temps:
    input(f"Set water bath to {temp}°C, press Enter when stable...")
    readings = []
    for _ in range(60):
        reading = read_ds18b20()
        readings.append(reading)
        time.sleep(1)
    avg_reading = np.mean(readings)
    calibration_points.append((temp, avg_reading))

# Fit linear correction
slope, intercept, r, _, _ = linregress(calibration_points)
print(f"Correction: True = {slope:.4f} × Reading + {intercept:.2f}")
```

**Step 3: Known Standard Response** (60 min)
```python
# Test with known concentration of target analyte
# Requires: Prepared yeast with known promoter activation

concentrations = [0, 0.1, 1, 10, 100]  # µM or µg/L
responses = []

for conc in concentrations:
    # Inject standard into chamber
    inject_standard(conc)
    time.sleep(300)  # Wait 5 min for response
    
    # Collect readings
    readings = []
    for _ in range(300):
        reading = sensor.capture()
        readings.append(reading.value)
        time.sleep(1)
    
    response = np.mean(readings) - mean_baseline
    responses.append((conc, response))
    
    # Flush and equilibrate
    flush_chamber()
    time.sleep(300)

# Generate calibration curve
# Fit: response = a × log(conc) + b (typically)
# Store curve parameters in EEPROM or file
```

### Field Validation (On-Site)

**Parallel Sampling Protocol:**
1. Deploy nodes at monitoring locations
2. Take simultaneous grab samples (250mL)
3. Preserve samples (acidify if metals analysis)
4. Send to certified lab (ICP-MS for metals)
5. Compare with sensor readings

**Acceptance Criteria:**
- ±30% agreement with lab for concentration
- 100% detection of spikes > 10× LOD
- < 5% false positive rate
- Response time < 15 min for 90% signal

---

## ☀️ Solar Power Integration Notes

### Power Budget

| Component | Active Current | Duty Cycle | Avg Power |
|-----------|----------------|------------|-----------|
| Pi Zero 2 W | 120mA @ 5V | 100% | 0.6W |
| Camera | 250mA @ 5V | 10% | 0.125W |
| Heater | 1000mA @ 5V | 25% | 1.25W |
| LEDs | 200mA @ 5V | 5% | 0.05W |
| Sensors | 50mA @ 5V | 100% | 0.25W |
| **TOTAL** | | | **~2.3W** |

### Daily Energy Requirement

- 2.3W × 24h = **55.2 Wh/day**
- With 3 days autonomy: **165.6 Wh battery**
- With 50% depth of discharge: **331.2 Wh usable battery**
- LiFePO4 12V 30Ah = **360 Wh** ✓ (Recommended)

### Solar Sizing

**Worst Case (Winter, 3 peak sun hours):**
- Required: 55.2 Wh ÷ 3h = 18.4W
- With 30% system losses: **~30W panel minimum**

**Recommended: 50W panel** (margin for cloudy days)

### Wiring Notes

```
Solar Panel 50W
    │
    ▼
┌─────────────┐
│   MC4       │  (or weatherproof connectors)
│  Connector  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  12V PWM    │  (Victron or Renogy recommended)
│ Charge Ctrl │
└──────┬──────┘
       │
   ┌───┴───┐
   │       │
   ▼       ▼
Battery  Load (5V via buck converter)
12V      │
30Ah     ▼
      ┌─────────┐
      │  DC-DC  │  (12V → 5V, 3A)
      │  Buck   │  (LM2596 or better)
      └────┬────┘
           │
     ┌─────┴─────┐
     ▼           ▼
 Pi Zero     Heater Ctrl
 (via GPIO)  (via MOSFET)
```

### Power Management Tips

1. **Implement sleep modes:**
   ```python
   # In sensor.py - sleep between readings
   import time
   time.sleep(60)  # 1 min between readings
   ```

2. **Schedule heater during peak sun:**
   ```python
   # Heat only during 10am-4pm when solar is available
   hour = datetime.now().hour
   if 10 <= hour <= 16:
       heater.enable()
   ```

3. **Battery voltage monitoring:**
   ```python
   # Add to node_provision.sh
   # Voltage divider: Battery ──[100k]──┬──[47k]──GND
   #                                   │
   #                                   ▼
   #                               ADC (GPIO)
   ```

4. **Low-battery shutdown:**
   ```python
   if battery_voltage < 3.3:
       logger.warning("Low battery - shutting down")
       subprocess.run(['sudo', 'shutdown', '-h', 'now'])
   ```

---

## 📋 Deployment Day Checklist

### Morning Setup (Gateway)
- [ ] Boot gateway, verify static IP
- [ ] Start mosquitto: `sudo systemctl start mosquitto`
- [ ] Start containers: `cd ~/deployment && docker-compose up -d`
- [ ] Verify dashboard loads at http://192.168.1.100:3000
- [ ] Test MQTT: `mosquitto_sub -t "mycosentinel/+/+" -v`

### Node Deployment (Repeat ×10)
- [ ] Mount stake/pole at GPS coordinates
- [ ] Secure enclosure with zip ties/lock
- [ ] Connect solar panel (if not pre-wired)
- [ ] Power on Pi Zero
- [ ] Verify WiFi connection: `iwconfig`
- [ ] Check MQTT connection: `mosquitto_pub -h 192.168.1.100 -t test -m "hello"`
- [ ] Verify data flowing in dashboard
- [ ] Take deployment photo
- [ ] Update deployment log with GPS coordinates

### Evening Verification
- [ ] All 10 nodes reporting on dashboard
- [ ] Battery voltages > 3.7V on all nodes
- [ ] No error messages in logs
- [ ] Gateway storage < 50% full
- [ ] Backup configuration to USB drive

---

## 🆘 Troubleshooting

### Node Won't Connect to WiFi
```bash
# On node - check WiFi
sudo iwlist wlan0 scan | grep ESSID
sudo systemctl restart dhcpcd
```

### MQTT Connection Fails
```bash
# Test from node
gateway_ip="192.168.1.100"
mosquitto_pub -h $gateway_ip -t "test" -m "hello" -u node01 -P password

# Check broker status on gateway
sudo systemctl status mosquitto
sudo tail -f /var/log/mosquitto/mosquitto.log
```

### No Sensor Data
```bash
# Check I2C devices
sudo i2cdetect -y 1
# Should show 0x48 and 0x49 for ADS1115s

# Check camera
libcamera-hello --qt-preview
```

### Low Battery
```bash
# Check voltage (if monitoring configured)
cat /sys/class/power_supply/battery/voltage_now

# Reduce power consumption
sudo systemctl stop bluetooth
sudo systemctl stop avahi-daemon
```

---

## 📞 Emergency Contacts

- **Deployment Lead:** [YOUR NAME] - [PHONE]
- **Technical Support:** [YOUR EMAIL]
- **Hardware Issues:** [MAKERSPACE/HARDWARE CONTACT]
- **Biological Questions:** [SYNTHBIO EXPERT]

---

*Document Version: 0.1.0*  
*Last Updated: 2026-03-28*  
*Ready for Field Deployment ✅*