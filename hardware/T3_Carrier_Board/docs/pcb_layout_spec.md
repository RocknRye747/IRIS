# IRIS T3 Carrier Board PCB Layout and Manufacturing Specifications

This document outlines the critical design and manufacturing requirements for the IRIS T3 Carrier Board to ensure reliability, signal integrity, and ease of assembly/repair in the field.

## 1. Physical and Mechanical Specifications

| Specification | Value | Notes |
| :--- | :--- | :--- |
| **Dimensions** | 85mm x 65mm | Standardized size for T3-class robotics head. |
| **Mounting Holes** | 4 x M3, Plated | Located at corners, 3mm diameter. |
| **Board Thickness** | 1.6mm | Standard PCB thickness. |
| **Solder Mask** | Matte Black or Matte Blue | Recommended for professional appearance and visibility of silkscreen. |
| **Silkscreen** | White | All connectors, pins, and component designators must be clearly labeled. |

## 2. Layer Stackup (4-Layer Recommended)

The recommended stackup is optimized for power distribution and signal integrity, especially for high-speed USB and SPI/MIPI lines.

| Layer | Function | Notes |
| :--- | :--- | :--- |
| **Top** | Signal / Component | Primary component placement and signal routing. |
| **Inner 1** | Ground Plane (GND) | Solid ground reference for all signals. |
| **Inner 2** | Power Plane (VCC) | Dedicated plane for 5V and 3.3V distribution. |
| **Bottom** | Signal / Component | Secondary signal routing and low-profile components. |

## 3. Critical Routing and Signal Integrity

### Power Section
*   **Buck Converter (MP1584EN)**: Follow datasheet recommendations for component placement. Keep the switching node (SW pin, inductor, output capacitor) loop area as small as possible to minimize EMI.
*   **Decoupling**: Place decoupling capacitors (e.g., 0.1µF) as close as possible to the VCC pins of the MCU header.
*   **Planes**: Use wide traces for power (5V, 3.3V) and ground connections to minimize impedance. Connect all ground pins to the solid inner ground plane with multiple vias.

### High-Speed Signals
*   **USB Data Lines (D+, D-)**: Must be routed as a **differential pair** with **controlled impedance** (90 Ohms). Keep the pair length matched and avoid routing over splits in the ground plane.
*   **SPI/MIPI Lines**: Route as short as possible. If using the JST-GH 6-pin for MIPI, ensure the differential pairs (CLK+/-, DATA+/-) are length-matched and impedance-controlled (100 Ohms).

## 4. Component Placement and Modular Design

*   **MCU Header**: Place the 40-pin header centrally on the left edge (as per the README layout) to facilitate easy access and modular swapping.
*   **Connectors**: All field-replaceable connectors (I2C, High-Bandwidth) must use the **JST-GH** series for ruggedness and standardization.
*   **Field Repair**: Group components by function (Power, MCU, I/O) and ensure sufficient clearance for manual soldering and repair of key components (e.g., regulators, fuses).
*   **Ground Stitching**: Place stitching vias along the perimeter of the board and around high-current/high-speed areas to ensure a robust ground connection between layers.

## 5. Manufacturing Export

The final repository must include the following manufacturing files:
*   **Gerber Files**: RS-274X format, including all copper layers, solder mask, silkscreen, and drill files.
*   **Drill Map**: Clearly indicating plated and non-plated holes.
*   **BOM (Bill of Materials)**: Comprehensive list of all components with vendor part numbers and footprints.
*   **Pick-and-Place File**: For automated assembly.
