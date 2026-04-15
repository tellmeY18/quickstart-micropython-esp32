# Wiring Guide

Common breadboard wiring diagrams for ESP32 and ESP32-C3 projects.
All diagrams assume 3.3V logic levels unless noted otherwise.

> **Important:** The ESP32-C3 is a 3.3V device. Never connect 5V signals
> directly to GPIO pins — you will damage the chip.

---

## Table of Contents

- [LED Output](#led-output)
- [Button Input](#button-input)
- [Potentiometer (ADC Input)](#potentiometer-adc-input)
- [NeoPixel WS2812B](#neopixel-ws2812b)
- [I2C Device](#i2c-device)
- [Full Breadboard Layout](#full-breadboard-layout)
- [Wire Color Conventions](#wire-color-conventions)

---

## LED Output

Drive an LED from a GPIO pin through a current-limiting resistor.

**Template:** `gpio`, `full`
**Example script:** `examples/blink.py`

### Schematic

```
   ESP32                       LED
  ┌──────┐
  │      │
  │ GPIOx├───┤ 330Ω ├───►|───┐
  │      │              Anode │ Cathode
  │  GND ├───────────────────┘
  │      │
  └──────┘
```

### Wiring Table

| ESP32 Pin | Component     | Notes                            |
|-----------|---------------|----------------------------------|
| GPIO 5    | Resistor leg 1| Any safe GPIO works              |
| —         | Resistor leg 2| Connect to LED anode (long leg)  |
| —         | LED cathode   | Short leg of LED                 |
| GND       | LED cathode   | Complete the circuit to ground   |

### Breadboard Layout

```
     ESP32-C3                    Breadboard
    ┌────────┐
    │        │
    │  GPIO5 ├──── wire ────► row 10, col a
    │        │                    │
    │   GND  ├──── wire ────►    │    row 15, col a
    │        │                    │         │
    └────────┘                    │         │
                                  │         │
                   row 10: [a]────┤330Ω├────[e]
                                        │
                   row 10: [f]────►|────[j]  (LED anode at f, cathode at j)
                                             │
                   row 15: [a]───────────────┘ (jumper to LED cathode row)
```

### Resistor Selection

| LED Color | Forward Voltage | Resistor (at 3.3V) | Current |
|-----------|-----------------|---------------------|---------|
| Red       | ~1.8V           | 330Ω                | ~4.5 mA |
| Green     | ~2.2V           | 220Ω                | ~5.0 mA |
| Blue      | ~3.0V           | 100Ω                | ~3.0 mA |
| White     | ~3.0V           | 100Ω                | ~3.0 mA |

> **Tip:** 330Ω works safely for all LED colors at 3.3V. When in doubt, use 330Ω.

---

## Button Input

Read a tactile push button using the ESP32's internal pull-up resistor.
No external resistor needed.

**Template:** `gpio`, `full`
**Example script:** `examples/button_read.py`

### Schematic

```
   ESP32                     Button
  ┌──────┐
  │      │               ┌──/ ──┐
  │ GPIOx├───────────────┤       │
  │      │               └───────┘
  │  GND ├───────────────────┘
  │      │
  └──────┘

  Internal pull-up enabled in software:
    Pin(x, Pin.IN, Pin.PULL_UP)

  Button open  → GPIO reads HIGH (1)
  Button pressed → GPIO reads LOW (0)
```

### Wiring Table

| ESP32 Pin | Component     | Notes                                   |
|-----------|---------------|-----------------------------------------|
| GPIO 4    | Button leg 1  | Any safe GPIO works                     |
| GND       | Button leg 2  | Other side of the same button           |

### How It Works

```
  Button OPEN (not pressed):          Button CLOSED (pressed):

  3.3V ──┤pull-up├── GPIO ── ○  ○     3.3V ──┤pull-up├── GPIO ──────┐
                     reads HIGH (1)                      reads LOW (0)│
                                                                GND ──┘
```

The internal pull-up resistor (~45 kΩ) holds the GPIO high. Pressing the
button connects GPIO directly to GND, pulling it low.

### Code Pattern

```python
from machine import Pin
import time

btn = Pin(4, Pin.IN, Pin.PULL_UP)

while True:
    if btn.value() == 0:       # 0 = pressed (pulled to GND)
        print("Button pressed!")
    time.sleep_ms(100)         # Simple debounce
```

---

## Potentiometer (ADC Input)

Read an analog voltage (0–3.3V) using a potentiometer as a voltage divider.

**Template:** `sensors`, `full`
**Example script:** `examples/adc_read.py`

### Schematic

```
   ESP32                    Potentiometer (10 kΩ typical)
  ┌──────┐
  │      │                    ┌──────────┐
  │ 3.3V ├────────────────────┤ Top      │
  │      │                    │          │
  │ GPIOx├────────────────────┤ Wiper    │  ← analog voltage out
  │      │                    │          │
  │  GND ├────────────────────┤ Bottom   │
  │      │                    └──────────┘
  └──────┘

  Wiper position:
    Full CCW  → 0V    (reads ~0)
    Middle    → 1.65V (reads ~32768)
    Full CW   → 3.3V  (reads ~65535)
```

### Wiring Table

| ESP32 Pin | Pot Terminal | Notes                              |
|-----------|--------------|------------------------------------|
| 3.3V      | Top pin      | Reference voltage (top of divider) |
| GPIO 2    | Wiper (middle)| Must be an ADC-capable pin        |
| GND       | Bottom pin   | Ground (bottom of divider)         |

### ADC-Capable Pins

| Chip      | ADC1 Pins                    | ADC2 Pins            | Notes                        |
|-----------|------------------------------|----------------------|------------------------------|
| ESP32     | GPIO 32–39                   | GPIO 0, 2, 4, 12–15 | ADC2 unavailable during WiFi |
| ESP32-C3  | GPIO 0–4                     | —                    | Only ADC1, always available  |

> **Warning:** On the original ESP32, ADC2 pins cannot be used while WiFi is active.
> Use ADC1 pins (GPIO 32–39) for reliable analog reads in web server templates.

### Attenuation Settings

| Setting | Input Range | Best For               |
|---------|-------------|------------------------|
| 0 dB    | 0–1.1V      | Precise low-voltage    |
| 2.5 dB  | 0–1.5V      | Sensor outputs         |
| 6 dB    | 0–2.2V      | Mid-range signals      |
| 11 dB   | 0–3.3V      | Full-range pot reading |

Default in all templates is `11db` (full 0–3.3V range). Set `adc_atten` in
`config.json` to change.

---

## NeoPixel WS2812B

Control individually addressable RGB LEDs (WS2812B / NeoPixel).

**Template:** `neopixel`, `full`

### Schematic — Small Strip (1–8 LEDs)

Powered directly from the ESP32's 3.3V pin:

```
   ESP32                    NeoPixel Strip
  ┌──────┐                 ┌──────────────────────┐
  │      │                 │  LED0   LED1   LED2  │
  │ GPIOx├─────────────────┤ DIN                  │
  │      │                 │                      │
  │ 3.3V ├─────────────────┤ VCC                  │
  │      │                 │                      │
  │  GND ├─────────────────┤ GND                  │
  │      │                 └──────────────────────┘
  └──────┘
```

### Schematic — Large Strip (9+ LEDs)

Requires external 5V power supply. **Do NOT power more than 8 LEDs from
the ESP32's 3.3V pin** — you will brown out the board.

```
   ESP32                     NeoPixel Strip            5V PSU
  ┌──────┐                  ┌──────────────┐        ┌────────┐
  │      │                  │              │        │        │
  │ GPIOx├──────────────────┤ DIN          │        │        │
  │      │                  │              │        │        │
  │      │                  │ VCC ─────────┼────────┤ +5V    │
  │      │                  │              │        │        │
  │  GND ├──────────────────┤ GND ─────────┼────────┤ GND    │
  │      │                  └──────────────┘        └────────┘
  └──────┘

  ⚠ CRITICAL: ESP32 GND and PSU GND MUST be connected (common ground).
  ⚠ The 3.3V data signal usually works with 5V strips, but if you get
    flickering, add a level shifter (3.3V → 5V) on the DIN line.
```

### Wiring Table

| ESP32 Pin | NeoPixel Pin | Notes                                |
|-----------|--------------|--------------------------------------|
| GPIO 10   | DIN          | Data in — any output-capable GPIO    |
| 3.3V      | VCC          | Only for ≤8 LEDs; else use 5V PSU   |
| GND       | GND          | Must share ground with ESP32         |

### Power Budget

Each WS2812B LED draws up to 60 mA at full white (R=255, G=255, B=255):

| LED Count | Max Current | Power Source          |
|-----------|-------------|-----------------------|
| 1–8       | 480 mA      | ESP32 3.3V pin (OK)   |
| 9–30      | 1.8 A       | External 5V, 2A PSU   |
| 31–60     | 3.6 A       | External 5V, 5A PSU   |
| 60+       | 3.6 A+      | Inject power at both ends |

### Config Example

```json
{
  "neopixel_pin": 10,
  "neopixel_count": 8
}
```

---

## I2C Device

Connect an I2C peripheral (sensor, display, etc.) using the SoftI2C bus.

**Template:** `sensors`, `full`
**Example script:** `examples/i2c_scan.py`

### Schematic

```
   ESP32                           I2C Device
  ┌──────┐                        ┌──────────┐
  │      │                        │          │
  │ GPIOx├──── SDA ───────────────┤ SDA      │
  │      │          │             │          │
  │ GPIOy├──── SCL ──┼────────────┤ SCL      │
  │      │           │  │         │          │
  │ 3.3V ├───────────┼──┼─────────┤ VCC      │
  │      │           │  │         │          │
  │  GND ├───────────┼──┼─────────┤ GND      │
  │      │           │  │         └──────────┘
  └──────┘           │  │
                 ┌───┘  └───┐
                 │  4.7kΩ   │  4.7kΩ      ← Pull-up resistors
                 │          │                (to 3.3V)
              3.3V        3.3V
```

### Wiring Table

| ESP32 Pin | I2C Device | Notes                                     |
|-----------|------------|-------------------------------------------|
| GPIO 6    | SDA        | Data line (default for ESP32-C3 templates) |
| GPIO 7    | SCL        | Clock line (default for ESP32-C3 templates)|
| 3.3V      | VCC        | Power the device                           |
| GND       | GND        | Common ground                              |

### Pull-Up Resistors

I2C requires pull-up resistors on both SDA and SCL lines. Many breakout
boards (Adafruit, SparkFun, etc.) include on-board pull-ups. If yours
doesn't, add external resistors:

| Bus Speed  | Recommended Pull-Up | Notes                      |
|------------|---------------------|----------------------------|
| 100 kHz    | 4.7 kΩ              | Standard mode (default)    |
| 400 kHz    | 2.2 kΩ              | Fast mode                  |

> **How to tell if you need pull-ups:** Run `esp run examples/i2c_scan.py`.
> If it finds no devices but the device is wired and powered, you likely
> need pull-up resistors. If the scan hangs, the pull-ups are definitely missing.

### Common I2C Addresses

| Device         | Address (hex) | Address (dec) | What It Is              |
|----------------|---------------|---------------|-------------------------|
| BME280         | 0x76 or 0x77  | 118 or 119    | Temp/humidity/pressure  |
| BMP280         | 0x76 or 0x77  | 118 or 119    | Temp/pressure           |
| SSD1306 OLED   | 0x3C or 0x3D  | 60 or 61      | 128x64 OLED display     |
| AHT20          | 0x38          | 56            | Temp/humidity           |
| MPU6050        | 0x68 or 0x69  | 104 or 105    | Accelerometer/gyro      |
| BH1750         | 0x23 or 0x5C  | 35 or 92      | Light sensor            |
| PCF8574        | 0x20–0x27     | 32–39         | I/O expander            |

### Config Example

```json
{
  "i2c_sda": 6,
  "i2c_scl": 7,
  "i2c_freq": 100000
}
```

---

## Full Breadboard Layout

A comprehensive setup with an LED, button, potentiometer, and I2C device
all on one breadboard. Use this as a starting point for the `full` template
or when combining multiple templates.

### Physical Layout

```
                        Full-size breadboard (830 tie-points)
    ┌──────────────────────────────────────────────────────────────────┐
    │  + (red)   ════════════════════════════════════════  3.3V rail   │
    │  − (blue)  ════════════════════════════════════════  GND rail    │
    │                                                                  │
    │   1  5  10  15  20  25  30  35  40  45  50  55  60              │
    │  ┌──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┐               │
    │ a│  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │               │
    │ b│  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │               │
    │ c│  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │               │
    │ d│  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │               │
    │ e│  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │               │
    │  ├──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┤  ← center    │
    │ f│  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │    gap        │
    │ g│  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │               │
    │ h│  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │               │
    │ i│  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │               │
    │ j│  │  │  │  │  │  │  │  │  │  │  │  │  │  │  │               │
    │  └──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┴──┘               │
    │                                                                  │
    │  + (red)   ════════════════════════════════════════  3.3V rail   │
    │  − (blue)  ════════════════════════════════════════  GND rail    │
    └──────────────────────────────────────────────────────────────────┘
```

### Component Placement

```
  ESP32-C3 DevKit (plugged across center gap at columns 1-15)

  Component 1: LED + Resistor (columns 20-25)
  ──────────────────────────────────────────
  Wire: GPIO 5 → row 20, col a
  330Ω resistor: row 20 col a ↔ row 20 col e  (across top half)
  LED anode (long leg): row 20, col f
  LED cathode (short leg): row 21, col f
  Wire: row 21, col a → GND rail

  Component 2: Button (columns 28-30)
  ──────────────────────────────────────────
  Tactile button: straddles center gap at rows 28-29
    Leg A: row 28, col e
    Leg B: row 28, col f
    Leg C: row 29, col e  (connected to A internally)
    Leg D: row 29, col f  (connected to B internally)
  Wire: GPIO 4 → row 28, col a
  Wire: row 28, col j → GND rail

  Component 3: Potentiometer (columns 35-37)
  ──────────────────────────────────────────
  Pot pin 1 (top):    row 35, col a → wire to 3.3V rail
  Pot pin 2 (wiper):  row 36, col a → wire to GPIO 2
  Pot pin 3 (bottom): row 37, col a → wire to GND rail

  Component 4: I2C Device (columns 45-50)
  ──────────────────────────────────────────
  I2C breakout pinout varies, but typically:
  VCC: wire to 3.3V rail
  GND: wire to GND rail
  SDA: wire to GPIO 6
  SCL: wire to GPIO 7
  4.7kΩ pull-up: 3.3V rail → SDA line (if no on-board pull-up)
  4.7kΩ pull-up: 3.3V rail → SCL line (if no on-board pull-up)
```

### Complete Wiring Summary

| ESP32-C3 Pin | Row/Col        | Component            | Function          |
|--------------|----------------|----------------------|-------------------|
| 3.3V         | + rail (top)   | Power rail           | 3.3V supply       |
| GND          | − rail (top)   | Ground rail          | Common ground     |
| GPIO 5       | row 20, col a  | 330Ω → LED           | LED output        |
| GPIO 4       | row 28, col a  | Tactile button       | Button input      |
| GPIO 2       | row 36, col a  | Pot wiper            | ADC analog input  |
| GPIO 6       | row 45, col a  | I2C device SDA       | I2C data          |
| GPIO 7       | row 47, col a  | I2C device SCL       | I2C clock         |

### Matching Config

```json
{
  "device_name": "ESP32-Full",
  "wifi_ssid": "YOUR_SSID",
  "wifi_password": "YOUR_PASSWORD",
  "ap_ssid": "ESP32-Full",
  "ap_password": "12345678",
  "web_port": 80,
  "gpio_whitelist": [5],
  "pin_aliases": {
    "led": 5,
    "button": 4
  },
  "adc_pins": [2],
  "adc_atten": "11db",
  "i2c_sda": 6,
  "i2c_scl": 7,
  "i2c_freq": 100000
}
```

---

## Wire Color Conventions

Using consistent wire colors makes debugging much easier:

| Color  | Signal    | Notes                        |
|--------|-----------|------------------------------|
| Red    | 3.3V / VCC| Power supply                 |
| Black  | GND       | Ground                       |
| Yellow | SCL       | I2C clock                    |
| Blue   | SDA       | I2C data                     |
| Green  | Data      | NeoPixel DIN, general signal |
| White  | GPIO      | General-purpose connections  |
| Orange | ADC       | Analog signals               |

---

## Safety Reminders

1. **Never exceed 3.3V on any GPIO pin.** The ESP32 is not 5V-tolerant.
2. **Never draw more than 40 mA from a single GPIO pin.** Use a transistor or MOSFET for higher-current loads.
3. **Never connect anything to GPIO 20/21 on ESP32-C3.** These are UART0 (REPL) pins.
4. **Always use a current-limiting resistor with LEDs.** Without one, you may damage the LED or the GPIO.
5. **Double-check polarity before powering on.** Reversed power on I2C sensors or NeoPixels can destroy them instantly.
6. **Disconnect the board from USB before making wiring changes.** Hot-wiring on a breadboard is fine for signals but risky for power.

> See [pin-reference.md](pin-reference.md) for complete GPIO maps and safe-pin tables.
> See [troubleshooting.md](troubleshooting.md) if something isn't working.