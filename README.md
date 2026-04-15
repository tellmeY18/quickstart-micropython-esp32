# ESP32 MicroPython Quickstart Toolkit

> Plug in a board, pick a template, ship in 2 minutes.

## What Is This?

A **zero-config, Nix-powered development environment** for ESP32 family boards running MicroPython. One command enters the dev shell with every tool you need — `esptool`, `mpremote`, `picocom`, and a custom `esp` CLI that auto-detects your board, flashes firmware, and deploys code. No manual installs, no version conflicts, no "works on my machine."

Instead of starting from scratch, you **pick a template** that matches your use case — a minimal health-check server, a GPIO toggle panel, a sensor dashboard, PWM controls, NeoPixel LEDs, or a full-featured kitchen-sink dashboard. Each template ships with a web UI, a REST API, and a `config.json` you fill in with your WiFi credentials. Standalone example scripts let you learn each hardware capability in isolation before combining them.

## Quickstart

```sh
# 1. Clone the repo
git clone https://github.com/YOUR_USER/esp32-micropython-toolkit.git
cd esp32-micropython-toolkit

# 2. Enter the Nix dev shell (installs all tools automatically)
nix develop

# 3. Plug in your ESP32 board via USB and verify detection
esp detect

# 4. Erase flash and write MicroPython firmware (first time only)
esp erase && esp flash

# 5. Scaffold a project from a template
esp init minimal

# 6. Edit config.json with your WiFi credentials
#    Set wifi_ssid and wifi_password at minimum
nano config.json

# 7. Push all files to the board and reboot
esp sync

# 8. Open http://<board-ip>/ in your browser — you're live!
```

The board's IP address is printed to serial output during boot. Use `esp monitor` or `esp repl` to see it.

## Available Templates

Pick a starting point. Start small, add complexity only when you need it.

| Template | Description | Use Case | Key API Endpoints |
|---|---|---|---|
| **`minimal`** | WiFi connect + status dashboard | Verify board works, starting point for custom projects | `GET /` (dashboard), `GET /api/status` |
| **`gpio`** | Digital GPIO read/write with toggle panel | Toggle LEDs, read buttons, control relays | `GET /api/gpio/pins`, `POST /api/gpio/<pin>/mode`, `POST /api/gpio/<pin>/toggle`, `POST /api/gpio/<pin>/value` |
| **`sensors`** | ADC voltage, I2C bus scan, internal temperature | Read potentiometers, discover I2C sensors, monitor temperature | `GET /api/temperature`, `GET /api/adc/all`, `GET /api/i2c/scan`, `POST /api/i2c/read` |
| **`pwm`** | PWM output with duty cycle slider | LED dimming, servo control, tone generation | `POST /api/pwm/<pin>/start`, `POST /api/pwm/<pin>/duty`, `POST /api/pwm/<pin>/stop`, `GET /api/pwm/<pin>` |
| **`neopixel`** | WS2812B RGB LED control with color picker | Addressable LED strips, status indicators, decorative lighting | `GET /api/neopixel`, `POST /api/neopixel`, `POST /api/neopixel/<index>`, `POST /api/neopixel/clear` |
| **`full`** | Everything: GPIO + ADC + PWM + I2C + WebSocket + debug logging | Complete dashboard, production-style monitoring, multi-feature projects | All of the above + `GET /api/debug/log`, WebSocket streaming at `/api/stream` |

### Switching Templates

```sh
esp init gpio          # overwrite main.py with the gpio template
nano config.json       # add gpio_whitelist, pin_aliases, etc.
esp sync               # push to board
```

Each template's `config.json.example` documents every available setting.

## Example Scripts

Standalone scripts that run directly on the board — no WiFi, no web server, no config needed. Great for learning one concept at a time.

```sh
esp run examples/blink.py          # watch an LED blink on and off
esp run examples/adc_read.py       # see analog readings on serial
```

| Script | What It Demonstrates | Wiring Needed |
|---|---|---|
| `blink.py` | Toggle a digital output on/off with a delay loop | LED + 330Ω resistor on any GPIO |
| `button_read.py` | Read a digital input using internal pull-up resistor | Momentary button between GPIO and GND |
| `adc_read.py` | Read analog voltage (0–3.3V) from an ADC-capable pin | Potentiometer wiper to ADC pin |
| `pwm_fade.py` | Smoothly fade an LED using PWM duty cycle | LED + 330Ω resistor on any PWM-capable GPIO |
| `i2c_scan.py` | Scan the I2C bus and list all device addresses found | Any I2C device on SDA/SCL pins |
| `wifi_scan.py` | Scan for nearby WiFi networks and print SSID/RSSI | None (uses built-in WiFi radio) |
| `internal_temp.py` | Read the ESP32's internal temperature sensor | None (on-chip sensor) |
| `deep_sleep.py` | Enter deep sleep mode and wake on a timer | None (observe via serial reconnection) |

## ESP CLI Reference

The `esp` CLI auto-detects your serial port and chip type. All commands are single-word verbs.

