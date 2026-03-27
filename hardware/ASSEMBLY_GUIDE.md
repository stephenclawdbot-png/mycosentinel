# MycoSentinel Build Guide
## For High School Students and First-Time Builders

---

## 📋 What You're Building

A device that grows fungi and measures their electrical signals to detect chemicals in the environment. Think of it like a "canary in a coal mine" but with mushrooms and electricity!

**Time Required:** 4-6 hours (first time)
**Skill Level:** Anyone who can solder and use a 3D printer

---

## 🛠️ Tools You'll Need

### Required:
- [ ] Soldering iron (15-60W)
- [ ] Solder (lead-free recommended)
- [ ] Wire cutters/strippers
- [ ] 3D printer (or access to one)
- [ ] Computer with Arduino IDE installed
- [ ] Multimeter (to check connections)
- [ ] Hot glue gun (for wire strain relief)

### Helpful but Optional:
- [ ] Heat gun (for shrink tubing)
- [ ] Tweezers (for small components)
- [ ] Helping hands (third hand tool)
- [ ] Oscilloscope (if available)

---

## 🧩 Parts Organization

### Before you start, sort your parts into cups or bowls:
1. **ESP32 and main electronics**
2. **Sensors** (DHT22, NTC, pH probe)
3. **Electrochemical setup** (graphite leads, reference electrode)
4. **Heating components** (silicone pad, MOSFET)
5. **Connectors and passives** (resistors, capacitors, wires)
6. **3D printed parts** (wait until printed)

---

## 🔬 Step 1: Prepare the Electrodes (20 minutes)

The most important part! These detect the fungal signals.

### 1.1 Working Electrode (WE)
```
Take: 1x 0.5mm graphite pencil lead

Step 1: Cut to 30mm length (use wire cutters)
Step 2: Cut the insulation tube to 25mm
Step 3: Strip 5mm of insulation from ONE end
Step 4: Wrap thin wire (28 AWG) around exposed graphite
Step 5: Solder the connection (graphite solders okay with flux)
Step 6: Slide heat shrink tubing over connection
Step 7: Heat with heat gun or lighter to seal
Step 8: Label "WE" with tape
```

### 1.2 Counter Electrode (CE)
```
Take: 1x 0.7mm graphite pencil lead

Step 1-4: Same as WE
Step 5: Label "CE" 

TIP: Use different diameter so you can tell them apart!
```

### 1.3 Reference Electrode (RE)
```
If you bought an Ag/AgCl electrode:
- Keep it in storage solution until use
- Don't let it dry out!

If making DIY:
- Take silver wire
- Coat in bleach (makes AgCl layer)
- Connect to shielded wire
```

**Result:** You should have 3 electrodes with wires sticking out.

---

## 🖨️ Step 2: Print the Bioreactor (2.5 hours, mostly waiting)

### Print Order:

**File 1: vessel_main.stl** (4 hours)
```slicer settings
Material: PETG (not PLA!)
Nozzle: 0.4mm
Layer: 0.2mm
Infill: 30%
Supports: YES (only for electrode wells)
```

**File 2: vessel_lid.stl** (45 min)
```slicer settings
Layer: 0.15mm (better threads)
Infill: 40%
Supports: NO
Orientation: Thread side UP
```

**File 3: electrode_holder.stl** (30 min)
```slicer settings
Layer: 0.15mm
Infill: 50%
Supports: NO
```

**File 4: heater_mount.stl** (25 min)

**File 5: sensor_cap.stl** (35 min)

### Post-Processing Checklist:
- [ ] Threads fit together (test lid on vessel)
- [ ] Electrode wells are clear of supports
- [ ] Smooth sealing surfaces with 400 grit sandpaper
- [ ] Thread M6 holes for sensors (use tap if available)
- [ ] Test O-ring fit on lid

---

## ⚡ Step 3: Build the Electronics (90 minutes)

### 3.1 Breadboard Layout

