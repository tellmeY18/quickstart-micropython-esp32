# Sensors Template

ADC voltage reading, I2C bus communication, and internal temperature sensing over a REST API with a live HTML dashboard.

## What This Template Does

Boots the ESP32, connects to WiFi (or starts an AP fallback), and serves:

- **`GET /`** — An HTML dashboard with live ADC gauge bars (auto-refresh every 2s), I2C device list, internal temperature display, and system status
- **`GET /api/status`** — JSON health-check endpoint
- **`GET /api/temperature`** — Internal MCU temperature in degrees Celsius
- **`GET /api/adc/all`** — Read all 5 ADC pins at once
- **`GET /api/adc/<pin>`** — Read a single ADC pin
- **`POST /api/adc/<pin>/config`** — Set ADC attenuation for a pin
- **`GET /api/i2c/scan`** — Scan the I2C bus for connected devices
- **`POST /api/i2c/read`** — Read bytes from an I2C device
- **`POST /api/i2c/write`** — Write bytes to an I2C device
- **`POST /api/i2c/write_read`** — Write-then-read I2C transaction
- **`POST /api/i2c/config`** — Reconfigure the I2C bus pins and frequency

No digital GPIO control, no PWM, no WebSocket streaming. For those features, see the `gpio`, `pwm`, or `full` templates.

## Files Included

| File | Purpose |
|---|---|
| `main.py` | Microdot web server with dashboard + status endpoint (~180 lines) |
| `sensor_handler.py` | ADC, I2C, and temperature API route handlers (~470 lines) |
| `config.json.example` | Configuration template (WiFi, ADC attenuation, I2C pins) |

Plus shared core files copied by `esp init`:

- `boot.py` — WiFi connect with AP fallback
- `lib/microdot.py` — Vendored Microdot async web framework

## Setup

```sh
nix develop                    # Enter the dev shell
esp detect                     # Verify board is connected
esp erase && esp flash         # First time only: flash MicroPython firmware
esp init sensors               # Scaffold this template
# Edit config.json — set wifi_ssid and wifi_password
esp sync                       # Push files to board + reboot
```

Open `http://<board-ip>/` in your browser to see the sensor dashboard.

## Configuration

`config.json` fields:

```json
{
  "device_name": "ESP32-Sensors",
  "wifi_ssid": "YOUR_SSID",
  "wifi_password": "YOUR_PASSWORD",
  "ap_ssid": "ESP32-Sensors",
  "ap_password": "12345678",
  "web_port": 80,
  "adc_atten": "11db",
  "i2c_sda": 6,
  "i2c_scl": 7,
  "i2c_freq": 100000
}
```

| Key | Type | Default | Description |
|---|---|---|---|
| `device_name` | string | `"ESP32-Sensors"` | Displayed in the dashboard title and `/api/status` |
| `wifi_ssid` | string | — | Your WiFi network name (2.4 GHz only) |
| `wifi_password` | string | — | Your WiFi password |
| `ap_ssid` | string | `"ESP32-Sensors"` | Fallback access point name |
| `ap_password` | string | `"12345678"` | Fallback access point password (min 8 chars) |
| `web_port` | int | `80` | HTTP server port |
| `adc_atten` | string | `"11db"` | Default ADC attenuation for all pins (see table below) |
| `i2c_sda` | int | `6` | GPIO pin number for I2C SDA line |
| `i2c_scl` | int | `7` | GPIO pin number for I2C SCL line |
| `i2c_freq` | int | `100000` | I2C bus clock frequency in Hz |
| `pin_aliases` | object | `{}` | Optional pin name aliases, e.g. `{"light": 0, "pot": 1}` |

## ADC Attenuation

The attenuation setting controls the ADC input voltage range. Higher attenuation allows reading higher voltages but reduces precision.

| Attenuation | Config Value | Input Range | Best For |
|---|---|---|---|
| 0 dB | `"0db"` | 0 – 0.75 V | Precision measurements, voltage dividers |
| 2.5 dB | `"2.5db"` | 0 – 1.05 V | Low-voltage sensors |
| 6 dB | `"6db"` | 0 – 1.75 V | Mid-range sensors |
| 11 dB | `"11db"` | 0 – 3.3 V | General purpose (default), potentiometers |

