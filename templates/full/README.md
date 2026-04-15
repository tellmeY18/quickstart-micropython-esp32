# Full Template

The **full** template is the complete ESP32 MicroPython dashboard — every peripheral, every
protocol, every API route. It packages the entire working codebase (GPIO, ADC, PWM, I2C,
batch operations, WebSocket streaming, debug logging) into a single deployable template.

> **This is the "kitchen sink."** If you only need one or two features, start with a smaller
> template (`minimal`, `gpio`, `sensors`, `pwm`) and add what you need. The full template
> loads everything and pays the RAM cost for all of it.

## Quick Start

```sh
esp init full
# Edit config.json — set wifi_ssid, wifi_password, and enable features
esp sync
# Open http://<board-ip>/ in a browser
```

## Files

| File | Purpose |
|---|---|
| `main.py` | Microdot web server — dashboard UI, `/api/status`, debug log routes, gpio_api integration |
| `gpio_api.py` | All hardware API routes — GPIO, ADC, PWM, I2C, batch, WebSocket (~1200 lines) |
| `debuglog.py` | Ring-buffer flash logger for crash diagnostics |
| `config.json.example` | Full configuration with all feature flags, pin aliases, ADC attenuation |

Additionally, `esp init` copies shared files from `core/`:

- `boot.py` — WiFi STA connection with AP fallback
- `lib/microdot.py` — Vendored Microdot async web framework
- `lib/websocket.py` — Vendored Microdot WebSocket extension

---

## Memory Warning

**Enabling all features on an ESP32-C3 may leave less than 80 KB of free heap.**

The ESP32-C3 has ~320 KB SRAM. MicroPython's runtime consumes ~100 KB. The full template
with all features enabled uses ~170 KB, leaving roughly 150 KB free. However, each active
WebSocket connection, each registered route closure, and each HTTP request/response cycle
allocates additional memory.

If you hit `MemoryError`:

1. Disable features you don't need in `config.json` (each disabled feature saves 5–20 KB)
2. Check `esp log` for the memory annotations — every log line includes free heap bytes
3. Consider starting with a smaller template instead
4. The `@app.before_request` handler runs `gc.collect()` before every request to reclaim memory

---

## Feature Flags

Features are controlled by the `features` object in `config.json`. Disabled features skip
route registration and heavy imports entirely, saving memory.

```json
{
  "features": {
    "gpio": false,
    "adc": false,
    "pwm": false,
    "i2c": false,
    "batch": false,
    "websocket": false
  }
}
```

| Flag | What it enables | Imports added | Approx. RAM cost |
|---|---|---|---|
| `gpio` | Digital pin read/write/toggle, pin mode configuration | `machine.Pin` | ~5 KB |
| `adc` | Analog-to-digital converter reading, attenuation config | `machine.ADC` | ~8 KB |
| `pwm` | PWM output control (frequency, duty cycle, start/stop) | `machine.PWM` | ~8 KB |
| `i2c` | I2C bus scan, raw read/write/write-read, bus reconfiguration | `machine.SoftI2C` | ~10 KB |
| `batch` | Multi-pin read and write in a single request | (none extra) | ~3 KB |
| `websocket` | Real-time pin state streaming over WebSocket | `uasyncio`, `lib.websocket` | ~15 KB |

All flags default to `false`. Enable only what you need.

---

## Configuration Reference

```json
{
  "device_name": "ESP32-Dashboard",
  "wifi_ssid": "YOUR_SSID",
  "wifi_password": "YOUR_PASSWORD",
  "ap_ssid": "ESP32-Dashboard",
  "ap_password": "12345678",
  "web_port": 80,
  "features": {
    "gpio": false,
    "adc": false,
    "pwm": false,
    "i2c": false,
    "batch": false,
    "websocket": false
  },
  "pin_aliases": {
    "led": 8,
    "relay": 5,
    "sensor_in": 3
  },
  "adc_atten": "11db"
}
```

| Key | Type | Default | Description |
|---|---|---|---|
| `device_name` | string | `"ESP32-Dashboard"` | Displayed in the HTML dashboard title |
| `wifi_ssid` | string | — | WiFi network name (required for STA mode) |
| `wifi_password` | string | — | WiFi password |
| `ap_ssid` | string | `"ESP32-Dashboard"` | Access point name if STA fails |
| `ap_password` | string | `"12345678"` | Access point password (min 8 chars) |
| `web_port` | int | `80` | HTTP server port |
| `features` | object | all `false` | Feature flag toggles (see above) |
| `pin_aliases` | object | `{}` | Map of friendly names to GPIO numbers |
| `adc_atten` | string | `"11db"` | Default ADC attenuation: `"0db"`, `"2.5db"`, `"6db"`, `"11db"` |
| `i2c_sda` | int | `8` | I2C SDA pin (used when `i2c` feature is enabled) |
| `i2c_scl` | int | `9` | I2C SCL pin |
| `i2c_freq` | int | `100000` | I2C bus frequency in Hz |

