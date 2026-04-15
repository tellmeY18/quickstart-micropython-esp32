# Minimal Template

WiFi connect + health-check endpoint only. The smallest possible web server on an ESP32.

## What This Template Does

Boots the ESP32, connects to WiFi (or starts an AP fallback), and serves:

- **`GET /`** — An HTML dashboard showing device name, IP address, uptime, and free memory (dark terminal theme)
- **`GET /api/status`** — JSON health-check endpoint

No GPIO, no peripherals, no debug logging. This is the "hello world" of the toolkit.

## Files Included

| File | Purpose |
|---|---|
| `main.py` | Microdot web server with dashboard + status endpoint (~50 lines) |
| `config.json.example` | Configuration template (WiFi credentials, device name, port) |

Plus shared core files copied by `esp init`:

- `boot.py` — WiFi connect with AP fallback
- `lib/microdot.py` — Vendored Microdot async web framework

## Setup

```sh
nix develop                    # Enter the dev shell
esp detect                     # Verify board is connected
esp erase && esp flash         # First time only: flash MicroPython firmware
esp init minimal               # Scaffold this template
# Edit config.json — set wifi_ssid and wifi_password
esp sync                       # Push files to board + reboot
```

Open `http://<board-ip>/` in your browser to see the dashboard.

## Configuration

`config.json` has exactly 6 keys:

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

| Key | Description |
|---|---|
| `device_name` | Displayed in the dashboard title and returned in `/api/status` |
| `wifi_ssid` | Your WiFi network name (2.4 GHz only) |
| `wifi_password` | Your WiFi password |
| `ap_ssid` | Fallback access point name (used if WiFi connection fails) |
| `ap_password` | Fallback access point password (min 8 characters) |
| `web_port` | HTTP server port (default 80) |

## API Reference

### `GET /`

Returns an HTML dashboard page with a dark terminal theme. The page auto-refreshes status every 5 seconds via JavaScript fetch.

**Dashboard displays:**

- Device name
- IP address
- WiFi mode (STA or AP)
- Uptime in seconds
- Free memory in KB

### `GET /api/status`

Returns a JSON object with device health information.

**Example response:**

```json
{
  "device_name": "ESP32-Dashboard",
  "ip": "192.168.1.42",
  "wifi_mode": "STA",
  "rssi_dbm": -45,
  "wifi_quality": "excellent",
  "uptime_s": 120,
  "free_mem": 165000,
  "free_mem_kb": 161
}
```

**Fields:**

| Field | Type | Description |
|---|---|---|
| `device_name` | string | From config.json |
| `ip` | string | Current IP address |
| `wifi_mode` | string | `"STA"` (connected to WiFi) or `"AP"` (access point mode) |
| `rssi_dbm` | int | WiFi signal strength in dBm (0 in AP mode) |
| `wifi_quality` | string | `"excellent"` / `"good"` / `"fair"` / `"weak"` / `"unusable"` / `"n/a"` |
| `uptime_s` | int | Seconds since boot |
| `free_mem` | int | Free heap memory in bytes |
| `free_mem_kb` | int | Free heap memory in KB |

**Example with curl:**

```sh
curl -s http://192.168.1.42/api/status | jq
```

## Memory Footprint

This template uses approximately 120 KB of RAM, leaving ~200 KB free on an ESP32-C3. It is the lightest template available.

## Next Steps

Once this template is working, you can graduate to more capable templates:

- **`gpio`** — Add digital pin control (toggle LEDs, read buttons)
- **`sensors`** — Add ADC voltage reading and I2C device communication
- **`pwm`** — Add PWM output for LED dimming and servo control
- **`neopixel`** — Add WS2812B RGB LED control
- **`full`** — Everything combined with WebSocket streaming

Run `esp templates` to see all available options, or `esp init <template>` to switch.