# CLAUDE.md — ESP-32 MicroPython Quickstart Toolkit

## What This Project Is

A zero-config, Nix-powered development environment for ESP-32 family boards running MicroPython.
One command to enter the dev shell, one command to flash firmware, one command to deploy.

This is **not** a single application — it's a **boilerplate toolkit**. Pick a template that matches
your use case, customize `config.json`, sync to the board, and start building. Standalone example
scripts let you learn each hardware capability in isolation before combining them.

### Core Value Proposition

| What you get | Why it matters |
|---|---|
| **Nix flake** | Reproducible dev environment — one `nix develop`, no manual installs, no version conflicts |
| **`esp` CLI** | Auto-detects port & chip, wraps esptool/mpremote into simple verbs |
| **Pinned firmware** | MicroPython v1.23.0 for ESP32 and ESP32-C3, guaranteed compatible |
| **Templates** | Don't start from scratch — pick a starting point, strip what you don't need |
| **Examples** | Standalone single-file scripts you can `esp run` to learn one concept at a time |
| **Vendored deps** | MicroPython has no pip — Microdot and its WebSocket extension ship in `core/lib/` |

---

## Quick Start

```sh
nix develop                    # 1. Enter the dev shell (all tools provided)
esp detect                     # 2. Verify board is connected
esp erase && esp flash         # 3. Erase flash + write MicroPython firmware
esp init minimal               # 4. Scaffold from the "minimal" template
# edit config.json with your WiFi credentials
esp sync                       # 5. Push files to board + reboot
# open http://<board-ip>/ in a browser
```

That's it. Five steps from zero to a working MicroPython web server on hardware.

---

## Repository Structure

```
project/
├── CLAUDE.md                  # ← This file (project guide & conventions)
├── README.md                  # User-facing quickstart (to be written)
├── ROADMAP.md                 # Development roadmap & task tracking
├── flake.nix                  # Core: Nix dev shell + esp CLI + pinned firmware
├── flake.lock
├── .gitignore
│
├── core/                      # Shared files used by all templates
│   ├── boot.py                # WiFi connect with AP fallback
│   ├── debuglog.py            # Ring-buffer flash logger for crash diagnostics
│   └── lib/
│       ├── microdot.py        # Vendored Microdot async web framework
│       └── websocket.py       # Vendored Microdot WebSocket extension
│
├── templates/                 # Pick a starting point for your project
│   ├── minimal/               # WiFi + health-check endpoint only
│   │   ├── main.py
│   │   └── config.json.example
│   ├── gpio/                  # Digital GPIO control over HTTP
│   │   ├── main.py
│   │   ├── gpio_api.py
│   │   └── config.json.example
│   ├── sensors/               # ADC + I2C scan + internal temperature
│   │   ├── main.py
│   │   └── config.json.example
│   ├── pwm/                   # PWM output (LED dimming, servos)
│   │   ├── main.py
│   │   └── config.json.example
│   ├── neopixel/              # WS2812B RGB LED control
│   │   ├── main.py
│   │   └── config.json.example
│   └── full/                  # Everything: GPIO+ADC+PWM+I2C+WebSocket+dashboard
│       ├── main.py
│       ├── gpio_api.py
│       └── config.json.example
│
├── examples/                  # Standalone scripts (esp run examples/blink.py)
│   ├── blink.py               # Toggle an LED on/off
│   ├── button_read.py         # Read a digital input with pull-up
│   ├── adc_read.py            # Read analog voltage from a pin
│   ├── pwm_fade.py            # Fade an LED using PWM duty cycle
│   ├── i2c_scan.py            # Scan I2C bus and list device addresses
│   ├── wifi_scan.py           # Scan for nearby WiFi networks
│   ├── internal_temp.py       # Read the ESP32's internal temperature sensor
│   └── deep_sleep.py          # Enter deep sleep and wake on timer
│
└── docs/
    ├── pin-reference.md       # ESP32 / C3 / S3 GPIO maps & safe-pin tables
    ├── wiring.md              # Common breadboard layouts with diagrams
    └── troubleshooting.md     # FAQ: flash failures, WiFi issues, memory errors
```

---

## How Templates Work

Each template directory contains a `main.py`, a `config.json.example`, and any template-specific
modules (e.g., `gpio_api.py`). Templates rely on shared files from `core/` (boot.py, debuglog.py,
lib/).

### `esp init <template-name>`

