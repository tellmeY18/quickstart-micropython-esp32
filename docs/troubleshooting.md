# Troubleshooting

Common issues when working with the ESP32 MicroPython Quickstart Toolkit, along with their likely causes and step-by-step solutions.

---

## Table of Contents

1. [No serial device found](#1-no-serial-device-found)
2. [Board not responding](#2-board-not-responding)
3. [WiFi won't connect](#3-wifi-wont-connect)
4. [Import error for microdot](#4-import-error-for-microdot)
5. [MemoryError](#5-memoryerror)
6. [OSError: \[Errno 2\] ENOENT](#6-oserror-errno-2-enoent)
7. [ADC reads 0 or 65535 constantly](#7-adc-reads-0-or-65535-constantly)
8. [I2C scan returns empty list](#8-i2c-scan-returns-empty-list)
9. [NeoPixel not lighting up](#9-neopixel-not-lighting-up)
10. [PWM has no visible effect](#10-pwm-has-no-visible-effect)
11. [Board keeps rebooting](#11-board-keeps-rebooting)
12. [Permission denied on serial port](#12-permission-denied-on-serial-port)
13. [Overriding the serial port](#13-overriding-the-serial-port)
14. [WebSocket connection drops immediately](#14-websocket-connection-drops-immediately)

---

## 1. No serial device found

**Symptom:** `esp detect` prints "No serial device found" or similar. No `/dev/ttyUSB*` or `/dev/cu.usbserial*` device appears.

**Likely causes:**

- The USB cable is **charge-only** (no data lines). This is the #1 cause.
- Missing USB-to-serial drivers for the board's bridge chip (CP2102, CH340, or FTDI).
- The board is not powered or not plugged in.

**Solutions:**

1. **Try a different USB cable.** Genuine data cables are usually thicker and labeled "data" or "sync." If in doubt, test the cable with a phone — if the computer can browse the phone's files, the cable has data lines.

2. **Check for the device manually:**
   ```
   # macOS
   ls /dev/cu.usb*

   # Linux
   ls /dev/ttyUSB* /dev/ttyACM*
   ```

3. **Install drivers if needed:**
   - **CP2102** (most common on ESP32 DevKit boards): [Silicon Labs CP210x drivers](https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers)
   - **CH340** (common on budget clones): [CH340 drivers](http://www.wch-ic.com/downloads/CH341SER_MAC_ZIP.html)
   - On Linux, most drivers are built into the kernel. Try `dmesg | tail -20` after plugging in.

4. **Try a different USB port.** Some USB hubs don't supply enough power or don't pass through serial data reliably. Use a port directly on the computer.

5. **Inspect the board.** Look for a lit power LED. If nothing lights up, the board itself may be dead or the USB connector may have a cold solder joint.

---

## 2. Board not responding

**Symptom:** `esp detect` finds the port, but `esp repl`, `esp sync`, or `esp run` hangs or times out. The board seems frozen.

**Likely causes:**

- The board's flash is corrupted or has no firmware.
- A previous MicroPython script entered an infinite loop or deep sleep.
- The boot.py on the board is crashing before the REPL starts.

**Solutions:**

1. **Erase and re-flash from scratch:**
   ```
   esp erase
   esp flash
   ```
   This wipes all files and firmware, then writes a clean MicroPython image. It fixes the vast majority of "unresponsive board" issues.

2. **Hold the BOOT button during reset.** On most ESP32 boards, holding the BOOT (or IO0) button while pressing RESET puts the chip into download mode, which allows `esptool` to communicate even if MicroPython is broken.

3. **Try raw serial monitoring:**
   ```
   esp monitor
   ```
   Press the RESET button on the board and watch the output. You'll see the ROM bootloader messages, which confirm the chip is alive even if MicroPython isn't starting.

4. **Check for deep sleep.** If you ran `examples/deep_sleep.py`, the board may be sleeping. Press RESET to wake it, or wait for the timer-based wakeup.

---

## 3. WiFi won't connect

**Symptom:** The board boots into AP mode (`ESP32-Dashboard` / `ESP32-Dev`) instead of connecting to your WiFi network. The serial output shows "WiFi connect failed" or the connection times out.

**Likely causes:**

- Wrong SSID or password in `config.json`.
- The WiFi network is 5 GHz only. ESP32 only supports **2.4 GHz**.
- The router is too far away or the signal is too weak.
- The SSID has special characters that aren't being escaped properly in JSON.

**Solutions:**

1. **Double-check `config.json`:**
   ```
   cat config.json
   ```
   Verify `wifi_ssid` and `wifi_password` are correct. Watch for trailing spaces, smart quotes (from copy-paste), or wrong capitalization. SSID matching is case-sensitive.

2. **Confirm your network is 2.4 GHz.** Check your router's settings. Many modern routers broadcast both 2.4 GHz and 5 GHz under the same SSID — the ESP32 will only see the 2.4 GHz band. If your router uses a combined SSID, try creating a separate 2.4 GHz-only SSID for testing.

3. **Test WiFi scanning:**
   ```
   esp run examples/wifi_scan.py
   ```
   This lists all visible networks. If your SSID doesn't appear, the board can't reach it (distance, wrong band, or the network is hidden).

4. **Move the board closer to the router** for initial testing. ESP32 has a PCB antenna with limited range, especially through walls.

5. **Check for special characters in the password.** If your password contains `"`, `\`, or non-ASCII characters, make sure they're properly escaped in the JSON:
   ```json
   {
     "wifi_password": "my\"pass\\word"
   }
   ```

6. **The AP fallback is working as designed.** If STA connection fails, `boot.py` automatically creates a fallback access point so you can still reach the board. Connect to the AP network, then navigate to `http://192.168.4.1/` to confirm the web server is running.

---

## 4. Import error for microdot

**Symptom:** The serial output shows `ImportError: no module named 'lib.microdot'` or `ImportError: no module named 'microdot'` when the board boots.

**Likely causes:**

- The `lib/` directory or its contents are missing from the board's filesystem.
- `esp sync` was not run after `esp init`, or `esp init` was not run at all.
- Files were manually uploaded but the directory structure is wrong.

**Solutions:**

1. **Re-run the full init + sync workflow:**
   ```
   esp init <template>    # re-scaffold from your template
   esp sync               # push all files to the board
   ```

2. **Verify files are on the board:**
   ```
   esp ls
   esp ls lib
   ```
   You should see at least:
   ```
   lib/
   lib/microdot.py
   lib/websocket.py    (if using gpio or full template)
   ```

3. **If using manual file pushing**, make sure the directory exists on the board first. `mpremote` won't auto-create parent directories:
   ```
   esp push lib/microdot.py
   esp push lib/websocket.py
   ```

4. **Check your import paths.** The templates use `from lib.microdot import Microdot`. If you moved files around, the import path must match the actual directory structure on the board.

---

## 5. MemoryError

**Symptom:** The board crashes with `MemoryError` during import, when building an HTML response, or when handling a request. This is most common on ESP32-C3 (~320 KB SRAM, ~100 KB used by MicroPython itself).

**Likely causes:**

- The template is too large for the available RAM (especially `full`).
- Large inline HTML strings consume heap at import time.
- Multiple modules imported simultaneously exhaust memory.
- Memory fragmentation after many requests without GC.

**Solutions:**

1. **Start with the `minimal` template** (~120 KB total) and add features incrementally. The `full` template uses ~170 KB and leaves only ~150 KB headroom on ESP32-C3.

2. **Call `gc.collect()` frequently.** Every template already does this in `@app.before_request`, but if you add custom code, sprinkle `gc.collect()` before heavy operations:
   ```python
   import gc
   gc.collect()
   # now do the heavy work
   ```

3. **Reduce inline HTML.** Large HTML strings are the biggest memory consumer after Microdot itself. Consider:
   - Minifying your HTML (remove whitespace, comments).
   - Serving static files from flash instead of inline strings.
   - Using shorter variable names in the HTML/JS.

4. **Check memory usage via the API:**
   ```
   curl http://<board-ip>/api/status | jq .free_mem_kb
   ```
   If free memory is below 30 KB, you're in the danger zone.

5. **Remove unused imports.** On MicroPython, every imported module stays in RAM. If you copied code from the `full` template but don't need I2C, don't import the I2C handler.

6. **Check the debug log for OOM traces:**
   ```
   esp log
   ```
   The `debuglog` module (used in the `full` template) records memory stats alongside log entries.

---

## 6. OSError: [Errno 2] ENOENT

**Symptom:** The board crashes with `OSError: [Errno 2] ENOENT` immediately after boot or when handling the first request.

**Likely causes:**

- `config.json` is missing from the board.
- You ran `esp init` which created `config.json.example` but didn't copy/rename it to `config.json`.
- `esp sync` was not run after editing config locally.

**Solutions:**

1. **Create `config.json` from the example:**
   ```
   cp config.json.example config.json
   ```

2. **Edit it with your WiFi credentials:**
   ```json
   {
     "device_name": "ESP32-Dev",
     "wifi_ssid": "YOUR_ACTUAL_SSID",
     "wifi_password": "YOUR_ACTUAL_PASSWORD",
     "ap_ssid": "ESP32-Dev",
     "ap_password": "12345678",
     "web_port": 80
   }
   ```

3. **Push to the board:**
   ```
   esp sync
   ```

4. **Verify it's on the board:**
   ```
   esp ls
   ```
   Look for `config.json` in the file listing.

5. **If the error names a different file**, the problem is the same — a file your code expects doesn't exist on the board. Check `esp ls` output against what your `main.py` tries to open.

---

## 7. ADC reads 0 or 65535 constantly

**Symptom:** `GET /api/adc/<pin>` always returns `raw: 0` or `raw: 65535` regardless of the input voltage.

**Likely causes:**

- The ADC pin has nothing connected (floating input reads noise, often 0 or max).
- The input voltage exceeds the ADC's range for the current attenuation setting.
- Wrong pin number — not all GPIOs have ADC capability.
- Wiring issue — broken connection or short.

**Solutions:**

1. **Check your wiring.** Use a multimeter to verify that the voltage at the GPIO pin is between 0 V and 3.3 V. See [wiring.md](wiring.md) for the potentiometer wiring diagram.

2. **Check the attenuation setting.** The ADC attenuation controls the voltage range:

   | Attenuation | Voltage Range | Use Case |
   |---|---|---|
   | `0db` | 0 – 1.0 V | Precision low-voltage sensors |
   | `2_5db` | 0 – 1.3 V | Low-voltage sensors |
   | `6db` | 0 – 2.0 V | Mid-range sensors |
   | `11db` | 0 – 3.3 V | General purpose (default) |

   If your input is 0–3.3 V but attenuation is set to `0db`, the reading will saturate at 65535 for anything above ~1 V.

3. **Verify the pin supports ADC:**
   - **ESP32:** ADC1 on GPIOs 32–39, ADC2 on GPIOs 0, 2, 4, 12–15, 25–27 (ADC2 unavailable during WiFi)
   - **ESP32-C3:** ADC1 on GPIOs 0–4 only. No ADC2.

4. **On ESP32 (original), ADC2 doesn't work when WiFi is active.** This is a hardware limitation. If you need ADC with WiFi, use ADC1 pins (GPIOs 32–39).

5. **Test with the standalone example:**
   ```
   esp run examples/adc_read.py
   ```
   This reads GPIO 0 by default and prints raw values to serial. Connect a potentiometer and turn the knob — you should see the value change.

---

## 8. I2C scan returns empty list

**Symptom:** `GET /api/i2c/scan` returns `{"devices": [], "count": 0}` even though a sensor is connected.

**Likely causes:**

- SDA and SCL wires are swapped.
- Missing or wrong pull-up resistors.
- The I2C device isn't powered.
- Wrong I2C pins configured in `config.json`.
- The device uses a non-standard I2C address.

**Solutions:**

1. **Check the wiring carefully.** I2C requires exactly 4 connections:
   - SDA → SDA (data)
   - SCL → SCL (clock)
   - VCC → 3.3 V (NOT 5 V unless the device has a level shifter)
   - GND → GND

   See [wiring.md](wiring.md) for a diagram.

2. **Verify pull-up resistors.** I2C requires pull-up resistors on both SDA and SCL (typically 4.7 kΩ to 3.3 V). Many breakout boards include onboard pull-ups, but if you're wiring a bare chip, you need to add them.

3. **Check `config.json` pin assignments:**
   ```json
   {
     "i2c_sda": 6,
     "i2c_scl": 7
   }
   ```
   The defaults (SDA=6, SCL=7) are for ESP32-C3. If you're using a different board or different pins, update these values.

4. **Check device power.** Some I2C sensors need time to power up. Add a small delay after boot.

5. **Test with the standalone example:**
   ```
   esp run examples/i2c_scan.py
   ```
   This scans all 127 I2C addresses and prints any that respond. If it finds nothing, the problem is definitely hardware/wiring.

6. **Try a lower I2C bus frequency.** Long wires or noisy environments can cause issues at 100 kHz. Try `"i2c_freq": 50000` in `config.json`.

7. **Make sure you're not using UART pins.** GPIO 20 (RX) and 21 (TX) on ESP32-C3 are reserved for UART. Don't use them for I2C.

---

## 9. NeoPixel not lighting up

**Symptom:** `POST /api/neopixel` returns `{"ok": true}` but the WS2812B LEDs stay dark.

**Likely causes:**

- Wrong data pin in `config.json`.
- VCC/GND not connected (or connected to wrong voltage).
- Data pin connected to DIN of the wrong end of the strip.
- The strip requires more current than USB can provide.

**Solutions:**

1. **Check `config.json`:**
   ```json
   {
     "neopixel_pin": 10,
     "neopixel_count": 8
   }
   ```
   Make sure `neopixel_pin` matches the GPIO you've wired to the strip's DIN (Data In) pad.

2. **Check power connections:**
   - VCC → 3.3 V (for 1–4 LEDs) or 5 V external supply (for more LEDs)
   - GND → GND (board and power supply must share a common ground)
   - DIN → your GPIO pin

3. **Check strip direction.** WS2812B strips have a data direction indicated by arrows printed on the strip. Connect your GPIO to the **DIN** (input) end, not DOUT (output).

4. **For more than 8 LEDs, use external power.** Each WS2812B LED draws up to 60 mA at full white. 8 LEDs = 480 mA, which exceeds most USB ports. Use a 5 V / 2 A power supply connected directly to the strip's VCC/GND pads, and share a common GND with the ESP32.

5. **Add a 300–500 Ω resistor** on the data line between the GPIO and DIN. This protects against voltage spikes and is recommended for reliable operation.

6. **Try setting a visible color via curl:**
   ```
   curl -X POST http://<board-ip>/api/neopixel \
     -H "Content-Type: application/json" \
     -d '{"r": 255, "g": 0, "b": 0}'
   ```
   If the API responds with `"ok": true` but nothing lights up, it's a hardware issue.

7. **Try a different GPIO pin.** Some pins have restrictions. GPIO 10 is a safe default on ESP32-C3.

---

## 10. PWM has no visible effect

**Symptom:** `POST /api/pwm/<pin>/start` returns success, duty cycle is set, but the LED doesn't dim or the servo doesn't move.

**Likely causes:**

- The duty cycle is 0% (LED fully off) or 100% (LED fully on, no dimming visible).
- The LED has no current-limiting resistor and the GPIO can't source enough current.
- Servo requires a specific frequency (50 Hz) and pulse width range.
- Wrong pin — the pin is valid for PWM but not connected to anything.

**Solutions:**

1. **Check the duty cycle value.** `duty_u16: 0` means fully off, `duty_u16: 65535` means fully on. For visible dimming, try a mid-range value:
   ```
   curl -X POST http://<board-ip>/api/pwm/5/start \
     -H "Content-Type: application/json" \
     -d '{"freq": 1000, "duty_u16": 32768}'
   ```

2. **For LEDs:** Use a 330 Ω resistor between the GPIO and LED anode. A frequency of 1000 Hz is ideal for LED dimming (no visible flicker). See [wiring.md](wiring.md) for the circuit.

3. **For servos:** Use 50 Hz frequency. Servo pulse width is typically:
   - 1 ms (duty_u16 ≈ 3277) → 0° position
   - 1.5 ms (duty_u16 ≈ 4915) → 90° (center)
   - 2 ms (duty_u16 ≈ 6554) → 180° position

4. **Test with the standalone example:**
   ```
   esp run examples/pwm_fade.py
   ```
   This fades an LED on GPIO 5 from off to full brightness and back. If it works, your wiring is fine and the issue is in your template configuration.

5. **Try a lower frequency.** If you're debugging, set `freq: 1` — the LED will blink once per second, making it obvious whether PWM is working at all.

6. **Make sure the pin is not also configured for GPIO or ADC.** On MicroPython, a pin can only be in one mode at a time. If you previously set it as a digital output, the PWM won't take effect until you restart.

---

## 11. Board keeps rebooting

**Symptom:** The serial monitor shows the board repeatedly printing boot messages, MicroPython startup text, or crash tracebacks in a loop.

**Likely causes:**

- An unhandled exception in `boot.py` or `main.py` triggers MicroPython's auto-restart.
- Out-of-memory crash during import (the `full` template on ESP32-C3 is tight).
- A strapping pin (GPIO 0, 2, or 8 on ESP32-C3) is being driven during boot, causing the chip to enter the wrong boot mode.
- Hardware brown-out — insufficient power supply.

**Solutions:**

1. **Check the debug log first:**
   ```
   esp log
   ```
   The `debuglog` module (in the `full` template) writes crash details to `/debug.log` on flash. This survives reboots and is the fastest way to find the root cause.

2. **Watch the serial output during boot:**
   ```
   esp monitor
   ```
   Press the RESET button and watch what happens. Look for Python tracebacks — they'll tell you exactly which line is crashing.

3. **If it's a MemoryError**, switch to a smaller template:
   ```
   esp init minimal
   esp sync
   ```
   See [MemoryError](#5-memoryerror) above for more details.

4. **Check for strapping pin conflicts.**
   - **ESP32-C3 strapping pins:** GPIO 2 (boot mode), GPIO 8 (boot mode), GPIO 9 (boot log)
   - **ESP32 strapping pins:** GPIO 0, 2, 5, 12, 15
   
   If you have external hardware driving these pins at boot time, the chip may enter download mode or fail to boot. Disconnect external hardware from strapping pins and re-test.

5. **Check power supply.** Brown-out detection will reset the ESP32 if voltage drops below ~2.6 V. If you're powering peripherals (servos, LED strips, sensors) from the USB 5 V/3.3 V rail, you may be drawing too much current. Use an external power supply for high-current peripherals.

6. **If all else fails**, erase and start fresh:
   ```
   esp erase
   esp flash
   esp init minimal
   # edit config.json
   esp sync
   ```

---

## 12. Permission denied on serial port

**Symptom:** `esp detect` or `esp flash` fails with `Permission denied: '/dev/ttyUSB0'` (Linux) or a similar access error on macOS.

**Likely causes:**

- Your user account doesn't have permission to access the serial device.
- Another program (Arduino IDE, another terminal, screen) has the port open exclusively.

**Solutions:**

### Linux

1. **Add your user to the `dialout` group** (Debian/Ubuntu) or `uucp` group (Arch):
   ```
   sudo usermod -aG dialout $USER
   ```
   **You must log out and log back in** (or reboot) for the group change to take effect.

2. **Verify group membership:**
   ```
   groups
   ```
   You should see `dialout` in the output.

3. **Quick temporary fix** (not recommended for daily use):
   ```
   sudo chmod 666 /dev/ttyUSB0
   ```

### macOS

1. Typically no extra permissions are needed on macOS. If you see access errors, check that no other application has the port open.

2. **Close any other serial monitors** — Arduino IDE, screen sessions, PlatformIO, etc. Only one program can use a serial port at a time:
   ```
   # Find processes using the serial port
   lsof | grep cu.usb
   ```

3. If you installed drivers (CP2102 / CH340), you may need to allow the kernel extension in **System Preferences → Security & Privacy → General** — look for a "System software from developer was blocked" message.

---

## 13. Overriding the serial port

**Symptom:** You have multiple boards connected, or `esp detect` picks the wrong port automatically.

**Solution:**

Set the `ESP_PORT` environment variable to force a specific serial port:

```
# macOS
export ESP_PORT=/dev/cu.usbmodem14101

# Linux
export ESP_PORT=/dev/ttyUSB1
```

After setting this, all `esp` commands will use the specified port instead of auto-detecting.

**Finding available ports:**

```
# macOS — list all USB serial devices
ls /dev/cu.usb*

# Linux — list all USB serial devices
ls /dev/ttyUSB* /dev/ttyACM*
```

You can also add the export line to your shell's RC file (`~/.bashrc`, `~/.zshrc`) to make it permanent for a particular board.

---

## 14. WebSocket connection drops immediately

**Symptom:** The WebSocket connection to `/api/stream` (in the `full` template) opens and then closes within a few seconds. The browser console shows `WebSocket connection closed` errors.

**Likely causes:**

- Low memory — the WebSocket handler allocates buffers and GC can't keep up.
- The `websocket` feature is not enabled in `config.json`.
- Network instability between the client and the board.

**Solutions:**

1. **Enable WebSocket in `config.json`** (full template):
   ```json
   {
     "features": {
       "websocket": true
     }
   }
   ```

2. **Reduce streaming frequency.** If you're streaming sensor data too fast, the board runs out of memory building frames. Increase the interval between updates.

3. **Use `websocat` for debugging** (available in the Nix dev shell):
   ```
   websocat ws://<board-ip>/api/stream
   ```
   This gives you a raw view of the WebSocket messages without browser overhead.

4. **Check memory before and during streaming:**
   ```
   curl http://<board-ip>/api/status | jq .free_mem_kb
   ```
   If free memory is under 40 KB, the WebSocket handler likely can't sustain a connection. Switch to a simpler template or reduce the feature set.

---

## Still stuck?

If none of the above solutions work:

1. **Read the debug log:** `esp log` — this contains timestamped, memory-annotated entries that usually point to the exact failure.
2. **Open the REPL:** `esp repl` — test things interactively. Try importing modules one at a time to find what's failing.
3. **Start minimal:** `esp init minimal && esp sync` — confirm the basic web server works, then add complexity one piece at a time.
4. **Check `CLAUDE.md`** for architecture details, RAM budget tables, and design decisions.
5. **Erase and reflash:** When all else fails, `esp erase && esp flash` gives you a clean slate.