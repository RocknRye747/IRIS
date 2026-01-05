# IRIS T3 Carrier Board Hardware Specifications

## 1. Microcontroller Support
The board features a 40-pin hybrid header designed to accommodate:
- **ESP32-S3 DevKitC-1**: 25.4mm (1.0") width, 2.54mm (0.1") pin pitch.
- **Raspberry Pi Pico / PicoW**: 21mm width, 2.54mm pin pitch.
- **Raspberry Pi CM4**: Supported via an optional adapter board.

## 2. Power Architecture
- **Input Voltage**: 5V - 15V DC (via XT30 or Barrel Jack).
- **Main Regulator (5V)**: MP1584EN Buck Converter.
    - Typical Application: 10uH Inductor, 22uF Output Capacitor.
    - Feedback Resistors for 5V: R1=40.2k, R2=7.68k (approximate for 0.8V reference).
- **Logic Regulator (3.3V)**: AMS1117-3.3 or RT9080 LDO.
- **Protection**: Polyfuse on input, ESD protection on USB-C.

## 3. Connectors & Pinouts
- **USB-C**: For phone compute and 5V input.
- **I2C Rails (JST-GH 4-pin)**:
    1. 3.3V
    2. SDA
    3. SCL
    4. GND
- **High-Bandwidth Rail (JST-GH 6-pin)**:
    1. 5V
    2. MIPI/SPI_CLK+
    3. MIPI/SPI_CLK-
    4. DATA+
    5. DATA-
    6. GND

## 4. Physical Dimensions
- **Board Size**: 85mm x 65mm.
- **Mounting**: 4 x M3 holes, plated.
- **Layer Stack**: 4-layer recommended (Signal, GND, Power, Signal).
