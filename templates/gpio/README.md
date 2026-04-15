# GPIO Template

Digital GPIO control over a REST API. Toggle LEDs, read buttons, and monitor pin states from a browser dashboard or with `curl`.

## What This Template Does

Boots the ESP32, connects to WiFi (or starts an AP fallback), and serves:

- **`GET /`** — An HTML dashboard with device status and a GPIO toggle panel for every pin in `gpio_whitelist`
- **`GET /api/status`** — JSON health-check endpoint (device name, IP, uptime, free memory)
- **`GET /api/gpio/*`** — REST API for reading and writing digital GPIO pins

The dashboard auto-refreshes pin states every 2 seconds. Pins can be toggled directly from the browser — unconfigured pins are automatically set to OUT mode on first toggle.

## Files Included

| File | Purpose |
|---|---|
| `main.py` | Microdot web server with status dashboard + GPIO toggle panel |
| `gpio_handler.py` | GPIO route handler — pin read/write/toggle over REST API |
| `config.json.example` | Configuration template (WiFi, pin aliases, GPIO whitelist) |

Plus shared core files copied by `esp init`:

- `boot.py` — WiFi connect with AP fallback
- `lib/microdot.py` — Vendored Microdot async web framework

## Setup

```sh
nix develop                    # Enter the dev shell
esp detect                     # Verify board is connected
esp erase && esp flash         # First time only: flash MicroPython firmware
esp init gpio                  # Scaffold this template
# Edit config.json — set wifi_ssid, wifi_password, and gpio_whitelist
esp sync                       # Push files to board + reboot
```

Open `http://<board-ip>/` in your browser to see the dashboard with the GPIO toggle panel.

## Configuration

`config.json` fields:

```json
{
  "device_name": "ESP32-GPIO",
  "wifi_ssid": "YOUR_SSID",
  "wifi_password": "YOUR_PASSWORD",
  "ap_ssid": "ESP32-GPIO",
  "ap_password": "12345678",
  "web_port": 80,
  "pin_aliases": {
    "led": 8,
    "button": 9
  },
  "gpio_whitelist": [2, 3, 4, 5, 6, 7, 8, 9, 10]
}
```

| Key | Description |
|---|---|
| `device_name` | Displayed in the dashboard title and returned in `/api/status` |
| `wifi_ssid` | Your WiFi network name (2.4 GHz only) |
| `wifi_password` | Your WiFi password |
| `ap_ssid` | Fallback access point name (used if WiFi connection fails) |
| `ap_password` | Fallback access point password (min 8 characters) |
| `web_port` | HTTP server port (default 80) |
| `pin_aliases` | Map of friendly names to GPIO numbers (e.g., `"led": 8`) |
| `gpio_whitelist` | Array of GPIO numbers shown in the dashboard toggle panel |

### Pin Aliases

The `pin_aliases` map lets you use friendly names in API calls instead of raw pin numbers. For example, with `"led": 8` configured, these two calls are equivalent:

```sh
curl -X POST http://192.168.1.42/api/gpio/8/toggle
curl -X POST http://192.168.1.42/api/gpio/led/toggle
```

Aliases work in all `/api/gpio/<pin_arg>` endpoints.

### GPIO Whitelist

The `gpio_whitelist` array controls which pins appear in the dashboard toggle panel. It does **not** restrict the API — you can still configure and control any valid pin via `curl` or code, even if it's not in the whitelist. The whitelist is purely a UI convenience.

## API Reference

All GPIO endpoints return JSON. Error responses include a descriptive `"error"` string.

---

### `GET /`

Returns the HTML dashboard page with:

- **Status card** — device name, IP, WiFi mode, signal quality, uptime, free RAM (refreshes every 5 seconds)
- **GPIO toggle panel** — one row per `gpio_whitelist` pin showing current state (HIGH/LOW) and a toggle button (refreshes every 2 seconds)

---

### `GET /api/status`

Returns device health information.

**Example:**

```sh
curl -s http://192.168.1.42/api/status | jq
```

**Response:**

```json
{
  "device_name": "ESP32-GPIO",
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

### `GET /api/gpio/capabilities`

Returns the chip's pin sets and safety notes. Useful for building dynamic UIs or for debugging which pins are available.

**Example:**

```sh
curl -s http://192.168.1.42/api/gpio/capabilities | jq
```

**Response:**

```json
{
  "digital_pins": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 18, 19],
  "output_pins": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 18, 19],
  "input_pins": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 18, 19, 20],
  "forbidden_pins": [20, 21],
  "pin_aliases": {"led": 8, "button": 9},
  "chip": "ESP32-C3",
  "notes": [
    "GPIO 20 is UART0 RX (input-only), GPIO 21 is UART0 TX — both reserved for REPL",
    "GPIO 0 and 2 are strapping pins — safe after boot but avoid driving during reset",
    "Internal temperature via GET /api/gpio/temperature (Celsius)"
  ]
}
```

---

### `GET /api/gpio/temperature`

Returns the ESP32's internal MCU temperature in Celsius.

**Example:**

```sh
curl -s http://192.168.1.42/api/gpio/temperature | jq
```

**Response:**

```json
{
  "temp_c": 42.0
}
```

---

### `GET /api/gpio/pins`

Lists all currently configured pins and their states.

**Example:**

```sh
curl -s http://192.168.1.42/api/gpio/pins | jq
```

**Response:**

```json
{
  "pins": {
    "8": {"pin": 8, "mode": "OUT", "value": 1},
    "9": {"pin": 9, "mode": "IN", "value": 0}
  },
  "aliases": {"led": 8, "button": 9},
  "count": 2
}
```

---

### `GET /api/gpio/<pin>`

Read the current state of a single pin. The `<pin>` parameter can be a GPIO number or a configured alias.

**Example:**

```sh
# By pin number
curl -s http://192.168.1.42/api/gpio/8 | jq