> **Note:** The ESP32-C3 has 5 ADC pins (GPIO 0–4) on ADC1 only. There is no ADC2 on the C3. All 5 pins use 12-bit resolution (0–65535 via `read_u16()`).

## API Reference

### `GET /api/status`

Returns device health information.

```sh
curl -s http://192.168.1.42/api/status | jq
```

```json
{
  "device_name": "ESP32-Sensors",
  "ip": "192.168.1.42",
  "wifi_mode": "STA",
  "rssi_dbm": -45,
  "wifi_quality": "excellent",
  "uptime_s": 120,
  "free_mem": 165000,
  "free_mem_kb": 161
}
```

---

### `GET /api/temperature`

Returns the ESP32's internal MCU temperature.

```sh
curl -s http://192.168.1.42/api/temperature | jq
```

```json
{
  "temp_c": 42.5
}
```

> **Note:** This is the *chip* temperature, not an external sensor. It is useful for monitoring board health but should not be used as an ambient temperature reading.

---

### `GET /api/adc/all`

Read all 5 ADC-capable pins (GPIO 0–4) in a single request.

```sh
curl -s http://192.168.1.42/api/adc/all | jq
```

```json
{
  "readings": {
    "0": {"pin": 0, "raw": 32768, "voltage_uv": 1650000, "voltage_v": 1.65, "atten": "11db"},
    "1": {"pin": 1, "raw": 0, "voltage_uv": 0, "voltage_v": 0.0, "atten": "11db"},
    "2": {"pin": 2, "raw": 65535, "voltage_uv": 3300000, "voltage_v": 3.3, "atten": "11db"},
    "3": {"pin": 3, "raw": 0, "voltage_uv": 0, "voltage_v": 0.0, "atten": "11db"},
    "4": {"pin": 4, "raw": 12345, "voltage_uv": 620000, "voltage_v": 0.62, "atten": "11db"}
  }
}
```

---

### `GET /api/adc/<pin>`

Read a single ADC pin. The `<pin>` parameter can be a GPIO number or a pin alias defined in `config.json`.

```sh
curl -s http://192.168.1.42/api/adc/0 | jq
```

```json
{
  "pin": 0,
  "raw": 32768,
  "voltage_uv": 1650000,
  "voltage_v": 1.65,
  "atten": "11db"
}
```

| Field | Type | Description |
|---|---|---|
| `pin` | int | GPIO pin number |
| `raw` | int | Raw 16-bit ADC value (0–65535) |
| `voltage_uv` | int | Voltage in microvolts |
| `voltage_v` | float | Voltage in volts (rounded to 3 decimal places) |
| `atten` | string | Current attenuation setting |

---

### `POST /api/adc/<pin>/config`

Set the ADC attenuation for a specific pin.

```sh
curl -s -X POST http://192.168.1.42/api/adc/0/config \
  -H "Content-Type: application/json" \
  -d '{"atten": "6db"}' | jq
```

```json
{
  "pin": 0,
  "atten": "6db",
  "status": "ok"
}
```

Valid `atten` values: `"0db"`, `"2.5db"`, `"6db"`, `"11db"`.

---

### `GET /api/i2c/scan`

Scan the I2C bus for connected devices. Returns both decimal and hex addresses.

```sh
curl -s http://192.168.1.42/api/i2c/scan | jq
```

```json
{
  "devices": [60, 104],
  "hex": ["0x3c", "0x68"],
  "count": 2
}
```

---

### `POST /api/i2c/read`

Read bytes from an I2C device.

```sh
curl -s -X POST http://192.168.1.42/api/i2c/read \
  -H "Content-Type: application/json" \
  -d '{"addr": 104, "nbytes": 2}' | jq
```

```json
{
  "addr": 104,
  "data": [255, 0],
  "hex": "ff00",
  "length": 2
}
```

| Body Field | Type | Required | Description |
|---|---|---|---|
| `addr` | int | yes | I2C device address (0–127) |
| `nbytes` | int | yes | Number of bytes to read (>= 1) |

---

### `POST /api/i2c/write`

Write bytes to an I2C device.

```sh
curl -s -X POST http://192.168.1.42/api/i2c/write \
  -H "Content-Type: application/json" \
  -d '{"addr": 60, "data": [0, 16, 0]}' | jq
```