Place your ESP32 on the left side of the breadboard. Leave room!

```
[BREADBOARD TOP VIEW]

    ───────────────────────────────────────────────────
    │ POWER RAILS (Red=+, Blue=-)                     │
    ├───────────────────────────────────────────────────┤
    │
    │  ESP32   │                                      │
    │  [====]  │  LMP91000   │   Sensors           │
    │  ######  │  [=====]    │   [DHT22]           │
    │  ######  │             │   [pH]              │
    │  [====]  │  MOSFET     │   [NTC]             │
    │          │  [====]     │                     │
    │          │             │   Connectors        │
    │          │             │   [OLED]            │
    │          │             │   [RTC]             │
    │
    ───────────────────────────────────────────────────
```

### 3.2 Wire the Power Rails

```
Step 1: Connect ESP32 3.3V to top red rail
Step 2: Connect ESP32 5V to another red rail (label it!)
Step 3: Connect ESP32 GND to both blue rails
Step 4: Test with multimeter - should read 3.3V and 5V
```

### 3.3 Connect the LMP91000 Potentiostat

This chip reads the electrode signals.

```
LMP91000 PIN → Connect To
─────────────────────────
VCC          → 3.3V rail
GND          → GND rail
CSB          → ESP32 GPIO 5
SCLK         → ESP32 GPIO 13
SDI          → ESP32 GPIO 14
SDO          → ESP32 GPIO 12
VOUT         → ESP32 GPIO 32

Also add:
- 100nF capacitor between C1 and C2
- 100nF capacitor between C2 and GND
- 10µF capacitor between VCC and GND
```

### 3.4 Connect Sensors

**DHT22 (Humidity & Temp):**
```
VCC  → 3.3V
GND  → GND
DATA → ESP32 GPIO 2
```
Add a 10K pull-up resistor between DATA and VCC (or buy module with built-in).

**NTC Thermistor (Temperature monitoring):**
```
Build voltage divider:
3.3V ──[10K]──┬──[NTC]──GND
              │
              └──► ESP32 GPIO 35
```

**pH Sensor:**
```
VCC  → 5V rail
GND  → GND
OUT  → ESP32 GPIO 34
```

### 3.5 Build the Heater Circuit

**CRITICAL:** Use logic-level MOSFET!

```
                    12V from buck converter
                    │
                ┌───┴───┐
                │Heater │
                │Pad    │
                └───┬───┘
                    │
                ┌───┴───┐
                │  D    │
    GPIO 4 ────►│G      S│────► GND
(through 10K)   │       │
                └───────┘
                IRLZ44N

Add 10K resistor between GPIO 4 and GND (pulldown)
```

**Test:** Before connecting heater, use multimeter on diode test. You should see ~0.5V between Source and Drain when MOSFET is on.

---

## 🧪 Step 4: Mechanical Assembly (45 minutes)

### 4.1 Install Heater
```
1. Clean inside heating channel with isopropyl alcohol
2. Apply thermal paste (or use tape if included)
3. Press silicone heating pad into channel
4. Route wires through cable gland
5. Secure with small zip ties
```

### 4.2 Install Electrodes
```
1. Insert electrode_holder into vessel main
2. Press should be tight (0.2mm interference)
3. Slide WE, RE, CE into respective wells
4. Check: electrodes should bottom out at same depth
5. Route wires through holder channels
6. Add dab of silicone RTV to seal (optional)
7. Thread wires through vessel cable gland
```

### 4.3 Install Environmental Sensors
```
1. Press DHT22 into sensor_cap cutout
2. Insert NTC thermistor into 2mm hole
3. Thread pH probe through BNC hole
4. Connect probe to sensor
5. Fit sensor_cap onto vessel_main
```

### 4.4 Wiring Management
```
1. Route all wires to one side
2. Use cable gland to secure
3. Add strain relief (hot glue or zip ties)
4. Label every wire with tape!
    - WE, CE, RE
    - HEATER+, HEATER-
    - DHT (data, vcc, gnd)
    - pH OUT
    - TEMP
```

