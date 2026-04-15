# NeoPixel Template

WS2812B RGB LED control over REST API. Set colors on individual LEDs or the
entire strip from a browser dashboard or with `curl`.

## What You Get

- **Color picker dashboard** at `GET /` — pick a color, click "Set", see it on the LEDs
- **REST API** for setting all LEDs, individual LEDs, or clearing the strip
- **Zero dependencies** beyond MicroPython built-ins and vendored Microdot

## Wiring

WS2812B LEDs (NeoPixels) use a single-wire data protocol. Connect three wires:

```
ESP32-C3          WS2812B
─────────         ───────
GPIO 10  ───────  DIN  (data in)
3V3      ───────  VCC  (power)
GND      ───────  GND  (ground)
```

- **Data pin** defaults to GPIO 10. Change `neopixel_pin` in `config.json` to
  use a different pin. Any digital-capable GPIO works.
- **VCC** connects to 3.3V from the ESP32 dev board's regulator. WS2812B LEDs
  are rated for 5V but run reliably at 3.3V with slightly reduced brightness.
- If your strip has multiple LEDs, chain them: DOUT of one LED connects to DIN
  of the next. VCC and GND are shared across all LEDs.

### Power Considerations

Each WS2812B LED draws up to **60 mA at full white** (all three color channels
at 255). Plan your power supply accordingly:

| LED Count | Max Current | Power Source |
|-----------|-------------|--------------|
| 1–4       | 240 mA      | USB / 3.3V pin — fine |
| 5–8       | 480 mA      | USB — borderline, keep brightness low |
| 9–30      | 1.8 A       | External 5V supply required |
| 30+       | 3+ A        | External 5V supply + capacitor across VCC/GND |

> **Important:** For more than ~8 LEDs, do **not** power them from the ESP32's
> 3.3V regulator — you will brown out the board. Use an external 5V power supply
> connected directly to the strip's VCC/GND, and share a common GND with the
> ESP32.

### WS2812B Timing Sensitivity

The WS2812B protocol is timing-critical (800 KHz signal). MicroPython's
`neopixel` module handles this via hardware-timed bitbanging. Keep wires
short (under 1 meter for the data line) and avoid running other high-priority
interrupts during `np.write()`. If you see flickering or wrong colors, add a
330Ω resistor in series on the data line and a 100µF capacitor across VCC/GND.

## Quick Start

```sh
esp init neopixel              # scaffold from this template
vim config.json                # set WiFi credentials, pin, LED count
esp sync                       # push to board + reset
# open http://<board-ip>/ in a browser
```

## Configuration

Edit `config.json` after scaffolding:

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

| Field | Description |
|-------|-------------|
| `neopixel_pin` | GPIO number connected to the strip's DIN line |
| `neopixel_count` | Number of LEDs in the chain |

## API Reference

All endpoints return JSON. POST bodies are JSON (`Content-Type: application/json`).

### GET /api/neopixel

Return the current state of all LEDs.

```sh
curl http://192.168.1.100/api/neopixel
```

Response:

```json
{
  "pin": 10,
  "count": 4,
  "pixels": [[255, 0, 0], [0, 255, 0], [0, 0, 255], [0, 0, 0]]
}
```

### POST /api/neopixel

Set **all** LEDs to the same color.

```sh
curl -X POST http://192.168.1.100/api/neopixel \
  -H "Content-Type: application/json" \
  -d '{"r": 255, "g": 0, "b": 128}'
```

Response:

```json
{
  "ok": true,
  "color": {"r": 255, "g": 0, "b": 128}
}
```

### POST /api/neopixel/\<index\>

Set a **single** LED by index (0-based).

```sh
# Set the third LED (index 2) to green
curl -X POST http://192.168.1.100/api/neopixel/2 \
  -H "Content-Type: application/json" \
  -d '{"r": 0, "g": 255, "b": 0}'
```

Response:

```json
{
  "ok": true,
  "index": 2,
  "color": {"r": 0, "g": 255, "b": 0}
}
```

Returns a `400` error if the index is out of range:

```json
{
  "error": "LED index 5 is out of range. Valid indices are 0 to 3 for a 4-LED strip."
}
```

### POST /api/neopixel/clear

Turn all LEDs off (set to black).

```sh
curl -X POST http://192.168.1.100/api/neopixel/clear
```

Response:

```json
{
  "ok": true,
  "status": "cleared"
}
```

### Error Responses

All errors return a JSON object with an `"error"` key and an appropriate HTTP
status code:

| Situation | Status | Example message |
|-----------|--------|-----------------|
| Missing or invalid RGB values | 400 | `"RGB values must be integers between 0 and 255. Got r=300, g=0, b=-1."` |
| LED index out of range | 400 | `"LED index 5 is out of range. Valid indices are 0 to 3 for a 4-LED strip."` |
| NeoPixel init failure | 500 | `"Failed to initialize NeoPixel on GPIO 10 with 4 LEDs: ..."` |
| Missing JSON body | 400 | `"Request body must be JSON with 'r', 'g', and 'b' fields."` |

## Multi-LED Addressing

For strips with multiple LEDs, use the index endpoint to create patterns:

```sh
# Set a 4-LED strip to red, green, blue, white
curl -X POST http://192.168.1.100/api/neopixel/0 -d '{"r":255,"g":0,"b":0}'
curl -X POST http://192.168.1.100/api/neopixel/1 -d '{"r":0,"g":255,"b":0}'
curl -X POST http://192.168.1.100/api/neopixel/2 -d '{"r":0,"g":0,"b":255}'
curl -X POST http://192.168.1.100/api/neopixel/3 -d '{"r":255,"g":255,"b":255}'
```

Each call to a single-LED endpoint writes to the strip immediately. For
latency-sensitive patterns, use the all-LEDs endpoint to set a uniform color
in one call.

## Dashboard

Open `http://<board-ip>/` in a browser to access the dashboard:

- **Status panel** — device name, IP address, WiFi signal, uptime, free RAM
- **Color picker** — HTML5 `<input type="color">` for intuitive color selection
- **Set Color button** — applies the picked color to all LEDs
- **Off button** — clears the strip (all LEDs to black)
- **Color preview swatch** — shows the currently applied color

## Files

| File | Purpose |
|------|---------|
| `main.py` | Microdot app, dashboard HTML, status routes |
| `neopixel_handler.py` | NeoPixel hardware driver + REST API routes |
| `config.json.example` | Template configuration (copy to `config.json`) |