```json
{
  "addr": 60,
  "bytes_written": 3,
  "status": "ok"
}
```

| Body Field | Type | Required | Description |
|---|---|---|---|
| `addr` | int | yes | I2C device address (0–127) |
| `data` | list[int] | yes | Bytes to write (each 0–255, at least one) |

---

### `POST /api/i2c/write_read`

Write bytes to a device and immediately read back without releasing the bus. This is the standard pattern for reading registers from I2C sensors.

```sh
# Read 6 bytes starting at register 0x3B on an MPU6050 (accel data)
curl -s -X POST http://192.168.1.42/api/i2c/write_read \
  -H "Content-Type: application/json" \
  -d '{"addr": 104, "write": [59], "read": 6}' | jq
```

```json
{
  "addr": 104,
  "wrote": [59],
  "data": [0, 128, 255, 192, 64, 0],
  "hex": "0080ffc04000",
  "length": 6
}
```

| Body Field | Type | Required | Description |
|---|---|---|---|
| `addr` | int | yes | I2C device address (0–127) |
| `write` | list[int] | yes | Bytes to write first (typically a register address) |
| `read` | int | yes | Number of bytes to read back (>= 1) |

---

### `POST /api/i2c/config`

Reconfigure the I2C bus with different SDA/SCL pins or clock frequency. Takes effect immediately — the old bus instance is discarded.

```sh
curl -s -X POST http://192.168.1.42/api/i2c/config \
  -H "Content-Type: application/json" \
  -d '{"sda": 8, "scl": 9, "freq": 400000}' | jq
```

```json
{
  "sda": 8,
  "scl": 9,
  "freq": 400000,
  "status": "ok"
}
```

| Body Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `sda` | int | no | from config | GPIO pin for SDA |
| `scl` | int | no | from config | GPIO pin for SCL |
| `freq` | int | no | from config | Clock frequency in Hz |

## Common I2C Device Addresses

When you run an I2C scan, here are some frequently seen addresses and what they typically belong to:

| Address (hex) | Address (dec) | Common Device |
|---|---|---|
| `0x3c` | 60 | SSD1306 OLED display (128x64 or 128x32) |
| `0x27` | 39 | PCF8574 I2C LCD backpack (16x2 or 20x4 LCD) |
| `0x68` | 104 | MPU6050 accelerometer/gyroscope |
| `0x76` | 118 | BME280 / BMP280 temperature/humidity/pressure sensor |
| `0x77` | 119 | BME280 / BMP280 (alternate address) |
| `0x48` | 72 | ADS1115 16-bit ADC |
| `0x50` | 80 | AT24C32 / AT24C256 EEPROM |
| `0x57` | 87 | DS3231 RTC (EEPROM portion) |
| `0x23` | 35 | BH1750 ambient light sensor |
| `0x29` | 41 | VL53L0X time-of-flight distance sensor |
| `0x40` | 64 | INA219 current/power monitor, or SHT30 humidity sensor |

> **Tip:** If a scan returns no devices, double-check your wiring, confirm SDA/SCL pin numbers match `config.json`, and make sure the device has pull-up resistors on SDA and SCL (4.7kΩ to 3.3V is typical).

## Wiring Examples

### Potentiometer (ADC)

```
3.3V ──┐
       ┣── Potentiometer (10kΩ)
       │      └── Wiper → GPIO 0 (ADC)
GND  ──┘
```

### I2C Device (e.g. BME280)

```
ESP32-C3          BME280
─────────         ──────
3.3V  ──────────  VCC
GND   ──────────  GND
GPIO 6 (SDA) ───  SDA   ──┬── 4.7kΩ ── 3.3V
GPIO 7 (SCL) ───  SCL   ──┬── 4.7kΩ ── 3.3V
```

## Memory Footprint

This template uses approximately 130 KB of RAM, leaving ~190 KB free on an ESP32-C3. The I2C bus instance is created lazily on first use to save memory if you only need ADC.

## Next Steps

- **`gpio`** — Add digital pin control (toggle LEDs, read buttons)
- **`pwm`** — Add PWM output for LED dimming and servo control
- **`neopixel`** — Add WS2812B RGB LED control
- **`full`** — Everything combined with WebSocket streaming

Run `esp templates` to see all available options, or `esp init <template>` to switch.