Scaffolds a working project by copying files into the deploy root:

1. Copies `core/boot.py`, `core/debuglog.py`, and `core/lib/*` into the project root
2. Copies the template's `main.py` (and any extra modules) into the project root
3. Copies the template's `config.json.example` → `config.json` (if no `config.json` exists yet)
4. Prints a reminder to edit `config.json` with WiFi credentials

After `esp init`, your root directory has everything needed for `esp sync`.

### `esp templates`

Lists available templates with one-line descriptions.

### Template Descriptions

| Template | What it does | Key files |
|---|---|---|
| `minimal` | WiFi connect + `/api/status` health-check. The smallest possible web server. | `main.py` |
| `gpio` | Digital GPIO read/write over REST API. Toggle LEDs, read buttons. | `main.py`, `gpio_api.py` |
| `sensors` | ADC voltage reading, I2C bus scan, internal temperature sensor. | `main.py` |
| `pwm` | PWM output control — LED brightness sliders, servo positioning. | `main.py` |
| `neopixel` | WS2812B RGB LED control with color picker. | `main.py` |
| `full` | Complete dashboard with GPIO + ADC + PWM + I2C + WebSocket streaming. The current codebase, packaged as a template. | `main.py`, `gpio_api.py` |

---

## The `esp` CLI

The `esp` helper is a shell script bundled in `flake.nix`. It auto-detects the serial port and
chip type, wrapping `esptool`, `mpremote`, and `picocom` into simple single-word commands.

### Core Commands (always available)

| Command | Description |
|---|---|
| `esp detect` | Detect serial port and chip type (ESP32 or ESP32-C3) |
| `esp erase` | Erase the board's entire flash (do this before first firmware flash) |
| `esp flash` | Flash MicroPython firmware (auto-selects correct binary for detected chip) |
| `esp sync` | Push all project files to the board and reset it |
| `esp push <file> [...]` | Push one or more specific files to the board |
| `esp run <script.py>` | Run a script on the board without copying it (great for examples) |
| `esp repl` | Open the MicroPython REPL (Ctrl+X to exit) |
| `esp monitor` | Raw serial monitor via picocom (Ctrl+A then Ctrl+X to exit) |
| `esp ls [path]` | List files on the board's filesystem |
| `esp log` | Print the contents of `debug.log` from the board |
| `esp log clear` | Delete `debug.log` from the board |

### Planned Commands

| Command | Description |
|---|---|
| `esp init <template>` | Scaffold a project from a template (copies core + template files) |
| `esp templates` | List all available templates with descriptions |

### Port Override

The CLI auto-detects USB serial ports. To force a specific port:

```sh
export ESP_PORT=/dev/cu.usbmodem14101
```

### Chip & Firmware Support

| Chip | Firmware | Flash Offset | Status |
|---|---|---|---|
| ESP32 | `ESP32_GENERIC-20240602-v1.23.0.bin` | `0x1000` | ✅ Supported |
| ESP32-C3 | `ESP32_GENERIC_C3-20240602-v1.23.0.bin` | `0x0` | ✅ Supported |
| ESP32-S2 | `ESP32_GENERIC_S2-20240602-v1.23.0.bin` | `0x0` | ✅ Supported |
| ESP32-S3 | `ESP32_GENERIC_S3-20240602-v1.23.0.bin` | `0x0` | ✅ Supported |

### Meshtastic Firmware Support

In addition to MicroPython, the toolkit supports flashing **Meshtastic** firmware — an open-source
LoRa mesh networking platform. This lets you use the same `nix develop` environment and `esp` CLI
to flash either MicroPython (for custom IoT projects) or Meshtastic (for off-grid mesh comms).

#### How It Works

Meshtastic firmware is fundamentally different from MicroPython:

| | MicroPython | Meshtastic |
|---|---|---|
| **What it is** | Python interpreter on hardware | Compiled C++ mesh radio firmware |
| **Firmware granularity** | One `.bin` per chip (ESP32, C3, S3…) | One `.factory.bin` per **board** (heltec-v3, tbeam, t-deck…) |
| **Flash process** | Single binary at one offset | Three binaries: factory + OTA + LittleFS at metadata-driven offsets |
| **Post-flash workflow** | Push `.py` files via `esp sync` | Configure via BLE app or `meshtastic` Python CLI |
| **Configuration** | `config.json` on flash filesystem | Protobuf settings over BLE/serial |