### Pin Aliases

Pin aliases let you use friendly names instead of GPIO numbers in all API calls. For example,
with `"led": 8` defined, you can use `/api/gpio/led` instead of `/api/gpio/8`.

---

## API Reference

All routes return JSON unless otherwise noted. Error responses include an `"error"` key with
a human-readable message and an appropriate HTTP status code.

### Core Routes (always available)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | HTML dashboard with auto-refreshing status display |
| GET | `/api/status` | Device status: IP, WiFi mode, RSSI, uptime, free memory |
| GET | `/api/debug/log` | Raw contents of `debug.log` (plain text) |
| POST | `/api/debug/clear` | Delete `debug.log` from flash |

### System Routes (always available, registered by gpio_api)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/gpio/capabilities` | Pin maps, feature flags, chip info, hardware notes |
| GET | `/api/gpio/temperature` | ESP32 internal die temperature in Celsius |

### GPIO Routes (requires `"gpio": true`)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/gpio/pins` | List all configured pins with current state |
| GET | `/api/gpio/<pin>` | Read current state of a configured pin |
| POST | `/api/gpio/<pin>/mode` | Set pin mode — body: `{"mode": "IN"\|"OUT", "pull": "up"\|"down"\|null}` |
| POST | `/api/gpio/<pin>/value` | Set output value — body: `{"value": 0\|1}` |
| POST | `/api/gpio/<pin>/toggle` | Toggle an OUT pin between 0 and 1 |

`<pin>` accepts a GPIO number (e.g., `8`) or a pin alias (e.g., `led`).

### ADC Routes (requires `"adc": true`)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/adc/all` | Read all ADC-capable pins (GPIO 0–4) |
| GET | `/api/adc/<pin>` | Read a single ADC pin — returns raw, microvolts, voltage |
| POST | `/api/adc/<pin>/config` | Set attenuation — body: `{"atten": "0db"\|"2.5db"\|"6db"\|"11db"}` |

### PWM Routes (requires `"pwm": true`)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/pwm/<pin>/start` | Start PWM — body: `{"freq": 1000, "duty_u16": 32768}` |
| POST | `/api/pwm/<pin>/duty` | Set duty cycle — body: `{"duty_u16": 0-65535}` |
| POST | `/api/pwm/<pin>/freq` | Set frequency — body: `{"freq": 1-40000000}` |
| POST | `/api/pwm/<pin>/stop` | Stop PWM and release the pin |
| GET | `/api/pwm/<pin>` | Read current PWM state (freq, duty) |

### I2C Routes (requires `"i2c": true`)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/i2c/scan` | Scan the I2C bus — returns list of device addresses |
| POST | `/api/i2c/read` | Read bytes — body: `{"addr": 0x50, "nbytes": 2}` |
| POST | `/api/i2c/write` | Write bytes — body: `{"addr": 0x50, "data": [0x00, 0x01]}` |
| POST | `/api/i2c/write_read` | Write then read — body: `{"addr": 0x50, "write": [0x00], "read": 2}` |
| POST | `/api/i2c/config` | Reconfigure I2C bus — body: `{"sda": 6, "scl": 7, "freq": 400000}` |

### Batch Routes (requires `"batch": true`)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/gpio/batch/read` | Read multiple pins — body: `{"pins": [5, 8, "led"]}` |
| POST | `/api/gpio/batch/write` | Write multiple pins — body: `{"pins": {"5": 1, "8": 0}}` |

### WebSocket Endpoint (requires `"websocket": true`)

| Protocol | Endpoint | Description |
|---|---|---|
| WS | `/ws/stream` | Real-time bidirectional pin state streaming |

---

## WebSocket Streaming

The `/ws/stream` endpoint provides real-time hardware state streaming over WebSocket.

### Connecting

```
ws://<board-ip>/ws/stream
```

From the command line (using `websocat`, available in the Nix dev shell):

```sh
websocat ws://<board-ip>/ws/stream
```

### Server Broadcasts

The server automatically broadcasts a state frame at a configurable interval (default: 100ms).
Each frame contains:

```json
{
  "ts": 12345,
  "gpio": {
    "5": {"mode": "OUT", "value": 1},
    "8": {"mode": "PWM", "freq": 1000, "duty_u16": 32768}
  },
  "adc": {
    "4": {"raw": 28500, "voltage_v": 1.432}
  },
  "temp_c": 42.5,
  "mem_free_kb": 98
}
```

### Client Commands

Send JSON messages to the server to control hardware or configure the stream:

#### `ping`

```json
{"cmd": "ping"}
```

Response: `{"cmd": "pong", "ts": 12345}`

#### `set` — Set a digital output pin

```json
{"cmd": "set", "pin": 5, "value": 1}
```

Response: `{"cmd": "set", "pin": 5, "value": 1, "status": "ok"}`

