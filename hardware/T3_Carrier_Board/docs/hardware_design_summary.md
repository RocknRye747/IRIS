# IRIS T3 Carrier Board Hardware Design Summary

## 1. Design Overview
The IRIS T3 Carrier Board is a modular, hardware-agnostic robotics backbone designed for humanitarian and research applications. It serves as a bridge between high-level compute (e.g., smartphones) and low-level sensors/actuators, supporting multiple microcontroller platforms including ESP32-S3 and Raspberry Pi Pico.

## 2. Core Components and Power Architecture
The design utilizes a high-efficiency power delivery system to support diverse input voltages and provide stable rails for sensitive electronics.

| Component | Specification | Function |
| :--- | :--- | :--- |
| **Main Regulator** | MP1584EN Buck Converter | Converts 5-15V input to a stable 5V rail (3A max). |
| **Logic Regulator** | AMS1117-3.3 LDO | Provides a clean 3.3V rail for the MCU and sensors. |
| **Protection** | Polyfuse & ESD Diodes | Protects against overcurrent and electrostatic discharge on USB lines. |

## 3. Universal MCU Socket
The 40-pin hybrid header is the "brain" of the board, allowing for seamless swapping between different microcontrollers.

*   **ESP32-S3 DevKitC-1**: Optimized for Wi-Fi/Bluetooth and AI acceleration.
*   **Raspberry Pi Pico / PicoW**: Ideal for low-power, real-time control.
*   **USB-C Phone Brain**: High-level compute via USB-C data lines mapped to the MCU header.

## 4. Expansion and Connectivity
The board features standardized connectors for rapid field deployment and modular upgrades.

*   **I2C Rails**: 2x JST-GH 4-pin connectors for standard sensors.
*   **High-Bandwidth Rail**: 1x JST-GH 6-pin connector for cameras or high-speed SPI/MIPI peripherals.
*   **Debug Interface**: Dedicated pads for SWD and UART0 console access.

## 5. Manufacturing and Layout
The PCB is designed as a 4-layer board (85mm x 65mm) with a focus on signal integrity and thermal management.

*   **Differential Pairs**: USB and MIPI lines are routed with controlled impedance.
*   **Ground Plane**: A solid internal ground plane provides a low-impedance return path for all signals.
*   **Field Repairability**: Component spacing and labeling are optimized for manual repair and modification.

---

## References
1. [ESP32-S3 DevKitC-1 User Guide](https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide_v1.0.html)
2. [Raspberry Pi Pico Datasheet](https://pip.raspberrypi.com/documents/RP-008307-DS-1-pico-datasheet.pdf)
3. [MP1584EN Datasheet](https://www.monolithicpower.com/en/documentview/productdocument/index/version/2/document_type/Datasheet/lang/en/sku/MP1584EN-LF-Z/document_id/204/)
