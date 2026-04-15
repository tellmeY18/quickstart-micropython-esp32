# CLAUDE.md — The Complete Guide to This Repository

This file is the single source of truth for understanding everything in this project. If you read nothing else, read this.

---

## What This Project Is

This is a complete, self-contained Internet of Things project that turns an ESP-32 microcontroller into a live health-check dashboard accessible over WiFi. The board boots up, connects to your local network (or creates its own), starts a tiny async web server, and serves a real-time status page showing whether the board is alive — its IP address, uptime, WiFi mode, and free memory.

The entire development environment is powered by a single Nix flake. There are no manual tool installs, no Python virtualenvs, no version conflicts, and no cloud dependencies. One command (`nix develop`) drops you into a shell with everything you need — toolchain, firmware, file transfer utilities, serial monitor, and a custom `esp` CLI that auto-detects your board and wraps every operation into simple subcommands.

Only four files are deployed to the board. The rest exist solely on your development machine.

---

## Why This Exists

The goal is dead simple: prove the board boots and talks HTTP. That's it. No Bluetooth, no GPIO pins, no sensor readings, no cloud integrations, no home automation. If you open a browser, navigate to the board's IP, and see the dashboard updating every five seconds — the board is alive and healthy.

This constraint is deliberate. It keeps the codebase tiny (around 200 lines of application code total), makes the project easy to reason about, and demonstrates MicroPython + Nix flakes without any distracting complexity.

---

## Repository Structure — Every File Explained

### Files That Live on the ESP-32 Board

These are the only files that get pushed to the microcontroller's flash storage via `esp sync`:

**`boot.py`** — This is the very first script MicroPython executes on power-on or reset. Its sole job is network connectivity. It reads WiFi credentials from `config.json`, activates the board's station interface (STA mode), and attempts to connect to your local WiFi network. It waits up to 10 seconds for a successful connection. If that succeeds, it prints the assigned IP address to the serial console and exits. If it fails (wrong credentials, router unreachable, no config), it gracefully falls back to Access Point mode — the board creates its own WiFi network named `ESP32-Dashboard` (configurable) with a password, so you can connect to it directly from your phone or laptop and still reach the dashboard. This fallback means the board is always reachable regardless of whether your WiFi is available.

**`main.py`** — This is the web server. MicroPython runs it automatically after `boot.py` completes. It uses Microdot (an async micro web framework) to serve two HTTP routes. The root route (`GET /`) returns a complete HTML page as an inline Python string — the dashboard UI with embedded CSS and JavaScript. The API route (`GET /api/status`) returns a JSON object containing the device name, current IP address, WiFi mode (STA or AP), uptime in seconds (calculated from `time.ticks_ms()` since boot), and free heap memory in kilobytes (after running garbage collection). The inline JavaScript in the HTML page polls this API endpoint every five seconds and updates the DOM in place, giving you a live-updating view of board health. The server listens on port 80 by default (configurable via `config.json`). There are no external JS files, no CSS files, no static assets — everything is baked into that single HTML string to avoid extra file reads on the constrained microcontroller filesystem.

**`config.json`** — The runtime configuration file. Contains your WiFi SSID and password, a human-readable device name (shown in the browser title and dashboard heading), AP mode SSID and password for the fallback network, and the web server port number. Both `boot.py` and `main.py` read this file on startup. This file is gitignored because it contains your real WiFi credentials — you should never commit it. Copy `config.json.example` and fill in your own values.

**`lib/microdot.py`** — The Microdot async web framework by Miguel Grinberg. It is a single-file, ~1500-line HTTP server framework designed specifically for MicroPython (though it also runs on standard CPython). It provides async request handling via `uasyncio`, route decorators, request parsing, JSON response serialization, cookie support, static file serving, error handlers, and more. It lives in a `lib/` subdirectory because that is MicroPython's conventional library search path. This file is vendored directly into the project (not installed via a package manager) because MicroPython has no `pip`. It comes from `github.com/miguelgrinberg/microdot`.

### Files That Live on the Dev Machine Only

**`flake.nix`** — The Nix flake definition. This is the backbone of the development environment. Explained in full detail in the Nix Flake section below.

**`flake.lock`** — The Nix lockfile. Pins exact revisions of `nixpkgs` (the package repository) and `flake-utils` (a helper library) so that every developer, on every machine, gets bit-for-bit identical tool versions. You never edit this by hand — Nix manages it. It currently tracks `nixpkgs` on the `nixos-unstable` channel and `flake-utils` from `numtide/flake-utils` on GitHub.

**`config.json.example`** — A safe-to-commit template showing the expected config structure with placeholder values. New users copy this to `config.json` and fill in their real WiFi credentials.

**`slides.md`** — A presentation deck written in Markdown for the `presenterm` terminal presentation tool. It walks through the project architecture, tech stack, design constraints, code highlights, and a live demo flow. Intended for presenting this project in an academic or meetup setting. It covers everything from the boot sequence to the Nix dev shell to the `esp` CLI.

**`CLAUDE.md`** — This file. The comprehensive project guide and conventions document.

**`.gitignore`** — Keeps `config.json` (which contains real WiFi passwords) and `.direnv` (Nix direnv cache) out of version control.

---

## How the Application Works End to End

The runtime flow on the ESP-32 board follows this sequence:

1. The board powers on (or resets). MicroPython's bootloader runs and then executes `boot.py` automatically.

2. `boot.py` opens `config.json`, extracts the WiFi SSID and password, and activates the station (client) network interface. It calls `sta.connect()` and polls `sta.isconnected()` in a loop for up to 10 seconds, sleeping 500ms between checks.

