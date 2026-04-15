# Changelog

## v0.1.0 — Quickstart Toolkit

Initial release of the ESP32 MicroPython Quickstart Toolkit.

### What Changed

This release transforms the project from a single-purpose GPIO dashboard into a
template-based quickstart toolkit for ESP32 development.

### Templates

Six ready-to-use templates, each a complete starting point:

- **minimal** — WiFi connect + health-check endpoint only (~50 lines)
- **gpio** — Digital GPIO control over HTTP (toggle LEDs, read buttons)
- **sensors** — ADC voltage reading, I2C bus communication, internal temperature
- **pwm** — PWM output control (LED dimming, servo positioning)
- **neopixel** — WS2812B RGB LED control with color picker dashboard
- **full** — Everything combined: GPIO + ADC + PWM + I2C + WebSocket streaming

### Example Scripts

Eight standalone scripts for learning hardware APIs:

- `blink.py` — Toggle an LED on/off
- `button_read.py` — Read a digital input with pull-up
- `adc_read.py` — Read analog voltage from a pin
- `pwm_fade.py` — Fade an LED using PWM duty cycle
- `i2c_scan.py` — Scan I2C bus and list device addresses
- `wifi_scan.py` — Scan for nearby WiFi networks
- `internal_temp.py` — Read the ESP32 internal temperature sensor
- `deep_sleep.py` — Enter deep sleep and wake on timer

### ESP CLI

New commands:
- `esp init <template>` — Scaffold a project from a template
- `esp templates` — List all available templates
- `esp sync` — Now auto-detects files (no hardcoded list)

Deprecated commands (still work with a notice):
- `esp gpio`, `esp adc`, `esp i2c`, `esp stream` — Use `curl` directly instead

### Supported Boards

- ESP32 (tested)
- ESP32-C3 (tested)
- ESP32-S2 (firmware pinned, untested)
- ESP32-S3 (firmware pinned, untested)

### Documentation

- `README.md` — User-facing quickstart
- `docs/pin-reference.md` — GPIO tables for ESP32 and ESP32-C3
- `docs/wiring.md` — Common breadboard circuit diagrams
- `docs/troubleshooting.md` — FAQ covering 14 common issues
- Template READMEs with full API references and curl examples

### Breaking Changes

If you were using the previous flat-file layout (`main.py`, `gpio_api.py`, `debuglog.py`
in the project root):

- Those files are now in `templates/full/`
- Use `esp init full` to scaffold the equivalent project
- The `esp sync` command now auto-detects files instead of using a hardcoded list
- Feature flags in `config.json` are only used by the `full` template; other templates
  don't need them