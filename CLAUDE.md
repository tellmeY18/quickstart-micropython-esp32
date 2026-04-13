# CLAUDE.md — ESP-32 MicroPython Dashboard

## Project Overview

A dead-simple "is the board alive?" dashboard served from an ESP-32 running MicroPython.
The board connects to WiFi, starts a tiny web server (Microdot), and serves a single
HTML page showing device name, IP address, uptime, and free memory. That's it — no
BLE, no GPIO, no automations, no cloud. Just proof the board boots and talks HTTP.

---

## Development Environment

### Prerequisites

- [Nix](https://nixos.org/) with flakes enabled
- An ESP-32 or ESP-32-C3 board connected via USB

### Entering the dev shell

```sh
nix develop
```

This provides: `esptool`, `mpremote`, `picocom`, `python3`, and the unified `esp` CLI.

### First-time board setup

```sh
esp detect          # verify port & chip detection
esp erase           # erase flash (first time only)
esp flash           # flash MicroPython v1.23.0 firmware
```

### Daily workflow

```sh
esp sync            # push all project files to the board + reset
esp repl            # interactive MicroPython REPL (Ctrl+X to exit)
esp monitor         # raw serial monitor (Ctrl+A then Ctrl+X to exit)
esp push main.py    # push a single file
esp run test.py     # run a script without copying it
esp ls              # list files on device
```

### Port override

```sh
export ESP_PORT=/dev/cu.usbmodem14101
```

---

## Project Structure

```
project/
├── CLAUDE.md          # ← this file (project plan & conventions)
├── flake.nix          # Nix dev shell (esptool, mpremote, picocom, esp CLI)
├── flake.lock
│
├── boot.py            # Runs on power-on: connects to WiFi
├── main.py            # Starts Microdot web server, serves dashboard + /api/status
├── config.json        # WiFi credentials and device name
│
└── lib/
    └── microdot.py    # Microdot — minimal async web framework for MicroPython
```

Only **4 files** go onto the board: `boot.py`, `main.py`, `config.json`, `lib/microdot.py`.

---

## Architecture

```
┌──────────────────────────────────────────┐
│              ESP-32 Board                │
│                                          │
│  boot.py ──► WiFi connect (or AP mode)   │
│                   │                      │
│  main.py ──► Microdot web server         │
│               │                          │
│    GET /          → inline HTML dashboard │
│    GET /api/status → JSON health check   │
│                                          │
│  Browser ◄─── WiFi ─────────────────┘    │
└──────────────────────────────────────────┘
```

### Design constraints

| Constraint | Rationale |
|---|---|
| **Inline HTML** | The dashboard HTML is a Python string in `main.py` — no extra file reads |
| **No JS file** | The page uses a tiny inline `<script>` to poll `/api/status` every 5 s |
| **Async Microdot** | Uses `uasyncio` so the server doesn't block |
| **JSON API** | `/api/status` returns `application/json` |
| **AP fallback** | If WiFi credentials fail, board creates AP `ESP32-Dashboard` so you can still reach it |

---

## Implementation Plan

### File: `config.json`

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

The user edits `wifi_ssid` and `wifi_password` before first sync.

---

### File: `boot.py`

Responsibilities:
1. Load `config.json` with `ujson`
2. Try connecting to `wifi_ssid` with a 10 s timeout
3. If it fails → start AP mode with `ap_ssid` / `ap_password`
4. Print the IP address to serial so the user can find it

---

### File: `main.py`

Responsibilities:
1. Import Microdot
2. Read `config.json` for `device_name` and `web_port`
3. Define two routes:

   **`GET /`** — returns an inline HTML string containing:
   - Device name as the heading
   - A `<div id="status">` that JS will fill
   - A small inline `<script>` that fetches `/api/status` every 5 s and
     renders: IP, WiFi mode, uptime, free memory
   - Minimal inline CSS (dark background, monospace, green text — terminal vibe)

   **`GET /api/status`** — returns JSON:
   ```json
   {
     "device_name": "ESP32-Dashboard",
     "ip": "192.168.1.42",
     "wifi_mode": "STA",
     "uptime_s": 312,
     "free_mem": 98304,
     "free_mem_kb": 96
   }
   ```

4. `app.run(port=config["web_port"])`

---

### File: `lib/microdot.py`

The single-file async Microdot release for MicroPython, downloaded from:
https://github.com/miguelgrinberg/microdot

Use the `microdot.py` file from the latest v2.x release (async variant).

---

## Milestone

After running:

```sh
# edit config.json with your WiFi creds
esp sync
```

Open `http://<board-ip>/` in a browser and see:

- Device name
- IP address
- WiFi mode (STA or AP)
- Uptime counting up every 5 seconds
- Free memory

That's the whole project. If this works, the board is alive and serving HTTP.