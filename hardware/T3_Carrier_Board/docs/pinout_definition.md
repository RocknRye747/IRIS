# IRIS T3 Carrier Board MCU Header Pinout Definition

The 40-pin MCU header is designed to be a universal socket, mapping the required peripheral buses to the most common pins for both ESP32-S3 and Raspberry Pi Pico/PicoW. The pinout is optimized for minimal routing complexity and signal integrity.

## 40-Pin Header Pin Map

| Pin No. | Name (T3 Label) | Function | ESP32-S3 Default Pin (Example) | Pico Default Pin (Example) | Notes |
| :---: | :--- | :--- | :--- | :--- | :--- |
| 1 | **3V3** | Logic Power Rail | 3V3 | 3V3 | Dedicated 3.3V power |
| 2 | **GND** | Ground | GND | GND | |
| 3 | **5V** | High Power Rail | 5V | VBUS | Dedicated 5V power |
| 4 | **V_SYS** | Raw Input Voltage | - | - | For monitoring/powering high-voltage peripherals |
| 5 | **I2C0_SDA** | I2C Bus 0 Data | GPIO 4 | GP 0 | Primary I2C for critical sensors |
| 6 | **I2C0_SCL** | I2C Bus 0 Clock | GPIO 5 | GP 1 | |
| 7 | **I2C1_SDA** | I2C Bus 1 Data | GPIO 6 | GP 2 | Secondary I2C for expansion |
| 8 | **I2C1_SCL** | I2C Bus 1 Clock | GPIO 7 | GP 3 | |
| 9 | **SPI0_MOSI** | SPI Bus 0 MOSI | GPIO 11 | GP 19 | Primary SPI for high-speed peripherals |
| 10 | **SPI0_MISO** | SPI Bus 0 MISO | GPIO 12 | GP 16 | |
| 11 | **SPI0_CLK** | SPI Bus 0 Clock | GPIO 13 | GP 18 | |
| 12 | **SPI0_CS** | SPI Bus 0 Chip Select | GPIO 10 | GP 17 | |
| 13 | **UART0_TX** | UART Bus 0 Transmit | GPIO 43 | GP 1 | Debug/Console UART |
| 14 | **UART0_RX** | UART Bus 0 Receive | GPIO 44 | GP 0 | |
| 15 | **UART1_TX** | UART Bus 1 Transmit | GPIO 17 | GP 4 | Secondary UART for external module |
| 16 | **UART1_RX** | UART Bus 1 Receive | GPIO 18 | GP 5 | |
| 17 | **ADC0** | Analog Input 0 | GPIO 1 | GP 26 | |
| 18 | **ADC1** | Analog Input 1 | GPIO 2 | GP 27 | |
| 19 | **ADC2** | Analog Input 2 | GPIO 3 | GP 28 | |
| 20 | **ADC3** | Analog Input 3 | GPIO 8 | - | ESP32-S3 specific ADC |
| 21 | **ADC4** | Analog Input 4 | GPIO 9 | - | ESP32-S3 specific ADC |
| 22 | **ADC5** | Analog Input 5 | GPIO 14 | - | ESP32-S3 specific ADC |
| 23 | **GPIO_A** | General Purpose I/O | GPIO 15 | GP 6 | |
| 24 | **GPIO_B** | General Purpose I/O | GPIO 16 | GP 7 | |
| 25 | **GPIO_C** | General Purpose I/O | GPIO 19 | GP 8 | |
| 26 | **GPIO_D** | General Purpose I/O | GPIO 20 | GP 9 | |
| 27 | **GPIO_E** | General Purpose I/O | GPIO 21 | GP 10 | |
| 28 | **GPIO_F** | General Purpose I/O | GPIO 38 | GP 11 | |
| 29 | **GPIO_G** | General Purpose I/O | GPIO 39 | GP 12 | |
| 30 | **GPIO_H** | General Purpose I/O | GPIO 40 | GP 13 | |
| 31 | **BOOT** | Boot Mode Select | GPIO 0 | RUN | ESP32-S3 Boot button/Pico RUN pin |
| 32 | **EN** | Enable/Reset | EN | RUN | ESP32-S3 Enable/Pico RUN pin |
| 33 | **USB_DP** | USB D+ | GPIO 20 | GP 20 | USB data lines for phone compute |
| 34 | **USB_DM** | USB D- | GPIO 19 | GP 21 | |
| 35 | **SPI1_MOSI** | SPI Bus 1 MOSI | GPIO 35 | GP 22 | Secondary SPI for high-bandwidth rail |
| 36 | **SPI1_MISO** | SPI Bus 1 MISO | GPIO 36 | GP 23 | |
| 37 | **SPI1_CLK** | SPI Bus 1 Clock | GPIO 37 | GP 24 | |
| 38 | **SPI1_CS** | SPI Bus 1 Chip Select | GPIO 41 | GP 25 | |
| 39 | **GND** | Ground | GND | GND | |
| 40 | **GND** | Ground | GND | GND | |

## Power Architecture Component Values

| Component | Value | Footprint | Function | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **U1 (Buck)** | MP1584EN | SOIC8E | Main 5V Regulator | Input 5-15V, Output 5V @ 3A |
| **L1** | 10 µH | 7x7mm | Buck Inductor | |
| **C_IN** | 47 µF | 1206 | Input Capacitor | Ceramic, 25V minimum |
| **C_OUT** | 22 µF | 1206 | Output Capacitor | Ceramic, 10V minimum |
| **R_FB1** | 40.2 kΩ | 0603 | Feedback Resistor (Top) | For 5V output |
| **R_FB2** | 7.68 kΩ | 0603 | Feedback Resistor (Bottom) | For 5V output |
| **U2 (LDO)** | AMS1117-3.3 | SOT-223 | 3.3V Regulator | Input 5V, Output 3.3V @ 1A |
| **C_LDO_IN** | 10 µF | 0805 | LDO Input Capacitor | |
| **C_LDO_OUT** | 10 µF | 0805 | LDO Output Capacitor | |
| **F1** | Polyfuse | SMD | Input Protection | Self-resetting fuse |
| **D1** | ESD Diode Array | SOT-23-6 | USB ESD Protection | On USB D+/D- lines |