---

## 💻 Step 5: Upload Firmware (30 minutes)

### 5.1 Install Arduino IDE
```
1. Download from arduino.cc
2. Install ESP32 board support:
   File → Preferences → Additional Board URLs
   Add: https://dl.espressif.com/dl/package_esp32_index.json
3. Tools → Board → Board Manager → Search "ESP32" → Install
4. Tools → Board → ESP32 Arduino → ESP32 Dev Module
```

### 5.2 Install Libraries
```
Sketch → Include Library → Manage Libraries
Search and install:
• DHT sensor library by Adafruit
• Adafruit Unified Sensor
• WiFi (built-in)
• PubSubClient (for MQTT)
• ArduinoJson
```

### 5.3 Upload Test Sketch

Create new sketch, paste in firmware (see FIRMWARE.md), then:

```
1. Connect ESP32 to computer via USB
2. Tools → Port → Select your device (COM3 on Windows)
3. Tools → Upload Speed → 115200
4. Verify (checkmark button) - should compile
5. Upload (arrow button) - should flash
6. Open Serial Monitor (magnifying glass)
7. Set baud to 115200
8. Press ESP32 RST button
```

**Expected Output:**
```
MycoSentinel v1.0 Booting...
WiFi connecting...
WiFi connected! IP: 192.168.1.XXX
Sensors initialized
Temperature: 24.5 C
Humidity: 45.2 %
pH: 6.98
Electrochemical signal: 0.023 nA
```

---

## 🔧 Step 6: Calibration (45 minutes)

### 6.1 Temperature Calibration
```
1. Place reference thermometer in vessel
2. Fill with water at room temperature
3. Wait 10 minutes for thermal equilibrium
4. Read NTC value from Serial Monitor
5. Read reference thermometer
6. Calculate offset: (actual - measured)
7. Update code with correction factor
```

### 6.2 pH Calibration (3-point)
```
You'll need: pH 4, 7, and 10 buffer solutions

Step 1: Calibrate midpoint (pH 7)
• Rinse probe with distilled water
• Immerse in pH 7 buffer
• Wait until reading stabilizes (~2 min)
• Note raw voltage or ADC value
• This is your V7 reference

Step 2: Calibrate acid (pH 4)
• Rinse, immerse in pH 4
• Wait, note reading
• This is V4

Step 3: Calibrate base (pH 10)
• Rinse, immerse in pH 10
• Wait, note V10

Step 4: Calculate slope
Slope = (V4 - V10) / 6  (6 is pH span from 4 to 10)
Offset = V7 (should be ~2.5V at pH 7)
```

### 6.3 Electrochemical Calibration
```
With electrodes in blank electrolyte (PBS or KCl):

1. Apply 0mV vs RE
2. Current should be near zero (<1 nA)
3. This is your baseline

Optional (with ferricyanide standard):
1. Add 1mM potassium ferricyanide
2. Run cyclic voltammetry
3. Should see peaks at ~200mV and ~-200mV
4. Peak current proportional to concentration
```

---

## 🧫 Step 7: Test Run (2-24 hours)

### 7.1 Sterilize Everything
```
1. Disassemble bioreactor
2. Clean with 70% ethanol
3. Autoclave-safe parts: 121°C for 20 min
   (PETG handles this once or twice)
   OR use bleach solution (10%) soak
4. Dry completely before use
```

### 7.2 First Biological Test

**Materials:**
- Potato Dextrose Broth (PDB) or simple sugar solution
- Safe fungus: Rhizopus stolonifer (bread mold) or Aspergillus niger
- Autoclave or pressure cooker for sterilization

