# SSD1306 Video Player for ESP32

Play monochrome video on a 128×64 SSD1306 OLED using an ESP32. This repository includes two playback examples and a Python GUI that converts video clips into raw `.dat` frame files.

> **Current implementation note:** the “MCU memory” sketch included here stores the `.dat` file in **LittleFS on the ESP32's internal flash**. It does not embed the video as a C/C++ array in the firmware image. The SD-card sketch reads the file from an SD card.

## Features

- SSD1306 128×64 monochrome OLED playback
- SD-card playback using SPI
- Internal-flash filesystem playback using LittleFS
- Python GUI converter with preview, trim, crop, zoom, brightness, contrast, threshold, text overlay, and image modes
- Raw frame format designed to match the Adafruit SSD1306 framebuffer

## Repository layout

```text
ssd1306-video-player/
├── README.md
├── LICENSE
├── .gitignore
├── requirements.txt
├── converter/
│   └── conv7.py
├── firmware/
│   ├── sd-card/
│   │   └── esp32_sdcard.ino
│   └── mcu-memory/
│       └── esp32_littlefs_player.ino
├── docs/
│   └── wiring.md
└── examples/
    └── .gitkeep
```

## Hardware

- ESP32 development board (the included pin defaults target a generic ESP32 Dev Module)
- 128×64 SSD1306 I²C OLED, usually at address `0x3C` (the SD-card sketch also tries `0x3D`)
- For SD playback: SPI microSD card module and a FAT-formatted microSD card

Check your module's voltage requirements before wiring it. Do not assume every SD module or OLED breakout is 5 V tolerant.

## 1. Convert a video to `.dat`

### Install Python dependencies

Python 3.9 or newer is recommended.

```bash
python -m venv .venv
```

Activate the environment:

**Windows**
```bat
.venv\Scripts\activate
```

**macOS/Linux**
```bash
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Launch the converter:

```bash
python converter/conv7.py
```

Open a supported video, adjust the preview and trim range, select `128x64 (Standard)`, choose an output filename, and click **Export to .DAT**.

### Output format

The converter writes frames consecutively, with no header or metadata.

For 128×64:
- One frame = `128 × 64 / 8 = 1024` bytes
- Byte order = SSD1306 page layout: 8 vertical pixels per byte, columns within each page
- Bit 0 represents the top pixel of each 8-pixel page
- Frame N begins at byte offset `N × 1024`

The current firmware sketches expect **128×64 / 1024-byte frames**. Although the GUI offers `128x32`, the supplied firmware has a fixed 1024-byte frame size and is not compatible with 128×32 exports without code changes.

Approximate file size:

`file size in bytes = frame count × 1024`

For example, a 10-second clip at 15 frames per second is about 150 × 1024 = 153,600 bytes (about 150 KiB). The converter currently exports the source/trimmed frame sequence; it does not currently provide a separate output-FPS control.

## 2. Playback from an SD card

Sketch: [`firmware/sd-card/esp32_sdcard.ino`](firmware/sd-card/esp32_sdcard.ino)

1. Install the Arduino libraries listed below.
2. Open the sketch in Arduino IDE.
3. Confirm the OLED and SD-card pin definitions at the top of the sketch.
4. Copy the exported `.dat` file to the root directory of the microSD card.
5. Insert the card and upload the sketch.
6. Open Serial Monitor at **115200 baud** for status and playback statistics.

Default pin assignments:

| Device signal | ESP32 pin |
|---|---:|
| OLED SDA | GPIO 21 |
| OLED SCL | GPIO 22 |
| SD MOSI | GPIO 23 |
| SD MISO | GPIO 19 |
| SD SCK | GPIO 18 |
| SD CS | GPIO 5 |

The sketch scans the card root and plays files ending in `.dat`. Press `s` in Serial Monitor to stop the current playback.

## 3. Playback from internal flash (LittleFS)

Sketch: [`firmware/mcu-memory/esp32_littlefs_player.ino`](firmware/mcu-memory/esp32_littlefs_player.ino)

This example opens `/11.dat` from LittleFS. You must upload the `.dat` file to the ESP32 LittleFS filesystem using a compatible filesystem upload workflow/tool for your Arduino-ESP32 version, and configure a suitable filesystem partition. Change `playVideo("/11.dat")` to match the uploaded file name.

LittleFS space is limited by the partition layout. A video file must fit in the available filesystem partition, leaving space for the firmware and filesystem overhead.

This method is **flash-filesystem playback**, not a video array compiled into program memory. A true compile-time embedded video would use a generated C/C++ byte array and a different playback function.

## Arduino libraries

Install these libraries through Arduino IDE Library Manager:
- Adafruit GFX Library
- Adafruit SSD1306

The ESP32 Arduino core supplies `Wire`, `SPI`, `SD`, and `LittleFS` support for compatible ESP32 boards.

## Wiring

See [`docs/wiring.md`](docs/wiring.md). Pin assignments can differ by board; change the definitions in the sketch to match your hardware.

## Known limitations / things to verify

- Current sketches target a 128×64 display and 1024-byte frames.
- Playback timing is targeted at approximately 60 FPS, but actual frame rate depends on display I²C speed, SD/filesystem read speed, and processing overhead.
- The converter's 128×32 option currently does not match the supplied firmware frame size.
- Test with a short clip first and check the reported frame count and FPS.
- The included sketches have been organized from the supplied files; hardware-specific behavior should be tested on your board before release.

## Contributing

Issues and pull requests are welcome. Useful next improvements include configurable playback FPS, explicit 128×32 firmware support, a small sample `.dat` clip, and a true firmware-embedded video example.

## License

MIT — see [`LICENSE`](LICENSE).