| Command | Description |
|---|---|
| `esp detect` | Detect serial port and chip type (ESP32 or ESP32-C3) |
| `esp erase` | Erase the board's entire flash memory |
| `esp flash` | Flash MicroPython v1.23.0 firmware (auto-selects for detected chip) |
| `esp sync` | Push all project files to the board and reset it |
| `esp push <file> [...]` | Push one or more specific files to the board |
| `esp run <script.py>` | Run a script on the board without copying it permanently |
| `esp repl` | Open the MicroPython REPL (Ctrl+X to exit) |
| `esp monitor` | Raw serial monitor via picocom (Ctrl+A then Ctrl+X to exit) |
| `esp ls [path]` | List files on the board's filesystem |
| `esp log` | Print the contents of `debug.log` from the board |
| `esp log clear` | Delete `debug.log` from the board |
| `esp init <template>` | Scaffold a project from a template (copies core + template files) |
| `esp templates` | List all available templates with descriptions |

### Port Override

The CLI auto-detects USB serial ports. To force a specific port:

```sh
export ESP_PORT=/dev/cu.usbmodem14101
```

## Supported Boards

| Chip | Firmware | Status |
|---|---|---|
| **ESP32** (original) | `ESP32_GENERIC-20240602-v1.23.0.bin` | ✅ Tested |
| **ESP32-C3** | `ESP32_GENERIC_C3-20240602-v1.23.0.bin` | ✅ Tested |
| **ESP32-S2** | — | 🔜 Planned |
| **ESP32-S3** | — | 🔜 Planned |

All firmware is MicroPython **v1.23.0**, pinned in `flake.nix` for reproducibility.

## Project Structure

```
project/
├── README.md                  ← You are here
├── CLAUDE.md                  # Project guide & conventions for AI/dev reference
├── ROADMAP.md                 # Development roadmap & task tracking
├── flake.nix                  # Nix dev shell + esp CLI + pinned firmware
├── flake.lock
├── .gitignore
│
├── core/                      # Shared files used by all templates
│   ├── boot.py                #   WiFi connect with AP fallback
│   ├── debuglog.py            #   Ring-buffer flash logger
│   └── lib/
│       ├── microdot.py        #   Vendored Microdot async web framework
│       └── websocket.py       #   Vendored Microdot WebSocket extension
│
├── templates/                 # Pick one as your starting point
│   ├── minimal/               #   WiFi + health-check only (~50 lines)
│   ├── gpio/                  #   Digital GPIO read/write over REST
│   ├── sensors/               #   ADC + I2C scan + temperature
│   ├── pwm/                   #   PWM output (LED dimming, servos)
│   ├── neopixel/              #   WS2812B RGB LED control
│   └── full/                  #   Everything combined + WebSocket + debug log
│
├── examples/                  # Standalone learning scripts
│   ├── blink.py
│   ├── button_read.py
│   ├── adc_read.py
│   ├── pwm_fade.py
│   ├── i2c_scan.py
│   ├── wifi_scan.py
│   ├── internal_temp.py
│   └── deep_sleep.py
│
└── docs/                      # Reference documentation
    ├── pin-reference.md       #   GPIO maps for ESP32 & ESP32-C3
    ├── wiring.md              #   Breadboard layouts with ASCII diagrams
    └── troubleshooting.md     #   FAQ: flash failures, WiFi, memory errors
```

## How Templates Work

Each template directory contains a `main.py`, a `config.json.example`, and any template-specific handler modules. Templates depend on shared files from `core/` (`boot.py`, `debuglog.py`, `lib/`).

Running `esp init <template-name>` scaffolds a working project:

1. Copies `core/boot.py`, `core/debuglog.py`, and `core/lib/*` into the deploy root
2. Copies the template's `main.py` and handler modules into the deploy root
3. Creates `config.json` from the template's `config.json.example` (if none exists yet)
4. Prints a reminder to edit `config.json` with your WiFi credentials

After `esp init`, your working directory has everything needed for `esp sync`.

## Config File

Every template uses a `config.json` for runtime settings. Minimal required fields:

```json
{
  "device_name": "ESP32-Dev",
  "wifi_ssid": "YOUR_SSID",
  "wifi_password": "YOUR_PASSWORD",
  "ap_ssid": "ESP32-Dev",
  "ap_password": "12345678",
  "web_port": 80
}
```

Templates add extra fields for their features (e.g., `gpio_whitelist`, `pin_aliases`, `neopixel_pin`, `adc_atten`). See each template's `config.json.example` for the full schema.

> **Note:** `config.json` is gitignored — your credentials never enter version control.

## Further Reading

- **[Pin Reference](docs/pin-reference.md)** — GPIO maps and safe-pin tables for ESP32 and ESP32-C3
- **[Wiring Guide](docs/wiring.md)** — Breadboard layouts with ASCII diagrams for LEDs, buttons, sensors, and more
- **[Troubleshooting](docs/troubleshooting.md)** — Solutions for common issues (serial detection, WiFi, memory, I2C, etc.)
- **[CLAUDE.md](CLAUDE.md)** — Full project conventions, design decisions, and architecture reference

## Contributing

This project is structured as a boilerplate toolkit. See [CLAUDE.md](CLAUDE.md) for design decisions, conventions, and the full architecture guide. The [ROADMAP.md](ROADMAP.md) tracks planned features and tasks.

## License

MIT