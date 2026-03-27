# STL File Descriptions for MycoSentinel Bioreactor

## Overview
All files are designed for **PETG printing** (autoclavable, food-safe, moisture resistant).

---

## File 1: vessel_main.stl
**Purpose:** Main bioreactor body - sample chamber, heating integration, sensor ports

### Specifications:
- **Overall dimensions:** 80mm outer diameter × 150mm height
- **Internal working volume:** 75mL (chamber for fungal culture)
- **Wall thickness:** 3mm (sufficient for 70°C autoclave cycles)
- **Material:** PETG
- **Print time:** ~3.5 hours
- **Filament required:** ~140g

### Features:
1. **Cylindrical sample chamber:** 60mm ID × 35mm depth
2. **Three electrode wells:** 12mm diameter × 25mm deep (positions at 120°)
3. **Heating channel:** 5mm × 30mm × 40mm integrated cavity for silicone pad
4. **Air gap insulation:** 10mm hollow zone below heating channel
5. **Sensor ports (3x):** M6 threaded holes at 90° intervals
6. **Cable gland port:** 10mm entry with strain relief for all wiring
7. **Mounting flange:** 4x 4mm holes for wall/lab stand mounting

### Slicer Settings:
```
Layer height: 0.2mm
Wall count: 4 (1.6mm)
Top/bottom layers: 5
Infill: 30% cubic
Supports: YES (for electrode wells only)
Support density: 15%
Print orientation: Upright (standing on base)
```

---

## File 2: vessel_lid.stl
**Purpose:** Threaded, sealable lid with gas exchange

### Specifications:
- **Thread:** M25 × 2mm pitch (matches vessel_main)
- **Outer diameter:** 85mm
- **Height:** 25mm
- **Material:** PETG
- **Print time:** ~45 minutes
- **Filament required:** ~20g

### Features:
1. **Internal thread:** Precision fit for gas-tight seal
2. **O-ring groove:** 25mm OD × 2mm cross-section (accepts 25mm×2mm O-ring)
3. **Gas exchange port:** 10mm hole compatible with 0.22μm syringe filter
4. **Knurled grip:** External texture for hand-tightening
5. **Sealing surface:** Flat, 1mm lip for O-ring compression

### Slicer Settings:
```
Layer height: 0.15mm (for thread quality)
Wall count: 3
Top/bottom layers: 4
Infill: 40% for sealing surface
Supports: NO
Print orientation: Thread-side UP
```

---

## File 3: electrode_holder.stl
**Purpose:** Precision alignment of 3-electrode array

### Specifications:
- **Overall dimensions:** 60mm diameter × 30mm height
- **Well count:** 3 (WE, RE, CE positions)
- **Well diameter:** 12mm
- **Well spacing:** 20mm center-to-center (equilateral triangle)
- **Material:** PETG
- **Print time:** ~30 minutes
- **Filament required:** ~15g

### Features:
1. **Press-fit into vessel_main:** 0.2mm interference fit
2. **Electrode channels:** 2mm wide grooves for wire routing
3. **Depth stops:** Wells bottom out at 15mm immersion depth
4. **Electrode retention:** Friction fit (2mm compression)
5. **Alignment markers:** "WE", "RE", "CE" embossed labels
6. **Sample port:** Central 15mm opening for culture access

### Electrode Placement:
```
        [WE]
         /\
        /  \
       /    \
    [CE]────[RE]
    
    WE: Working Electrode (0.5mm graphite)
    CE: Counter Electrode (0.7mm graphite)  
    RE: Reference Electrode (Ag/AgCl pellet)
```

### Slicer Settings:
```
Layer height: 0.15mm
Wall count: 3
Top/bottom layers: 4
Infill: 50% (for dimensional stability)
Supports: NO
Print orientation: Grooves UP
```

---

## File 4: heater_mount.stl
**Purpose:** Secure positioning of silicone heating pad

### Specifications:
- **Channel dimensions:** 32mm × 42mm × 6mm
- **Pad size:** 25mm × 50mm × 1mm (when inserted)
- **Material:** PETG
- **Print time:** ~25 minutes
- **Filament required:** ~12g

### Features:
1. **Sliding entry:** Heater inserts from below
2. **Retention clips:** Flex tabs hold pad with 1mm interference
3. **Thermal bridge:** 1mm wall between heater and vessel
4. **Wiring channel:** 3mm groove for 12V power cable
5. **Mounting tabs:** 2× M3 screw holes for external retention

### Slicer Settings:
```
Layer height: 0.2mm
Wall count: 3
Top/bottom layers: 5 (thermal mass)
Infill: 40%
Supports: NO
Print orientation: Channel UP
```

---

## File 5: sensor_cap.stl
**Purpose:** Environmental sensor mounting plate

### Specifications:
- **Diameter:** 80mm (matches vessel_main)
- **Height:** 20mm
- **Material:** PETG
- **Print time:** ~35 minutes
- **Filament required:** ~18g

### Features:
1. **DHT22 mount:** 15.5mm × 12mm cutout (friction fit, vents for airflow)
2. **pH probe entry:** BNC connector compatible 12mm hole
3. **NTC thermistor well:** 2mm diameter hole near vessel wall
4. **Cable gland:** PG7 compatible thread (for strain relief)
5. **Ventilation slots:** 3× 2mm × 15mm (humidity equalization)
6. **Press-fit seal:** Tapered edge seals against vessel_main rim

### Slicer Settings:
```
Layer height: 0.2mm
Wall count: 3
Top/bottom layers: 4
Infill: 30%
Supports: YES (for DHT22 cutout bridge)
Print orientation: Open side UP
```

---

## File 6: cable_gland_insert.stl
**Purpose:** Waterproof cable pass-through

### Specifications:
- **Thread:** M12 × 1.5mm (PG7 compatible)
- **ID:** 6mm (for 5 wires + 2mm tubing)
- **Material:** PETG (with TPU gasket if available)
- **Print time:** ~10 minutes
- **Filament required:** ~5g

### Features:
1. **Watertight thread:** Seals against vessel_main port
2. **Split design:** Two halves clamp around cables
3. **Gland compression:** 2mm silicone gasket compression
4. **Strain relief:** Internal barbs grip cable insulation

---

## Assembly Notes

### Print Order (for single printer)
1. heater_mount.stl (25 min) - test print first
2. electrode_holder.stl (30 min)
3. vessel_lid.stl (45 min)
4. sensor_cap.stl (35 min)
5. vessel_main.stl (3.5 hrs) - overnight print

### Post-Processing Required:
- **Drill/thread electrode holes:** Clean up with 12mm drill
- **Tap M6 sensor ports:** Use M6 tap for sensor mounting
- **Smooth sealing surfaces:** Light sanding with 400 grit
- **Test O-ring fit:** Verify compression on lid

### Recommended Filament:
- **Brand:** eSUN, Hatchbox, or Overture
- **Color:** Natural or white (for contamination visibility)
- **Temperature:** 230°C nozzle, 70°C bed
- **Drying:** 4 hours @ 60°C before printing (PETG is hygroscopic)

---

*Version: 1.0*