**Steps:**
```
1. Prepare 50mL sterile PDB
2. Pour into sterile bioreactor
3. Install electrodes (sterilized)
4. Inoculate with small piece of fungal colony
   (use sterile technique!)
5. Seal with lid + gas exchange filter
6. Start data logging
7. Set temperature to 28°C (optimal for most fungi)
```

### 7.3 Expected Results

**Hours 0-6:** Baseline stable, current near zero
**Hours 6-12:** Current starts increasing as spores germinate
**Hours 12-24:** Exponential growth, resistance drops
**Hours 24+:** Stationary phase, signal plateaus

**What you should see:**
- Real-time current (nA to µA range)
- Temperature cycling around setpoint
- Humidity increase as fungus respires
- pH changes as metabolic products form

---

## 🐛 Troubleshooting

### Problem: Nothing happens after inoculation
**Check:**
- Temperature? Should be 25-30°C
- Sterility? Contamination might outcompete
- Viability? Spores must be alive
- Nutrition? Check PDB preparation

### Problem: No electrical signal
**Check:**
- All 3 electrodes submerged?
- Graphite leads making contact?
- LMP91000 configured properly?
- Bias voltage applied? (200-400mV vs RE)

### Problem: pH readings crazy
**Check:**
- Probe fully submerged?
- Calibrated recently?
- Cable shielded?
- Reference electrode not dry?

### Problem: Heater not warming
**Check:**
- 12V present at heater terminals?
- MOSFET is IRLZ44N (not IRFZ44N)?
- PWM signal on GPIO 4?
- Heater resistance ~28Ω?

### Problem: WiFi won't connect
**Check:**
- Credentials correct in code?
- Router supports 2.4GHz?
- Signal strength in location?
- Try different GPIO pins?

---

## 📊 Step 8: Data Visualization

### Serial Monitor (Simplest)
Just watch the numbers scroll by!

### Arduino Serial Plotter
Tools → Serial Plotter
Format your output as: `temp,humidity,ph,current`

### Cloud Dashboard (Advanced)
Set up InfluxDB + Grafana:
- ESP32 sends HTTP POST to server
- Server stores in time-series database
- Grafana dashboards show graphs

---

## 📝 Maintenance Log

**Before Each Run:**
- [ ] Calibrate pH probe (or at least verify with pH 7)
- [ ] Test temperature reading with thermometer
- [ ] Check all wire connections
- [ ] Verify electrochemical baseline
- [ ] Sterilize vessel and electrodes

**Monthly:**
- [ ] Replace reference electrode (Ag/AgCl wears out)
- [ ] Replace graphite electrodes (can oxidize)
- [ ] Check MOSFET for heating
- [ ] Update firmware if needed
- [ ] Clean pH probe with electrode storage solution

---

## 🎓 Learning Extensions

Once it's working, try these experiments:

1. **Dose Response:** Add known amounts of pollutant to
   measure signal change

2. **Comparison Test:** Test different fungal species for
   sensitivity

3. **Environmental Sampling:** Take readings from local
   water/ soil samples

4. **Optimization:** Adjust temperature, pH, humidity to
   maximize sensitivity

5. **Network:** Build 3 nodes and compare readings across
   locations

---

## ⚠️ Safety Reminders

- **Biological:** Use only Biosafety Level 1 organisms
  (bread mold, common fungi). Never use unknown samples!
  
- **Chemical:** Handle pH buffers carefully (can irritate)

- **Electrical:** 12V is low voltage but can still cause
  burns if shorted. Always power off before connecting!

- **Heat:** Heating pad reaches 60°C+. Don't touch when
  powered. Use thermistor safety cutoff!

---

## 🆘 Getting Help

If stuck:
1. Re-read the section - did you miss a step?
2. Check all connections with multimeter
3. Look for example code online: "ESP32 DHT22" etc.
4. Post clear question with: photos, code snippet,
   Serial Monitor output, what you tried

---

**Congratulations! You've built a working fungal biosensor.**

*Document Version: 1.0*
*Target: First-time builders, ages 14+*
