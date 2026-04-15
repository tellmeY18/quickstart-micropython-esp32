# PWM Template

Control PWM (Pulse Width Modulation) outputs on your ESP32 over HTTP. Dim LEDs, position
servos, drive motors — anything that responds to a variable-duty-cycle signal.

## What This Does

- Starts a web server with a browser-based dashboard
- Provides REST API endpoints to start, stop, and adjust PWM on any safe GPIO pin
- Dashboard includes a real-time slider for duty cycle control with live frequency/duty readout
- Pin alias support so you can refer to pins by name in your config

## PWM Basics

PWM rapidly switches a pin between HIGH and LOW at a fixed **frequency**. The fraction of
each cycle spent HIGH is the **duty cycle**.

| Term | Range | Description |
|---|---|---|
| **Frequency** | 1 Hz – 40 MHz | How many on/off cycles per second. Higher = smoother for LEDs, but must match your device's requirements. |
| **Duty cycle (%)** | 0 – 100% | Percentage of each cycle the pin is HIGH. 0% = always off, 100% = always on. |
| **duty_u16** | 0 – 65535 | MicroPython's 16-bit duty value. 0 = 0%, 32768 = 50%, 65535 = 100%. |

### Converting Between duty_u16 and Percentage

```
duty_u16 = int(percentage / 100 * 65535)
percentage = duty_u16 / 65535 * 100
```

### Common Frequency Choices

| Use Case | Frequency | Why |
|---|---|---|
| LED dimming | 1000 Hz (1 kHz) | Fast enough to eliminate visible flicker |
| Servo control | 50 Hz | Standard hobby servo signal frequency |
| Motor speed | 1000–20000 Hz | Depends on motor driver; higher = less audible whine |
| Buzzer/tone | 200–5000 Hz | Audible range; duty ~50% for loudest output |

## Wiring Guide

### LED Dimming (Default Setup)

```
ESP32 GPIO 5 ──[ 330Ω ]──►|── GND
                         (LED)
```

1. Connect a **330Ω resistor** from GPIO 5 to the **anode** (long leg) of an LED
2. Connect the **cathode** (short leg, flat side) of the LED to **GND**
3. The 330Ω resistor limits current to ~10 mA at 3.3V — safe for the ESP32 and most LEDs

> **Tip:** If you don't have a 330Ω resistor, anything from 220Ω to 1kΩ will work. Lower
> resistance = brighter LED, higher = dimmer. Don't go below 100Ω.

### Servo Motor (50 Hz)

```
Servo ─── Red ────── 5V (external supply)
      ─── Brown/Blk ─ GND (shared with ESP32)
      ─── Orange ──── ESP32 GPIO 5
```

> **Important:** Power servos from an external 5V supply, not from the ESP32's 3.3V pin.
> Connect the grounds together (ESP32 GND ↔ servo supply GND).

Servo pulse width mapping at 50 Hz (20 ms period):

| Position | Pulse Width | duty_u16 |
|---|---|---|
| 0° (min) | 1.0 ms | `int(1.0 / 20.0 * 65535)` = **3277** |
| 90° (center) | 1.5 ms | `int(1.5 / 20.0 * 65535)` = **4915** |
| 180° (max) | 2.0 ms | `int(2.0 / 20.0 * 65535)` = **6554** |

## Quick Start

```sh
esp init pwm                   # scaffold from this template
vim config.json                # set wifi_ssid and wifi_password
esp sync                       # push to board + reset
# open http://<board-ip>/ in a browser
```

## Configuration

Edit `config.json` (copied from `config.json.example` during `esp init`):

```json
{
  "device_name": "ESP32-PWM",
  "wifi_ssid": "YOUR_SSID",
  "wifi_password": "YOUR_PASSWORD",
  "ap_ssid": "ESP32-PWM",
  "ap_password": "12345678",
  "web_port": 80,
  "pin_aliases": {
    "led": 5
  }
}
```

