---
title: ESP-32 MicroPython Dashboard
author: Mathew
---

<!-- jump_to_middle -->

ESP-32 MicroPython Dashboard
---

_A dead-simple "is the board alive?" dashboard_

Served from an ESP-32 running **MicroPython**

<!-- end_slide -->

What is this?
---

A minimal health-check dashboard served directly from an **ESP-32** microcontroller.

<!-- pause -->

The board connects to WiFi, starts a tiny web server, and serves a single HTML page showing:

* **Device name**
* **IP address**
* **WiFi mode** (STA or AP)
* **Uptime** — counting up every 5 seconds
* **Free memory**

<!-- pause -->

> [!note]
> That's it — no BLE, no GPIO, no automations, no cloud.
> Just proof the board boots and talks HTTP.

<!-- end_slide -->

Tech Stack
---

| Layer | Technology |
| --------------- | ------------------------------- |
| Hardware | ESP-32 / ESP-32-C3 |
| Runtime | MicroPython v1.23.0 |
| Web Framework | Microdot (async, single-file) |
| Dev Environment | Nix Flakes |
| Tooling | esptool, mpremote, picocom |

<!-- end_slide -->

Architecture
---

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

<!-- end_slide -->

Project Structure
---

Only **4 files** go onto the board:

```
project/
├── boot.py            # WiFi connect on power-on
├── main.py            # Microdot web server + dashboard
├── config.json        # WiFi creds & device name
└── lib/
    └── microdot.py    # Async web framework (single file)
```

<!-- pause -->

Supporting files (dev machine only):

```
├── CLAUDE.md          # Project plan & conventions
├── flake.nix          # Nix dev shell
├── flake.lock
└── slides.md          # This presentation!
```

<!-- end_slide -->

Design Constraints
---

| Constraint | Rationale |
| -------------------- | ------------------------------------------------- |
| **Inline HTML** | Dashboard is a Python string — no extra file reads |
| **No JS file** | Tiny inline `<script>` polls `/api/status` every 5s |
| **Async Microdot** | Uses `uasyncio` so the server doesn't block |
| **JSON API** | `/api/status` returns `application/json` |
| **AP fallback** | If WiFi fails → creates AP `ESP32-Dashboard` |

<!-- end_slide -->

config.json
---

Simple JSON config — edit WiFi creds before first sync:

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

<!-- end_slide -->

boot.py — WiFi Connection
---

Runs on power-on: connect to WiFi or fall back to AP mode.

```python {1-5|7-12|14-18|all} +line_numbers
# Load config and attempt WiFi
with open("config.json") as f:
    config = ujson.load(f)
ssid = config["wifi_ssid"]
password = config["wifi_password"]

# Try Station (client) mode
sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.connect(ssid, password)
# Wait up to 10 seconds ...
# ✓ Connected → print IP

# WiFi failed? Start AP mode
sta.active(False)
ap = network.WLAN(network.AP_IF)
ap.active(True)
ap.config(essid=ap_ssid, password=ap_password)
```

<!-- end_slide -->

main.py — Web Server
---

Two routes serve the entire dashboard:

```python {1-6|8-19|all} +line_numbers
# GET / — serve inline HTML dashboard
@app.route("/")
async def index(request):
    return Response(HTML,
        headers={"Content-Type": "text/html"})

# GET /api/status — JSON health check
@app.route("/api/status")
async def api_status(request):
    gc.collect()
    ip, mode = get_wifi_info()
    uptime_ms = time.ticks_diff(
        time.ticks_ms(), BOOT_TICKS)
    return {
        "device_name": DEVICE_NAME,
        "ip": ip,
        "wifi_mode": mode,
        "uptime_s": uptime_ms // 1000,
        "free_mem_kb": gc.mem_free() // 1024,
    }
```

<!-- end_slide -->

The Dashboard UI
---

Inline HTML with a _terminal vibe_:

<!-- column_layout: [1, 1] -->

<!-- column: 0 -->

**Styling:**
* Dark background (`#0d1117`)
* Green monospace text
* Blue heading
* Rounded stat container

**JavaScript:**
* Fetches `/api/status` every 5s
* Updates DOM in-place
* Shows error state if offline

<!-- column: 1 -->