3. If the connection succeeds, the board has an IP address on your local network (assigned by your router's DHCP). It prints this IP to the serial console and moves on.

4. If the connection fails (timeout, wrong password, no router), `boot.py` deactivates the station interface and activates the Access Point interface instead. It configures the AP with a name and password from `config.json` (defaulting to `ESP32-Dashboard` / `12345678`) and WPA/WPA2 security. Now the board itself is a WiFi hotspot. You connect to it directly and the board is reachable at its AP IP (typically `192.168.4.1`).

5. Either way, `boot.py` finishes and MicroPython automatically runs `main.py`.

6. `main.py` loads `config.json` again (for the device name and port), records the current tick count as a boot timestamp for uptime calculations, and initializes a Microdot application with two route handlers.

7. The Microdot server starts listening on the configured port (default 80) using `uasyncio`, MicroPython's cooperative async framework. This means it can handle multiple requests without blocking.

8. When a browser hits `GET /`, the server responds with the full HTML dashboard — a self-contained page with inline CSS (dark theme, monospace font, green-on-black terminal aesthetic) and inline JavaScript. The JS immediately calls `fetch('/api/status')` and then sets up a `setInterval` to repeat that call every 5 seconds.

9. When the JS calls `GET /api/status`, the server runs garbage collection (`gc.collect()`), measures free heap memory, calculates uptime by diffing the current ticks against the boot timestamp, checks which network interface is active (STA or AP), and returns all of this as a JSON object.

10. The JavaScript receives the JSON response and updates the DOM — showing IP address, WiFi mode, uptime counter, and free memory. If the fetch fails (board powered off, WiFi dropped), it shows an error message in red.

The dashboard has no external dependencies, no CDN links, no build step. It is entirely self-hosted on the microcontroller.

---

## The Nix Flake — How It Works and What It Provides

### Why Nix

Nix is a purely functional package manager. A Nix flake is a standardized way to define reproducible project environments. The advantage here is that anyone cloning this repo can run `nix develop` and get the exact same tools at the exact same versions, regardless of their operating system (macOS or Linux), what they have installed globally, or what other Python versions exist on their machine. There is no "works on my machine" problem.

### Flake Inputs

The flake declares two inputs:

- **nixpkgs** — The main Nix package collection, pinned to the `nixos-unstable` branch. This is where all the tools (`esptool`, `mpremote`, `picocom`, `python3`, `pyserial`) come from. The exact commit is locked in `flake.lock`.

- **flake-utils** — A helper library from `numtide` that provides `eachDefaultSystem`, a function that generates outputs for all standard platforms (x86_64-linux, aarch64-linux, x86_64-darwin, aarch64-darwin) from a single definition. This means the flake works on Intel Macs, Apple Silicon Macs, and Linux machines without any platform-specific code.

### Pinned Firmware

The flake uses `pkgs.fetchurl` to download two MicroPython firmware binaries directly from `micropython.org` and pin them by SHA-256 hash:

- **ESP32 generic** — `ESP32_GENERIC-20240602-v1.23.0.bin` (for standard ESP32 chips, flashed at offset `0x1000`)
- **ESP32-C3 generic** — `ESP32_GENERIC_C3-20240602-v1.23.0.bin` (for the RISC-V based ESP32-C3, flashed at offset `0x0`)

Because these are fetched with cryptographic hashes, Nix guarantees you get the exact same firmware binary every time. If the upstream file changes or is tampered with, the build fails. This is a significant reproducibility advantage over manually downloading firmware.

### The `esp` CLI — A Custom Shell Script

The most substantial part of the flake is `esp-helper`, a Bash script wrapped with `pkgs.writeShellScriptBin` so it appears as the `esp` command in your PATH inside the dev shell. This script is the unified interface for all board operations. It uses `set -euo pipefail` for strict error handling throughout. Here is what each subcommand does:

**`esp detect`** — Runs port detection (scanning `/dev/cu.usbmodem*` and `/dev/cu.usbserial*` on macOS, `/dev/ttyUSB*` and `/dev/ttyACM*` on Linux, or using the `ESP_PORT` environment variable if set), then runs `esptool --port <port> chip_id` to identify the connected chip. Prints the detected port and chip type. This is your "is the board plugged in?" sanity check.

**`esp erase`** — Detects the port and runs `esptool erase_flash`. This wipes the entire flash memory on the board. You typically only do this once before first flashing, or when you want a clean slate.

**`esp flash`** — Detects port and chip, selects the correct pinned firmware binary and flash offset for that chip, then runs `esptool write_flash` at 460800 baud. The firmware selection is fully automatic — you do not need to know which chip you have or which firmware to download.

**`esp sync`** — The main deployment command. Detects the port, creates the `lib/` directory on the board if it does not exist, then uses `mpremote` to copy all six board files — `boot.py`, `main.py`, `config.json`, `gpio_api.py`, `lib/microdot.py`, and `lib/websocket.py` — to the board in a single chained command, followed by a board reset. After this, the board reboots and your code is running. Files that do not exist locally are skipped with a warning.

**`esp push <file> [...]`** — Pushes one or more individual files to the board. If the file is in a subdirectory (like `lib/microdot.py`), it creates the directory on the board first. Useful for quick iteration on a single file without resyncing everything.

**`esp run <script.py>`** — Runs a Python script on the board without copying it to flash. The script executes in RAM and is gone after the board resets. Useful for one-off tests and debugging.

**`esp repl`** — Opens an interactive MicroPython REPL on the board via `mpremote`. You can type Python expressions and see them execute on the microcontroller in real time. Exit with `Ctrl+X`.

**`esp monitor`** — Opens a raw serial connection to the board using `picocom` at 115200 baud. This shows all serial output (print statements, boot messages, tracebacks). Exit with `Ctrl+A` then `Ctrl+X`. Useful for seeing `boot.py` connection logs and server startup messages.

**`esp ls [path]`** — Lists files on the board's filesystem using `mpremote`. Defaults to the root `/` directory. Handy for verifying what is actually on the device.

**`esp gpio <pin> [value]`** — Quick digital read/write from the host shell. With one argument reads the pin; with two sets the value. Requires `ESP_IP` environment variable.

**`esp adc <pin>`** — Reads one ADC sample and displays voltage.

**`esp i2c scan`** — Scans the I2C bus and displays found devices.

**`esp stream [pin,pin,...]`** — Opens a WebSocket stream to the board for real-time monitoring. Optionally filter to specific pins.

### The Dev Shell

The flake's output is a single `devShells.default` built with `pkgs.mkShell`. When you run `nix develop`, Nix builds (or fetches from cache) every dependency and drops you into a shell with these tools on your PATH:

- **esptool** — The official Espressif tool for communicating with ESP chip bootloaders. Used for flashing firmware, erasing flash, reading chip info.
- **python3** — CPython interpreter, available in case you need to run any host-side Python scripts.
- **pyserial** — Python serial port library, a dependency of `esptool` and useful for any custom serial communication scripts.
- **mpremote** — The official MicroPython remote control tool. Handles file transfer (copying files to/from the board), REPL access, running scripts remotely, and filesystem operations.
- **picocom** — A minimal terminal emulation program for serial ports. Provides raw serial monitoring of the board's output.
- **curl** — HTTP client used by the `esp gpio`, `esp adc`, and `esp i2c` helper subcommands to call the board's REST API.
- **websocat** — A command-line WebSocket client. Used by `esp stream` to connect to the board's `/ws/stream` endpoint for real-time pin monitoring.
- **jq** — JSON pretty-printer. Used by the CLI helpers to format API responses for human-readable terminal output.
- **esp** — The custom CLI described above.

On shell entry, a `shellHook` prints `"ESP32 dev shell ready. Run 'esp' for commands."` so you know the environment is active.

---

## Supported Hardware

The project supports two ESP-32 variants:

- **ESP32** — The original Xtensa-based dual-core chip. Firmware is flashed at memory offset `0x1000`. This is the most common variant found in generic dev boards like the ESP32-DevKitC, NodeMCU-32S, and similar.

- **ESP32-C3** — The newer RISC-V based single-core chip. Firmware is flashed at memory offset `0x0`. Found in boards like the ESP32-C3-DevKitM and Seeed XIAO ESP32C3.

The `esp` CLI automatically distinguishes between these two chips using `esptool chip_id` and selects the correct firmware and flash offset. You never need to specify which board you have.

---

## Configuration

The board's behavior is controlled entirely by `config.json`. The fields are:

- **device_name** — A human-readable name displayed in the browser tab title and as the dashboard heading. Default: `ESP32-Dashboard`.
- **wifi_ssid** — The name of your local WiFi network to connect to in station mode.
- **wifi_password** — The password for your WiFi network.
- **ap_ssid** — The name of the fallback WiFi network the board creates if station mode fails. Default: `ESP32-Dashboard`.
- **ap_password** — The password for the fallback AP network. Must be at least 8 characters for WPA2. Default: `12345678`.
- **web_port** — The TCP port the Microdot web server listens on. Default: `80`.

This file is gitignored. Copy `config.json.example` and fill in your real values.

---

## Design Decisions and Constraints

**Inline HTML** — The entire dashboard UI is a Python string in `main.py`. There are no separate HTML, CSS, or JS files on the board. This avoids multiple file reads on the microcontroller's slow flash filesystem and keeps deployment simple (fewer files to sync).

**No external JS or CSS** — The dashboard's `<style>` block and `<script>` block are embedded directly in the HTML string. No CDN links, no npm packages, no build tools. The board needs zero internet access to serve its own dashboard.

**Async Microdot** — The web framework uses `uasyncio` (MicroPython's async/await implementation) for cooperative multitasking. This means the server can handle overlapping requests without threads (which MicroPython does not support well on ESP32).

**JSON API separation** — The dashboard UI and the data it displays are served by separate routes. The HTML page is static (served once), and the dynamic data comes from `/api/status` via fetch. This keeps the HTML response small and cacheable, and makes the API independently useful (you could query it with `curl` or another tool).

**AP fallback** — If WiFi credentials are wrong or the router is offline, the board does not just sit there doing nothing. It creates its own WiFi network so you can always reach it. This is critical for initial setup (when you might not have the right credentials yet) and for resilience.

**Garbage collection before memory reporting** — The `/api/status` handler calls `gc.collect()` before reading `gc.mem_free()` to give an accurate picture of actually available memory rather than memory that could be reclaimed.

**Tick-based uptime** — Uptime uses `time.ticks_ms()` and `time.ticks_diff()` which handles the eventual integer wraparound correctly (MicroPython ticks wrap around approximately every 12.4 days on 32-bit counters). For a simple dashboard, this is perfectly adequate.

---

## Quick Start — Step by Step

1. **Enter the dev shell** — Run `nix develop` from the project root. This downloads and configures all tools automatically. You will see the ready message in your terminal.

2. **Set up your config** — Copy `config.json.example` to `config.json` and edit it with your WiFi network name and password.

3. **Connect the board** — Plug your ESP32 or ESP32-C3 into a USB port. Run `esp detect` to verify the board is recognized and to see which port and chip type were detected.

4. **Flash firmware (first time only)** — Run `esp erase` to wipe the flash, then `esp flash` to write the MicroPython v1.23.0 firmware. This only needs to happen once per board (or when you want to update the MicroPython version).

5. **Deploy your code** — Run `esp sync` to push all four application files to the board and trigger a reboot.

6. **Open the dashboard** — Watch the serial output (`esp monitor`) to see the board connect to WiFi and print its IP address. Open that IP in a browser. You should see the dashboard with live-updating stats.

7. **Iterate** — Edit `main.py` or `boot.py` locally, run `esp sync` again, and the board reboots with your changes. For quick single-file changes, use `esp push main.py`.

---

## Troubleshooting

**"No serial device found"** — The board is not plugged in, or the USB cable is charge-only (no data lines). Try a different cable. On macOS, look for `/dev/cu.usbmodem*` or `/dev/cu.usbserial*` devices. On Linux, look for `/dev/ttyUSB*` or `/dev/ttyACM*`.

**"Multiple devices found"** — You have more than one serial device connected. The CLI picks the first one. Set `export ESP_PORT=/dev/cu.usbmodem14101` (or whatever your port is) to force a specific device.

**WiFi connection fails, board goes to AP mode** — Check your SSID and password in `config.json`. The SSID is case-sensitive. After fixing, run `esp push config.json` to update just the config, then reset the board.

**Dashboard shows "Error fetching status"** — The board may have rebooted or lost WiFi. Check `esp monitor` for serial output. If the board is in AP mode, make sure your computer is connected to the board's AP network.

**esptool fails during flash** — Some boards require holding the BOOT button during the initial connection. Try holding BOOT, pressing RESET, then releasing BOOT before running `esp flash`.

---

## Tech Stack Summary

| Layer             | Technology                              |
| ----------------- | --------------------------------------- |
| Hardware          | ESP-32 or ESP-32-C3                     |
| Runtime           | MicroPython v1.23.0                     |
| Web Framework     | Microdot (async, single-file, vendored) |
| Dev Environment   | Nix Flakes (nixpkgs unstable)           |
| Firmware Flashing | esptool                                 |
| File Transfer     | mpremote                                |
| Serial Monitor    | picocom                                 |
| WebSocket Transport | Microdot WebSocket extension (vendored) |
| Unified CLI       | Custom `esp` shell script via Nix       |

---

## File Inventory

| File                | Where It Lives  | Purpose                                         |
| ------------------- | --------------- | ------------------------------------------------ |
| `boot.py`           | Board + Repo    | WiFi connection with AP fallback on power-on     |
| `main.py`           | Board + Repo    | Microdot web server, dashboard HTML, JSON API    |
| `config.json`       | Board only      | WiFi credentials and device settings (gitignored)|
| `lib/microdot.py`   | Board + Repo    | Vendored async HTTP framework for MicroPython    |
| `gpio_api.py`       | Board + Repo    | All GPIO, ADC, PWM, I2C route handlers and WebSocket broadcaster |
| `lib/websocket.py`  | Board + Repo    | Vendored Microdot WebSocket extension for real-time streaming    |
| `config.json.example` | Repo only     | Template config safe to commit                   |
| `flake.nix`         | Repo only       | Nix dev shell, esp CLI, pinned firmware          |
| `flake.lock`        | Repo only       | Pinned dependency versions for reproducibility   |
| `slides.md`         | Repo only       | Presentation deck (for presenterm)               |
| `CLAUDE.md`         | Repo only       | This comprehensive project guide                 |
| `.gitignore`        | Repo only       | Excludes config.json and .direnv from git        |


---

## Part II — GPIO & Sensor API Suite

This section extends the base project with a full hardware-control API layer. The goal is to expose every meaningful peripheral of the ESP32-C3 — digital GPIO, ADC, PWM, I2C bus scan, internal temperature — over both a REST HTTP API and a WebSocket channel for real-time, bidirectional streaming. No UI is shipped with this layer. The board is the server; you talk to it with `curl`, a WebSocket client, or any host-side script.

---

### ESP32-C3 Hardware Capabilities Reference

Before writing a line of code it is essential to know exactly what the chip can do and where the landmines are. The ESP32-C3 is a single-core RISC-V chip, not the Xtensa ESP32. The peripheral set differs in important ways.

**Usable GPIO pins and their capabilities:**

| GPIO | Digital IN | Digital OUT | ADC | PWM | Notes |
|------|-----------|------------|-----|-----|-------|
| 0    | ✓ | ✓ | ADC1-CH0 | ✓ | Strapping pin — avoid pulling low at boot |
| 1    | ✓ | ✓ | ADC1-CH1 | ✓ | |
| 2    | ✓ | ✓ | ADC1-CH2 | ✓ | Strapping pin — must be high at boot |
| 3    | ✓ | ✓ | ADC1-CH3 | ✓ | |
| 4    | ✓ | ✓ | ADC1-CH4 | ✓ | |
| 5    | ✓ | ✓ | — | ✓ | Default SPI SS |
| 6    | ✓ | ✓ | — | ✓ | Default SPI MISO |
| 7    | ✓ | ✓ | — | ✓ | Default SPI MOSI |
| 8    | ✓ | ✓ | — | ✓ | Default I2C SDA; onboard RGB on some boards |
| 9    | ✓ | ✓ | — | ✓ | Default I2C SCL; BOOT button on most boards |
| 10   | ✓ | ✓ | — | ✓ | Default SPI SCK |
| 18   | ✓ | ✓ | — | ✓ | USB D- on boards with native USB — check your board |
| 19   | ✓ | ✓ | — | ✓ | USB D+ on boards with native USB — check your board |
| 20   | ✓ | — | — | — | UART0 RX (REPL) — read-only, do not drive |
| 21   | — | ✓ | — | — | UART0 TX (REPL) — do not repurpose |

**Critical constraints for the API implementation:**

- **ADC only on GPIO 0–4.** These are ADC block 1 pins. The ESP32-C3 has no ADC block 2, so there is no conflict with WiFi (unlike the classic ESP32 where ADC2 is disabled when WiFi is active). All five ADC pins are safe to read concurrently with the WiFi stack running.
- **No DAC.** The ESP32-C3 has no digital-to-analog converter. Analog output must be done with PWM.
- **No capacitive touch.** Skip any touch-sensor API surface.
- **No `esp32.raw_temperature()`** — that function is Xtensa-only. On C3, use `esp32.mcu_temperature()` which returns Celsius directly.
- **PWM on all output-capable pins** via the LED PWM controller. Frequency range 1 Hz – 40 MHz with 13-bit duty resolution at typical frequencies.
- **I2C defaults: SDA = GPIO8, SCL = GPIO9.** Can be remapped to any output-capable pin in software.
- **GPIO 0, 2 are strapping pins.** They must be in a specific state at boot. They are safe to use after boot but avoid driving them to the wrong state while programming.

---

### Architecture of the API Layer

The API is implemented as a single additional file — `gpio_api.py` — that is imported by `main.py`. This keeps the routing file small and makes the hardware abstraction independently testable in the REPL. A second vendored file — `lib/websocket.py` — enables the Microdot WebSocket extension.

The complete set of files deployed to the board grows from four to six:

| File | Role |
|------|------|
| `boot.py` | Unchanged — WiFi/AP setup |
| `main.py` | Extended — mounts gpio_api routes onto the Microdot app |
| `config.json` | Extended — adds a `pin_aliases` map and `adc_atten` setting |
| `gpio_api.py` | New — all GPIO, ADC, PWM, I2C, and internal sensor logic |
| `lib/microdot.py` | Unchanged |
| `lib/websocket.py` | New — Microdot's WebSocket extension (vendored from the same repo) |

**Transport strategy:**

- **HTTP REST** for all stateless, one-shot operations: reading a pin once, setting a pin, scanning I2C, querying the pin map, reading internal temperature.
- **WebSocket** (`ws://`) for continuous, low-latency streaming: a client connects to `/ws/stream` and receives a JSON frame every N milliseconds containing the current state of every monitored pin, ADC readings, and temperature. The client can also send JSON commands over the same socket to set pins without making a separate HTTP call.

This hybrid approach keeps the REST API fully usable with `curl` while supporting real-time clients (dashboards, Python scripts, Node-RED, etc.) through the WebSocket channel.

---

### New and Modified Files — Full Specification

#### `gpio_api.py` (new, lives on board)

This module owns all hardware interaction. It exposes a single function `register_routes(app)` that attaches every route to the Microdot app passed in from `main.py`. It maintains two module-level dictionaries:

- `PIN_REGISTRY` — maps pin numbers to their current mode (`IN`, `OUT`, `PWM`, `ADC`) and a live `machine.Pin` or `machine.PWM` object.
- `STREAM_CONFIG` — holds the list of pins currently being streamed over the WebSocket and the polling interval in milliseconds.

**Internal structure:**

```python
# gpio_api.py — outline, not final code
import json
import gc
import esp32
import uasyncio as asyncio
from machine import Pin, ADC, PWM, SoftI2C

from microdot import Response
from microdot.websocket import with_websocket

# --- Safe pin sets (C3-specific) ---
DIGITAL_PINS  = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 18, 19}
ADC_PINS      = {0, 1, 2, 3, 4}          # ADC1 only
OUTPUT_PINS   = DIGITAL_PINS             # all digital pins can be outputs
INPUT_PINS    = DIGITAL_PINS | {20}      # GPIO20 is input-only

PIN_REGISTRY  = {}   # {pin_num: {"mode": str, "obj": machine object}}
STREAM_CONFIG = {"pins": [], "interval_ms": 100}
_ws_clients   = []   # list of active WebSocket connections

def register_routes(app):
    # --- attach all routes here ---
    pass
```

#### `lib/websocket.py` (new, vendored)

Microdot's WebSocket extension lives in a separate file alongside `microdot.py`. It is sourced from `https://github.com/miguelgrinberg/microdot/blob/main/src/microdot/websocket.py`. This file must be vendored (downloaded and committed) the same way `microdot.py` is — MicroPython has no package installer. The `esp sync` command in `flake.nix` must be updated to push this additional file.

#### `config.json` changes

Two new optional keys:

```json
{
  "pin_aliases": {
    "led": 8,
    "relay": 5,
    "sensor_in": 3
  },
  "adc_atten": "11db"
}
```

`pin_aliases` lets external clients refer to pins by friendly name in API calls. `adc_atten` sets the default ADC attenuation for all channels. Valid values: `"0db"` (0–1.0 V), `"2.5db"` (0–1.34 V), `"6db"` (0–2.0 V), `"11db"` (0–3.6 V). Defaults to `"11db"` to match the 3.3 V GPIO rail.

---

### Complete REST API Reference

All responses are `application/json`. All request bodies that require parameters use `application/json`. Numeric pin values in URL paths are the bare GPIO number (e.g., `/api/gpio/8`). Aliases defined in `pin_aliases` are accepted anywhere a pin number is accepted.

#### System

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/gpio/pins` | Returns the full pin map: every pin, its current mode, direction, and value |
| `GET` | `/api/gpio/capabilities` | Returns static chip capabilities: valid GPIO set, ADC pins, PWM pins, no-DAC flag |
| `GET` | `/api/gpio/temperature` | Returns the ESP32-C3 internal MCU temperature in °C via `esp32.mcu_temperature()` |

**`GET /api/gpio/pins` response example:**
```json
{
  "pins": {
    "0":  {"mode": "IN",  "value": 1},
    "5":  {"mode": "OUT", "value": 0},
    "8":  {"mode": "PWM", "freq": 1000, "duty_u16": 32768},
    "2":  {"mode": "ADC", "raw": 2418, "voltage_uv": 1650000}
  },
  "aliases": {"led": 8, "relay": 5}
}
```

#### Digital GPIO

| Method | Path | Body | Description |
|--------|------|------|-------------|
| `GET`  | `/api/gpio/<pin>` | — | Read current pin mode and value |
| `POST` | `/api/gpio/<pin>/mode` | `{"mode": "IN"\|"OUT", "pull": "up"\|"down"\|null}` | Configure pin direction. Resets any active PWM on that pin. |
| `POST` | `/api/gpio/<pin>/value` | `{"value": 0\|1}` | Set digital output (pin must be in OUT mode) |
| `POST` | `/api/gpio/<pin>/toggle` | — | Toggle current output state |

**`GET /api/gpio/8` response example:**
```json
{"pin": 8, "mode": "OUT", "value": 0}
```

**`POST /api/gpio/8/value` body:**
```json
{"value": 1}
```

#### ADC (Analog Input — GPIO 0–4 only)

| Method | Path | Body | Description |
|--------|------|------|-------------|
| `GET`  | `/api/adc/<pin>` | — | Single ADC sample. Returns raw 12-bit value and calibrated voltage in µV. |
| `POST` | `/api/adc/<pin>/config` | `{"atten": "11db"}` | Change attenuation on a specific pin |
| `GET`  | `/api/adc/all` | — | Read all five ADC pins in one call |

**`GET /api/adc/2` response example:**
```json
{
  "pin": 2,
  "raw": 2418,
  "voltage_uv": 1650000,
  "voltage_v": 1.65,
  "atten": "11db"
}
```

**`GET /api/adc/all` response example:**
```json
{
  "readings": {
    "0": {"raw": 0,    "voltage_v": 0.0},
    "1": {"raw": 1024, "voltage_v": 0.82},
    "2": {"raw": 2418, "voltage_v": 1.65},
    "3": {"raw": 4095, "voltage_v": 3.3},
    "4": {"raw": 512,  "voltage_v": 0.41}
  }
}
```

#### PWM (on any digital output pin)

| Method | Path | Body | Description |
|--------|------|------|-------------|
| `POST` | `/api/pwm/<pin>/start` | `{"freq": 1000, "duty_u16": 32768}` | Start PWM on pin. `duty_u16` is 0–65535 (maps to 0–100% duty). |
| `POST` | `/api/pwm/<pin>/duty`  | `{"duty_u16": 49152}` | Update duty cycle without stopping the signal |
| `POST` | `/api/pwm/<pin>/freq`  | `{"freq": 5000}` | Update frequency without stopping the signal |
| `POST` | `/api/pwm/<pin>/stop`  | — | Stop PWM and release pin back to digital OUT |
| `GET`  | `/api/pwm/<pin>` | — | Get current PWM parameters |

**`POST /api/pwm/5/start` body:**
```json
{"freq": 1000, "duty_u16": 32768}
```

**`GET /api/pwm/5` response:**
```json
{"pin": 5, "active": true, "freq": 1000, "duty_u16": 32768, "duty_pct": 50.0}
```

#### I2C Bus

The I2C routes operate on a single soft-I2C bus instance. Pins default to SDA=8, SCL=9 but can be overridden in the config or per-request. The bus is initialized lazily on first use and torn down when no longer needed to free the pins.

| Method | Path | Body | Description |
|--------|------|------|-------------|
| `GET`  | `/api/i2c/scan` | — | Scan the I2C bus and return a list of detected device addresses |
| `POST` | `/api/i2c/read` | `{"addr": 60, "nbytes": 6}` | Read N bytes from device at 7-bit address |
| `POST` | `/api/i2c/write` | `{"addr": 60, "data": [0x00, 0xFF]}` | Write bytes to device |
| `POST` | `/api/i2c/write_read` | `{"addr": 60, "write": [0x01], "read": 2}` | Write then read (register read pattern) |
| `POST` | `/api/i2c/config` | `{"sda": 8, "scl": 9, "freq": 400000}` | Reconfigure bus pins and frequency |

**`GET /api/i2c/scan` response:**
```json
{"devices": [60, 104], "hex": ["0x3c", "0x68"], "count": 2}
```

**`POST /api/i2c/read` body / response:**
```json
// body
{"addr": 104, "nbytes": 6}

// response
{"addr": 104, "data": [72, 0, 18, 0, 251, 255], "hex": "480012 00FBFF"}
```

#### Batch Operations

For setting or reading multiple pins in a single HTTP round-trip (important on slow WiFi):

| Method | Path | Body | Description |
|--------|------|------|-------------|
| `POST` | `/api/gpio/batch/read` | `{"pins": [0, 2, 5]}` | Read multiple pins at once |
| `POST` | `/api/gpio/batch/write` | `{"pins": {"5": 1, "9": 0}}` | Set multiple output pins at once |

---

### WebSocket API — Real-Time Channel

The WebSocket endpoint lives at `/ws/stream`. A client opens a persistent connection and gets push updates. The connection is also a command channel — the client can send JSON commands to set pins without a separate HTTP call.

**Connecting:**
```
ws://<board-ip>/ws/stream
```

Microdot's `with_websocket` decorator handles the HTTP → WebSocket upgrade automatically. The handler registers the socket in `_ws_clients` and runs two concurrent async tasks:

1. **Broadcaster task** — loops at `STREAM_CONFIG["interval_ms"]` milliseconds and sends a snapshot frame to every connected client.
2. **Receiver task** — awaits incoming messages from this specific client and dispatches commands.

Multiple simultaneous WebSocket clients are supported. Each connection gets the same broadcast frames.

#### Server-to-client frames

The board sends a frame at the configured interval (default 100 ms). The frame structure:

```json
{
  "ts": 84231,
  "gpio": {
    "0": {"mode": "IN",  "value": 1},
    "5": {"mode": "OUT", "value": 0},
    "8": {"mode": "PWM", "duty_u16": 32768}
  },
  "adc": {
    "2": {"raw": 2418, "voltage_v": 1.65},
    "3": {"raw": 0,    "voltage_v": 0.0}
  },
  "temp_c": 43.2,
  "mem_free_kb": 112
}
```

`ts` is `time.ticks_ms()` — the board's uptime in milliseconds. Only pins currently in `STREAM_CONFIG["pins"]` are included in `gpio` and `adc` blocks. If the list is empty, all known pins from `PIN_REGISTRY` are included.

#### Client-to-server commands

The client sends JSON over the same socket. The `cmd` field dispatches to the correct handler:

**Set a digital pin:**
```json
{"cmd": "set", "pin": 5, "value": 1}
```

**Set PWM duty:**
```json
{"cmd": "pwm_duty", "pin": 8, "duty_u16": 49152}
```

**Change stream configuration (which pins, how fast):**
```json
{"cmd": "stream_config", "pins": [0, 2, 3, 5, 8], "interval_ms": 200}
```

**Ping/pong (keepalive):**
```json
{"cmd": "ping"}
```
Response:
```json
{"cmd": "pong", "ts": 84500}
```

**Error responses** (sent back on invalid commands):
```json
{"error": "pin 25 is not a valid C3 GPIO", "cmd": "set", "pin": 25}
```

---

### Implementation Plan — Step by Step

This section describes how to build the API layer incrementally, in order of increasing complexity. Each phase is independently testable.

**Phase 1 — Vendor `websocket.py` and extend `esp sync`**

Download `websocket.py` from `github.com/miguelgrinberg/microdot/blob/main/src/microdot/websocket.py` and place it at `lib/websocket.py` in the repo. Update the `esp sync` subcommand in `flake.nix` to include this file in the `mpremote` copy chain alongside the existing four files. Verify with `esp ls lib/` that both `microdot.py` and `websocket.py` appear on the board.

**Phase 2 — Pin registry and capabilities endpoint**

Create `gpio_api.py` with just `DIGITAL_PINS`, `ADC_PINS`, `PIN_REGISTRY`, and the three system routes: `/api/gpio/pins`, `/api/gpio/capabilities`, `/api/gpio/temperature`. Import and call `register_routes(app)` from `main.py`. Deploy with `esp sync` and test with `curl http://<board-ip>/api/gpio/capabilities`.

**Phase 3 — Digital GPIO CRUD**

Add the four digital routes (`GET /<pin>`, `POST /<pin>/mode`, `POST /<pin>/value`, `POST /<pin>/toggle`). Implement input validation — reject any pin number not in `DIGITAL_PINS`, reject mode changes that would put the REPL UART pins in OUTPUT mode. Use the `PIN_REGISTRY` to track live `machine.Pin` objects so pins are not re-constructed on every request.

Test sequence using `curl`:
```bash
# Configure GPIO5 as output
curl -X POST http://<ip>/api/gpio/5/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "OUT"}'

# Set it high
curl -X POST http://<ip>/api/gpio/5/value \
  -H "Content-Type: application/json" \
  -d '{"value": 1}'

# Read it back
curl http://<ip>/api/gpio/5
```

**Phase 4 — ADC endpoints**

Add ADC routes. Instantiate `machine.ADC` objects lazily when first requested for a given pin. Cache the object in `PIN_REGISTRY` under mode `"ADC"`. Always call `adc.read_uv()` rather than `adc.read_u16()` to get calibrated microvolts — then derive voltage_v by dividing by 1,000,000. Set attenuation to `ADC.ATTN_11DB` by default so the full 0–3.3 V range is readable.

Important: calling `machine.ADC()` on a pin already configured as digital OUT in `PIN_REGISTRY` should return a 400 error and a clear message, not silently reconfigure the pin.

**Phase 5 — PWM endpoints**

Add PWM routes. Use `machine.PWM(Pin(n), freq=f)` to create the object. Store in `PIN_REGISTRY` under mode `"PWM"`. The duty cycle is always expressed as `duty_u16` (0–65535) internally but return `duty_pct` as a float for convenience. `POST /stop` must call `pwm_obj.deinit()` and remove the entry from the registry, restoring the pin to a neutral state.

**Phase 6 — I2C bus routes**

Maintain a single module-level `_i2c` instance (or `None` if not initialized). The `/api/i2c/scan` route initializes it on first call using defaults from `config.json`. The `/api/i2c/config` route tears down and re-creates the bus if pins or frequency change. Return raw byte arrays as lists of integers in JSON (MicroPython's `json.dumps` cannot serialize `bytes` directly — convert with `list(data)`).

**Phase 7 — Batch endpoints**

`POST /api/gpio/batch/write` iterates the provided pin-value dict, reads from `PIN_REGISTRY` to find each pin's `machine.Pin` object, and calls `.value()` on each. It collects any errors (unknown pin, wrong mode) into an `errors` list and returns a partial success response rather than failing the whole batch.

**Phase 8 — WebSocket stream**

This is the most complex phase. The implementation must handle the constraint that MicroPython's `uasyncio` on C3 does not support `asyncio.wait()` with multiple futures (unlike CPython). The recommended pattern is a single coroutine per connection that polls both an inbound queue and a tick counter:

```python
@app.route('/ws/stream')
@with_websocket
async def ws_stream(request, ws):
    _ws_clients.append(ws)
    last_broadcast = time.ticks_ms()
    try:
        while True:
            # Non-blocking receive attempt using asyncio.wait_for with timeout
            try:
                msg = await asyncio.wait_for(ws.receive(), 
                                              STREAM_CONFIG["interval_ms"] / 1000)
                await _handle_ws_command(ws, msg)
            except asyncio.TimeoutError:
                pass  # no inbound message, fall through to broadcast

            now = time.ticks_ms()
            if time.ticks_diff(now, last_broadcast) >= STREAM_CONFIG["interval_ms"]:
                frame = _build_stream_frame()
                await ws.send(json.dumps(frame))
                last_broadcast = now

    except Exception:
        pass
    finally:
        _ws_clients.remove(ws)
```

The key insight: use `asyncio.wait_for` with a timeout equal to the broadcast interval as a non-blocking receive. If the timeout fires, broadcast and loop. If a message arrives first, handle it and then check whether it is also time to broadcast. This avoids the missing `asyncio.wait` on MicroPython while keeping both directions active.

**Phase 9 — Error handling and pin safety**

Add a module-level `FORBIDDEN_PINS` set: `{20, 21}` (UART0 RX/TX used by the REPL). Any attempt to configure these as outputs or drive them via the API should return HTTP 403 with a descriptive error. Add range checks: GPIO numbers must be in `DIGITAL_PINS`. PWM frequency must be between 1 and 40,000,000. Duty must be 0–65535. ADC pins must be in `ADC_PINS`. I2C addresses must be 0–127.

**Phase 10 — Config extension and `esp push` workflow**

Extend `config.json.example` with the new keys. Document in this file (see below) that after adding pin aliases, only `esp push config.json` is needed — no full re-flash. Add a new `esp alias` subcommand to `flake.nix` that prints the current aliases from the on-board config by running a one-liner via `mpremote exec`.

---

### New `esp` CLI Subcommands

These additions to the `esp` shell script in `flake.nix` support the GPIO API workflow:

**`esp gpio <pin> [value]`** — Quick digital read/write from the host shell without opening a browser. With no second argument, reads the pin. With `0` or `1`, sets the output. Internally calls `curl` against the REST API. Requires the board's IP to be in the environment variable `ESP_IP`, or looks it up via mDNS if `avahi-browse` is available.

**`esp adc <pin>`** — Reads one ADC sample from the specified pin and prints the voltage in human-readable form.

**`esp stream [pin,pin,...]`** — Opens a WebSocket connection to `/ws/stream` using `websocat` (added to the Nix dev shell) and pretty-prints incoming frames. If pins are specified, sends a `stream_config` command first to filter the stream. Exit with `Ctrl+C`.

**`esp i2c scan`** — Calls `GET /api/i2c/scan` and prints a formatted table of found devices.

**`esp alias`** — Prints the `pin_aliases` map from the board's `config.json`.

These subcommands all share the same port-detection logic as the existing subcommands and respect `ESP_PORT` and the new `ESP_IP` environment variable.

---

### New Dev Shell Dependencies

Add the following to the `buildInputs` list in `flake.nix`:

- **`curl`** — Already present on most systems but should be explicit for the `esp gpio` and `esp adc` helper subcommands.
- **`websocat`** — A command-line WebSocket client (`nixpkgs` package: `websocat`). Used by `esp stream` to connect to the WebSocket endpoint.
- **`jq`** — JSON pretty-printer (`nixpkgs` package: `jq`). Used by the CLI helpers to format API responses.

---

### New Files — Repository Inventory Update

| File | Where It Lives | Purpose |
|------|---------------|---------|
| `gpio_api.py` | Board + Repo | All GPIO, ADC, PWM, I2C route handlers and WebSocket broadcaster |
| `lib/websocket.py` | Board + Repo | Vendored Microdot WebSocket extension |

The updated `esp sync` command pushes all six board files in sequence:
```
mpremote connect <port> \
  mkdir :lib \
  cp boot.py :boot.py \
  cp main.py :main.py \
  cp config.json :config.json \
  cp gpio_api.py :gpio_api.py \
  cp lib/microdot.py :lib/microdot.py \
  cp lib/websocket.py :lib/websocket.py \
  + reset
```

---

### Design Decisions for This Layer

**Lazy pin initialization** — `machine.Pin`, `machine.ADC`, and `machine.PWM` objects are created on first API access and cached in `PIN_REGISTRY`. This avoids consuming resources for peripherals the caller never uses, and keeps boot time fast.

**Mode exclusivity** — A pin can only be in one mode at a time. Requesting ADC on a pin currently in PWM mode returns a 409 Conflict. This prevents the silent corruption that would occur if two `machine` objects held the same pin simultaneously.

**No persistent pin state across reboots** — MicroPython has no NVS (non-volatile storage) API in the standard library. Pin modes set via the API are lost on reset. If persistence is needed in a future phase, `config.json` can be written from `gpio_api.py` using `ujson.dump()` on a `pin_state` key.

**JSON-only responses** — Every response, including errors, is `application/json` with a consistent envelope: `{"error": "..."}` for failures. HTTP status codes are used correctly (200, 400, 403, 404, 409, 500) so host-side code can branch on status without parsing the body.

**No authentication** — This API has no authentication. It is intended for local network use (STA mode on a trusted LAN, or directly over the AP fallback network). Do not expose port 80 to the internet.

**Streaming interval floor** — The minimum `interval_ms` for the WebSocket stream is 50 ms. Below this, the async task does not yield long enough to allow the HTTP server to service other requests, and the board becomes unresponsive to REST calls while a WebSocket client is connected.

**Memory budget** — The ESP32-C3 GENERIC firmware ships with approximately 250 KB of free heap after MicroPython starts. Importing `gpio_api.py` with all objects initialized costs roughly 15–20 KB. Each active WebSocket connection costs approximately 2–4 KB. Budget accordingly if running multiple concurrent clients.

---

### Quick-Start for the GPIO API

After completing the base project quick-start:

1. **Vendor the WebSocket module** — Download `websocket.py` from the Microdot repository and place it at `lib/websocket.py`.

2. **Extend config** — Add `pin_aliases` and `adc_atten` to your `config.json`.

3. **Create `gpio_api.py`** — Implement the phases above, starting with the system routes.

4. **Update `main.py`** — Add `from gpio_api import register_routes` and call `register_routes(app)` before `app.run()`.

5. **Deploy** — Run `esp sync`. Watch `esp monitor` to confirm no import errors on boot.

6. **Smoke test**:
   ```bash
   # Confirm capabilities
   curl http://<board-ip>/api/gpio/capabilities | jq

   # Set GPIO5 high
   curl -X POST http://<board-ip>/api/gpio/5/mode \
     -H "Content-Type: application/json" -d '{"mode":"OUT"}'
   curl -X POST http://<board-ip>/api/gpio/5/value \
     -H "Content-Type: application/json" -d '{"value":1}'

   # Read ADC on GPIO2
   curl http://<board-ip>/api/adc/2 | jq

   # Scan I2C
   curl http://<board-ip>/api/i2c/scan | jq

   # Open WebSocket stream
   esp stream 2,5
   ```

7. **Iterate** — Edit `gpio_api.py` locally, run `esp push gpio_api.py`, then reset the board with `mpremote connect <port> reset`. No full sync needed for single-file changes.