### Pin Aliases

The `pin_aliases` object lets you refer to pins by name in the API and dashboard. The
dashboard uses the `"led"` alias by default (falls back to GPIO 5 if not defined).

You can add more aliases:

```json
"pin_aliases": {
  "led": 5,
  "servo": 6,
  "motor": 7
}
```

## API Reference

All endpoints accept and return JSON. Replace `<pin>` with a GPIO number (e.g., `5`) or
a pin alias (e.g., `led`).

### Start PWM

```
POST /api/pwm/<pin>/start
```

Initialize PWM on a pin with the given frequency and duty cycle.

**Request body:**

```json
{
  "freq": 1000,
  "duty_u16": 32768
}
```

| Field | Type | Range | Default | Description |
|---|---|---|---|---|
| `freq` | int | 1 – 40000000 | *required* | Frequency in Hz |
| `duty_u16` | int | 0 – 65535 | 0 | 16-bit duty cycle value |

**Example — start LED dimming at 50%:**

```sh
curl -X POST http://192.168.1.100/api/pwm/led/start \
  -H "Content-Type: application/json" \
  -d '{"freq": 1000, "duty_u16": 32768}'
```

**Example — start servo at center position (90°):**

```sh
curl -X POST http://192.168.1.100/api/pwm/6/start \
  -H "Content-Type: application/json" \
  -d '{"freq": 50, "duty_u16": 4915}'
```

**Response (200):**

```json
{
  "pin": 5,
  "mode": "PWM",
  "freq": 1000,
  "duty_u16": 32768,
  "duty_pct": 50.0
}
```

**Error — forbidden pin (409):**

```json
{
  "error": "Pin 20 is reserved for UART RX and cannot be used as an output."
}
```

**Error — mode conflict (409):**

```json
{
  "error": "Pin 5 is currently in a different mode. Stop the current mode before starting PWM."
}
```

### Set Duty Cycle

```
POST /api/pwm/<pin>/duty
```

Change the duty cycle on a pin that already has PWM running.

**Request body:**

```json
{
  "duty_u16": 49152
}
```

**Example — set LED to 75% brightness:**

```sh
curl -X POST http://192.168.1.100/api/pwm/led/duty \
  -H "Content-Type: application/json" \
  -d '{"duty_u16": 49152}'
```

**Response (200):**

```json
{
  "pin": 5,
  "mode": "PWM",
  "freq": 1000,
  "duty_u16": 49152,
  "duty_pct": 75.0
}
```

**Error — pin not in PWM mode (400):**

```json
{
  "error": "Pin 5 is not currently in PWM mode. Start PWM first with POST /api/pwm/5/start."
}
```

### Set Frequency

```
POST /api/pwm/<pin>/freq
```

Change the frequency on a pin that already has PWM running.

**Request body:**

```json
{
  "freq": 5000
}
```

**Example — change to 5 kHz:**

```sh
curl -X POST http://192.168.1.100/api/pwm/led/freq \
  -H "Content-Type: application/json" \
  -d '{"freq": 5000}'
```

**Response (200):**

```json
{
  "pin": 5,
  "mode": "PWM",
  "freq": 5000,
  "duty_u16": 49152,
  "duty_pct": 75.0
}
```

### Stop PWM

```
POST /api/pwm/<pin>/stop
```

Deinitialize PWM on a pin and release it for other use.

**Example:**

```sh
curl -X POST http://192.168.1.100/api/pwm/led/stop
```

**Response (200):**

```json
{
  "pin": 5,
  "status": "stopped",
  "mode": "released"
}
```

### Read PWM State

```
GET /api/pwm/<pin>
```

Get the current PWM configuration for a pin.

**Example:**

```sh
curl http://192.168.1.100/api/pwm/led
```

**Response (200):**

```json
{
  "pin": 5,
  "mode": "PWM",
  "freq": 1000,
  "duty_u16": 32768,
  "duty_pct": 50.0
}
```

