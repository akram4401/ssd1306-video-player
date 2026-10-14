# Wiring

## SSD1306 I²C OLED (default ESP32 pins)

| OLED | ESP32 |
|---|---:|
| VCC | Use the voltage supported by your OLED breakout |
| GND | GND |
| SDA | GPIO 21 |
| SCL | GPIO 22 |

## SPI microSD module (SD-card sketch defaults)

| SD module | ESP32 |
|---|---:|
| CS | GPIO 5 |
| SCK / CLK | GPIO 18 |
| MISO | GPIO 19 |
| MOSI | GPIO 23 |
| VCC | Follow the module's input-voltage requirements |
| GND | GND |

Both devices share ground. The SD-card sketch uses SPI pins that are separate from the OLED's I²C pins. Verify the pinout of your exact ESP32 board and modules before powering the circuit.
