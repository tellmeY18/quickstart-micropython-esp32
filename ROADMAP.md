# ROADMAP.md — Quickstart Toolkit Transformation

This document is the implementation plan for transforming the ESP-32 MicroPython dashboard project from a single-purpose GPIO API server into a **zero-config quickstart toolkit** for ESP-32 family development.

The goal: a developer plugs in any ESP-32 board, runs `nix develop && esp flash`, picks a template, and has working code on hardware in under two minutes.

---

## Table of Contents

- [Design Principles](#design-principles)
- [What We Are NOT Building](#what-we-are-not-building-non-goals)
- [Current Inventory](#current-inventory)
- [Target Repository Structure](#target-repository-structure)
- [Migration Map](#migration-map)
- [gpio\_api.py Decomposition Plan](#gpio_apipy-decomposition-plan)
- [Milestone 0 — Planning & Audit](#milestone-0--planning--audit)
- [Milestone 1 — Repository Restructure](#milestone-1--repository-restructure)
- [Milestone 2 — Create the `minimal` Template](#milestone-2--create-the-minimal-template)
- [Milestone 3 — Create the `gpio` Template](#milestone-3--create-the-gpio-template)
- [Milestone 4 — Create the `sensors` Template](#milestone-4--create-the-sensors-template)
- [Milestone 5 — Create the `pwm` Template](#milestone-5--create-the-pwm-template)
- [Milestone 6 — Create the `neopixel` Template](#milestone-6--create-the-neopixel-template)
- [Milestone 7 — Create the `full` Template](#milestone-7--create-the-full-template)
- [Milestone 8 — Create Example Scripts](#milestone-8--create-example-scripts)
- [Milestone 9 — Generalize the `esp` CLI](#milestone-9--generalize-the-esp-cli)
- [Milestone 10 — Documentation](#milestone-10--documentation)
- [Milestone 11 — Multi-Board Support](#milestone-11--multi-board-support)
- [Milestone 12 — Polish & Release](#milestone-12--polish--release)
- [Milestone 13 — Meshtastic Firmware Support](#milestone-13--meshtastic-firmware-support)
- [Dependency Graph](#dependency-graph)

---

## Design Principles

These principles govern every decision in the transformation. When in doubt, refer back here.

1. **Two-minute time-to-blink.** A new user should go from `git clone` to blinking LED in under two minutes. Every friction point between "I have a board" and "it's doing something" is a bug.

2. **Templates are complete, standalone starting points.** Each template directory contains everything needed to build and run — no assembly required. A template is not a library; it is a copy-and-modify codebase. Users are expected to edit template files directly, not import from them.

3. **Core provides shared infrastructure, not shared logic.** The `core/` directory contains only files that are identical across every template: `boot.py` (WiFi connect), `lib/microdot.py` (web framework), and `lib/websocket.py` (WebSocket extension). No application logic lives in `core/`.

4. **Examples are throwaway learning tools.** Example scripts run with `esp run`, demonstrate one concept, require no project setup, and fit on a single screen. They are self-contained — no imports from `core/` or `lib/`.

5. **The `esp` CLI is board-agnostic.** CLI commands work with any template, any board variant, any file layout. The CLI never hardcodes file lists or pin numbers. Board-specific knowledge lives in templates and docs, not in the CLI.

6. **Feature flags are dead; templates are alive.** The current `config.json` feature-flag system (`"gpio": false, "adc": false, ...`) added complexity without benefit — users didn't know what to enable. Templates replace flags: you pick the template with the features you need, and it just works.

7. **RAM is the constraint, not disk.** The ESP32-C3 has ~320 KB SRAM and MicroPython uses ~100 KB at idle. Every template must leave ≥100 KB free heap after boot. Templates that combine too many features risk OOM and must document their memory footprint.

8. **No cloud, no build step, no native toolchain.** The entire development workflow is: Nix shell → serial connection → push files → done. No cross-compilation, no C extensions, no cloud accounts, no Docker.

9. **Config is minimal and obvious.** Each template's `config.json.example` contains only the keys that template actually uses. No unused keys, no nested objects unless genuinely needed, no mystery abbreviations.

10. **Errors are sentences, not codes.** Every API error response includes a human-readable message explaining what went wrong and what to do about it. No bare status codes, no `{"error": 42}`.

---

## What We Are NOT Building (Non-Goals)

| Non-Goal | Rationale |
|---|---|
| A library / package manager | Templates are copy-paste starting points, not `pip install` packages. There is no `import esp_toolkit`. |
| Cloud connectivity (MQTT, AWS IoT, etc.) | Out of scope. The toolkit is local-network-only. Cloud integration can be a future community template. |
| A web-based template picker / project generator | `esp init <template>` copies files. No web UI, no wizard, no interactive prompts. |
| BLE support | BLE + WiFi coexistence on ESP32-C3 is RAM-prohibitive (~50 KB overhead). Dropped from the template set. Could be a standalone example. |
| OTA (over-the-air) firmware updates | Complex, security-sensitive, and out of scope for a quickstart toolkit. |
| Support for non-MicroPython firmware | CircuitPython, Arduino, ESP-IDF are all out of scope. MicroPython v1.23.0 only. |
| A dashboard UI framework | The `minimal` template includes a basic HTML status page. Other templates expose JSON APIs only. Building a React/Vue dashboard is the user's job. |
| Unit test infrastructure | MicroPython's test tooling is limited. We verify by running on hardware. Each milestone has manual verification steps. |

---

## Current Inventory

Files on disk today and their roles:

| File | Lines | Role | Keep / Move / Delete |
|---|---|---|---|
| `CLAUDE.md` | ~798 | Project guide (old dashboard + Phase 2 plan) | **Rewrite** — becomes toolkit guide |
| `ROADMAP.md` | ~797 | GPIO API roadmap (old scope) | **Replace** — this document |
| `boot.py` | ~45 | WiFi connect with AP fallback | **Move** → `core/boot.py` (minor cleanup) |
| `main.py` | ~270 | Microdot server + inline HTML + debug instrumentation | **Decompose** → template `main.py` files |
| `config.json` | — | Runtime config (gitignored) | Stays gitignored; templates provide `.example` |
| `config.json.example` | ~22 | Template config with feature flags | **Decompose** → per-template examples |
| `gpio_api.py` | ~1200 | REST + WebSocket API for all peripherals | **Decompose** → per-template handler files |
| `debuglog.py` | ~150 | Ring-buffer flash logger | **Move** → `templates/full/debuglog.py` |
| `flake.nix` | ~250 | Nix dev shell + `esp` CLI | **Modify** — generalize CLI |
| `flake.lock` | — | Nix lock file | Stays |
| `.gitignore` | 2 lines | Ignores `config.json` and `.direnv` | **Expand** |
| `lib/microdot.py` | ~1500 | Vendored Microdot framework | **Move** → `core/lib/microdot.py` |
| `lib/websocket.py` | — | Vendored Microdot WebSocket extension | **Move** → `core/lib/websocket.py` |

---

## Target Repository Structure

```
project/
├── CLAUDE.md              # Rewritten toolkit guide
├── README.md              # User-facing quickstart (new)
├── ROADMAP.md             # This file
├── CHANGELOG.md           # Release notes (new, Milestone 12)
├── flake.nix              # Generalized Nix dev shell + esp CLI
├── flake.lock
├── .gitignore
│
├── core/                  # Shared files — identical in every template
│   ├── boot.py            # WiFi connect with AP fallback
│   └── lib/
│       ├── microdot.py    # Vendored Microdot web framework
│       └── websocket.py   # Vendored Microdot WebSocket extension
│
├── templates/             # Pick-a-starting-point system
│   ├── minimal/           # WiFi + health-check endpoint only
│   │   ├── main.py
│   │   ├── config.json.example
│   │   └── README.md
│   ├── gpio/              # Digital GPIO control over HTTP
│   │   ├── main.py
│   │   ├── gpio_handler.py
│   │   ├── config.json.example
│   │   └── README.md
│   ├── sensors/           # ADC + I2C + internal temp
│   │   ├── main.py
│   │   ├── sensor_handler.py
│   │   ├── config.json.example
│   │   └── README.md
│   ├── pwm/               # PWM output control
│   │   ├── main.py
│   │   ├── pwm_handler.py
│   │   ├── config.json.example
│   │   └── README.md
│   ├── neopixel/          # WS2812B LED control
│   │   ├── main.py
│   │   ├── neopixel_handler.py
│   │   ├── config.json.example
│   │   └── README.md
│   └── full/              # Everything combined (batteries-included)
│       ├── main.py
│       ├── gpio_api.py
│       ├── debuglog.py
│       ├── config.json.example
│       └── README.md
│
├── examples/              # Standalone scripts for `esp run`
│   ├── blink.py
│   ├── button_read.py
│   ├── adc_read.py
│   ├── pwm_fade.py
│   ├── i2c_scan.py
│   ├── wifi_scan.py
│   ├── internal_temp.py
│   └── deep_sleep.py
│
└── docs/
    ├── pin-reference.md   # ESP32 / C3 / S3 pin maps
    ├── wiring.md          # Common breadboard diagrams
    └── troubleshooting.md # FAQ and common issues
```

---

## Migration Map

Exactly where every current file ends up. Nothing is deleted until its replacement is verified.

| Current Path | Destination(s) | Action | Notes |
|---|---|---|---|
| `boot.py` | `core/boot.py` | Copy → clean up → verify → delete original | Remove any debug cruft; keep AP fallback logic intact |
| `main.py` | `templates/minimal/main.py` | Extract health-check routes (~50 lines) | Strip debuglog, gpio_api imports, feature flags |
| `main.py` | `templates/gpio/main.py` | New file importing `gpio_handler` | Uses cleaned-up HTML from minimal + GPIO panel |
| `main.py` | `templates/sensors/main.py` | New file importing `sensor_handler` | Status page + sensor readings |
| `main.py` | `templates/pwm/main.py` | New file importing `pwm_handler` | Status page + PWM controls |
| `main.py` | `templates/neopixel/main.py` | New file importing `neopixel_handler` | Status page + color API |
| `main.py` | `templates/full/main.py` | Copy current file as-is | Preserve all debug instrumentation |
| `gpio_api.py` | `templates/gpio/gpio_handler.py` | Extract digital GPIO subset | See decomposition plan below |
| `gpio_api.py` | `templates/sensors/sensor_handler.py` | Extract ADC + I2C + temp subset | See decomposition plan below |
| `gpio_api.py` | `templates/pwm/pwm_handler.py` | Extract PWM subset | See decomposition plan below |
| `gpio_api.py` | `templates/full/gpio_api.py` | Copy as-is | Unchanged; this is the "everything" template |
| `debuglog.py` | `templates/full/debuglog.py` | Copy as-is | Only the full template uses flash logging |
| `config.json.example` | `templates/*/config.json.example` | Split into per-template configs | Each template only includes its own keys |
| `config.json` | (stays gitignored) | No action | Users create from `.example` |
| `lib/microdot.py` | `core/lib/microdot.py` | Move (copy first) | Vendored, no changes |
| `lib/websocket.py` | `core/lib/websocket.py` | Move (copy first) | Vendored, no changes |
| `flake.nix` | `flake.nix` (in-place edit) | Modify | Add `esp init`, `esp templates`; generalize `esp sync` |
| `flake.lock` | `flake.lock` | No change | — |
| `.gitignore` | `.gitignore` | Expand | Add `config.json` patterns for template dirs |
| `CLAUDE.md` | `CLAUDE.md` | Rewrite | Becomes toolkit contributor guide |
| `ROADMAP.md` | `ROADMAP.md` | Replace | This document |

---

## gpio_api.py Decomposition Plan

The current `gpio_api.py` is 1,206 lines organized as a single `register_routes(app)` function containing all route definitions and helpers. This section maps every function to its destination.

### Shared Utilities

These helper functions are used by multiple templates. Each template that needs them will carry its own copy (inlined or in its handler file) rather than creating a shared utility module — this keeps templates self-contained per Design Principle #2.

| Function | Lines | Purpose | Destination |
|---|---|---|---|
| `_resolve_pin(pin_arg)` | L109–131 | Resolve pin number or string alias to int | `gpio_handler.py`, `pwm_handler.py`, `sensor_handler.py` (copy into each) |
| `_validate_digital_pin(pin_num)` | L134–145 | Check pin is in the valid digital set | `gpio_handler.py` only |
| `_check_forbidden_output(pin_num)` | L148–163 | Reject UART0 TX/RX pins for output use | `gpio_handler.py`, `pwm_handler.py` (copy into each) |
| `_pin_state(pin_num)` | L166–193 | Build a state dict from PIN_REGISTRY entry | `gpio_handler.py`, `pwm_handler.py` (copy into each, stripped to relevant modes) |
| `_check_memory()` | L196–202 | GC + low-memory warning | All handlers (copy into each) |

### Pin Set Constants

| Constant | Lines | Destination |
|---|---|---|
| `DIGITAL_PINS` | L62 | `gpio_handler.py`, `pwm_handler.py` |
| `ADC_PINS` | L65 | `sensor_handler.py` |
| `OUTPUT_PINS` | L68 | `gpio_handler.py`, `pwm_handler.py` |
| `INPUT_PINS` | L71 | `gpio_handler.py` |
| `FORBIDDEN_PINS` | L74 | `gpio_handler.py`, `pwm_handler.py` |
| `PIN_REGISTRY` | L79 | `gpio_handler.py`, `pwm_handler.py` (each has its own) |

### Route → Template Mapping

#### → `templates/gpio/gpio_handler.py`

Digital GPIO control: configure pin modes, read/write digital values, toggle outputs.

| Function | Lines | Route | Method |
|---|---|---|---|
| `gpio_capabilities` | L215–243 | `GET /api/gpio/capabilities` | Always registered |
| `gpio_temperature` | L246–251 | `GET /api/gpio/temperature` | Always registered |
| `gpio_pins` | L261–271 | `GET /api/gpio/pins` | Lists all configured pin states |
| `gpio_read` | L276–298 | `GET /api/gpio/<pin>` | Read a single pin's state |
| `gpio_set_mode` | L303–361 | `POST /api/gpio/<pin>/mode` | Configure IN/OUT mode |
| `gpio_set_value` | L366–398 | `POST /api/gpio/<pin>/value` | Set output HIGH/LOW |
| `gpio_toggle` | L403–428 | `POST /api/gpio/<pin>/toggle` | Toggle an output pin |

**Estimated size:** ~250 lines (helpers + routes + constants)

**Changes from original:**
- Remove feature flag checks (this template always has GPIO enabled)
- Remove conditional `from machine import Pin` — just import it at module level
- Remove the `_F_GPIO` guard — the entire file *is* the GPIO feature
- Keep `_pin_aliases` support from config
- Keep `gpio_capabilities` but simplify: only report digital pin info, remove ADC/PWM/I2C capability fields since those live in other templates
- Keep `gpio_temperature` — it's a one-liner and universally useful

#### → `templates/sensors/sensor_handler.py`

Analog-to-digital conversion, I2C bus scanning/communication, and internal temperature.

| Function | Lines | Route | Method |
|---|---|---|---|
| `gpio_temperature` | L246–251 | `GET /api/temperature` | Internal temp (renamed route) |
| `_init_adc` | L439–469 | (internal helper) | Lazy ADC initialization |
| `_read_adc` | L471–483 | (internal helper) | Take ADC reading |
| `adc_read_all` | L486–495 | `GET /api/adc/all` | Read all ADC-capable pins |
| `adc_config` | L498–536 | `POST /api/adc/<pin>/config` | Set ADC attenuation |
| `adc_read` | L539–555 | `GET /api/adc/<pin>` | Read single ADC pin |
| `_get_i2c` | L725–733 | (internal helper) | Lazy I2C bus init |
| `i2c_scan` | L736–750 | `GET /api/i2c/scan` | Scan I2C bus for devices |
| `i2c_read` | L753–785 | `POST /api/i2c/read` | Read bytes from I2C device |
| `i2c_write` | L788–821 | `POST /api/i2c/write` | Write bytes to I2C device |
| `i2c_write_read` | L824–868 | `POST /api/i2c/write_read` | Write-then-read transaction |
| `i2c_config` | L871–904 | `POST /api/i2c/config` | Reconfigure I2C bus pins/freq |

**Estimated size:** ~350 lines (ADC helpers + I2C helpers + routes + constants)

**Changes from original:**
- Remove all feature flag checks
- Import `ADC`, `SoftI2C` unconditionally at module level
- Rename `gpio_temperature` route from `/api/gpio/temperature` to `/api/temperature` (it's not GPIO-specific)
- Carry own copy of `_resolve_pin` (needed for ADC pin argument resolution)
- Carry own copy of `_check_memory`
- `_ATTEN_MAP`, `_ATTEN_REVERSE`, `_default_atten` move here from the module-level ADC section
- I2C default pins come from config (`i2c_sda`, `i2c_scl`, `i2c_freq`)

#### → `templates/pwm/pwm_handler.py`

Pulse-width modulation: start/stop PWM, adjust duty cycle and frequency.

| Function | Lines | Route | Method |
|---|---|---|---|
| `pwm_start` | L567–619 | `POST /api/pwm/<pin>/start` | Initialize PWM on a pin |
| `pwm_duty` | L622–648 | `POST /api/pwm/<pin>/duty` | Set duty cycle |
| `pwm_freq` | L651–677 | `POST /api/pwm/<pin>/freq` | Set frequency |
| `pwm_stop` | L680–699 | `POST /api/pwm/<pin>/stop` | Stop PWM and release pin |
| `pwm_read` | L702–714 | `GET /api/pwm/<pin>` | Read current PWM state |

**Estimated size:** ~200 lines (helpers + routes + constants)

**Changes from original:**
- Remove feature flag checks
- Import `PWM` unconditionally at module level
- Carry own copies of: `_resolve_pin`, `_check_forbidden_output`, `_pin_state` (PWM-mode branch only), `_check_memory`
- Own `PIN_REGISTRY` dict for tracking PWM-mode pins
- Own `OUTPUT_PINS`, `FORBIDDEN_PINS` constants

#### → `templates/neopixel/neopixel_handler.py` (new code)

NeoPixel / WS2812B LED control. This handler is **new** — the current `gpio_api.py` does not implement NeoPixel support. The code will be written from scratch using MicroPython's built-in `neopixel` module.

| Function | Route | Method | Purpose |
|---|---|---|---|
| `neopixel_status` | `GET /api/neopixel` | Read | Return current color (R, G, B) and LED count |
| `neopixel_set` | `POST /api/neopixel` | Write | Set all LEDs to `{"r": N, "g": N, "b": N}` |
| `neopixel_set_pixel` | `POST /api/neopixel/<index>` | Write | Set a single LED by index |
| `neopixel_clear` | `POST /api/neopixel/clear` | Write | Turn all LEDs off |
| `neopixel_fill` | `POST /api/neopixel/fill` | Write | Fill all LEDs with one color (alias for set) |

**Estimated size:** ~120 lines

#### → `templates/full/` (unchanged)

The "batteries-included" template preserves the current codebase as-is.

| Function | Lines | Stays In |
|---|---|---|
| `batch_read` | L916–947 | `templates/full/gpio_api.py` |
| `batch_write` | L950–996 | `templates/full/gpio_api.py` |
| `_build_stream_frame` | L1011–1052 | `templates/full/gpio_api.py` |
| `_handle_ws_command` | L1054–1170 | `templates/full/gpio_api.py` |
| `ws_stream` | L1174–1200 | `templates/full/gpio_api.py` |

These batch and WebSocket features are too advanced and RAM-heavy for single-purpose templates. They only make sense when all peripherals are loaded together with the full feature-flag system.

---

## Milestone 0 — Planning & Audit

**Description:** Inventory the existing codebase, map every function to its destination, and confirm the decomposition plan is sound. This milestone is the document you are reading — it is complete when the team agrees on the plan.

### Tasks

- [x] Read and understand every line of `gpio_api.py` (1,206 lines, 34 functions)
- [x] Read and understand `main.py` (270 lines, debug instrumentation, feature flag system)
- [x] Read and understand `boot.py` (45 lines, WiFi + AP fallback)
- [x] Read and understand `debuglog.py` (150 lines, ring-buffer flash logger)
- [x] Read and understand `config.json.example` (22 lines, feature flags + pin aliases)
- [x] Read and understand `flake.nix` (250 lines, esp CLI with 14 subcommands)
- [x] Map every function in `gpio_api.py` to a destination template handler
- [x] Identify shared utilities that must be copied into multiple handlers
- [x] Identify new code that must be written (neopixel handler, example scripts)
- [x] Define the target directory structure
- [x] Write the full migration map (current file → destination)
- [x] Write the `gpio_api.py` decomposition plan with line-number references
- [x] Define design principles and non-goals
- [x] Write this ROADMAP.md

### Files Touched

- `ROADMAP.md` — replaced entirely (this document)

### Dependencies

None — this is the starting point.

### Definition of Done

- [x] This ROADMAP.md exists and covers all 12 milestones
- [x] Every function in `gpio_api.py` has a named destination
- [x] Every current file has a migration path documented
- [x] Design principles and non-goals are written down
- [x] The team can read this document and execute any milestone independently (given its dependencies are met)

---

## Milestone 1 — Repository Restructure

**Description:** Create the directory skeleton and move shared files into `core/`. This is a pure file-organization change — no code is modified. The original files remain in place until Milestone 7 confirms the `full` template works as a drop-in replacement.

### Tasks

- [x] Create directory: `core/`
- [x] Create directory: `core/lib/`
- [x] Create directory: `templates/`
- [x] Create directory: `templates/minimal/`
- [x] Create directory: `templates/gpio/`
- [x] Create directory: `templates/sensors/`
- [x] Create directory: `templates/pwm/`
- [x] Create directory: `templates/neopixel/`
- [x] Create directory: `templates/full/`
- [x] Create directory: `examples/`
- [x] Create directory: `docs/`
- [x] Copy `boot.py` → `core/boot.py`
- [x] Clean up `core/boot.py`: remove any dead code, ensure it reads `config.json` from the working directory (not a hardcoded path), add a brief header comment explaining its role
- [x] Copy `lib/microdot.py` → `core/lib/microdot.py`
- [x] Copy `lib/websocket.py` → `core/lib/websocket.py`
- [ ] Verify `core/boot.py` runs correctly on hardware when manually copied with `esp push`
- [ ] Verify `core/lib/microdot.py` imports correctly on-device

### Files Created

- `core/boot.py`
- `core/lib/microdot.py`
- `core/lib/websocket.py`

### Files Touched

None modified — originals remain.

### Dependencies

- Milestone 0 (this plan must be finalized)

### Definition of Done

- [x] All 11 directories exist in the repo
- [ ] `core/boot.py` connects to WiFi (or starts AP) when pushed to a board and rebooted
- [ ] `core/lib/microdot.py` can be imported in a REPL session on the board without error
- [x] Original `boot.py`, `lib/microdot.py`, `lib/websocket.py` are still in place (not deleted yet)

---

## Milestone 2 — Create the `minimal` Template

**Description:** Build the simplest possible template: WiFi connect, Microdot server, one HTML dashboard page, one JSON health-check endpoint. No GPIO, no peripherals, no debug logging. This is the "hello world" of the toolkit — proof the board boots and serves HTTP. Target: ~50 lines for `main.py`.

### Tasks

- [x] Create `templates/minimal/main.py` with:
  - [x] Import `gc`, `time`, `network`, `ujson`
  - [x] Load `config.json` for `device_name` and `web_port`
  - [x] Import `Microdot` and `Response` from `lib.microdot`
  - [x] `GET /` route: inline HTML dashboard (device name, IP, uptime, free memory — dark terminal theme)
  - [x] `GET /api/status` route: JSON `{ device_name, ip, wifi_mode, rssi_dbm, wifi_quality, uptime_s, free_mem, free_mem_kb }`
  - [x] `app.run(port=config["web_port"])` at the bottom
  - [x] No `debuglog` import or fallback stubs
  - [x] No `gpio_api` import
  - [x] No feature flag parsing
  - [x] No `@app.before_request` GC handler (simplicity over optimization for the minimal template)
  - [x] Helper function `get_wifi_info()` returning `(ip, mode, rssi, quality)` — same logic as current `main.py` lines 126–137
  - [x] Helper function `_rssi_quality(rssi)` — same logic as current `main.py` lines 119–125
- [x] Create `templates/minimal/config.json.example`:
  ```json
  {
    "device_name": "ESP32-Dashboard",
    "wifi_ssid": "YOUR_SSID",
    "wifi_password": "YOUR_PASSWORD",
    "ap_ssid": "ESP32-Dashboard",
    "ap_password": "12345678",
    "web_port": 80
  }
  ```
- [x] Create `templates/minimal/README.md` with:
  - [x] One-line description of what this template does
  - [x] Prerequisites (Nix, board, USB cable)
  - [x] Setup steps (`esp init minimal`, edit config, `esp sync`)
  - [x] What you'll see in the browser (screenshot or description)
  - [x] API endpoint documentation (`GET /` and `GET /api/status`)
  - [x] Inline HTML description (dark theme, monospace, green text)
  - [x] How to extend it (pointer to other templates)
- [ ] Test on hardware:
  - [ ] Copy `core/boot.py`, `core/lib/microdot.py`, `templates/minimal/main.py`, and a filled-in `config.json` to the board
  - [ ] Verify the board boots, connects to WiFi, and serves the dashboard at `http://<ip>/`
  - [ ] Verify `curl http://<ip>/api/status` returns valid JSON
  - [ ] Verify free memory is ≥150 KB (minimal template should be very lightweight)

### Files Created

- `templates/minimal/main.py` (~50 lines)
- `templates/minimal/config.json.example`
- `templates/minimal/README.md`

### Dependencies

- Milestone 1 (need `core/boot.py` and `core/lib/microdot.py`)

### Definition of Done

- [x] `templates/minimal/main.py` is ≤60 lines
- [x] `config.json.example` has exactly 6 keys (no feature flags, no pin config)
- [ ] Board serves the HTML dashboard at `GET /`
- [ ] `GET /api/status` returns JSON with all 8 fields
- [ ] No import errors, no tracebacks in serial output
- [ ] Free memory after boot is ≥150 KB

---

## Milestone 3 — Create the `gpio` Template

**Description:** Extract digital GPIO control from `gpio_api.py` into a standalone handler. This template lets users toggle LEDs, read buttons, and configure pin modes over HTTP. No ADC, no PWM, no I2C, no WebSocket.

### Tasks

- [x] Create `templates/gpio/gpio_handler.py`:
  - [x] Copy utility functions from `gpio_api.py`:
    - `_resolve_pin` (L109–131) — include `_pin_aliases` loading from config
    - `_validate_digital_pin` (L134–145)
    - `_check_forbidden_output` (L148–163)
    - `_pin_state` (L166–193) — strip ADC and PWM branches; keep only IN/OUT
    - `_check_memory` (L196–202)
  - [x] Copy constants: `DIGITAL_PINS`, `OUTPUT_PINS`, `INPUT_PINS`, `FORBIDDEN_PINS`
  - [x] Create module-level `PIN_REGISTRY = {}`
  - [x] Import `from machine import Pin` at module level (unconditional)
  - [x] Import `esp32` at module level for temperature
  - [x] Create `register_routes(app, config)` function containing:
    - `gpio_capabilities` (L215–243) — simplified: remove ADC/PWM/I2C/batch/websocket fields; only report digital pins and GPIO-specific capabilities
    - `gpio_temperature` (L246–251) — unchanged
    - `gpio_pins` (L261–271) — unchanged
    - `gpio_read` (L276–298) — unchanged
    - `gpio_set_mode` (L303–361) — unchanged
    - `gpio_set_value` (L366–398) — unchanged
    - `gpio_toggle` (L403–428) — unchanged
  - [x] Remove all feature flag conditionals (`if _F_GPIO:` guards)
  - [x] Pass config as argument to `register_routes` instead of reading `config.json` inside the module
  - [x] Keep pin alias resolution from config
- [x] Create `templates/gpio/main.py`:
  - [x] Same base as `minimal/main.py` (config loading, Microdot app, status route, dashboard HTML)
  - [x] Import `from gpio_handler import register_routes`
  - [x] Call `register_routes(app, config)` before `app.run()`
  - [x] Add GPIO toggle panel to the inline HTML dashboard:
    - For each pin in `gpio_whitelist`, show pin number + toggle switch
    - Inline JS: fetch `GET /api/gpio/pins` every 1s, POST to `/api/gpio/<pin>/value` on toggle click
  - [x] Add `@app.before_request` GC handler (GPIO state tracking uses more memory)
- [x] Create `templates/gpio/config.json.example`:
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
- [x] Create `templates/gpio/README.md` with:
  - [x] What this template does
  - [x] Wiring guide (on-board LED GPIO 8, external LED on GPIO 2 with resistor)
  - [x] Setup steps
  - [x] Full API endpoint documentation with `curl` examples for every route
  - [x] Pin safety notes (UART pins, strapping pins)
- [ ] Test on hardware:
  - [ ] Configure GPIO 8 (on-board LED) as OUT, set value 1 — LED turns on
  - [ ] Toggle GPIO 8 — LED turns off
  - [ ] Read GPIO 9 (BOOT button) — returns 1 when not pressed, 0 when pressed
  - [ ] Verify `GET /api/gpio/capabilities` returns correct pin lists
  - [ ] Verify `GET /api/gpio/pins` returns all configured pins
  - [ ] Verify attempting to write UART pin 21 returns 403
  - [ ] Verify free memory ≥120 KB

### Files Created

- `templates/gpio/gpio_handler.py` (~250 lines)
- `templates/gpio/main.py` (~100 lines)
- `templates/gpio/config.json.example`
- `templates/gpio/README.md`

### Dependencies

- Milestone 1 (core files)
- Milestone 2 (minimal template establishes the `main.py` pattern)

### Definition of Done

- [ ] All 7 GPIO routes respond correctly
- [ ] On-board LED (GPIO 8) can be toggled from `curl`
- [ ] BOOT button (GPIO 9) state can be read from `curl`
- [ ] Pin whitelist enforcement works (rejected pin returns error)
- [ ] UART pin protection works (GPIO 20/21 return 403)
- [x] No feature flag code exists in `gpio_handler.py`
- [ ] Free memory ≥120 KB after boot

---

## Milestone 4 — Create the `sensors` Template

**Description:** Extract analog sensing (ADC) and I2C bus communication from `gpio_api.py` into a sensor-focused handler. Also includes internal temperature. This template is for reading physical world data — light levels, potentiometer positions, temperature sensors, I2C peripherals.

### Tasks

- [x] Create `templates/sensors/sensor_handler.py`:
  - [x] Copy utility functions:
    - `_resolve_pin` (L109–131)
    - `_check_memory` (L196–202)
  - [x] Copy ADC constants: `ADC_PINS`
  - [x] Copy ADC infrastructure:
    - `_ATTEN_MAP`, `_ATTEN_REVERSE`, `_default_atten` setup (L96–108)
    - `_init_adc` (L439–469)
    - `_read_adc` (L471–483)
  - [x] Copy I2C infrastructure:
    - Module-level `_i2c = None`
    - `_get_i2c` (L725–733)
  - [x] Import at module level: `from machine import Pin, ADC, SoftI2C` and `import esp32`
  - [x] Create `register_routes(app, config)` containing:
    - `GET /api/temperature` — internal temp (renamed from `/api/gpio/temperature`)
    - `GET /api/adc/all` (L486–495) — read all ADC pins
    - `POST /api/adc/<pin>/config` (L498–536) — set attenuation
    - `GET /api/adc/<pin>` (L539–555) — read single ADC pin
    - `GET /api/i2c/scan` (L736–750) — scan I2C bus
    - `POST /api/i2c/read` (L753–785) — read from I2C device
    - `POST /api/i2c/write` (L788–821) — write to I2C device
    - `POST /api/i2c/write_read` (L824–868) — write-then-read transaction
    - `POST /api/i2c/config` (L871–904) — reconfigure I2C bus
  - [x] Remove all feature flag conditionals
  - [x] Read I2C pin defaults from config parameter
  - [x] Read ADC attenuation default from config parameter
- [x] Create `templates/sensors/main.py`:
  - [x] Same base as minimal template
  - [x] Import and register sensor routes
  - [x] Dashboard HTML: status panel + live ADC gauge (progress bar updating every 1s) + I2C device list
- [x] Create `templates/sensors/config.json.example`:
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
- [x] Create `templates/sensors/README.md` with:
  - [x] What this template does
  - [x] Wiring guide (potentiometer on GPIO 4, I2C device on GPIO 6/7)
  - [x] ADC attenuation explanation table (0dB, 2.5dB, 6dB, 11dB → voltage ranges)
  - [x] Full API docs with `curl` examples
  - [x] Common I2C addresses table (0x3C = OLED, 0x27 = LCD, 0x68 = MPU6050, etc.)
- [ ] Test on hardware:
  - [ ] Read ADC pin 4 — returns raw value and voltage
  - [ ] Change attenuation on pin 4 — voltage reading changes accordingly
  - [ ] Read internal temperature — returns reasonable °C value
  - [ ] Scan I2C bus — returns empty list (or discovered devices if connected)
  - [ ] Verify free memory ≥120 KB

### Files Created

- `templates/sensors/sensor_handler.py` (~350 lines)
- `templates/sensors/main.py` (~80 lines)
- `templates/sensors/config.json.example`
- `templates/sensors/README.md`

### Dependencies

- Milestone 1 (core files)
- Milestone 2 (main.py pattern)

### Definition of Done

- [ ] `GET /api/temperature` returns `{"temp_c": <number>}`
- [ ] `GET /api/adc/<pin>` returns raw, voltage_uv, voltage_v for ADC-capable pins
- [ ] `GET /api/adc/all` returns readings for all 5 ADC pins (0–4)
- [ ] `POST /api/adc/<pin>/config` successfully changes attenuation
- [ ] `GET /api/i2c/scan` returns device list (even if empty)
- [ ] I2C read/write/write_read endpoints respond correctly
- [ ] Non-ADC pins return appropriate error messages
- [x] No feature flag code exists in `sensor_handler.py`
- [ ] Free memory ≥120 KB after boot

---

## Milestone 5 — Create the `pwm` Template

**Description:** Extract PWM (pulse-width modulation) control from `gpio_api.py`. This template controls LED brightness, servo motors, buzzers — anything that needs a variable-duty-cycle signal. Clean, focused: just PWM start, stop, duty, frequency, and read.

### Tasks

- [x] Create `templates/pwm/pwm_handler.py`:
  - [x] Copy utility functions:
    - `_resolve_pin` (L109–131)
    - `_check_forbidden_output` (L148–163)
    - `_check_memory` (L196–202)
    - `_pin_state` (L166–193) — keep only the PWM branch
  - [x] Copy constants: `OUTPUT_PINS`, `FORBIDDEN_PINS`
  - [x] Create module-level `PIN_REGISTRY = {}`
  - [x] Import: `from machine import Pin, PWM`
  - [x] Create `register_routes(app, config)` containing:
    - `POST /api/pwm/<pin>/start` (L567–619) — initialize PWM
    - `POST /api/pwm/<pin>/duty` (L622–648) — set duty cycle
    - `POST /api/pwm/<pin>/freq` (L651–677) — set frequency
    - `POST /api/pwm/<pin>/stop` (L680–699) — stop and release
    - `GET /api/pwm/<pin>` (L702–714) — read current state
  - [x] Remove all feature flag conditionals
  - [x] Validate `freq` range (1–40,000,000) and `duty_u16` range (0–65535) in each route
- [x] Create `templates/pwm/main.py`:
  - [x] Same base as minimal template
  - [x] Import and register PWM routes
  - [x] Dashboard HTML: status panel + PWM slider (range input, 0–100%, sends duty on `input` event)
  - [x] Debounce slider input in JS (max 5 requests/sec)
- [x] Create `templates/pwm/config.json.example`:
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
- [x] Create `templates/pwm/README.md` with:
  - [x] What this template does
  - [x] PWM basics: frequency, duty cycle, duty_u16 vs percentage
  - [x] Wiring guide (LED with resistor on GPIO 5)
  - [x] Full API docs with `curl` examples for every route
  - [x] Common use cases: LED dimming, servo control (50 Hz, 1–2 ms pulse)
- [ ] Test on hardware:
  - [ ] Start PWM on GPIO 5 at 1 kHz, 50% duty — LED at half brightness
  - [ ] Change duty to 100% — LED at full brightness
  - [ ] Change duty to 0% — LED off
  - [ ] Change frequency to 50 Hz — visible flicker (expected for LED, correct for servo)
  - [ ] Stop PWM — pin released, LED off
  - [ ] Read PWM state — returns freq, duty_u16, duty_pct
  - [ ] Verify free memory ≥130 KB

### Files Created

- `templates/pwm/pwm_handler.py` (~200 lines)
- `templates/pwm/main.py` (~80 lines)
- `templates/pwm/config.json.example`
- `templates/pwm/README.md`

### Dependencies

- Milestone 1 (core files)
- Milestone 2 (main.py pattern)

### Definition of Done

- [ ] All 5 PWM routes respond correctly
- [ ] LED brightness visually changes with duty cycle adjustment
- [ ] PWM stop releases the pin cleanly
- [ ] Forbidden pins (20, 21) are rejected
- [ ] Invalid freq/duty values return descriptive errors
- [x] No feature flag code exists in `pwm_handler.py`
- [ ] Free memory ≥130 KB after boot

---

## Milestone 6 — Create the `neopixel` Template

**Description:** New template (not extracted from `gpio_api.py` — NeoPixel was never implemented). Provides HTTP API control of WS2812B addressable RGB LEDs using MicroPython's built-in `neopixel` module. Includes a color picker in the dashboard.

### Tasks

- [x] Create `templates/neopixel/neopixel_handler.py` from scratch:
  - [x] Import `neopixel` and `from machine import Pin`
  - [x] Module-level `_np = None` (lazily initialized NeoPixel instance)
  - [x] Module-level `_current_color = (0, 0, 0)` (track last-set color)
  - [x] Helper `_init_np(pin, count)` — create `neopixel.NeoPixel(Pin(pin), count)`
  - [x] Helper `_validate_rgb(r, g, b)` — check 0–255 range
  - [x] Create `register_routes(app, config)` containing:
    - `GET /api/neopixel` — return `{"pin": N, "count": N, "color": {"r": N, "g": N, "b": N}}`
    - `POST /api/neopixel` — body `{"r": 255, "g": 0, "b": 128}` → set all LEDs, return `{"ok": true, ...}`
    - `POST /api/neopixel/<index>` — set a single LED by index
    - `POST /api/neopixel/clear` — turn all LEDs off (shorthand for r=0, g=0, b=0)
  - [x] Read NeoPixel pin and LED count from config
  - [x] Return descriptive errors for invalid color values, out-of-range index, init failure
- [x] Create `templates/neopixel/main.py`:
  - [x] Same base as minimal template
  - [x] Import and register NeoPixel routes
  - [x] Dashboard HTML: status panel + RGB color picker
  - [x] Color picker implementation: three range sliders (R, G, B: 0–255) + color preview swatch + "Set" button + "Off" button
  - [x] Alternatively: `<input type="color">` element that extracts R, G, B from the hex value
  - [x] JS sends POST on button click (not on every slider move — NeoPixel writes are slow)
- [x] Create `templates/neopixel/config.json.example`:
  ```json
  {
    "device_name": "ESP32-NeoPixel",
    "wifi_ssid": "YOUR_SSID",
    "wifi_password": "YOUR_PASSWORD",
    "ap_ssid": "ESP32-NeoPixel",
    "ap_password": "12345678",
    "web_port": 80,
    "neopixel_pin": 10,
    "neopixel_count": 1
  }
  ```
- [x] Create `templates/neopixel/README.md` with:
  - [x] What this template does
  - [x] NeoPixel wiring guide (data line on GPIO 10, VCC to 3.3V, GND to GND)
  - [x] Power considerations (each LED draws up to 60mA at full white — external power for >8 LEDs)
  - [x] Full API docs with `curl` examples
  - [x] Multi-LED addressing explanation
  - [x] Note: WS2812B timing is strict; avoid running `esp repl` during NeoPixel writes
- [ ] Test on hardware:
  - [ ] Set color to red `{"r": 255, "g": 0, "b": 0}` — LED turns red
  - [ ] Set color to green — LED turns green
  - [ ] Set color to blue — LED turns blue
  - [ ] Clear — LED turns off
  - [ ] Read status — returns current color
  - [ ] If multi-LED chain: set individual pixel by index
  - [ ] Verify free memory ≥140 KB (NeoPixel is very lightweight)

### Files Created

- `templates/neopixel/neopixel_handler.py` (~120 lines, written from scratch)
- `templates/neopixel/main.py` (~80 lines)
- `templates/neopixel/config.json.example`
- `templates/neopixel/README.md`

### Dependencies

- Milestone 1 (core files)
- Milestone 2 (main.py pattern)
- No dependency on `gpio_api.py` — this is new code

### Definition of Done

- [ ] `POST /api/neopixel {"r":255,"g":0,"b":0}` turns LED red
- [ ] `GET /api/neopixel` returns current color state
- [ ] `POST /api/neopixel/clear` turns LED off
- [x] Invalid RGB values (e.g., 300, -1, "hello") return descriptive errors
- [x] Config supports different pin numbers and LED counts
- [ ] Dashboard color picker works in browser
- [ ] Free memory ≥140 KB after boot

---

## Milestone 7 — Create the `full` Template

**Description:** Copy the current working project (main.py + gpio_api.py + debuglog.py) into `templates/full/` as-is. This is the "batteries-included" template that preserves 100% of existing functionality including batch operations, WebSocket streaming, debug logging, and all feature flags. Zero code changes — just a file copy and a README.

### Tasks

- [x] Copy `gpio_api.py` → `templates/full/gpio_api.py` (verbatim)
- [x] Copy `debuglog.py` → `templates/full/debuglog.py` (verbatim)
- [x] Copy `main.py` → `templates/full/main.py` (verbatim)
- [x] Copy `config.json.example` → `templates/full/config.json.example` (verbatim)
- [ ] Verify the full template works by:
  - [ ] Pushing `core/boot.py` + `core/lib/*` + `templates/full/*` + a valid `config.json` to the board
  - [ ] Confirming all endpoints respond (status, GPIO, ADC, PWM, I2C, batch, WebSocket)
  - [ ] This is the critical verification — if this works, we can safely delete the root-level originals later
- [x] Create `templates/full/README.md` with:
  - [x] What this template does (everything — all peripherals, all protocols)
  - [x] Memory warning: enabling all features may leave <80 KB free on ESP32-C3
  - [x] Feature flag documentation (explain each flag in `config.json`)
  - [x] Complete API reference (all routes from all feature groups)
  - [x] WebSocket streaming documentation
  - [x] Debug log access (`GET /api/debug/log`, `esp log`)
  - [x] Known limitations (RAM pressure with all features enabled)

### Files Created

- `templates/full/main.py` (copy of current `main.py`)
- `templates/full/gpio_api.py` (copy of current `gpio_api.py`)
- `templates/full/debuglog.py` (copy of current `debuglog.py`)
- `templates/full/config.json.example` (copy of current `config.json.example`)
- `templates/full/README.md` (new)

### Dependencies

- Milestone 1 (core files must exist — `core/boot.py` and `core/lib/` must be verified working)

### Definition of Done

- [x] `templates/full/` contains exact copies of current `main.py`, `gpio_api.py`, `debuglog.py`, `config.json.example`
- [ ] Board boots and serves all endpoints when running from `core/` + `templates/full/` files
- [ ] WebSocket streaming works (`websocat ws://<ip>/ws/stream`)
- [ ] Debug log is accessible via `GET /api/debug/log`
- [ ] Batch read/write endpoints work
- [ ] **This milestone proves the new directory structure is a valid replacement for the old flat layout**

---

## Milestone 8 — Create Example Scripts

**Description:** Write 8 standalone MicroPython scripts, each demonstrating a single hardware concept. Every script is fully self-contained (no project imports), includes a docstring with wiring instructions, and runs directly with `esp run examples/<name>.py`. These are learning tools for people who want to understand the hardware before picking a template.

### Tasks

- [x] Create `examples/blink.py`:
  - [x] Toggle on-board LED (GPIO 8) on/off every 500 ms
  - [x] Docstring: no wiring needed, uses on-board LED
  - [x] Use `machine.Pin` and `time.sleep`
  - [x] Print each toggle to serial: "LED ON" / "LED OFF"
  - [x] Run for 20 cycles (10 seconds) then stop

- [x] Create `examples/button_read.py`:
  - [x] Read BOOT button (GPIO 9) state in a loop
  - [x] Docstring: no wiring needed, uses on-board BOOT button
  - [x] Configure as input with pull-up
  - [x] Print state changes: "PRESSED" / "RELEASED"
  - [x] Run for 30 seconds then stop

- [x] Create `examples/adc_read.py`:
  - [x] Read ADC on GPIO 4 every second
  - [x] Docstring: connect potentiometer wiper to GPIO 4, ends to 3.3V and GND
  - [x] Print raw value (0–65535), voltage (0–3.3V)
  - [x] Use 11dB attenuation for full range
  - [x] Run for 30 seconds then stop

- [x] Create `examples/pwm_fade.py`:
  - [x] Fade LED brightness up and down using PWM on GPIO 5
  - [x] Docstring: connect LED + 330Ω resistor between GPIO 5 and GND
  - [x] Ramp duty from 0% to 100% in 2 seconds, then back down
  - [x] Use 1 kHz frequency
  - [x] Run 3 full cycles then stop and deinit PWM

- [x] Create `examples/i2c_scan.py`:
  - [x] Scan I2C bus and report discovered devices
  - [x] Docstring: connect I2C device, SDA to GPIO 6, SCL to GPIO 7
  - [x] Use `machine.SoftI2C`
  - [x] Print each discovered address in hex
  - [x] Include a lookup table for common addresses (0x3C = OLED, 0x27 = LCD, 0x68 = MPU6050, 0x76 = BME280, 0x48 = ADS1115, 0x50 = EEPROM)
  - [x] Run once and exit

- [x] Create `examples/wifi_scan.py`:
  - [x] Scan for nearby WiFi networks
  - [x] Docstring: no wiring needed
  - [x] Use `network.WLAN(network.STA_IF).scan()`
  - [x] Print SSID, channel, RSSI, security type for each network
  - [x] Sort by signal strength (RSSI descending)
  - [x] Run once and exit

- [x] Create `examples/internal_temp.py`:
  - [x] Read ESP32 internal temperature sensor every 2 seconds
  - [x] Docstring: no wiring needed, uses on-chip sensor
  - [x] Use `esp32.mcu_temperature()` (returns Celsius)
  - [x] Print temperature with timestamp
  - [x] Run for 20 seconds then stop

- [x] Create `examples/deep_sleep.py`:
  - [x] Enter deep sleep for 5 seconds, then wake and print wake reason
  - [x] Docstring: board will disconnect from serial during sleep — reconnect after 5s
  - [x] Print "Going to sleep for 5 seconds..." then call `machine.deepsleep(5000)`
  - [x] On wake: print "Woke up!" and the wake reason from `machine.reset_cause()`
  - [x] Include a table mapping reset cause constants to human names

- [ ] Test each script on hardware:
  - [ ] `esp run examples/blink.py` — LED blinks
  - [ ] `esp run examples/button_read.py` — serial shows press/release
  - [ ] `esp run examples/adc_read.py` — serial shows voltage readings
  - [ ] `esp run examples/pwm_fade.py` — LED fades in and out
  - [ ] `esp run examples/i2c_scan.py` — serial shows scan results
  - [ ] `esp run examples/wifi_scan.py` — serial shows nearby networks
  - [ ] `esp run examples/internal_temp.py` — serial shows temperature
  - [ ] `esp run examples/deep_sleep.py` — board sleeps and wakes

### Files Created

- `examples/blink.py` (~20 lines)
- `examples/button_read.py` (~25 lines)
- `examples/adc_read.py` (~25 lines)
- `examples/pwm_fade.py` (~30 lines)
- `examples/i2c_scan.py` (~35 lines)
- `examples/wifi_scan.py` (~30 lines)
- `examples/internal_temp.py` (~20 lines)
- `examples/deep_sleep.py` (~25 lines)

### Dependencies

- Milestone 1 (directory exists)
- No code dependencies — examples are self-contained
- Hardware dependency: board must have MicroPython flashed

### Definition of Done

- [ ] All 8 scripts run successfully with `esp run examples/<name>.py`
- [x] Each script has a docstring explaining purpose, wiring, and expected output
- [x] Each script is self-contained (no `from lib import ...`, no `import gpio_handler`, etc.)
- [x] Each script terminates on its own (no infinite loops unless explicitly bounded)
- [x] Each script prints human-readable output to serial console

---

## Milestone 9 — Generalize the `esp` CLI

**Description:** Update the `esp` helper script in `flake.nix` to support the template system. Add `esp init <template>` (copy core + template files to working directory), `esp templates` (list available templates), and generalize `esp sync` to auto-detect which files to push instead of using a hardcoded list. Move API-specific CLI commands (gpio, adc, i2c, stream) out of the core CLI.

### Tasks

#### New commands

- [x] Add `esp init <template>` command:
- [x] Validate template name exists in `templates/` directory
- [x] Determine the project root by finding the directory containing `flake.nix`
- [x] Copy all files from `core/` to the project root (preserving directory structure): `boot.py`, `lib/microdot.py`, `lib/websocket.py`
- [x] Copy all files from `templates/<name>/` to the project root (flat — template files go into root, not into a `templates/` subdirectory)
- [x] If `config.json.example` was copied and no `config.json` exists, print a reminder: "Edit config.json before syncing"
- [x] If any destination file already exists, warn and ask before overwriting (or use a `--force` flag)
- [x] Print a summary of files copied and next steps

- [x] Add `esp templates` command:
- [x] Scan `templates/` directory for subdirectories
- [x] For each template, read the first line of its `README.md` (the `# Title` line) as a description
- [x] Print a formatted table: name, description
  - [ ] Example output:
    ```
    Available templates:
      minimal     WiFi + health-check endpoint only
      gpio        Digital GPIO control over HTTP
      sensors     ADC + I2C + internal temperature
      pwm         PWM output control
      neopixel    WS2812B LED control
      full        Everything combined (batteries-included)
    ```

#### Modify `esp sync`

- [x] Replace the hardcoded file list (`boot.py main.py config.json gpio_api.py debuglog.py lib/microdot.py lib/websocket.py`) with dynamic detection:
- [x] Always sync: `boot.py`, `main.py`, `config.json` (if they exist in the working directory)
- [x] Auto-detect `lib/` directory: if it exists, sync all `.py` files in it
- [x] Auto-detect handler files: glob for `*_handler.py` and `*_api.py` in the working directory
- [x] Auto-detect `debuglog.py` if present
- [x] Print the list of files being synced before pushing
- [x] Create `lib/` directory on device if any lib files are being pushed
- [x] Alternative simpler approach: sync **all** `.py` and `.json` files in the project root + `lib/` directory, excluding `flake.*`, `CLAUDE.md`, `ROADMAP.md`, and dotfiles. This is more robust and requires zero configuration.

#### Demote API-specific commands

- [x] Remove `esp gpio` from the core CLI (move to a note in `templates/gpio/README.md` showing equivalent `curl` commands)
- [x] Remove `esp adc` from the core CLI (move to `templates/sensors/README.md`)
- [x] Remove `esp i2c` from the core CLI (move to `templates/sensors/README.md`)
- [x] Remove `esp stream` from the core CLI (move to `templates/full/README.md`)
- [x] Update the usage line: `esp {detect|erase|flash|monitor|repl|sync|push|run|ls|log|init|templates}`
- [x] Keep `esp gpio`, `esp adc`, `esp i2c`, `esp stream` as hidden commands (still work if invoked, but not listed in usage) — this avoids breaking existing users during transition. They print a deprecation notice pointing to the template README.

#### Other cleanup

- [x] Update `flake.nix` description from "ESP32 MicroPython development environment" to "ESP32 MicroPython quickstart toolkit"
- [x] Update shell hook message to mention `esp templates` and `esp init`
- [x] Keep all existing non-API commands unchanged: `detect`, `erase`, `flash`, `monitor`, `repl`, `push`, `run`, `ls`, `log`

### Files Touched

- `flake.nix` — significant modifications to the `esp-helper` script

### Dependencies

- Milestone 1 (directory structure must exist)
- Milestone 2–7 (templates must exist for `esp init` and `esp templates` to work)
- Can be developed in parallel with templates if the directory structure is set up

### Definition of Done

- [x] `esp templates` lists all 6 templates with descriptions
- [x] `esp init minimal` copies `boot.py`, `lib/microdot.py`, `lib/websocket.py`, `main.py`, `config.json.example` to the project root
- [x] `esp init gpio` copies all gpio template files + core files
- [x] `esp init nonexistent` prints an error listing valid template names
- [x] `esp sync` auto-detects files to push (no hardcoded list)
- [x] `esp sync` prints the file list before pushing
- [x] `esp gpio 8` still works but prints a deprecation notice
- [x] `esp` (no args) shows the updated usage line including `init` and `templates`
- [x] Existing commands (`detect`, `erase`, `flash`, `monitor`, `repl`, `push`, `run`, `ls`, `log`) all still work unchanged

---

## Milestone 10 — Documentation

**Description:** Write all user-facing documentation. The README.md is the front door of the project — it must communicate what this is, who it's for, and how to get started in under 30 seconds of reading. Supporting docs cover pin references, wiring diagrams, and troubleshooting.

### Tasks

#### README.md (project root)

- [x] Write `README.md` with the following sections:
  - [x] **Title and one-line description:** "ESP32 MicroPython Quickstart Toolkit — plug in a board, pick a template, ship in 2 minutes"
  - [x] **What is this?** — 2-paragraph explanation
  - [x] **Quickstart** — numbered steps:
    1. `git clone` + `cd`
    2. `nix develop`
    3. Plug in board, `esp detect`
    4. `esp erase && esp flash` (first time only)
    5. `esp init minimal`
    6. Edit `config.json`
    7. `esp sync`
    8. Open `http://<ip>/` in browser
  - [x] **Available Templates** — table with name, description, use case, API endpoints
  - [x] **Example Scripts** — table with script name and what it demonstrates
  - [x] **ESP CLI Reference** — table of all commands with one-line descriptions
  - [x] **Supported Boards** — ESP32, ESP32-C3 (tested), ESP32-S2/S3 (planned)
  - [x] **Project Structure** — tree diagram
  - [x] **Contributing** — pointer to `CLAUDE.md`
  - [x] **License** — TBD

#### CLAUDE.md (rewrite)

- [x] Rewrite `CLAUDE.md` as a toolkit contributor guide:
  - [x] Project overview (toolkit, not dashboard)
  - [x] Development environment (Nix, entering dev shell)
  - [x] How to add a new template (step-by-step)
  - [x] How to add a new example script
  - [x] Template anatomy (what files, what conventions)
  - [x] Handler module pattern (`register_routes(app, config)`)
  - [x] Config conventions (minimal keys, no nesting, descriptive names)
  - [x] Testing checklist (hardware verification for each template)
  - [x] Memory budget guidelines
  - [x] Pin safety rules

#### docs/pin-reference.md

- [x] Write pin reference tables:
  - [x] ESP32 (original): all GPIOs, ADC1/ADC2, touch, DAC, strapping pins, flash pins
  - [x] ESP32-C3: all GPIOs (0–21), ADC1 (0–4), no ADC2/touch/DAC, strapping pins, UART0 pins
  - [x] ESP32-S3 (placeholder): note that support is coming in Milestone 11
  - [x] For each board: table columns = GPIO#, ADC, PWM, I2C default, Notes (strapping, UART, flash)
  - [x] Pin safety summary: which pins to never touch, which are safe after boot

#### docs/wiring.md

- [x] Write wiring guides with ASCII diagrams:
  - [x] LED output (GPIO → 330Ω → LED → GND)
  - [x] Button input (GPIO → button → GND, enable internal pull-up)
  - [x] Potentiometer (wiper → GPIO, ends → 3.3V and GND)
  - [x] NeoPixel (DIN → GPIO, VCC → 3.3V, GND → GND)
  - [x] I2C device (SDA → GPIO, SCL → GPIO, VCC → 3.3V, GND → GND)
  - [x] Multiple components on one breadboard (comprehensive wiring for the `full` template)

#### docs/troubleshooting.md

- [x] Write FAQ / troubleshooting:
  - [x] "No serial device found" → check USB cable (data vs. charge-only), check drivers
  - [x] "Board not responding" → try `esp erase && esp flash`
  - [x] "WiFi won't connect" → check SSID/password, check 2.4 GHz (ESP32 doesn't do 5 GHz)
  - [x] "Import error for microdot" → ensure `lib/` directory exists on board, re-run `esp sync`
  - [x] "MemoryError" → which template are you using? Try `minimal`. Run `gc.collect()`. Reduce inline HTML size.
  - [x] "OSError: [Errno 2]" → config.json missing, copy from .example
  - [x] "ADC reads 0 or 65535 constantly" → check wiring, check attenuation setting
  - [x] "I2C scan returns empty list" → check SDA/SCL wiring, check pull-up resistors, verify device power
  - [x] "NeoPixel not lighting up" → check data pin direction, check VCC (needs 3.3V minimum), check GND connection
  - [x] "PWM no visible effect" → check wiring, check duty cycle (0 = off, 65535 = full on), try lower frequency to see flicker
  - [x] "Board keeps rebooting" → check `esp log` for crash info, could be OOM or bad wiring on a strapping pin
  - [x] "Permission denied on /dev/ttyUSB0" → add user to `dialout` group (Linux), or check System Preferences → Security (macOS)
  - [x] Port override: `export ESP_PORT=/dev/cu.usbmodem14101`

#### Template READMEs

- [x] Verify each template's `README.md` was created in its milestone (Milestones 2–7)
- [x] Ensure consistent format across all template READMEs:
  1. Title
  2. What this template does (1–2 sentences)
  3. Files included
  4. Setup steps
  5. API Reference (table of routes)
  6. curl examples
  7. Wiring (if applicable)
  8. Next steps / how to extend

### Files Created

- `README.md` (project root)
- `docs/pin-reference.md`
- `docs/wiring.md`
- `docs/troubleshooting.md`

### Files Touched

- `CLAUDE.md` — rewritten

### Dependencies

- Milestone 2–7 (all templates must exist so we can document them accurately)
- Milestone 8 (examples must exist)
- Milestone 9 (CLI must be finalized)

### Definition of Done

- [x] `README.md` quickstart can be followed by a new user from zero to working dashboard
- [x] `docs/pin-reference.md` has complete pin tables for ESP32 and ESP32-C3
- [x] `docs/wiring.md` has ASCII diagrams for all common circuits
- [x] `docs/troubleshooting.md` covers the 12 most common issues
- [x] `CLAUDE.md` accurately reflects the toolkit (not the old dashboard project)
- [x] All 6 template READMEs exist and follow the same format

---

## Milestone 11 — Multi-Board Support

**Description:** Extend the toolkit to support ESP32-S2 and ESP32-S3 boards in addition to the existing ESP32 and ESP32-C3. This means pinning firmware images, updating chip detection, and documenting board-specific pin differences. Templates themselves should work across boards without modification (the pin numbers change but the APIs are the same).

### Tasks

#### Firmware

- [x] Find the MicroPython v1.23.0 firmware URL for ESP32-S2 generic
- [x] Add `firmware.esp32s2` to the `firmware` attrset in `flake.nix` with pinned hash
- [x] Find the MicroPython v1.23.0 firmware URL for ESP32-S3 generic
- [x] Add `firmware.esp32s3` to the `firmware` attrset in `flake.nix` with pinned hash
- [x] Update `firmware_for_chip` function to handle `esp32s2` and `esp32s3`
- [x] Update `flash_offset_for_chip` function (S2 and S3 use offset `0x1000` like original ESP32)

#### Chip Detection

- [x] Update `detect_chip` function in esp CLI:
- [x] Add `ESP32-S2` detection (grep for "ESP32-S2" in esptool output)
- [x] Add `ESP32-S3` detection (grep for "ESP32-S3" in esptool output)
- [ ] Test detection with each board variant (need hardware access or documented test procedure)

#### Documentation

- [x] Add ESP32-S2 pin table to `docs/pin-reference.md`:
- [x] GPIOs, ADC channels, touch pins, DAC, strapping pins
- [x] Note: S2 has no Bluetooth at all
- [x] Add ESP32-S3 pin table to `docs/pin-reference.md`:
- [x] GPIOs, ADC channels, touch pins, strapping pins
- [x] Note: S3 has BLE 5.0 + WiFi 6
- [ ] Add board-specific notes to each template README where relevant:
- [ ] ADC pin numbers differ between ESP32 (many ADC pins) and C3 (only 0–4)
- [ ] On-board LED pin varies: GPIO 2 (many ESP32 boards), GPIO 8 (most C3 boards), varies for S2/S3
- [ ] BOOT button pin: GPIO 0 (ESP32), GPIO 9 (C3), varies for S2/S3
- [x] Update `README.md` supported boards section

#### Template Compatibility

- [x] Review each handler's hardcoded pin sets:
- [x] `gpio_handler.py` `DIGITAL_PINS` — currently ESP32-C3 specific
- [x] `sensor_handler.py` `ADC_PINS` — currently `{0,1,2,3,4}` (C3 only)
- [x] Consider making pin sets config-driven or auto-detected
- [x] Evaluate approach: hardcoded pin sets per board (simple, explicit) vs. config-driven (flexible, more work)
- [x] Decision: keep hardcoded sets for v1.0 but add a `"board"` key to config that selects the correct set. Default to `"esp32c3"`.
- [ ] Add `"board": "esp32c3"` to each template's `config.json.example`

### Files Touched

- `flake.nix` — add firmware URLs, update chip detection
- `docs/pin-reference.md` — add S2 and S3 tables
- `README.md` — update supported boards
- Template `config.json.example` files — add `"board"` key
- Template handler files — add board-aware pin set selection

### Dependencies

- Milestone 9 (CLI must be stable before adding more chip variants)
- Milestone 10 (docs must exist before adding board-specific sections)

### Definition of Done

- [x] `esp detect` correctly identifies ESP32, ESP32-C3, ESP32-S2, and ESP32-S3
- [x] `esp flash` uses the correct firmware for each detected chip
- [x] `docs/pin-reference.md` has pin tables for all 4 board variants
- [ ] `esp init minimal && esp sync` works on an ESP32-S3 (or S2) board
- [ ] Templates degrade gracefully on boards with different pin capabilities (descriptive error if a configured pin doesn't exist on the detected board)

---

## Milestone 12 — Polish & Release

**Description:** Final cleanup, verification, and release. Remove orphaned files from the repository root, update `.gitignore`, run through every template on hardware one final time, tag v0.1.0.

### Tasks

#### Cleanup

- [ ] Delete orphaned root-level files (only after Milestone 7 confirms `templates/full/` works):
- [ ] Delete root `main.py` (replaced by templates)
- [ ] Delete root `gpio_api.py` (replaced by template handlers)
- [ ] Delete root `debuglog.py` (moved to `templates/full/`)
- [ ] Delete root `config.json.example` (replaced by per-template examples)
- [ ] Delete root `lib/microdot.py` (moved to `core/lib/`)
- [ ] Delete root `lib/websocket.py` (moved to `core/lib/`)
- [ ] Delete root `lib/` directory (if empty after above)
- [ ] Keep root `boot.py` only if `esp init` copies `core/boot.py` there; otherwise delete
- [x] Verify no broken references after deletion (grep for old import paths)
- [x] Verify `flake.nix` doesn't reference any deleted files

#### .gitignore update

- [x] Expand `.gitignore`:
  ```
  # Runtime config (contains WiFi credentials)
  config.json
  
  # Nix
  .direnv
  result
  
  # MicroPython
  debug.log
  
  # Python
  __pycache__/
  *.pyc
  
  # Editor
  .vscode/
  .idea/
  *.swp
  *~
  
  # OS
  .DS_Store
  Thumbs.db
  ```

#### Final verification

- [ ] Run through the full quickstart path from `git clone` to working dashboard (on a clean machine if possible)
- [ ] Test each template individually on hardware:
  - [ ] `esp init minimal && esp sync` → dashboard works
  - [ ] `esp init gpio && esp sync` → GPIO toggle works
  - [ ] `esp init sensors && esp sync` → ADC reads work
  - [ ] `esp init pwm && esp sync` → LED fading works
  - [ ] `esp init neopixel && esp sync` → LED color changes work
  - [ ] `esp init full && esp sync` → all endpoints work
- [ ] Test each example script with `esp run`
- [ ] Verify `esp templates` output is accurate and well-formatted
- [ ] Verify no `config.json` files are committed to the repo

#### Release

- [x] Create `CHANGELOG.md`:
- [x] v0.1.0 release notes
- [x] Summary of the transformation from single-purpose dashboard to toolkit
- [x] List of templates with brief descriptions
- [x] List of example scripts
- [x] List of supported boards
- [x] Breaking changes from the old layout (if anyone was using the raw repo)
- [ ] Final commit: "restructure: transform dashboard project into quickstart toolkit"
- [ ] Tag `v0.1.0`
- [ ] Verify the repo looks good on GitHub (README renders, directory structure is clean)

### Files Created

- `CHANGELOG.md`

### Files Deleted

- `main.py` (root)
- `gpio_api.py` (root)
- `debuglog.py` (root)
- `config.json.example` (root)
- `lib/microdot.py` (root)
- `lib/websocket.py` (root)
- `lib/` (root directory)
- `boot.py` (root — if replaced by `core/boot.py` via `esp init`)

### Dependencies

- All previous milestones (1–11) must be complete
- Hardware access for final verification

### Definition of Done

- [ ] Repository root contains only: `CLAUDE.md`, `README.md`, `ROADMAP.md`, `CHANGELOG.md`, `flake.nix`, `flake.lock`, `.gitignore`, and the 4 directories (`core/`, `templates/`, `examples/`, `docs/`)
- [ ] No orphaned files from the old layout remain
- [ ] All templates work on hardware
- [ ] All example scripts work on hardware
- [ ] `v0.1.0` tag exists
- [x] A new user can follow the README and have a working board in <2 minutes

---

## Milestone 13 — Meshtastic Firmware Support

**Description:** Extend the toolkit to flash Meshtastic firmware (LoRa mesh networking) in
addition to MicroPython. This adds `esp mesh` subcommands for listing boards, flashing firmware,
and basic configuration. The same Nix dev shell and `esptool` are reused — no additional
toolchain installation needed.

Meshtastic firmware is distributed as architecture-specific ZIP archives on GitHub, each containing
board-specific `.factory.bin` files (e.g., `firmware-heltec-v3-2.5.x.factory.bin`), OTA binaries,
LittleFS images, and metadata JSON with partition offsets. The flash process writes three binaries
at three different offsets, driven by the metadata.

### Background

| Concept | Detail |
|---|---|
| **Firmware source** | GitHub releases: `meshtastic/firmware` |
| **Archive format** | `firmware-{arch}-{version}.zip` (one ZIP per chip architecture) |
| **ZIP contents** | `firmware-{board}-{ver}.factory.bin`, `mt-{mcu}-ota.bin`, `littlefs-{board}-{ver}.bin`, `firmware-{board}-{ver}.mt.json` |
| **Flash offsets** | Factory at `0x00`, OTA offset from `.mt.json`, LittleFS offset from `.mt.json` |
| **Post-flash config** | Meshtastic app (BLE), `meshtastic` Python CLI, or web UI at `meshtastic.local` |

### Tasks

#### Nix Firmware Pinning

- [ ] Choose a stable Meshtastic firmware release version to pin (check https://meshtastic.org/downloads/)
- [ ] Add `meshtastic-firmware` attribute set to `flake.nix` with `pkgs.fetchzip` entries:
  - [ ] `meshtastic-firmware.esp32` — `firmware-esp32-{version}.zip`
  - [ ] `meshtastic-firmware.esp32s3` — `firmware-esp32s3-{version}.zip`
  - [ ] `meshtastic-firmware.esp32c3` — `firmware-esp32c3-{version}.zip`
  - [ ] `meshtastic-firmware.esp32c6` — `firmware-esp32c6-{version}.zip`
- [ ] Use `fetchzip` with `stripRoot = false` (firmware ZIPs have flat directory layout)
- [ ] Add `meshtastic` Python package to `buildInputs` (for post-flash configuration via serial/BLE)
- [ ] Set shell variable `MESHTASTIC_FW_VERSION` for display in `esp mesh info`

#### CLI Commands — `esp mesh` subcommand group

- [ ] Add `cmd_mesh_boards` function:
  - [ ] Auto-detect chip with existing `detect_chip` function
  - [ ] Select the correct firmware directory for the detected architecture
  - [ ] List all `firmware-*-*.factory.bin` files, extracting board names
  - [ ] Pretty-print board names with architecture info
- [ ] Add `cmd_mesh_flash` function:
  - [ ] Accept `<board>` argument (e.g., `heltec-v3`, `tbeam-s3-core`)
  - [ ] Auto-detect chip and select firmware directory
  - [ ] Locate `firmware-{board}-{ver}.factory.bin` in the firmware directory
  - [ ] Read `firmware-{board}-{ver}.mt.json` for OTA and SPIFFS offsets
  - [ ] Locate `mt-{mcu}-ota.bin` (unified OTA binary per MCU)
  - [ ] Locate `littlefs-{board}-{ver}.bin`
  - [ ] Validate all three files exist before starting
  - [ ] Run: `esptool erase_flash`
  - [ ] Run: `esptool write_flash 0x00 {factory.bin}`
  - [ ] Run: `esptool write_flash {ota_offset} {ota.bin}`
  - [ ] Run: `esptool write_flash {spiffs_offset} {littlefs.bin}`
  - [ ] Print success message with next steps (configure via app or CLI)
- [ ] Add `cmd_mesh_info` function:
  - [ ] Print pinned Meshtastic firmware version
  - [ ] Print supported architectures
  - [ ] Print path to firmware directory (for advanced users)
- [ ] Add `cmd_mesh_config` function:
  - [ ] Wrapper around `meshtastic` Python CLI
  - [ ] Auto-detect port
  - [ ] Pass through any additional arguments to `meshtastic` CLI
  - [ ] Example: `esp mesh config --set lora.region US`
- [ ] Add `mesh)` case to main dispatch in `esp` CLI:
  - [ ] Route `esp mesh boards` → `cmd_mesh_boards`
  - [ ] Route `esp mesh flash <board>` → `cmd_mesh_flash`
  - [ ] Route `esp mesh info` → `cmd_mesh_info`
  - [ ] Route `esp mesh config [args...]` → `cmd_mesh_config`
- [ ] Update `esp` usage line to include `mesh` subcommand

#### Safety & UX

- [ ] Add warning before `esp mesh flash` that this will overwrite MicroPython (or any existing firmware)
- [ ] Add antenna warning: "Do NOT power on a Meshtastic device without an antenna attached!"
- [ ] Validate board name against available firmware files; suggest closest match on typo
- [ ] Handle case where detected chip doesn't match board's expected chip (e.g., trying to flash `heltec-v3` on an ESP32-C3)

#### Documentation

- [ ] Add `docs/meshtastic.md`:
  - [ ] What is Meshtastic and why it's supported
  - [ ] Quick start: flash + configure
  - [ ] Board selection guide (how to identify your board)
  - [ ] Common configuration examples (region, channel, etc.)
  - [ ] Switching between MicroPython and Meshtastic on the same board
  - [ ] Updating to a newer Meshtastic firmware version (changing the pin in flake.nix)
  - [ ] Troubleshooting: flash failures, boot loops, antenna warnings
- [ ] Update `CLAUDE.md` with Meshtastic section (CLI commands, board table, design rationale)
- [ ] Update `README.md` to mention Meshtastic support
- [ ] Update dev shell banner to mention `esp mesh` commands

#### Testing

- [ ] Test `esp mesh boards` shows correct board list for detected architecture
- [ ] Test `esp mesh flash <board>` succeeds on at least one ESP32-S3 board (e.g., Heltec V3)
- [ ] Test `esp mesh info` displays correct version
- [ ] Test `esp mesh config --info` passes through to meshtastic CLI correctly
- [ ] Test re-flashing MicroPython after Meshtastic (verify `esp erase && esp flash` still works)
- [ ] Test error handling: wrong board name, missing firmware, chip mismatch

### Files Touched

- `flake.nix` — add Meshtastic firmware pinning, `meshtastic` Python package, `esp mesh` CLI commands
- `CLAUDE.md` — add Meshtastic section
- `README.md` — mention Meshtastic support

### Files Created

- `docs/meshtastic.md` — Meshtastic-specific documentation

### Dependencies

- Milestone 9 (CLI must be stable — `detect_port`, `detect_chip`, `erase` must work)
- Milestone 11 (multi-board chip detection must support S2/S3/C3/C6)
- Independent of all template milestones (M2–M8) — Meshtastic doesn't use MicroPython templates

### Definition of Done

- [ ] `esp mesh boards` lists available boards for the detected chip
- [ ] `esp mesh flash heltec-v3` (or another board) successfully flashes all 3 partitions
- [ ] `esp mesh info` shows pinned firmware version
- [ ] `esp mesh config --info` displays device info after flashing
- [ ] `docs/meshtastic.md` exists and covers quick start + board selection
- [ ] Re-flashing MicroPython after Meshtastic works (`esp erase && esp flash`)
- [ ] Dev shell banner mentions Meshtastic support

---

## Dependency Graph

```
Milestone 0 (Planning)
    │
    ▼
Milestone 1 (Restructure)
    │
    ├──────────┬───────────┬───────────┬──────────────┐
    ▼          ▼           ▼           ▼              ▼
  M2         M3          M4          M5             M7
(minimal)  (gpio)     (sensors)    (pwm)          (full)
    │          │           │           │              │
    │          ▼           ▼           ▼              │
    │        (depends on M2 for main.py pattern)     │
    │                                                 │
    ├──────────┐                                      │
    ▼          ▼                                      │
  M6         M8                                      │
(neopixel) (examples)                                │
    │          │                                      │
    ▼          ▼                                      ▼
    └──────────┴──────────────────────────────────────┘
                           │
                           ▼
                    Milestone 9 (CLI)
                           │
                     ┌─────┴─────┐
                     ▼           ▼
              Milestone 10   Milestone 13
              (Docs)         (Meshtastic)
                     │           │
                     ▼           │
              Milestone 11      │
              (Multi-Board)     │
                     │           │
                     ▼           ▼
                    Milestone 12 (Release)
```

**Parallelizable work:**

- Milestones 3, 4, 5, 6 can all be developed in parallel (they share the pattern from M2 but don't depend on each other)
- Milestone 7 only depends on Milestone 1 (it's a copy of existing files)
- Milestone 8 only depends on Milestone 1 (examples are self-contained)
- Milestones 3–8 can all proceed in parallel once M1 and M2 are done

**Critical path:** M0 → M1 → M2 → M9 → M10 → M11 → M12

**Independent tracks:** Milestone 13 (Meshtastic) can proceed in parallel with Milestones 10–11 once M9 is complete. It only requires stable CLI infrastructure and multi-chip detection.

**Estimated effort:** Each template milestone (M2–M7) is approximately 2–4 hours of implementation and testing. M8 (examples) is ~3 hours. M9 (CLI) is ~4 hours. M10 (docs) is ~6 hours. M11 (multi-board) depends on hardware availability. M12 (release) is ~2 hours.

---

*Last updated: project planning phase. This document replaces the previous GPIO API roadmap.*