```json
// Response from /api/status
{
  "device_name": "ESP32-Dashboard",
  "ip": "192.168.1.42",
  "wifi_mode": "STA",
  "uptime_s": 312,
  "free_mem": 98304,
  "free_mem_kb": 96
}
```

<!-- end_slide -->

Dev Environment — Nix Flakes
---

One command sets up **everything**:

```bash
nix develop
```

<!-- pause -->

The `flake.nix` provides:

* `esptool` — flash firmware & erase flash
* `mpremote` — file transfer + REPL
* `picocom` — raw serial monitor
* `python3` + `pyserial`
* **`esp`** — unified CLI wrapping all of the above

<!-- pause -->

> [!tip]
> No manual installs. No virtualenvs. No version conflicts.
> Just `nix develop` and go.

<!-- end_slide -->

The `esp` CLI
---

A custom shell script bundled in `flake.nix` that auto-detects port & chip:

<!-- column_layout: [1, 1] -->

<!-- column: 0 -->

**Hardware:**

```bash
esp detect   # show port, chip, firmware
esp erase    # erase flash (first time)
esp flash    # flash MicroPython
```

**Serial:**

```bash
esp repl     # REPL (Ctrl+X to exit)
esp monitor  # raw serial (picocom)
```

<!-- column: 1 -->

**File Transfer:**

```bash
esp sync          # push all files + reset
esp push main.py  # push single file
esp run test.py   # run without copying
esp ls            # list device flash
```

**Port Override:**

```bash
export ESP_PORT=/dev/cu.usbmodem14101
```

<!-- end_slide -->

Auto-Detection Magic
---

The `esp` CLI does smart **port** and **chip** detection:

```bash {1-4|6-9|all} +line_numbers
# Port detection priority:
# 1. ESP_PORT env var (if set)
# 2. /dev/cu.usbmodem*  (macOS)
# 3. /dev/ttyUSB*       (Linux)

# Chip detection via esptool:
# → ESP32      (flash offset 0x1000)
# → ESP32-C3   (flash offset 0x0)
# → ESP32-S2, S3, C6 detected too
```

<!-- pause -->

**Firmware is pinned** in `flake.nix` via `fetchurl` with SHA256 hashes:
* `ESP32_GENERIC-20240602-v1.23.0.bin`
* `ESP32_GENERIC_C3-20240602-v1.23.0.bin`

> [!note]
> Reproducible builds — every developer gets the exact same firmware.

<!-- end_slide -->

Getting Started
---

**Step 1:** Enter the dev shell

```bash
nix develop
```

<!-- pause -->

**Step 2:** First-time board setup

```bash
esp detect    # verify port & chip
esp erase     # erase flash
esp flash     # flash MicroPython v1.23.0
```

<!-- pause -->

**Step 3:** Configure and deploy

```bash
# edit config.json with your WiFi creds
esp sync      # push all files + reset
```

<!-- pause -->

**Step 4:** Open `http://<board-ip>/` in a browser 🎉

<!-- end_slide -->

Demo Flow
---

```
 ┌─────────────┐     ┌─────────────────┐     ┌──────────────┐
 │  nix develop │ ──► │   esp sync      │ ──► │  Browser     │
 │  (get tools) │     │ (push & reset)  │     │  opens page  │
 └─────────────┘     └─────────────────┘     └──────────────┘
                                                     │
                                                     ▼
                                              ┌──────────────┐
                                              │  Dashboard   │
                                              │  • Name      │
                                              │  • IP        │
                                              │  • Uptime ↑  │
                                              │  • Memory    │
                                              └──────────────┘
```

If WiFi fails → board creates AP **`ESP32-Dashboard`** → connect directly.

<!-- end_slide -->

Key Takeaways
---

* **Minimal footprint** — 4 files, ~200 lines of code total

<!-- pause -->

* **Reproducible environment** — Nix flakes, pinned firmware

<!-- pause -->

* **Zero dependencies on cloud** — everything runs on the board

<!-- pause -->

* **Smart tooling** — the `esp` CLI auto-detects everything

<!-- pause -->

* **AP fallback** — always reachable, even without WiFi config

<!-- pause -->

> _If the dashboard loads, the board is alive._ ✓

<!-- end_slide -->

<!-- jump_to_middle -->

Thank You
---

**ESP-32 MicroPython Dashboard**

_Questions?_