# By alias
curl -s http://192.168.1.42/api/gpio/led | jq
```

**Response:**

```json
{
  "pin": 8,
  "mode": "OUT",
  "value": 1
}
```

**Error (pin not configured):**

```json
{
  "error": "GPIO 8 has not been configured yet. Use POST /api/gpio/8/mode first."
}
```

---

### `POST /api/gpio/<pin>/mode`

Configure a pin as digital input or output.

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `mode` | string | yes | `"IN"` or `"OUT"` |
| `pull` | string | no | `"up"`, `"down"`, or `null` (only meaningful for IN mode) |

**Examples:**

```sh
# Configure GPIO 8 as output (for driving an LED)
curl -s -X POST http://192.168.1.42/api/gpio/8/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "OUT"}' | jq

# Configure GPIO 9 as input with pull-up (for reading a button)
curl -s -X POST http://192.168.1.42/api/gpio/9/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "IN", "pull": "up"}' | jq

# Using an alias
curl -s -X POST http://192.168.1.42/api/gpio/button/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "IN", "pull": "up"}' | jq
```

**Response:**

```json
{
  "pin": 8,
  "mode": "OUT",
  "value": 0
}
```

---

### `POST /api/gpio/<pin>/value`

Set a pin's output value to HIGH (1) or LOW (0). The pin must already be configured as OUT.

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `value` | int | yes | `0` (LOW) or `1` (HIGH) |

**Examples:**

```sh
# Turn LED on (set HIGH)
curl -s -X POST http://192.168.1.42/api/gpio/led/value \
  -H "Content-Type: application/json" \
  -d '{"value": 1}' | jq

# Turn LED off (set LOW)
curl -s -X POST http://192.168.1.42/api/gpio/8/value \
  -H "Content-Type: application/json" \
  -d '{"value": 0}' | jq
```

**Response:**

```json
{
  "pin": 8,
  "mode": "OUT",
  "value": 1
}
```

**Error (pin is in input mode):**

```json
{
  "error": "GPIO 9 is in IN mode. Only pins in OUT mode can be written to."
}
```

---

### `POST /api/gpio/<pin>/toggle`

Toggle an output pin between HIGH and LOW. The pin must already be configured as OUT.

**Example:**

```sh
curl -s -X POST http://192.168.1.42/api/gpio/led/toggle | jq
```

**Response:**

```json
{
  "pin": 8,
  "mode": "OUT",
  "value": 0
}
```

**Error (pin not configured):**

```json
{
  "error": "GPIO 8 has not been configured yet. Use POST /api/gpio/8/mode first."
}
```

## Quick Recipe: Blink an LED

Set up a pin and toggle it from the command line:

```sh
# 1. Configure pin 8 as output
curl -s -X POST http://192.168.1.42/api/gpio/8/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "OUT"}'

# 2. Turn on
curl -s -X POST http://192.168.1.42/api/gpio/8/value \
  -H "Content-Type: application/json" \
  -d '{"value": 1}'

# 3. Toggle (turns off)
curl -s -X POST http://192.168.1.42/api/gpio/8/toggle

# 4. Toggle again (turns on)
curl -s -X POST http://192.168.1.42/api/gpio/8/toggle
```

Or use the dashboard — click the toggle button next to GPIO 8 and it will auto-configure as OUT and toggle.

## Quick Recipe: Read a Button

```sh
# 1. Configure pin 9 as input with pull-up
curl -s -X POST http://192.168.1.42/api/gpio/9/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "IN", "pull": "up"}'

# 2. Read the button state (1 = not pressed, 0 = pressed with pull-up wiring)
curl -s http://192.168.1.42/api/gpio/9 | jq .value
```

## Pin Safety Notes

### UART0 Pins (GPIO 20 and 21) — Forbidden

GPIO 20 (UART0 RX) and GPIO 21 (UART0 TX) are used by the MicroPython REPL. The API will refuse to configure these pins as outputs to prevent breaking your serial connection:

- **GPIO 20** — Input-only. Can be read but not configured as output.
- **GPIO 21** — Completely blocked. Cannot be read or configured via the API.

### Strapping Pins (GPIO 0 and 2)

GPIO 0 and GPIO 2 are ESP32-C3 strapping pins that affect boot behavior. They are **safe to use after boot** but should not be held HIGH or LOW during a reset, as this can put the chip into download mode or change boot configuration.

**Practical advice:** Don't connect buttons or switches to GPIO 0 or 2 that might be pressed during a power cycle. For LEDs or outputs that are driven after boot, they work fine.

### Input-Only Pins

GPIO 20 is the only input-only pin on the ESP32-C3. All other digital pins (0–10, 18, 19) support both input and output.

### Missing Pins (GPIO 11–17)

GPIO 11–17 are used internally by the ESP32-C3 for SPI flash and are not available for user applications. The API will reject any attempt to use them.

## Memory Footprint

This template uses approximately 140 KB of RAM, leaving ~180 KB free on an ESP32-C3. The GPIO handler adds minimal overhead since it only uses the built-in `machine.Pin` class.

## Next Steps

Once you're comfortable with digital GPIO, consider graduating to a more capable template:

- **`sensors`** — Add ADC voltage reading and I2C device scanning
- **`pwm`** — Add PWM output for LED dimming and servo control
- **`neopixel`** — Add WS2812B RGB LED control with a color picker
- **`full`** — Everything combined with WebSocket streaming

Run `esp templates` to see all available options, or `esp init <template>` to switch.