#### Meshtastic CLI Commands

| Command | Description |
|---|---|
| `esp mesh flash <board>` | Flash Meshtastic firmware for a specific board (e.g., `heltec-v3`) |
| `esp mesh boards` | List available board targets from the pinned firmware |
| `esp mesh info` | Show pinned Meshtastic firmware version |
| `esp mesh config` | Open Meshtastic Python CLI for device configuration |

#### Meshtastic Quick Start

```sh
nix develop                        # 1. Enter dev shell
esp detect                         # 2. Verify board connection
esp erase                          # 3. Erase flash
esp mesh boards                    # 4. List available boards
esp mesh flash heltec-v3           # 5. Flash Meshtastic for your board
# configure via Meshtastic app or: meshtastic --set lora.region US
```

#### Supported Meshtastic Boards (ESP32-based)

The firmware ZIPs are pinned per architecture. Popular ESP32-based boards include:

| Board | Chip | Notable Features |
|---|---|---|
| `heltec-v3` | ESP32-S3 | Built-in OLED, SX1262 LoRa |
| `tbeam-s3-core` | ESP32-S3 | GPS, 18650 battery holder |
| `t-deck` | ESP32-S3 | Keyboard + screen |
| `station-g2` | ESP32-S3 | High-power (1W) transceiver |
| `tlora-t3s3-v1` | ESP32-S3 | Budget-friendly with SX1262 |

> **Note:** The full list of boards depends on the pinned firmware version. Run `esp mesh boards`
> to see all available targets for your architecture.

#### Design: Why Both Firmwares?

Many ESP32 developers work with **both** MicroPython (for custom sensor/control projects) and
Meshtastic (for LoRa mesh networking). Having both in one Nix flake means:
- One `nix develop` — no separate toolchain installs
- Same `esptool` version for both — no version conflicts
- Same port detection logic — `esp detect` works for either
- Easy switching — reflash between MicroPython and Meshtastic on the same board

---

## Shared Core Files

### `core/boot.py`

Runs on every power-on. Loads `config.json`, attempts WiFi STA connection with a 10-second
timeout, falls back to AP mode (`ESP32-Dashboard` / `12345678`) if WiFi fails. Prints the
board's IP to serial output so you can find it.

### `core/debuglog.py`

Ring-buffer flash logger. Writes timestamped, memory-annotated lines to `/debug.log` on flash.
Auto-truncates at 16 KB to prevent filling flash. Designed to survive crashes — flushes every
write. Functions: `log()`, `section()`, `log_exception()`, `mem()`, `dump()`, `clear()`.

### `core/lib/microdot.py`

