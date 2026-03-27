# MycoSentinel 10-Node Physical Deployment Map

## Overview

This diagram shows the physical layout of the 10-node deployment within a 500m radius of the gateway.

```
                         NORTH (↑)
                           │
                           │
         ┌─────────────────┼─────────────────┐
         │    Sector C     │    Sector A     │
         │    (Control)    │   (Upwind)      │
         │                 │                 │
     MS-C3 ◯           ☀️ MS-C4 ◯         ◯ MS-A3
         │                 │                 │
         │                 │    ~ ~ ~ ~ ~ ~ ~│~ ~ ~ ~ ~
         │                 │    ~ Water Body ~
         │                 │    ~ ~ ~ ~ ~ ~ ~│~ ~ ~ ~ ~
         │                 │                 │
     MS-B2 ◯─────────[GATEWAY]───────────◯ MS-A2
         │                 │  192.168.10.1   │
         │                 │                 │
         │                 │    ~ ~ ~ ~ ~ ~ ~│~ ~ ~ ~ ~
         │                 │    ~ Water Body ~
         │                 │    ~ ~ ~ ~ ~ ~ ~│~ ~ ~ ~ ~
         │                 │                 │
     MS-B1 ◯           ◯ MS-B3            ◯ MS-A1
         │           MS-C1 │                 │
         │    Sector B      │    Sector C     │
         │   (Primary)      │   (Control)     │
     MS-C2 ◯─────────────┼───────────────────┘
                       │
                       │
                    SOUTH

LEGEND:
========
◯ Sensor Node (1.5-2m above ground)
[GATEWAY] Central hub (building/shed/vehicle)
~ ~ ~ Water body (river, pond, monitoring target)
☀️ Solar panel location

DISTANCES (from Gateway):
------------------------
MS-A1: 180m (NE)      MS-A2: 120m (NE)      MS-A3: 85m (NE)
MS-B1: 90m (SW)       MS-B2: 140m (SW)     MS-B3: 160m (SW)
MS-C1: 200m (NW)      MS-C2: 175m (SE)     MS-C3: 220m (NE-NW)
MS-C4: 240m (North)

SECTOR BREAKDOWN:
=================
Sector A (3 nodes): Northeast quadrant
• Purpose: Upwind reference, baseline establishment
• Primary risk: Cross-contamination from upwind sources

Sector B (3 nodes): Southwest quadrant
• Purpose: Primary monitoring zone (prevailing downwind)
• Primary risk: Source proximity calibration

Sector C (4 nodes): Northwest/Southeast quadrants
• Purpose: Control/baseline, triangulation validation
• Primary risk: Far-field signal detection

SPACING:
========
• Minimum inter-node: 75m
• Maximum inter-node: 150m
• Average spacing: 100m
• Gateway to nearest: 85m (MS-A3)
• Gateway to farthest: 240m (MS-C4)

TERRAIN CONSIDERATIONS:
========================
• All nodes on flat to gently sloping terrain
• Clear line of sight to gateway or adjacent node
• Avoid low-lying areas (flood risk)
• Avoid hilltops (wind damage risk)
• Prefer south-facing slopes for solar exposure

COVERAGE PATTERN:
=================
┌─────────────────────────────────────────────────┐
│                                                 │
│    C3 ╭───────────────╮ C4                      │
│      ╱    Sector C     ╲                        │
│     ╱                   ╲  A3                   │
│  B2 │    [GATEWAY]      │╱  ╲                   │
│     │       ★           │      A2               │
│      ╲                   ╲      │                │
│       ╲    Sector B       ╲    A1                │
│        ╲    C1  C2        │                     │
│         ╲_________________╱                      │
│                                                 │
│    ~ = Water bodies (target monitoring areas)   │
│                                                 │
└─────────────────────────────────────────────────┘

INSTALLATION REQUIREMENTS:
==========================
Per Node:
• 1.5m steel ground stake (tamped 0.5m deep)
• IP67 enclosure mounting bracket
• Solar panel mounting (30° tilt, South-facing)
• Ground wire connection (if lightning risk)
• GPS coordinate logged (±3m accuracy)

Gateway:
• Secure building/shed OR vehicle mounting
• Ethernet or 4G connectivity
• Mains power or UPS backup
• Climate control if possible (fan/cooling)

MAINTENANCE ACCESS:
===================
• All nodes within 250m of vehicular access
• No nodes require climbing or special equipment
• Clear paths for inspection between nodes
• Emergency access routes identified
```

## Coordinates Template

| Node | GPS Latitude | GPS Longitude | Elevation (m) | Install Date | Installer |
|------|--------------|---------------|---------------|--------------|-----------|
| GATEWAY | ___________ | ____________ | _______ | ______ | _______ |
| MS-A1 | ___________ | ____________ | _______ | ______ | _______ |
| MS-A2 | ___________ | ____________ | _______ | ______ | _______ |
| MS-A3 | ___________ | ____________ | _______ | ______ | _______ |
| MS-B1 | ___________ | ____________ | _______ | ______ | _______ |
| MS-B2 | ___________ | ____________ | _______ | ______ | _______ |
| MS-B3 | ___________ | ____________ | _______ | ______ | _______ |
| MS-C1 | ___________ | ____________ | _______ | ______ | _______ |
| MS-C2 | ___________ | ____________ | _______ | ______ | _______ |
| MS-C3 | ___________ | ____________ | _______ | ______ | _______ |
| MS-C4 | ___________ | ____________ | _______ | ______ | _______ |

## Communication Range Map

```
Signal Strength Zones (from Gateway)
=====================================
        ╭──────────────────╮
      ╱    Strong (-50dBm)   ╲
     ╱   ┌─────────────┐     ╲
    │    │  Excellent   │      │
    │    │   Coverage    │      │
    │    └─────────────┘       │
    │   Moderate (-70dBm)      │
    │  ┌───────────────────────┐ │
    │  │    Good Coverage      │ │
    │  └───────────────────────┘ │
    │       Weak (-80dBm)        │
     ╲  ┌─────────────────────┐  ╱
      ╲ │   Marginal          │ ╱
       ╲│   (Mesh fallback)   │╱
        └─────────────────────┘
        
Radius:
• Strong: 0-100m
• Moderate: 100-200m
• Weak: 200-300m (use mesh)
• No signal: >300m without repeater

Mesh Fallback Routes
====================
If MS-C4 cannot reach gateway directly:
MS-C4 → MS-C3 → MS-B2 → Gateway
  or
MS-C4 → MS-C3 → MS-C2 → MS-A2 → Gateway

Expected Packet Loss
====================
• A-series nodes (85-180m): <1%
• B-series nodes (90-160m): <1%
• C1/C2 nodes (175-200m): 2-5%
• C3/C4 nodes (220-240m): 5-15%
  (expect mesh fallback usage)
```
