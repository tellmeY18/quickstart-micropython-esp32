# ROADMAP.md — GPIO & Peripheral API Suite

This document is the implementation plan for extending the ESP-32 MicroPython project with a full hardware-control API layer. Every meaningful peripheral on the board — digital GPIO, analog-to-digital conversion, pulse-width modulation, I2C bus communication, internal temperature sensing — will be exposed over a REST HTTP API and a WebSocket channel for real-time bidirectional streaming.

No frontend code will be built. The board is the server. You talk to it with `curl`, `websocat`, a Python script, or any HTTP/WebSocket client.

---

## Table of Contents

- [Goals and Non-Goals](#goals-and-non-goals)
- [What Exists Today](#what-exists-today)
- [What We Are Building](#what-we-are-building)
- [ESP32-C3 Hardware Reference](#esp32-c3-hardware-reference)
- [Architecture](#architecture)
- [New and Modified Files](#new-and-modified-files)
- [API Surface Overview](#api-surface-overview)
- [Milestone 1 — Foundation](#milestone-1--foundation)
- [Milestone 2 — Digital GPIO](#milestone-2--digital-gpio)
- [Milestone 3 — Analog Input (ADC)](#milestone-3--analog-input-adc)
- [Milestone 4 — PWM Output](#milestone-4--pwm-output)
- [Milestone 5 — I2C Bus](#milestone-5--i2c-bus)
- [Milestone 6 — Batch Operations](#milestone-6--batch-operations)
- [Milestone 7 — WebSocket Real-Time Stream](#milestone-7--websocket-real-time-stream)
- [Milestone 8 — Tooling Updates](#milestone-8--tooling-updates)
- [Milestone 9 — Hardening and Safety](#milestone-9--hardening-and-safety)
- [Design Principles](#design-principles)
- [Error Handling Convention](#error-handling-convention)
- [Memory Budget](#memory-budget)
- [Verification Strategy](#verification-strategy)

---

## Goals and Non-Goals

**Goals:**

- Expose every usable peripheral of the ESP32-C3 over HTTP and WebSocket
- Make every endpoint stateless and independently testable with `curl`
- Support real-time streaming of pin states and ADC readings via WebSocket
- Keep the existing health-check dashboard (`GET /` and `GET /api/status`) fully intact and unchanged
- Extend the `esp` CLI and Nix flake with convenience subcommands for the new API
- Maintain the zero-external-dependency, no-cloud, local-network-only philosophy

**Non-Goals:**

- No frontend, no dashboard UI, no HTML pages for GPIO control
- No Bluetooth (MicroPython's BLE support on C3 is unstable)
- No persistent pin state across reboots (MicroPython has no standard NVS API)
- No authentication (this is a trusted local network tool, not an internet-facing service)
- No SPI bus support in this phase (I2C covers the most common sensor use cases)
- No capacitive touch (the ESP32-C3 does not have touch-sensing hardware)

---

## What Exists Today

The board currently runs four files. `boot.py` handles WiFi connection with AP fallback. `main.py` runs a Microdot async web server serving an inline HTML dashboard at `GET /` and a JSON health-check at `GET /api/status`. `config.json` holds WiFi credentials and device settings. `lib/microdot.py` is the vendored Microdot web framework.

The Nix flake provides `esptool`, `mpremote`, `picocom`, `python3`, `pyserial`, and the custom `esp` CLI. The `esp sync` command pushes exactly those four files to the board.

The existing `GET /api/status` endpoint returns device name, IP address, WiFi mode, uptime, and free memory. There is no hardware control of any kind — no GPIO reads, no pin configuration, no analog input, no bus access.

---

## What We Are Building

A complete peripheral API layer implemented in a single new file (`gpio_api.py`) that is imported by `main.py` and registers all new routes onto the existing Microdot app. A second vendored file (`lib/websocket.py`) enables the Microdot WebSocket extension for real-time streaming.

The API will support:

- **Digital GPIO** — configure any valid pin as input or output, read its value, set its value, toggle it
- **ADC (analog-to-digital)** — read calibrated voltage from any ADC-capable pin, configure attenuation
- **PWM (pulse-width modulation)** — start, stop, and adjust frequency and duty cycle on any output-capable pin
- **I2C bus** — scan for devices, read bytes, write bytes, do register-style write-then-read operations, reconfigure bus pins and frequency
- **Internal temperature** — read the ESP32-C3's on-die temperature sensor
- **Batch operations** — read or write multiple pins in a single HTTP round-trip
- **WebSocket stream** — push live snapshots of pin states, ADC readings, and temperature at a configurable interval, and accept commands over the same socket

---

## ESP32-C3 Hardware Reference

This section exists so that every implementation decision in the milestones below can be traced back to a concrete hardware constraint. The ESP32-C3 is a RISC-V chip, not Xtensa. Its peripheral set differs from the classic ESP32 in important ways.

### Pin Map

| GPIO | Input | Output | ADC       | PWM | Default Function | Notes |
|------|-------|--------|-----------|-----|------------------|-------|
| 0    | yes   | yes    | ADC1-CH0  | yes | —                | Strapping pin — do not pull low at boot |
| 1    | yes   | yes    | ADC1-CH1  | yes | —                | |
| 2    | yes   | yes    | ADC1-CH2  | yes | —                | Strapping pin — must be high at boot |
| 3    | yes   | yes    | ADC1-CH3  | yes | —                | |
| 4    | yes   | yes    | ADC1-CH4  | yes | —                | |
| 5    | yes   | yes    | —         | yes | SPI SS           | |
| 6    | yes   | yes    | —         | yes | SPI MISO         | |
| 7    | yes   | yes    | —         | yes | SPI MOSI         | |
| 8    | yes   | yes    | —         | yes | I2C SDA          | Onboard RGB LED on some boards |
| 9    | yes   | yes    | —         | yes | I2C SCL          | BOOT button on most boards |
| 10   | yes   | yes    | —         | yes | SPI SCK          | |
| 18   | yes   | yes    | —         | yes | USB D-           | Only on boards with native USB |
| 19   | yes   | yes    | —         | yes | USB D+           | Only on boards with native USB |
| 20   | yes   | **no** | —         | no  | UART0 RX (REPL)  | Input only — never drive this |
| 21   | **no**| yes    | —         | no  | UART0 TX (REPL)  | Do not repurpose — REPL output |

### Critical Constraints

- **ADC is only available on GPIO 0 through 4.** These are all ADC block 1. The ESP32-C3 has no ADC block 2, which means there is no conflict with WiFi (unlike the classic ESP32 where ADC2 is disabled while WiFi is active). All five ADC pins are safe to read concurrently with WiFi running.

- **There is no DAC.** The ESP32-C3 has no digital-to-analog converter. Analog output must be simulated with PWM.

- **There is no capacitive touch hardware.** No touch-sensing API surface is needed.

- **Internal temperature uses `esp32.mcu_temperature()`.** The classic ESP32's `esp32.raw_temperature()` does not exist on C3. The C3 function returns degrees Celsius directly.

- **PWM is available on all output-capable pins** through the LED PWM controller. Frequency range is 1 Hz to 40 MHz with up to 13-bit duty resolution at typical frequencies.

- **I2C default pins are SDA=GPIO8, SCL=GPIO9.** These can be remapped to any output-capable pin in software using `machine.SoftI2C`.

- **GPIO 20 and 21 are the REPL UART.** GPIO 20 is RX (input only) and GPIO 21 is TX. Driving these as outputs would destroy the serial REPL. The API must refuse any attempt to configure these as outputs.

- **GPIO 0 and 2 are strapping pins.** They must be in specific states at boot for the chip to start correctly. They are safe to use after boot, but the API should document this caveat.

---

## Architecture

### Transport Strategy

Two transports serve different use cases:

**HTTP REST** handles all stateless, one-shot operations — read a pin, set a value, scan I2C, query capabilities, read temperature. Every request is independent. Every response is JSON. You can test everything with `curl`. This is the primary interface.

**WebSocket** (`ws://`) handles continuous, low-latency streaming. A client connects to `/ws/stream` and receives a JSON frame at a configurable interval containing the current state of monitored pins, ADC readings, and temperature. The client can also send JSON commands over the same socket to set pins or change the stream configuration without making separate HTTP calls. This is the interface for real-time monitoring tools, data loggers, and automation scripts.

### Module Responsibility

All hardware interaction lives in `gpio_api.py`. This module exports a single function `register_routes(app)` that takes the Microdot app instance from `main.py` and attaches every new route to it. The module maintains two internal data structures:

**PIN_REGISTRY** — a dictionary mapping GPIO numbers to their current mode (IN, OUT, PWM, ADC) and the live `machine.Pin`, `machine.PWM`, or `machine.ADC` object. Pins are initialized lazily on first access and cached here. This avoids constructing hardware objects for peripherals the caller never uses, keeps boot time fast, and prevents conflicting objects on the same pin.

**STREAM_CONFIG** — holds the list of pins currently being streamed over WebSocket and the polling interval in milliseconds. Clients can change this at runtime through the WebSocket command channel.

### Mode Exclusivity

A pin can only be in one mode at a time. If GPIO 5 is currently in PWM mode and someone tries to configure it as a digital input, the API must refuse with a 409 Conflict response. The caller must first stop the PWM via the PWM stop endpoint, which releases the pin and removes it from the registry, before reconfiguring it. This prevents the silent corruption that would occur if two `machine` objects held the same physical pin simultaneously.

### Lazy Initialization

No hardware objects are created at import time or at server startup. The first API call that targets a specific pin creates the corresponding `machine.Pin`, `machine.ADC`, or `machine.PWM` object and caches it in PIN_REGISTRY. Subsequent calls reuse the cached object. This keeps memory usage proportional to the number of pins actually in use, not the total number of available pins.

---

## New and Modified Files

### New Files

| File | Lives On | Purpose |
|------|----------|---------|
| `gpio_api.py` | Board + Repo | All GPIO, ADC, PWM, I2C, temperature route handlers and WebSocket broadcaster |
| `lib/websocket.py` | Board + Repo | Vendored Microdot WebSocket extension from `github.com/miguelgrinberg/microdot` |
| `ROADMAP.md` | Repo only | This file |

### Modified Files

| File | What Changes |
|------|-------------|
| `main.py` | Add two lines: import `register_routes` from `gpio_api` and call it with the `app` instance before `app.run()` |
| `config.json.example` | Add `pin_aliases` and `adc_atten` keys with example values |
| `flake.nix` | Extend `esp sync` file list to include `gpio_api.py` and `lib/websocket.py`. Add `curl`, `jq`, and `websocat` to dev shell `buildInputs`. Add new `esp` subcommands (`gpio`, `adc`, `stream`, `i2c`) |

### Unchanged Files

`boot.py`, `lib/microdot.py`, `flake.lock`, `slides.md`, `CLAUDE.md`, `.gitignore` — none of these are touched.

---

## API Surface Overview

Every response is `application/json`. Every error response uses the same envelope: a JSON object with an `"error"` key containing a human-readable string. HTTP status codes are used correctly (200, 400, 403, 404, 409, 500).

### System Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/gpio/pins` | Full pin map — every pin, its current mode, direction, and value |
| GET | `/api/gpio/capabilities` | Static chip info — valid GPIO set, ADC pins, PWM pins, constraints |
| GET | `/api/gpio/temperature` | Internal MCU temperature in degrees Celsius |

### Digital GPIO Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/gpio/<pin>` | Read current mode and value of a single pin |
| POST | `/api/gpio/<pin>/mode` | Configure pin as IN or OUT with optional pull-up/pull-down |
| POST | `/api/gpio/<pin>/value` | Set digital output (pin must be in OUT mode) |
| POST | `/api/gpio/<pin>/toggle` | Flip current output state |

### ADC Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/adc/<pin>` | Single ADC sample — raw 12-bit value and calibrated voltage |
| GET | `/api/adc/all` | Read all five ADC-capable pins in one call |
| POST | `/api/adc/<pin>/config` | Change attenuation on a specific pin |

### PWM Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/pwm/<pin>/start` | Start PWM with given frequency and duty cycle |
| POST | `/api/pwm/<pin>/duty` | Update duty cycle without stopping the signal |
| POST | `/api/pwm/<pin>/freq` | Update frequency without stopping the signal |
| POST | `/api/pwm/<pin>/stop` | Stop PWM and release pin back to neutral state |
| GET | `/api/pwm/<pin>` | Get current PWM parameters |

### I2C Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/i2c/scan` | Scan bus and return list of detected device addresses |
| POST | `/api/i2c/read` | Read N bytes from a device at a 7-bit address |
| POST | `/api/i2c/write` | Write bytes to a device |
| POST | `/api/i2c/write_read` | Write then read (register-read pattern) |
| POST | `/api/i2c/config` | Reconfigure bus pins and clock frequency |

### Batch Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/gpio/batch/read` | Read multiple pins in a single request |
| POST | `/api/gpio/batch/write` | Set multiple output pins in a single request |

### WebSocket Endpoint

| Protocol | Path | Purpose |
|----------|------|---------|
| WS | `/ws/stream` | Bidirectional real-time channel — server pushes state frames, client sends commands |

---

## Milestone 1 — Foundation

**Goal:** Get the new file structure in place. Vendor the WebSocket extension. Extend the `esp sync` command. Confirm the board boots cleanly with the new files present but no new routes active yet.

**Why this is first:** Everything else depends on these files existing on the board and being importable without errors. If the import fails or the sync is broken, nothing in later milestones works. Solving deployment first means you can iterate fast on everything that follows.

### Tasks

- [x] **1.1 — Vendor `lib/websocket.py`**
  Download the Microdot WebSocket extension from `github.com/miguelgrinberg/microdot/blob/main/src/microdot/websocket.py`. Place it at `lib/websocket.py` in the repo alongside `lib/microdot.py`. This file must be the version compatible with the `microdot.py` already vendored in the project — same major version, same import structure.

- [x] **1.2 — Create `gpio_api.py` skeleton**
  Create `gpio_api.py` at the project root (same level as `main.py`). It should contain the pin set constants (`DIGITAL_PINS`, `ADC_PINS`, `OUTPUT_PINS`, `INPUT_PINS`, `FORBIDDEN_PINS`), empty `PIN_REGISTRY` and `STREAM_CONFIG` dictionaries, a `register_routes(app)` function that does nothing yet, and a print statement so you can confirm the import happened on the serial console.

- [x] **1.3 — Modify `main.py` to import `gpio_api`**
  Add the import of `register_routes` from `gpio_api` and call `register_routes(app)` right before the `app.run()` call. This is a two-line change. The existing dashboard and status routes must continue to work exactly as before.

- [x] **1.4 — Update `esp sync` in `flake.nix`**
  Extend the `files` array in the `cmd_sync` function to include `gpio_api.py` and `lib/websocket.py`. The sync command must now push six files instead of four: `boot.py`, `main.py`, `config.json`, `gpio_api.py`, `lib/microdot.py`, `lib/websocket.py`.

- [ ] **1.5 — Deploy and verify**
  Run `esp sync`. Watch `esp monitor` for boot output. Confirm there are no import errors. Confirm the existing `GET /api/status` still returns valid JSON. Confirm `esp ls` shows all six files on the board. Confirm `esp ls lib/` shows both `microdot.py` and `websocket.py`.

### Verification

```
esp sync
esp monitor           # no tracebacks on boot
curl http://<ip>/api/status | jq   # existing endpoint still works
esp ls                # six files visible
esp ls lib/           # microdot.py and websocket.py both present
```

### Definition of Done

The board boots without errors. The existing dashboard and API are unaffected. The new files are on the board's filesystem. `gpio_api.register_routes` is being called on startup. Nothing is broken.

---

## Milestone 2 — Digital GPIO

**Goal:** Full CRUD control over digital pins. Configure any valid pin as input or output, read its value, set it, toggle it. Implement the system endpoints (pin map, capabilities, temperature) as well.

**Why this is second:** Digital GPIO is the most fundamental peripheral. Every other feature (ADC, PWM) builds on top of the pin abstraction. The system endpoints (`/capabilities`, `/pins`, `/temperature`) are also trivial to implement here and immediately useful for verifying the API is alive.

### Tasks

- [x] **2.1 — Implement pin resolution helper**
  Write an internal function `_resolve_pin(pin_arg)` that accepts either an integer GPIO number or a string alias from `config.json`'s `pin_aliases` map. If the argument is a string that matches an alias, resolve it to the integer. If it is a raw integer, validate that it is in `DIGITAL_PINS`. Return the integer or raise a descriptive error. This function is used by every endpoint that takes a `<pin>` URL parameter.

- [x] **2.2 — Implement `GET /api/gpio/capabilities`**
  Return a static JSON object describing the chip's hardware. This includes the set of all valid GPIO numbers, which of those support ADC, which support PWM, the fact that there is no DAC, the UART pins that are forbidden, and the I2C default pins. This endpoint takes no arguments and never changes. It is the first thing a client calls to understand what the board can do.

- [x] **2.3 — Implement `GET /api/gpio/temperature`**
  Call `esp32.mcu_temperature()` and return the result as `{"temp_c": <float>}`. This is a one-liner endpoint and a useful smoke test that the module is working.

- [x] **2.4 — Implement `POST /api/gpio/<pin>/mode`**
  Accept a JSON body with `"mode"` (either `"IN"` or `"OUT"`) and an optional `"pull"` field (`"up"`, `"down"`, or `null`). Validate that the pin is in `DIGITAL_PINS` and not in `FORBIDDEN_PINS`. If the pin is already in `PIN_REGISTRY` under a different mode (e.g., PWM or ADC), return 409 Conflict — the caller must release it first. Create a `machine.Pin` object with the specified direction and pull configuration, store it in `PIN_REGISTRY`, and return the new pin state.

- [x] **2.5 — Implement `GET /api/gpio/<pin>`**
  Look up the pin in `PIN_REGISTRY`. If it is not there, return 404 with a message that the pin has not been configured yet. If it is there, return its mode and current `.value()`. For PWM pins, also return frequency and duty. For ADC pins, return the last reading.

- [x] **2.6 — Implement `POST /api/gpio/<pin>/value`**
  Accept `{"value": 0}` or `{"value": 1}`. The pin must be in `PIN_REGISTRY` with mode `"OUT"`. If the pin is not configured, return 400. If it is configured as input, return 400 with a message saying you cannot write to an input pin. Call `.value(v)` on the cached `machine.Pin` object and return the new state.

- [x] **2.7 — Implement `POST /api/gpio/<pin>/toggle`**
  The pin must be in OUT mode. Read its current `.value()`, flip it (XOR with 1), write it back, and return the new state. No request body is needed.

- [x] **2.8 — Implement `GET /api/gpio/pins`**
  Iterate `PIN_REGISTRY` and build a JSON object showing every configured pin's number, mode, and current value. Also include the `pin_aliases` map from config so the client knows which names map to which numbers. Pins that have never been configured do not appear here — this is not a list of all possible pins (that is what `/capabilities` is for), but a snapshot of what is currently active.

- [x] **2.9 — Guard FORBIDDEN_PINS**
  Any request targeting GPIO 20 or 21 for output configuration must return HTTP 403 with a clear error message explaining these are the REPL UART pins. GPIO 20 may be read as an input (it is RX), but GPIO 21 must be refused entirely. Test this explicitly.

### Verification

```
# Read capabilities
curl http://<ip>/api/gpio/capabilities | jq

# Read temperature
curl http://<ip>/api/gpio/temperature | jq

# Configure GPIO5 as output
curl -X POST http://<ip>/api/gpio/5/mode \
  -H 'Content-Type: application/json' -d '{"mode":"OUT"}'

# Set it high
curl -X POST http://<ip>/api/gpio/5/value \
  -H 'Content-Type: application/json' -d '{"value":1}'

# Read it back
curl http://<ip>/api/gpio/5 | jq

# Toggle it
curl -X POST http://<ip>/api/gpio/5/toggle | jq

# View all active pins
curl http://<ip>/api/gpio/pins | jq

# Attempt forbidden pin — must get 403
curl -X POST http://<ip>/api/gpio/21/mode \
  -H 'Content-Type: application/json' -d '{"mode":"OUT"}'
```

### Definition of Done

You can configure any valid pin as input or output, read its value, set it, and toggle it through HTTP. Invalid pins and forbidden pins are rejected with proper error codes and messages. The temperature endpoint returns a plausible Celsius value. The capabilities endpoint accurately describes the ESP32-C3 pin map.

---

## Milestone 3 — Analog Input (ADC)

**Goal:** Read calibrated analog voltages from GPIO 0 through 4. Configure per-pin attenuation. Read all ADC pins in a single call.

**Why this is third:** ADC is the next most common use case after digital GPIO. Sensor projects almost always need to read an analog voltage. This milestone is self-contained — it does not depend on PWM or I2C.

### Understanding ADC on MicroPython

MicroPython's `machine.ADC` on ESP32-C3 provides two key methods. `read_uv()` returns a calibrated reading in microvolts, which accounts for the non-linearity of the ADC hardware. `read_u16()` returns a raw 16-bit value (0–65535) but is not calibrated. The API should prefer `read_uv()` for accuracy and derive the human-readable voltage by dividing by 1,000,000.

Attenuation controls the input voltage range. `ADC.ATTN_0DB` reads 0 to ~1.0 V. `ADC.ATTN_2_5DB` reads 0 to ~1.34 V. `ADC.ATTN_6DB` reads 0 to ~2.0 V. `ADC.ATTN_11DB` reads 0 to ~3.6 V (covering the full 3.3 V GPIO rail). The default should be 11 dB so that typical sensor circuits just work out of the box.

### Tasks

- [x] **3.1 — Implement ADC pin validation**
  Create a helper that checks whether a given GPIO number is in the `ADC_PINS` set (0, 1, 2, 3, 4). If someone tries to read ADC on GPIO 5, return 400 with a message saying that pin does not have ADC capability.

- [x] **3.2 — Implement ADC mode conflict check**
  If a pin is already in `PIN_REGISTRY` as a digital OUT or PWM pin, return 409 Conflict. The caller must release the pin first. ADC and digital output cannot coexist on the same physical pin.

- [x] **3.3 — Implement `GET /api/adc/<pin>`**
  On first access, create a `machine.ADC(machine.Pin(n))` object, set its attenuation to the default from `config.json` (or 11 dB if not specified), and store it in `PIN_REGISTRY` with mode `"ADC"`. Call `read_uv()` to get the calibrated microvolt reading. Return the pin number, raw value from `read_u16()`, microvolt value from `read_uv()`, derived voltage in volts (microvolts divided by 1,000,000 rounded to 3 decimal places), and the current attenuation setting.

- [x] **3.4 — Implement `GET /api/adc/all`**
  Loop over all five ADC pins (0 through 4). For each one, lazily initialize an ADC object if not already in the registry, take a reading, and collect the results into a single `"readings"` object keyed by pin number. This endpoint is the efficient way to sample all analog inputs in one HTTP round-trip.

- [x] **3.5 — Implement `POST /api/adc/<pin>/config`**
  Accept `{"atten": "11db"}` (or `"0db"`, `"2.5db"`, `"6db"`). Map the string to the corresponding `machine.ADC` constant. If the ADC object already exists in the registry, call `.atten()` on it. If it does not exist yet, create it with the specified attenuation. Return the updated configuration.

- [x] **3.6 — Read default attenuation from config**
  When `gpio_api.py` loads `config.json`, read the `"adc_atten"` key if present. Use it as the default attenuation for all ADC pins that are initialized without an explicit config call. If the key is missing, default to `"11db"`.

### Verification

```
# Read single ADC pin
curl http://<ip>/api/adc/2 | jq

# Read all ADC pins
curl http://<ip>/api/adc/all | jq

# Change attenuation
curl -X POST http://<ip>/api/adc/2/config \
  -H 'Content-Type: application/json' -d '{"atten":"6db"}'

# Confirm it took effect
curl http://<ip>/api/adc/2 | jq

# Try an invalid pin — must get 400
curl http://<ip>/api/adc/5 | jq
```

### Definition of Done

You can read calibrated voltages from any of the five ADC pins. Attenuation is configurable per-pin and defaults to 11 dB. The `/api/adc/all` endpoint returns all five readings in one response. Mode conflicts with digital and PWM are caught and reported.

---

## Milestone 4 — PWM Output

**Goal:** Start, stop, and dynamically adjust PWM signals on any output-capable pin.

**Why this is fourth:** PWM is needed for LED dimming, motor control, servo positioning, and buzzer tones. It depends on understanding the pin registry and mode exclusivity established in Milestone 2.

### Understanding PWM on MicroPython

MicroPython's `machine.PWM` wraps the ESP32-C3's LED PWM controller. You create a PWM object on a pin with a frequency and duty cycle. The duty cycle is expressed as `duty_u16` (0 to 65535, mapping to 0% to 100%). Frequency can range from 1 Hz to 40 MHz, though practical limits depend on the desired duty resolution — at very high frequencies, fewer distinct duty levels are available.

When PWM is stopped, `pwm.deinit()` must be called to release the hardware channel. If you skip this, the channel remains allocated and the pin continues outputting the last signal.

### Tasks

- [x] **4.1 — Implement `POST /api/pwm/<pin>/start`**
  Accept `{"freq": 1000, "duty_u16": 32768}`. Validate that the pin is in `OUTPUT_PINS` and not in `FORBIDDEN_PINS`. If the pin is currently in a different mode in `PIN_REGISTRY`, return 409 Conflict. Create a `machine.PWM(machine.Pin(n), freq=f)` object, set its `duty_u16`, store it in the registry with mode `"PWM"`, and return the active PWM parameters including a computed `duty_pct` (percentage as a float).

- [x] **4.2 — Validate frequency and duty ranges**
  Frequency must be between 1 and 40,000,000. Duty must be between 0 and 65535. Return 400 with a clear message if either value is out of range. Include the valid range in the error message so the caller does not have to guess.

- [x] **4.3 — Implement `POST /api/pwm/<pin>/duty`**
  Accept `{"duty_u16": 49152}`. The pin must already be in PWM mode in the registry. Call `.duty_u16(value)` on the cached PWM object. Return the updated parameters. This allows adjusting brightness or speed without any signal interruption.

- [x] **4.4 — Implement `POST /api/pwm/<pin>/freq`**
  Accept `{"freq": 5000}`. Same pattern as duty — the pin must already be in PWM mode. Call `.freq(value)` on the cached object. Return the updated parameters.

- [x] **4.5 — Implement `POST /api/pwm/<pin>/stop`**
  Call `pwm.deinit()` on the cached object. Remove the pin from `PIN_REGISTRY` entirely, restoring it to an unconfigured state. Return a confirmation. After this, the pin can be reconfigured as digital input, digital output, or ADC.

- [x] **4.6 — Implement `GET /api/pwm/<pin>`**
  If the pin is in the registry with mode `"PWM"`, return its current frequency, duty_u16, and duty_pct. If it is not in PWM mode, return 404.

### Verification

```
# Start PWM at 1kHz, 50% duty
curl -X POST http://<ip>/api/pwm/5/start \
  -H 'Content-Type: application/json' -d '{"freq":1000,"duty_u16":32768}'

# Read current state
curl http://<ip>/api/pwm/5 | jq

# Adjust duty to 75%
curl -X POST http://<ip>/api/pwm/5/duty \
  -H 'Content-Type: application/json' -d '{"duty_u16":49152}'

# Change frequency
curl -X POST http://<ip>/api/pwm/5/freq \
  -H 'Content-Type: application/json' -d '{"freq":5000}'

# Stop PWM
curl -X POST http://<ip>/api/pwm/5/stop

# Confirm pin is released
curl http://<ip>/api/gpio/pins | jq
```

### Definition of Done

You can start PWM on any output-capable pin, adjust frequency and duty independently and without interruption, stop it cleanly, and the pin returns to an unconfigured state ready for reuse.

---

## Milestone 5 — I2C Bus

**Goal:** Scan for I2C devices, read and write bytes, perform register-style write-then-read operations, and reconfigure the bus pins and frequency at runtime.

**Why this is fifth:** I2C is the most common bus for sensors, displays, and other peripherals. Once this works, the board can talk to an enormous range of external hardware — temperature/humidity sensors (SHT30, BME280), accelerometers (MPU6050), OLED displays (SSD1306), and more.

### Understanding I2C on MicroPython

MicroPython provides `machine.SoftI2C` for bit-banged I2C. On ESP32-C3, this is the recommended approach because `machine.I2C` (hardware I2C) has known stability issues on some firmware versions. `SoftI2C` works on any pair of output-capable GPIO pins.

The bus is initialized with an SDA pin, an SCL pin, and a clock frequency (typically 100 kHz or 400 kHz). The `.scan()` method probes every address from 0 to 127 and returns a list of addresses that acknowledged. `.readfrom(addr, nbytes)` and `.writeto(addr, data)` handle raw byte transfers. `.writeto_then_readfrom(addr, write_buf, read_buf)` or the equivalent two-call pattern handles register reads.

Bytes in MicroPython are `bytes` objects. `json.dumps()` in MicroPython cannot serialize `bytes` directly, so all byte data must be converted to lists of integers before returning as JSON.

### Tasks

- [x] **5.1 — Implement lazy I2C bus initialization**
  Maintain a module-level `_i2c` variable initialized to `None`. On the first I2C endpoint call, create a `machine.SoftI2C` instance using the default pins (SDA=8, SCL=9) and frequency (100 kHz), or values from `config.json` if specified. Cache the instance so subsequent calls reuse it.

- [x] **5.2 — Implement `GET /api/i2c/scan`**
  Initialize the bus if needed, call `.scan()`, and return the list of detected addresses in both decimal and hex formats, plus a count. This is the I2C equivalent of "is anything plugged in?".

- [x] **5.3 — Implement `POST /api/i2c/read`**
  Accept `{"addr": 104, "nbytes": 6}`. Validate that `addr` is 0 to 127 and `nbytes` is positive. Call `.readfrom(addr, nbytes)` and return the data as a list of integers and as a hex string.

- [x] **5.4 — Implement `POST /api/i2c/write`**
  Accept `{"addr": 104, "data": [0, 255]}`. Convert the list of integers to `bytes`. Call `.writeto(addr, data)`. Return confirmation with the number of bytes written.

- [x] **5.5 — Implement `POST /api/i2c/write_read`**
  Accept `{"addr": 104, "write": [1], "read": 2}`. This is the register-read pattern: write a register address, then immediately read N bytes back. Call `.writeto(addr, bytes(write_data), stop=False)` followed by `.readfrom(addr, read_count)`. Return the read data as a list and hex string.

- [x] **5.6 — Implement `POST /api/i2c/config`**
  Accept `{"sda": 8, "scl": 9, "freq": 400000}`. If an I2C instance already exists, deinitialize it. Create a new `SoftI2C` with the specified parameters. This allows switching between different sensor breakout boards that might be wired to different pins.

- [x] **5.7 — Handle I2C errors gracefully**
  I2C operations can fail if no device is at the specified address, if the bus is shorted, or if the wiring is wrong. Wrap every I2C call in a try/except that catches `OSError` and returns a 500 response with the error message. Do not let a failed scan crash the server.

### Verification

```
# Scan bus
curl http://<ip>/api/i2c/scan | jq

# Read 6 bytes from device at address 0x68
curl -X POST http://<ip>/api/i2c/read \
  -H 'Content-Type: application/json' -d '{"addr":104,"nbytes":6}'

# Write to a device
curl -X POST http://<ip>/api/i2c/write \
  -H 'Content-Type: application/json' -d '{"addr":104,"data":[0,0]}'

# Register read: write register 0x75, read 1 byte (WHO_AM_I)
curl -X POST http://<ip>/api/i2c/write_read \
  -H 'Content-Type: application/json' -d '{"addr":104,"write":[117],"read":1}'

# Reconfigure bus to different pins
curl -X POST http://<ip>/api/i2c/config \
  -H 'Content-Type: application/json' -d '{"sda":3,"scl":4,"freq":400000}'
```

### Definition of Done

You can scan the I2C bus and find connected devices. You can read and write raw bytes. You can do register-style read operations. You can reconfigure the bus pins and frequency without rebooting. I2C errors do not crash the server.

---

## Milestone 6 — Batch Operations

**Goal:** Read or write multiple pins in a single HTTP request to minimize round-trip latency over WiFi.

**Why this is sixth:** By this point, digital GPIO is fully working. Batch operations are a performance optimization for clients that need to interact with many pins simultaneously. On a slow WiFi link, the overhead of individual HTTP requests per pin becomes painful. A single batch call eliminates that.

### Tasks

- [x] **6.1 — Implement `POST /api/gpio/batch/read`**
  Accept `{"pins": [0, 2, 5, 8]}`. For each pin, look it up in `PIN_REGISTRY`. If it is configured, read its value. If it is not configured, include an error for that pin in the response. Return a `"results"` object keyed by pin number, each with mode and value (or error message). The endpoint must never fail entirely because one pin is invalid — it returns partial results.

- [x] **6.2 — Implement `POST /api/gpio/batch/write`**
  Accept `{"pins": {"5": 1, "9": 0}}`. For each pin-value pair, verify the pin is in `PIN_REGISTRY` in OUT mode. Set the value. Collect any errors (wrong mode, unknown pin, forbidden pin) into an `"errors"` list. Return both the successfully written pins and the errors. This is a partial-success model — some pins may succeed while others fail, and the response must reflect both.

- [x] **6.3 — Support aliases in batch operations**
  The pin keys in batch requests can be either integer GPIO numbers or string aliases from `pin_aliases`. The same `_resolve_pin()` helper from Milestone 2 should handle this transparently.

### Verification

```
# Batch read
curl -X POST http://<ip>/api/gpio/batch/read \
  -H 'Content-Type: application/json' -d '{"pins":[0,2,5]}'

# Batch write
curl -X POST http://<ip>/api/gpio/batch/write \
  -H 'Content-Type: application/json' -d '{"pins":{"5":1,"9":0}}'
```

### Definition of Done

You can read and write multiple pins in a single HTTP call. Partial failures are reported without aborting the entire batch. Aliases work in batch contexts.

---

## Milestone 7 — WebSocket Real-Time Stream

**Goal:** A persistent WebSocket connection that pushes live snapshots of pin states, ADC readings, and temperature at a configurable interval, and accepts commands from the client without separate HTTP calls.

**Why this is seventh:** This is the most complex feature. It requires the WebSocket extension vendored in Milestone 1, the pin registry populated by Milestones 2–5, and a solid understanding of MicroPython's `uasyncio` cooperative scheduling model. It must be built last so that all the pieces it depends on are stable and tested.

### Understanding the uasyncio Constraint

MicroPython's `uasyncio` on ESP32-C3 does not support `asyncio.wait()` with multiple futures the way CPython does. You cannot wait on both "incoming WebSocket message" and "broadcast timer" simultaneously using `asyncio.gather()` with proper cancellation.

The recommended pattern is to use `asyncio.wait_for()` with a timeout equal to the broadcast interval. If a message arrives before the timeout, handle it. If the timeout fires, broadcast and loop. This gives you bidirectional communication without needing multiple concurrent tasks per connection.

### Server-to-Client Frame Format

The board sends a JSON frame at the configured interval. The frame includes a timestamp (ticks_ms), the state of every monitored pin (digital values, PWM parameters, ADC readings), the internal temperature, and free memory. Only pins listed in `STREAM_CONFIG["pins"]` are included. If the list is empty, all pins currently in `PIN_REGISTRY` are included.

### Client-to-Server Commands

The client sends JSON objects with a `"cmd"` field. Supported commands:

- `"set"` — set a digital output pin: `{"cmd": "set", "pin": 5, "value": 1}`
- `"pwm_duty"` — change PWM duty: `{"cmd": "pwm_duty", "pin": 8, "duty_u16": 49152}`
- `"stream_config"` — change which pins are streamed and how fast: `{"cmd": "stream_config", "pins": [0, 2, 5], "interval_ms": 200}`
- `"ping"` — keepalive: `{"cmd": "ping"}` → responds with `{"cmd": "pong", "ts": <ticks>}`

Invalid commands return an error frame with the original `"cmd"` and `"pin"` echoed back.

### Tasks

- [x] **7.1 — Implement the stream frame builder**
  Write an internal function `_build_stream_frame()` that reads the current state of every pin in `STREAM_CONFIG["pins"]` (or all registered pins if the list is empty), reads ADC values for any ADC pins, reads the temperature, runs `gc.collect()` and reads free memory, and returns a dict ready for `json.dumps()`. This function is called on every broadcast tick.

- [x] **7.2 — Implement the WebSocket command dispatcher**
  Write an internal function `_handle_ws_command(ws, msg)` that parses the incoming JSON string, extracts the `"cmd"` field, and dispatches to the appropriate handler. For `"set"`, reuse the same pin-write logic from the digital GPIO endpoint. For `"pwm_duty"`, reuse the PWM duty logic. For `"stream_config"`, update `STREAM_CONFIG`. For `"ping"`, respond with `"pong"`. For anything else, send back an error frame.

- [x] **7.3 — Implement the `/ws/stream` endpoint**
  Register a route with the `@with_websocket` decorator from the vendored `websocket.py`. The handler adds the connection to a `_ws_clients` list, enters a loop that alternates between receiving messages (with timeout) and broadcasting frames, and removes the connection from the list on exit. The loop uses `asyncio.wait_for(ws.receive(), timeout)` where timeout is `STREAM_CONFIG["interval_ms"] / 1000`.

- [x] **7.4 — Enforce minimum interval**
  The minimum allowed `interval_ms` is 50. Below this, the async event loop does not yield long enough to service HTTP requests, and the board becomes unresponsive to REST calls. If a client sends a `stream_config` command with `interval_ms` less than 50, clamp it to 50 and include a warning in the response frame.

- [x] **7.5 — Handle multiple clients**
  The `_ws_clients` list supports multiple simultaneous WebSocket connections. Each connection gets its own handler coroutine. All connections receive the same broadcast frame content but are sent independently. If one client disconnects or errors, it is removed from the list without affecting others.

- [x] **7.6 — Handle disconnection gracefully**
  Wrap the entire WebSocket handler in try/finally. The `finally` block removes the client from `_ws_clients` and silently swallows any connection-closed exceptions. The server must never crash because a WebSocket client dropped.

### Verification

This milestone is best tested with `websocat` (added to the dev shell in Milestone 8, but can be installed manually for testing):

```
# Connect and watch frames
websocat ws://<ip>/ws/stream

# In another terminal, set a pin and watch the stream update
curl -X POST http://<ip>/api/gpio/5/mode \
  -H 'Content-Type: application/json' -d '{"mode":"OUT"}'
curl -X POST http://<ip>/api/gpio/5/value \
  -H 'Content-Type: application/json' -d '{"value":1}'

# Send a command through the WebSocket (interactive mode)
# Type: {"cmd":"ping"}
# Expect: {"cmd":"pong","ts":...}

# Change stream config
# Type: {"cmd":"stream_config","pins":[0,2,5],"interval_ms":200}
```

### Definition of Done

A WebSocket client can connect and receive live state frames at a configurable interval. The client can send commands to set pins and adjust the stream. Multiple clients can connect simultaneously. Disconnection is handled cleanly. The REST API remains responsive while a WebSocket stream is active.

---

## Milestone 8 — Tooling Updates

**Goal:** Extend the Nix dev shell and `esp` CLI with convenience tools for the new API. Add `curl`, `jq`, and `websocat` to the dev shell. Add new `esp` subcommands for quick pin control from the host terminal.

**Why this is eighth:** The API is fully functional by now. This milestone makes it ergonomic to use from the command line without manually constructing `curl` commands every time.

### Tasks

- [x] **8.1 — Add `curl`, `jq`, `websocat` to `flake.nix` buildInputs**
  These three tools should be explicitly listed in the `buildInputs` of `mkShell` so they are guaranteed available in the dev shell. `curl` is likely already on the system but should be explicit for reproducibility. `jq` formats JSON output. `websocat` is the WebSocket CLI client.

- [x] **8.2 — Implement `esp gpio <pin> [value]`**
  A convenience subcommand. With one argument, it reads the pin: `curl -s http://$ESP_IP/api/gpio/<pin> | jq`. With two arguments, it sets the pin value: `curl -s -X POST http://$ESP_IP/api/gpio/<pin>/value -H 'Content-Type: application/json' -d '{"value":<value>}'`. Requires `ESP_IP` environment variable to be set (the board's IP address).

- [x] **8.3 — Implement `esp adc <pin>`**
  Reads a single ADC sample: `curl -s http://$ESP_IP/api/adc/<pin> | jq`.

- [x] **8.4 — Implement `esp i2c scan`**
  Calls `GET /api/i2c/scan` and pretty-prints the result.

- [x] **8.5 — Implement `esp stream [pin,pin,...]`**
  Opens a WebSocket connection to `/ws/stream` using `websocat`. If pins are specified, sends a `stream_config` command first to filter the output. Pipes through `jq` for readability. Exit with Ctrl+C.

- [x] **8.6 — Update `esp` usage message**
  The help text printed when you run `esp` with no arguments should list all the new subcommands alongside the existing ones.

- [x] **8.7 — Update `config.json.example`**
  Add the `pin_aliases` and `adc_atten` keys with example values and comments explaining their purpose.

### Definition of Done

Running `esp gpio 5 1` from the host sets GPIO 5 high on the board. Running `esp adc 2` prints a voltage reading. Running `esp stream` opens a live feed. All new subcommands are documented in the help output.

---

## Milestone 9 — Hardening and Safety

**Goal:** Comprehensive input validation, error handling, memory safety, and documentation. This is the polish pass that turns a working prototype into a robust API.

**Why this is last:** You cannot harden what does not exist. Every endpoint is functional and tested by this point. Now you go through each one systematically and stress-test the edge cases.

### Tasks

- [x] **9.1 — Audit every endpoint for missing input validation**
  Go through each route handler and verify that every expected field in the request body is checked for presence, correct type, and valid range. Missing fields should return 400 with a message naming the missing field. Wrong types (string where int expected) should return 400. Out-of-range values should return 400 with the valid range stated in the error message.

- [x] **9.2 — Audit every endpoint for missing error handling**
  Wrap any `machine.*` call that can throw an `OSError` or `ValueError` in a try/except. Return 500 with the exception message. The server must never crash from a hardware error.

- [x] **9.3 — Add memory-conscious garbage collection**
  Call `gc.collect()` at the start of complex endpoints (batch operations, I2C reads, WebSocket frame building) to prevent memory fragmentation from accumulating over long-running sessions. Log free memory on the serial console if it drops below a threshold (say 50 KB).

- [ ] **9.4 — Test mode conflict matrix**
  Systematically test every mode transition: IN→OUT, OUT→IN, OUT→PWM (should fail with 409), PWM→ADC (should fail with 409), PWM→stop→ADC (should succeed), ADC→OUT (should fail with 409), and so on. Verify that every transition either succeeds correctly or returns the right error.

- [ ] **9.5 — Test pin alias resolution everywhere**
  Verify that aliases work in single-pin endpoints, batch endpoints, and WebSocket commands. Verify that an unknown alias returns 400 with a message listing the valid aliases.

- [ ] **9.6 — Stress-test WebSocket with multiple clients**
  Connect two or three WebSocket clients simultaneously. Verify they all receive frames. Disconnect one abruptly (kill the process). Verify the others continue receiving. Verify the REST API remains responsive throughout.

- [ ] **9.7 — Test memory under sustained load**
  Leave a WebSocket stream running at 100ms interval for 10 minutes. Periodically check `GET /api/status` to monitor free memory. If memory drops continuously, there is a leak somewhere — likely in frame serialization or connection handling.

- [x] **9.8 — Update CLAUDE.md**
  Add a new section to CLAUDE.md documenting the GPIO API layer: the new files, the API surface, the design decisions, and the updated `esp sync` workflow. This keeps CLAUDE.md as the single source of truth.

### Definition of Done

Every endpoint rejects invalid input with clear error messages and correct HTTP status codes. No hardware error crashes the server. Memory remains stable under sustained use. CLAUDE.md reflects the new state of the project.

---

## Design Principles

These apply to every line of code across all milestones:

**JSON everywhere** — Every response, including errors, is `application/json`. No plain text, no HTML, no ad-hoc formats.

**Correct HTTP status codes** — 200 for success. 400 for bad input (wrong type, out of range, missing field). 403 for forbidden operations (UART pins). 404 for pins not yet configured. 409 for mode conflicts. 500 for hardware errors.

**Descriptive errors** — Error messages should tell the caller what went wrong and how to fix it. Not `"invalid pin"` but `"GPIO 25 is not a valid pin on the ESP32-C3. Valid pins are: 0-10, 18, 19"`. Not `"wrong mode"` but `"GPIO 5 is currently in PWM mode. Call POST /api/pwm/5/stop first to release it"`.

**Lazy initialization** — Hardware objects are created on first use, not at startup. This keeps boot fast and memory usage proportional to actual use.

**Mode exclusivity** — One mode per pin at a time, enforced strictly. No silent reconfiguration.

**Partial success for batch operations** — Batch read and write do not fail atomically. If three out of five pins succeed, return three results and two errors. This is more useful than all-or-nothing on a constrained device.

**No global state leaks** — The only mutable module-level state is `PIN_REGISTRY`, `STREAM_CONFIG`, `_ws_clients`, and `_i2c`. Everything else is local to the request handler.

---

## Error Handling Convention

Every error response follows this format:

```
{"error": "<human-readable message>"}
```

The HTTP status code carries the semantic meaning. The `error` field carries the human-readable explanation. Endpoints that involve a specific pin echo the pin number back:

```
{"error": "GPIO 25 is not a valid C3 GPIO", "pin": 25}
```

WebSocket error frames include the original command:

```
{"error": "pin 25 is not a valid C3 GPIO", "cmd": "set", "pin": 25}
```

---

## Memory Budget

The ESP32-C3 with MicroPython v1.23.0 has approximately 250 KB of free heap after boot. Here is the estimated memory cost of the API layer:

| Component | Estimated Cost |
|-----------|---------------|
| `gpio_api.py` module loaded | ~15–20 KB |
| Each `machine.Pin` object in registry | ~0.1 KB |
| Each `machine.ADC` object in registry | ~0.2 KB |
| Each `machine.PWM` object in registry | ~0.2 KB |
| `SoftI2C` bus instance | ~0.5 KB |
| Each active WebSocket connection | ~2–4 KB |
| Each broadcast frame (serialized JSON) | ~0.5–1 KB (transient) |

With all five ADC pins active, ten digital pins configured, a couple PWM channels, one I2C bus, and two WebSocket clients, the total API overhead is roughly 30–35 KB — leaving well over 200 KB free for the Microdot server, network stack, and any future extensions.

The `gc.collect()` call in performance-critical paths (frame builder, batch operations) keeps the heap from fragmenting over long-running sessions.

---

## Verification Strategy

Every milestone has its own verification section with specific `curl` commands to run. Beyond those, the overall strategy is:

1. **Serial console** — Always watch `esp monitor` during development. Import errors, tracebacks, and memory warnings appear here before they manifest as silent API failures.

2. **Incremental deployment** — Use `esp push gpio_api.py` for single-file iteration during development. Only use `esp sync` when testing the full boot sequence.

3. **Isolation testing** — Test each peripheral independently before combining them. Configure one digital pin, verify it works, then add ADC, then PWM, then I2C. Do not try to test everything at once.

4. **Conflict testing** — After individual features work, deliberately test the conflict paths: try to read ADC on a pin that is in PWM mode, try to toggle a pin that is in input mode, try to configure GPIO 21 as an output. These must all fail gracefully.

5. **Endurance testing** — Leave the board running with a WebSocket stream for at least 10 minutes. Monitor memory via `GET /api/status`. The free memory value should stabilize, not continuously decline.