Vendored [Microdot](https://github.com/miguelgrinberg/microdot) v2.x — a single-file async
web framework for MicroPython. Provides routing, request/response handling, JSON support.

### `core/lib/websocket.py`

Vendored Microdot WebSocket extension. Used by templates that need real-time streaming
(e.g., `full`, `gpio`).

---

## Example Scripts

Examples are standalone — they don't need `boot.py`, `config.json`, or Microdot. Run them
directly on the board to learn one concept at a time:

```sh
esp run examples/blink.py          # watch the LED blink
esp run examples/adc_read.py       # see analog readings on serial
esp run examples/i2c_scan.py       # discover connected I2C devices
```

Each example is self-contained: imports only MicroPython built-ins (`machine`, `time`, `network`,
etc.), prints results to serial, and exits cleanly. Read the source to understand the API, then
incorporate the pattern into your template-based project.

---

## Design Decisions

### Why Nix?

MicroPython tooling (`esptool`, `mpremote`, `picocom`) has version-specific quirks. Nix pins
exact versions in `flake.nix` so every developer gets the identical environment. No `pip install`
gone wrong, no Homebrew version drift, no "works on my machine." One `nix develop` and you're
ready.

### Why MicroPython?

Python on hardware. The REPL lets you test GPIO, WiFi, and peripherals interactively without
compile-flash cycles. Ideal for prototyping and learning. The tradeoff (vs. C/Arduino) is speed
and memory — but for IoT dashboards and control interfaces, it's more than enough.

### Why Microdot?

It's a single `.py` file that provides Flask-like routing with async support on MicroPython.
No compilation, no C modules, no package manager — just copy the file to the board. The async
design means the web server doesn't block while waiting for requests.

### Why Templates Over a Monolith?

The old approach bundled everything into one `main.py` + `gpio_api.py` (~2400 lines combined).
Problem: you pay the RAM cost for features you don't use, and the codebase is intimidating for
newcomers. Templates let you start small (`minimal` = ~50 lines) and graduate to complexity
(`full`) when you need it. Each template is self-contained and understandable.

### Why Vendored Dependencies?

MicroPython has no `pip`. There's `mip` for installing packages, but it requires internet access
on the board and introduces version uncertainty. Vendoring `microdot.py` and `websocket.py`
directly into `core/lib/` guarantees they're always available and version-locked.

---

## Config File Convention

Every template ships a `config.json.example`. The user copies it to `config.json` (which is
gitignored) and fills in their WiFi credentials. Minimal config:

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

Templates that use GPIO/ADC/PWM add extra fields (e.g., `features`, `pin_aliases`, `adc_atten`)
to the same `config.json` — see each template's `config.json.example` for the full schema.

---

## Development Workflow

### Entering the dev shell

```sh
nix develop
```

Provides: `esptool`, `mpremote`, `picocom`, `python3`, `pyserial`, `curl`, `jq`, `websocat`,
and the `esp` CLI helper.

### First-time board setup

```sh
esp detect                     # verify port & chip detection
esp erase                      # erase flash (required before first firmware flash)
esp flash                      # flash MicroPython v1.23.0 (auto-selects for chip)
```

### Starting a new project

```sh
esp init minimal               # scaffold from template
vim config.json                # set wifi_ssid and wifi_password
esp sync                       # push to board + reset
```

### Daily iteration

```sh
# edit main.py or other files locally
esp sync                       # push all files + reset
esp repl                       # interactive REPL for testing (Ctrl+X to exit)
esp monitor                    # raw serial output (Ctrl+A, Ctrl+X to exit)
esp run examples/blink.py      # quickly test a standalone script
esp log                        # check debug.log on the board
esp ls                         # list files on the board
```

---

## Migration Note

The existing codebase (`boot.py`, `main.py`, `gpio_api.py`, `debuglog.py`) is being reorganized
into the template structure described above:

- `boot.py` and `debuglog.py` → `core/` (shared by all templates)
- `lib/microdot.py` and `lib/websocket.py` → `core/lib/`
- Current `main.py` + `gpio_api.py` (full dashboard with GPIO/ADC/PWM/I2C/WebSocket) → `templates/full/`
- A stripped-down `main.py` with only `/` and `/api/status` → `templates/minimal/`
- Feature-specific slices of `gpio_api.py` → `templates/gpio/`, `templates/sensors/`, etc.

The API-specific CLI commands (`esp gpio`, `esp adc`, `esp i2c`, `esp stream`) will be removed
from the core `esp` CLI. They were tightly coupled to the `full` template's HTTP API and required
`ESP_IP` to be set. Users of the `full` template can use `curl`/`websocat` directly, or these
commands can be re-added as template-specific tooling in the future.

Until the reorganization is complete, the existing flat file layout still works — `esp sync`
pushes the current root-level files to the board as before.

---

## RAM Budget (ESP32-C3)

The ESP32-C3 has ~320 KB SRAM. MicroPython uses ~100 KB. Budget per template:

| Template | Estimated Usage | Headroom |
|---|---|---|
| `minimal` | ~120 KB (runtime + Microdot + HTML) | ~200 KB |
| `gpio` | ~140 KB (+ gpio_api routes) | ~180 KB |
| `sensors` | ~130 KB (+ ADC/I2C wrappers) | ~190 KB |
| `full` | ~170 KB (everything loaded) | ~150 KB |

The `full` template is the tightest fit. If you hit `MemoryError`, start with a smaller
template and add only what you need.

---

## Conventions

- **All board files go through `esp sync`** — never manually `mpremote cp` individual files
  unless debugging. The sync command ensures a consistent set of files on the board.
- **`config.json` is gitignored** — credentials never enter version control. Only
  `config.json.example` is tracked.
- **Debug with `debuglog`** — use `log()` instead of bare `print()` for anything you want
  to survive a crash. Read logs with `esp log` or `GET /api/debug/log`.
- **GC early and often** — call `gc.collect()` before heavy operations. Microdot's
  `@app.before_request` hook is a good place.
- **One feature per template** — templates should be minimal and focused. If a user needs
  GPIO + NeoPixel, they start with one template and copy routes from the other, or use `full`.