Pin must already be configured in OUT mode via the REST API.

#### `pwm_duty` — Set PWM duty cycle

```json
{"cmd": "pwm_duty", "pin": 8, "duty_u16": 49152}
```

Response: `{"cmd": "pwm_duty", "pin": 8, "duty_u16": 49152, "status": "ok"}`

Pin must already be in PWM mode.

#### `stream_config` — Configure broadcast settings

```json
{"cmd": "stream_config", "pins": [5, 8], "interval_ms": 200}
```

Response: `{"cmd": "stream_config", "pins": [5, 8], "interval_ms": 200, "status": "ok"}`

- `pins` — List of pin numbers to include in broadcasts. Empty list = all registered pins.
- `interval_ms` — Broadcast interval in milliseconds. Minimum 50ms (values below 50 are clamped).

---

## Debug Logging

The `debuglog` module writes timestamped, memory-annotated log lines to `/debug.log` on flash.
Every line includes milliseconds since boot and free heap bytes, making it easy to trace
memory leaks and crash sequences.

### Accessing Logs

| Method | How |
|---|---|
| CLI | `esp log` — prints debug.log from the board |
| CLI | `esp log clear` — deletes debug.log |
| HTTP | `GET /api/debug/log` — returns log as plain text |
| HTTP | `POST /api/debug/clear` — deletes the log file |
| REPL | `from debuglog import dump; dump()` |

### Log Format

```
     12345 |  102400 | main.py: debuglog imported OK
     12350 |  102400 | ---------- MAIN.PY START ----------
```

Each line: `<ms_since_boot> | <free_heap_bytes> | <message>`

### Log Size

The log file auto-truncates at 16 KB. When the limit is exceeded, the oldest half is discarded
and a truncation marker is inserted. This prevents flash from filling up during long runs.

---

## ESP32-C3 Pin Reference

| Pin | Capabilities | Notes |
|---|---|---|
| GPIO 0 | Digital, ADC | Strapping pin — safe after boot |
| GPIO 1 | Digital, ADC | General purpose |
| GPIO 2 | Digital, ADC | Strapping pin — safe after boot |
| GPIO 3 | Digital, ADC | General purpose |
| GPIO 4 | Digital, ADC | General purpose |
| GPIO 5 | Digital, PWM | General purpose |
| GPIO 6 | Digital, PWM | Default I2C SDA (configurable) |
| GPIO 7 | Digital, PWM | Default I2C SCL (configurable) |
| GPIO 8 | Digital, PWM | On-board LED on most dev boards |
| GPIO 9 | Digital | BOOT button on most dev boards |
| GPIO 10 | Digital, PWM | General purpose |
| GPIO 18 | Digital | USB D- (avoid if using USB) |
| GPIO 19 | Digital | USB D+ (avoid if using USB) |
| GPIO 20 | Input only | UART0 RX — **forbidden** (REPL) |
| GPIO 21 | — | UART0 TX — **forbidden** (REPL) |

- **ADC pins**: GPIO 0–4 only (ADC1; no ADC2 on C3, no WiFi conflict)
- **Forbidden pins**: GPIO 20 and 21 are reserved for the REPL serial console
- **No DAC**: The ESP32-C3 has no DAC hardware — use PWM for analog-like output
- **No touch**: The ESP32-C3 has no capacitive touch hardware

---

## Known Limitations

1. **RAM pressure** — With all six features enabled and a WebSocket client connected, free
   memory can drop below 80 KB. Each HTTP request temporarily allocates additional buffers.
   The `@app.before_request` GC hook helps, but complex API calls under load can still trigger
   `MemoryError`.

2. **Single WebSocket client** — While the code supports multiple WebSocket clients in
   `_ws_clients`, practical RAM limits on the ESP32-C3 mean only 1–2 concurrent WebSocket
   connections are reliable.

3. **No HTTPS** — Microdot on MicroPython does not support TLS. All traffic is unencrypted.
   Do not expose the board directly to the internet.

4. **Blocking ADC reads** — `adc.read_uv()` blocks briefly. During WebSocket streaming with
   ADC pins, broadcast timing may jitter.

5. **I2C is SoftI2C** — Uses bit-banged software I2C, not hardware I2C. Reliable up to
   400 kHz but not suitable for high-speed peripherals.

6. **Pin mode conflicts** — A pin can only be in one mode at a time (IN, OUT, PWM, ADC).
   Attempting to use a pin in a different mode returns HTTP 409 Conflict. Release the current
   mode first (e.g., `POST /api/pwm/<pin>/stop`).

7. **No persistent pin state** — Pin configurations are lost on reboot. After `esp sync` or
   power cycle, all pins return to unconfigured state.

8. **Config loaded twice** — Both `main.py` and `gpio_api.py` independently read
   `config.json`. This is intentional to keep modules decoupled, but it means config changes
   require a full reboot (`esp sync` handles this automatically).