**Error — pin not active (404):**

```json
{
  "error": "Pin 5 has no active PWM configuration."
}
```

### System Endpoints

These are provided by `main.py` directly:

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Dashboard with PWM slider UI |
| `/api/status` | GET | Device name, uptime, IP, RSSI, free memory |

## Dashboard

The web dashboard at `http://<board-ip>/` provides:

- **Status panel** — device name, uptime, WiFi signal strength, free memory
- **PWM control** — start/stop button, frequency display, duty cycle slider (0–100%)
- **Live readout** — current frequency and duty cycle update as you adjust the slider

The slider is debounced to a maximum of 5 requests per second to avoid flooding the board.

## Common Use Cases

### LED Brightness Control

```sh
# Start at 1 kHz, 0% brightness
curl -X POST http://192.168.1.100/api/pwm/led/start \
  -d '{"freq": 1000, "duty_u16": 0}'

# Gradually increase brightness
curl -X POST http://192.168.1.100/api/pwm/led/duty -d '{"duty_u16": 16384}'   # 25%
curl -X POST http://192.168.1.100/api/pwm/led/duty -d '{"duty_u16": 32768}'   # 50%
curl -X POST http://192.168.1.100/api/pwm/led/duty -d '{"duty_u16": 49152}'   # 75%
curl -X POST http://192.168.1.100/api/pwm/led/duty -d '{"duty_u16": 65535}'   # 100%

# Turn off
curl -X POST http://192.168.1.100/api/pwm/led/stop
```

### Servo Sweep (50 Hz)

```sh
# Start servo PWM at 50 Hz, centered
curl -X POST http://192.168.1.100/api/pwm/6/start \
  -d '{"freq": 50, "duty_u16": 4915}'

# Move to 0° (1 ms pulse)
curl -X POST http://192.168.1.100/api/pwm/6/duty -d '{"duty_u16": 3277}'

# Move to 180° (2 ms pulse)
curl -X POST http://192.168.1.100/api/pwm/6/duty -d '{"duty_u16": 6554}'

# Release servo
curl -X POST http://192.168.1.100/api/pwm/6/stop
```

### Buzzer Tone (Square Wave)

```sh
# Play a 440 Hz tone (A4 note) at 50% duty for a square wave
curl -X POST http://192.168.1.100/api/pwm/7/start \
  -d '{"freq": 440, "duty_u16": 32768}'

# Change pitch
curl -X POST http://192.168.1.100/api/pwm/7/freq -d '{"freq": 880}'   # A5
curl -X POST http://192.168.1.100/api/pwm/7/freq -d '{"freq": 1760}'  # A6

# Silence
curl -X POST http://192.168.1.100/api/pwm/7/stop
```

## Safe Pins (ESP32-C3)

| GPIO | OK for PWM? | Notes |
|---|---|---|
| 0–10 | ✅ Yes | General-purpose, safe for output |
| 18–19 | ✅ Yes | USB D-/D+ on some boards, but usable for PWM |
| 20 | ❌ No | UART RX — reserved, blocked by firmware |
| 21 | ❌ No | UART TX — reserved, blocked by firmware |

## Troubleshooting

**"Pin X is reserved for UART RX/TX"** — Pins 20 and 21 are used for serial communication.
Use a different pin.

**"Pin X is currently in a different mode"** — The pin is being used for something else
(e.g., digital output). Stop the other mode first before starting PWM.

**LED not dimming, just on/off** — Make sure your frequency is high enough (≥100 Hz). At
very low frequencies, you'll see the LED blink rather than dim.

**Servo jittering** — Ensure the servo has its own power supply and shares a common ground
with the ESP32. Also verify frequency is exactly 50 Hz.

**MemoryError** — Run `esp log` to check memory usage. This template is lightweight
(~130 KB) but if you've added other code, you may need to free resources.