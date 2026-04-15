# ESP32 GPIO Pin Reference

Quick-reference tables for every ESP32 variant supported by this toolkit.
Use these tables when choosing pins in `config.json` or wiring up a breadboard.

> **Legend**
> - ✅ = supported / safe to use
> - ⚠️ = usable with caveats (strapping pin, or shared function)
> - ❌ = do not use (flash, UART, or restricted)
> - `—` = not available on this pin

---

## ESP32 (Original / WROOM-32)

The classic ESP32 has 34 GPIO-capable pins (GPIO 0–19, 21–23, 25–27, 32–39).
GPIOs 20, 24, 28–31 do not exist on the WROOM-32 module.

### GPIO Table

| GPIO | Direction | ADC | Touch | PWM | I2C | SPI | Notes |
|------|-----------|-----|-------|-----|-----|-----|-------|
| 0 | I/O | ADC2 CH1 | Touch 1 | ✅ | ✅ | — | ⚠️ **Strapping pin** — must be HIGH or floating at boot. Connected to BOOT button on most dev boards. Safe to use as output after boot. |
| 1 | I/O | — | — | ✅ | — | — | ❌ **UART0 TX** — used by REPL/serial output. Do not use. |
| 2 | I/O | ADC2 CH2 | Touch 2 | ✅ | ✅ | — | ⚠️ **Strapping pin** — must be LOW or floating at boot. Often connected to onboard LED. Safe after boot. |
| 3 | I/O | — | — | ✅ | — | — | ❌ **UART0 RX** — used by REPL/serial input. Do not use. |
| 4 | I/O | ADC2 CH0 | Touch 0 | ✅ | ✅ | — | ✅ Safe. Good general-purpose pin. |
| 5 | I/O | — | — | ✅ | ✅ | VSPI SS | ⚠️ **Strapping pin** — controls boot debug output. Directly usable for output; pulled up internally at boot. |
| 6 | I/O | — | — | — | — | Flash CLK | ❌ **Connected to internal SPI flash.** Never use. |
| 7 | I/O | — | — | — | — | Flash D0 | ❌ **Connected to internal SPI flash.** Never use. |
| 8 | I/O | — | — | — | — | Flash D1 | ❌ **Connected to internal SPI flash.** Never use. |
| 9 | I/O | — | — | — | — | Flash D2 | ❌ **Connected to internal SPI flash.** Never use. |
| 10 | I/O | — | — | — | — | Flash D3 | ❌ **Connected to internal SPI flash.** Never use. |
| 11 | I/O | — | — | — | — | Flash CMD | ❌ **Connected to internal SPI flash.** Never use. |
| 12 | I/O | ADC2 CH5 | Touch 5 | ✅ | ✅ | HSPI MISO | ⚠️ **Strapping pin** — controls flash voltage. Must be LOW at boot for 3.3V flash. Safe after boot. |
| 13 | I/O | ADC2 CH4 | Touch 4 | ✅ | ✅ | HSPI MOSI | ✅ Safe. |
| 14 | I/O | ADC2 CH6 | Touch 6 | ✅ | ✅ | HSPI CLK | ✅ Safe. |
| 15 | I/O | ADC2 CH3 | Touch 3 | ✅ | ✅ | HSPI SS | ⚠️ **Strapping pin** — controls boot log output. Safe after boot. |
| 16 | I/O | — | — | ✅ | ✅ | — | ✅ Safe. Often used for UART2 RX (reassignable). |
| 17 | I/O | — | — | ✅ | ✅ | — | ✅ Safe. Often used for UART2 TX (reassignable). |
| 18 | I/O | — | — | ✅ | ✅ | VSPI CLK | ✅ Safe. Default VSPI clock. |
| 19 | I/O | — | — | ✅ | ✅ | VSPI MISO | ✅ Safe. Default VSPI MISO. |
| 21 | I/O | — | — | ✅ | **SDA** | — | ✅ Safe. **Default I2C SDA.** |
| 22 | I/O | — | — | ✅ | **SCL** | — | ✅ Safe. **Default I2C SCL.** |
| 23 | I/O | — | — | ✅ | ✅ | VSPI MOSI | ✅ Safe. Default VSPI MOSI. |
| 25 | I/O | ADC2 CH8 | — | ✅ | ✅ | — | ✅ Safe. Also DAC1 output. |
| 26 | I/O | ADC2 CH9 | — | ✅ | ✅ | — | ✅ Safe. Also DAC2 output. |
| 27 | I/O | ADC2 CH7 | Touch 7 | ✅ | ✅ | — | ✅ Safe. |
| 32 | I/O | ADC1 CH4 | Touch 9 | ✅ | ✅ | — | ✅ Safe. |
| 33 | I/O | ADC1 CH5 | Touch 8 | ✅ | ✅ | — | ✅ Safe. |
| 34 | **Input only** | ADC1 CH6 | — | ❌ | ❌ | — | ⚠️ Input only — no internal pull-up/pull-down. |
| 35 | **Input only** | ADC1 CH7 | — | ❌ | ❌ | — | ⚠️ Input only — no internal pull-up/pull-down. |
| 36 (VP) | **Input only** | ADC1 CH0 | — | ❌ | ❌ | — | ⚠️ Input only — no internal pull-up/pull-down. |
| 39 (VN) | **Input only** | ADC1 CH3 | — | ❌ | ❌ | — | ⚠️ Input only — no internal pull-up/pull-down. |

### ESP32 ADC Notes

- **ADC1** (GPIOs 32–39): Always available. Use these for reliable analog reads.
- **ADC2** (GPIOs 0, 2, 4, 12–15, 25–27): **Cannot be used while WiFi is active.** Since this toolkit always enables WiFi, prefer ADC1 pins for analog input.
- Attenuation settings control the input voltage range:

| Attenuation | Voltage Range | Config Value |
|-------------|---------------|--------------|
| 0 dB | 0 – 1.1 V | `"0db"` |
| 2.5 dB | 0 – 1.5 V | `"2.5db"` |
| 6 dB | 0 – 2.2 V | `"6db"` |
| 11 dB | 0 – 3.3 V | `"11db"` (default) |

### ESP32 Recommended Safe Pins

**Best general-purpose pins:** 4, 5, 13, 14, 16, 17, 18, 19, 21, 22, 23, 25, 26, 27, 32, 33

**Best ADC pins (WiFi-safe):** 32, 33, 34, 35, 36, 39

---

## ESP32-C3 (RISC-V)

The ESP32-C3 has 22 GPIO pins (GPIO 0–21). It is a single-core RISC-V chip
with no DAC, no touch sensing, and only ADC1 (no ADC2).

### GPIO Table

| GPIO | Direction | ADC | PWM | I2C | Notes |
|------|-----------|-----|-----|-----|-------|
| 0 | I/O | ADC1 CH0 | ✅ | ✅ | ✅ Safe. |
| 1 | I/O | ADC1 CH1 | ✅ | ✅ | ✅ Safe. |
| 2 | I/O | ADC1 CH2 | ✅ | ✅ | ⚠️ **Strapping pin** — controls boot mode. Safe after boot. |
| 3 | I/O | ADC1 CH3 | ✅ | ✅ | ✅ Safe. |
| 4 | I/O | ADC1 CH4 | ✅ | ✅ | ✅ Safe. |
| 5 | I/O | — | ✅ | ✅ | ✅ Safe. Good general-purpose pin. |
| 6 | I/O | — | ✅ | **SDA** | ✅ Safe. **Default I2C SDA** in this toolkit. |
| 7 | I/O | — | ✅ | **SCL** | ✅ Safe. **Default I2C SCL** in this toolkit. |
| 8 | I/O | — | ✅ | ✅ | ⚠️ **Strapping pin** — controls boot message printing. Often connected to onboard RGB LED (if present). Safe after boot. |
| 9 | I/O | — | ✅ | ✅ | ⚠️ **Strapping pin** — controls boot source. Connected to BOOT button on most dev boards. Safe after boot. |
| 10 | I/O | — | ✅ | ✅ | ✅ Safe. Good for NeoPixel data pin. |
| 11 | I/O | — | ✅ | ✅ | ❌ **Connected to internal flash (VDD_SPI).** Avoid on most modules. |
| 12 | I/O | — | ✅ | ✅ | ❌ **Connected to internal SPI flash (SPIHD).** Do not use. |
| 13 | I/O | — | ✅ | ✅ | ❌ **Connected to internal SPI flash (SPIWP).** Do not use. |
| 14 | I/O | — | ✅ | ✅ | ❌ **Connected to internal SPI flash (SPICS0).** Do not use. |
| 15 | I/O | — | ✅ | ✅ | ❌ **Connected to internal SPI flash (SPICLK).** Do not use. |
| 16 | I/O | — | ✅ | ✅ | ❌ **Connected to internal SPI flash (SPID).** Do not use. |
| 17 | I/O | — | ✅ | ✅ | ❌ **Connected to internal SPI flash (SPIQ).** Do not use. |
| 18 | I/O | — | ✅ | ✅ | ✅ Safe. USB D- on USB-equipped boards (detachable from USB in software). |
| 19 | I/O | — | ✅ | ✅ | ✅ Safe. USB D+ on USB-equipped boards (detachable from USB in software). |
| 20 | **Input only** | — | ❌ | ❌ | ❌ **UART0 RX** — used by REPL/serial input. Do not use. |
| 21 | I/O | — | ❌ | ❌ | ❌ **UART0 TX** — used by REPL/serial output. Do not use. |

### ESP32-C3 ADC Notes

- **ADC1 only**: GPIOs 0–4 (5 channels). No ADC2 exists on the C3.
- ADC works normally while WiFi is active (unlike ESP32 ADC2).
- Same attenuation settings as the original ESP32 (see table above).

### ESP32-C3 Recommended Safe Pins

**Best general-purpose I/O:** 0, 1, 3, 4, 5, 6, 7, 10, 18, 19

**Best ADC pins:** 0, 1, 3, 4 (GPIO 2 also works but is a strapping pin)

**Default I2C:** SDA = GPIO 6, SCL = GPIO 7

**Default NeoPixel:** GPIO 10

> **Note:** The templates in this toolkit default to ESP32-C3 pin assignments.
> If you are using an original ESP32, you will need to update pin numbers in
> your `config.json`.

---

## ESP32-S3 (Dual-Core Xtensa LX7)

The ESP32-S3 has up to 45 GPIO pins (GPIO 0–21, 26–48) with dual-core
Xtensa LX7, USB OTG, USB JTAG, and extended ADC/touch channels.
GPIOs 22–25 do not exist on the WROOM-1 module.

### Key Differences from ESP32

| Feature | ESP32 | ESP32-S3 |
|---------|-------|----------|
| CPU | Dual Xtensa LX6 | Dual Xtensa LX7 |
| ADC channels | ADC1 (8) + ADC2 (10) | ADC1 (10) + ADC2 (10) |
| Touch pins | 10 | 14 |
| USB | No native | USB OTG + USB JTAG |
| DAC | 2 channels | None |
| Max GPIOs | 34 | 45 |

### GPIO Table

| GPIO | Direction | ADC | Touch | PWM | I2C | Notes |
|------|-----------|-----|-------|-----|-----|-------|
| 0 | I/O | — | — | ✅ | ✅ | ⚠️ **Strapping pin** — controls boot mode. Safe after boot. |
| 1 | I/O | ADC1 CH0 | Touch 1 | ✅ | ✅ | ✅ Safe. |
| 2 | I/O | ADC1 CH1 | Touch 2 | ✅ | ✅ | ✅ Safe. |
| 3 | I/O | ADC1 CH2 | Touch 3 | ✅ | ✅ | ⚠️ **Strapping pin** — JTAG signal select. Safe after boot. |
| 4 | I/O | ADC1 CH3 | Touch 4 | ✅ | ✅ | ✅ Safe. Good general-purpose pin. |
| 5 | I/O | ADC1 CH4 | Touch 5 | ✅ | ✅ | ✅ Safe. |
| 6 | I/O | ADC1 CH5 | Touch 6 | ✅ | ✅ | ✅ Safe. |
| 7 | I/O | ADC1 CH6 | Touch 7 | ✅ | ✅ | ✅ Safe. |
| 8 | I/O | ADC1 CH7 | Touch 8 | ✅ | **SDA** | ✅ Safe. **Default I2C SDA** in this toolkit. |
| 9 | I/O | ADC1 CH8 | Touch 9 | ✅ | **SCL** | ✅ Safe. **Default I2C SCL** in this toolkit. |
| 10 | I/O | ADC1 CH9 | Touch 10 | ✅ | ✅ | ✅ Safe. |
| 11 | I/O | ADC2 CH0 | Touch 11 | ✅ | ✅ | ⚠️ VDD_SPI power supply pin on some modules. Check your board. |
| 12 | I/O | ADC2 CH1 | Touch 12 | ✅ | ✅ | ✅ Safe. |
| 13 | I/O | ADC2 CH2 | Touch 13 | ✅ | ✅ | ✅ Safe. |
| 14 | I/O | ADC2 CH3 | Touch 14 | ✅ | ✅ | ✅ Safe. |
| 15 | I/O | ADC2 CH4 | — | ✅ | ✅ | ✅ Safe. |
| 16 | I/O | ADC2 CH5 | — | ✅ | ✅ | ✅ Safe. |
| 17 | I/O | ADC2 CH6 | — | ✅ | ✅ | ✅ Safe. |
| 18 | I/O | ADC2 CH7 | — | ✅ | ✅ | ✅ Safe. |
| 19 | I/O | ADC2 CH8 | — | ✅ | ✅ | ⚠️ **USB D-** — avoid if using native USB. |
| 20 | I/O | ADC2 CH9 | — | ✅ | ✅ | ⚠️ **USB D+** — avoid if using native USB. |
| 21 | I/O | — | — | ✅ | ✅ | ✅ Safe. |
| 26 | I/O | — | — | — | — | ❌ **Connected to SPI flash (SPICS1).** Do not use. |
| 27 | I/O | — | — | — | — | ❌ **Connected to SPI flash (SPIHD).** Do not use. |
| 28 | I/O | — | — | — | — | ❌ **Connected to SPI flash (SPIWP).** Do not use. |
| 29 | I/O | — | — | — | — | ❌ **Connected to SPI flash (SPICS0).** Do not use. |
| 30 | I/O | — | — | — | — | ❌ **Connected to SPI flash (SPICLK).** Do not use. |
| 31 | I/O | — | — | — | — | ❌ **Connected to SPI flash (SPIQ).** Do not use. |
| 32 | I/O | — | — | — | — | ❌ **Connected to SPI flash (SPID).** Do not use. |
| 33 | I/O | — | — | ✅ | ✅ | ⚠️ Connected to octal PSRAM on some modules. Check your board. |
| 34 | I/O | — | — | ✅ | ✅ | ⚠️ Connected to octal PSRAM on some modules. Check your board. |
| 35 | I/O | — | — | ✅ | ✅ | ⚠️ Connected to octal PSRAM on some modules. Check your board. |
| 36 | I/O | — | — | ✅ | ✅ | ⚠️ Connected to octal PSRAM on some modules. Check your board. |
| 37 | I/O | — | — | ✅ | ✅ | ⚠️ Connected to octal PSRAM on some modules. Check your board. |
| 38 | I/O | — | — | ✅ | ✅ | ✅ Safe. Good general-purpose pin. |
| 39 | I/O | — | — | ✅ | ✅ | ✅ Safe. JTAG MTCK — usable as GPIO when not debugging. |
| 40 | I/O | — | — | ✅ | ✅ | ✅ Safe. JTAG MTDO — usable as GPIO when not debugging. |
| 41 | I/O | — | — | ✅ | ✅ | ✅ Safe. JTAG MTDI — usable as GPIO when not debugging. |
| 42 | I/O | — | — | ✅ | ✅ | ✅ Safe. JTAG MTMS — usable as GPIO when not debugging. |
| 43 | I/O | — | — | ✅ | — | ❌ **UART0 TX** — used by REPL/serial output. Do not use. |
| 44 | I/O | — | — | ✅ | — | ❌ **UART0 RX** — used by REPL/serial input. Do not use. |
| 45 | I/O | — | — | ✅ | ✅ | ⚠️ **Strapping pin** — controls VDD_SPI voltage. Safe after boot. |
| 46 | I/O | — | — | ✅ | ✅ | ⚠️ **Strapping pin** — controls boot log output. Safe after boot. |
| 47 | I/O | — | — | ✅ | ✅ | ✅ Safe. |
| 48 | I/O | — | — | ✅ | ✅ | ✅ Safe. Often connected to onboard RGB LED (NeoPixel). |

### ESP32-S3 ADC Notes

- **ADC1** (GPIOs 1–10): Always available. Use these for reliable analog reads.
- **ADC2** (GPIOs 11–20): **Cannot be used while WiFi is active.** Since this toolkit always enables WiFi, prefer ADC1 pins for analog input.
- Same attenuation settings as the original ESP32 (see ESP32 ADC Notes table above).

### ESP32-S3 Recommended Safe Pins

**Best general-purpose I/O:** 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15, 16, 17, 18, 21, 38, 39, 40, 41, 42, 47, 48

**Best ADC pins (WiFi-safe):** 1, 2, 4, 5, 6, 7, 8, 9, 10 (ADC1 only)

**Default I2C:** SDA = GPIO 8, SCL = GPIO 9

**Default NeoPixel:** GPIO 48

> **Note:** GPIOs 22–25 do not exist on the ESP32-S3-WROOM module. GPIOs 33–37
> may be unavailable on modules with octal PSRAM — check your board's schematic.
> For the full datasheet, see the
> [Espressif ESP32-S3 datasheet](https://www.espressif.com/sites/default/files/documentation/esp32-s3_datasheet_en.pdf).

---

## ESP32-S2 (Single-Core Xtensa LX7)

The ESP32-S2 is a single-core Xtensa LX7 chip with native USB, 43 GPIOs
(GPIO 0–21, 26–46), ADC1 (10 channels) + ADC2 (10 channels), touch sensing
(14 channels), DAC (2 channels), and no Bluetooth.
GPIOs 22–25 do not exist on the WROOM module.

### Key Differences from ESP32

| Feature | ESP32 | ESP32-S2 |
|---------|-------|----------|
| CPU | Dual Xtensa LX6 | **Single** Xtensa LX7 |
| ADC channels | ADC1 (8) + ADC2 (10) | ADC1 (10) + ADC2 (10) |
| Touch pins | 10 | 14 |
| USB | No native | Native USB (CDC/JTAG) |
| DAC | 2 channels | 2 channels |
| Bluetooth | Classic + BLE | **None** |
| Max GPIOs | 34 | 43 |

### GPIO Table

| GPIO | Direction | ADC | Touch | PWM | I2C | Notes |
|------|-----------|-----|-------|-----|-----|-------|
| 0 | I/O | — | — | ✅ | ✅ | ⚠️ **Strapping pin** — controls boot mode. Safe after boot. |
| 1 | I/O | ADC1 CH0 | Touch 1 | ✅ | ✅ | ✅ Safe. |
| 2 | I/O | ADC1 CH1 | Touch 2 | ✅ | ✅ | ✅ Safe. |
| 3 | I/O | ADC1 CH2 | Touch 3 | ✅ | ✅ | ✅ Safe. |
| 4 | I/O | ADC1 CH3 | Touch 4 | ✅ | ✅ | ✅ Safe. Good general-purpose pin. |
| 5 | I/O | ADC1 CH4 | Touch 5 | ✅ | ✅ | ✅ Safe. |
| 6 | I/O | ADC1 CH5 | Touch 6 | ✅ | ✅ | ✅ Safe. |
| 7 | I/O | ADC1 CH6 | Touch 7 | ✅ | ✅ | ✅ Safe. |
| 8 | I/O | ADC1 CH7 | Touch 8 | ✅ | **SDA** | ✅ Safe. **Default I2C SDA** in this toolkit. |
| 9 | I/O | ADC1 CH8 | Touch 9 | ✅ | **SCL** | ✅ Safe. **Default I2C SCL** in this toolkit. |
| 10 | I/O | ADC1 CH9 | Touch 10 | ✅ | ✅ | ✅ Safe. |
| 11 | I/O | ADC2 CH0 | Touch 11 | ✅ | ✅ | ✅ Safe. |
| 12 | I/O | ADC2 CH1 | Touch 12 | ✅ | ✅ | ✅ Safe. |
| 13 | I/O | ADC2 CH2 | Touch 13 | ✅ | ✅ | ✅ Safe. |
| 14 | I/O | ADC2 CH3 | Touch 14 | ✅ | ✅ | ✅ Safe. |
| 15 | I/O | ADC2 CH4 | — | ✅ | ✅ | ✅ Safe. XTAL_32K_P — usable if not using external 32 kHz crystal. |
| 16 | I/O | ADC2 CH5 | — | ✅ | ✅ | ✅ Safe. XTAL_32K_N — usable if not using external 32 kHz crystal. |
| 17 | I/O | ADC2 CH6 | — | ✅ | ✅ | ✅ Safe. Also DAC1 output. |
| 18 | I/O | ADC2 CH7 | — | ✅ | ✅ | ✅ Safe. Also DAC2 output. |
| 19 | I/O | ADC2 CH8 | — | ✅ | ✅ | ⚠️ **USB D-** — avoid if using native USB. |
| 20 | I/O | ADC2 CH9 | — | ✅ | ✅ | ⚠️ **USB D+** — avoid if using native USB. |
| 21 | I/O | — | — | ✅ | ✅ | ✅ Safe. |
| 26 | I/O | — | — | — | — | ❌ **Connected to SPI flash (SPICS1).** Do not use. |
| 27 | I/O | — | — | — | — | ❌ **Connected to SPI flash (SPIHD).** Do not use. |
| 28 | I/O | — | — | — | — | ❌ **Connected to SPI flash (SPIWP).** Do not use. |
| 29 | I/O | — | — | — | — | ❌ **Connected to SPI flash (SPICS0).** Do not use. |
| 30 | I/O | — | — | — | — | ❌ **Connected to SPI flash (SPICLK).** Do not use. |
| 31 | I/O | — | — | — | — | ❌ **Connected to SPI flash (SPIQ).** Do not use. |
| 32 | I/O | — | — | — | — | ❌ **Connected to SPI flash (SPID).** Do not use. |
| 33 | I/O | — | — | ✅ | ✅ | ⚠️ Connected to PSRAM on some modules. Check your board. |
| 34 | I/O | — | — | ✅ | ✅ | ⚠️ Connected to PSRAM on some modules. Check your board. |
| 35 | I/O | — | — | ✅ | ✅ | ⚠️ Connected to PSRAM on some modules. Check your board. |
| 36 | I/O | — | — | ✅ | ✅ | ⚠️ Connected to PSRAM on some modules. Check your board. |
| 37 | I/O | — | — | ✅ | ✅ | ⚠️ Connected to PSRAM on some modules. Check your board. |
| 38 | I/O | — | — | ✅ | ✅ | ✅ Safe. Good general-purpose pin. |
| 39 | I/O | — | — | ✅ | ✅ | ✅ Safe. JTAG MTCK — usable as GPIO when not debugging. |
| 40 | I/O | — | — | ✅ | ✅ | ✅ Safe. JTAG MTDO — usable as GPIO when not debugging. |
| 41 | I/O | — | — | ✅ | ✅ | ✅ Safe. JTAG MTDI — usable as GPIO when not debugging. |
| 42 | I/O | — | — | ✅ | ✅ | ✅ Safe. JTAG MTMS — usable as GPIO when not debugging. |
| 43 | I/O | — | — | ✅ | — | ❌ **UART0 TX** — used by REPL/serial output. Do not use. |
| 44 | I/O | — | — | ✅ | — | ❌ **UART0 RX** — used by REPL/serial input. Do not use. |
| 45 | I/O | — | — | ✅ | ✅ | ⚠️ **Strapping pin** — controls VDD_SPI voltage. Safe after boot. |
| 46 | **Input only** | — | — | ❌ | ❌ | ⚠️ **Strapping pin** — controls boot log. Input only, no internal pull-up/down. |

### ESP32-S2 ADC Notes

- **ADC1** (GPIOs 1–10): Always available. Use these for reliable analog reads.
- **ADC2** (GPIOs 11–20): **Cannot be used while WiFi is active.** Since this toolkit always enables WiFi, prefer ADC1 pins for analog input.
- Same attenuation settings as the original ESP32 (see ESP32 ADC Notes table above).
- **DAC**: GPIO 17 (DAC1) and GPIO 18 (DAC2) can output analog voltage (8-bit, 0–3.3 V).

### ESP32-S2 Recommended Safe Pins

**Best general-purpose I/O:** 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 21, 38, 39, 40, 41, 42

**Best ADC pins (WiFi-safe):** 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 (ADC1 only)

**Default I2C:** SDA = GPIO 8, SCL = GPIO 9

**Default NeoPixel:** GPIO 38

> **Note:** GPIOs 22–25 do not exist on the ESP32-S2-WROOM module. GPIOs 33–37
> may be unavailable on modules with PSRAM — check your board's schematic.
> The ESP32-S2 has **no Bluetooth** — if you need BLE, use the ESP32, C3, or S3.
> For the full datasheet, see the
> [Espressif ESP32-S2 datasheet](https://www.espressif.com/sites/default/files/documentation/esp32-s2_datasheet_en.pdf).

---

## Pin Safety Summary — All Chips

### Never Touch These Pins

| Chip | Pins | Reason |
|------|------|--------|
| ESP32 | 6, 7, 8, 9, 10, 11 | Connected to internal SPI flash |
| ESP32 | 1, 3 | UART0 TX/RX (serial REPL) |
| ESP32-C3 | 11, 12, 13, 14, 15, 16, 17 | Connected to internal SPI flash |
| ESP32-C3 | 20, 21 | UART0 RX/TX (serial REPL) |
| ESP32-S2 | 26, 27, 28, 29, 30, 31, 32 | Connected to internal SPI flash |
| ESP32-S2 | 43, 44 | UART0 TX/RX (serial REPL) |
| ESP32-S3 | 26, 27, 28, 29, 30, 31, 32 | Connected to internal SPI flash |
| ESP32-S3 | 43, 44 | UART0 TX/RX (serial REPL) |

### Safe After Boot (Strapping Pins)

| Chip | Pins | Notes |
|------|------|-------|
| ESP32 | 0, 2, 5, 12, 15 | Don't drive during reset/boot sequence. Safe for GPIO/PWM after boot completes. |
| ESP32-C3 | 2, 8, 9 | Same rule — don't drive during boot. GPIO 9 is often the BOOT button. |
| ESP32-S2 | 0, 45, 46 | GPIO 0 = boot mode, GPIO 45 = VDD_SPI, GPIO 46 = boot log (input only). |
| ESP32-S3 | 0, 3, 45, 46 | GPIO 0 = boot mode, GPIO 3 = JTAG select, GPIO 45/46 = VDD_SPI / boot log. |

### Best Pins for Common Tasks

| Task | ESP32 | ESP32-C3 | ESP32-S2 | ESP32-S3 |
|------|-------|----------|----------|----------|
| LED output | 4, 16, 17, 25, 26 | 3, 4, 5, 10 | 4, 5, 6, 7, 38 | 4, 5, 6, 7, 38, 48 |
| Button input | 4, 16, 17, 32, 33 | 3, 4, 5, 9 (BOOT btn) | 4, 5, 6, 7, 38 | 4, 5, 6, 7, 38, 47 |
| ADC (with WiFi) | 32, 33, 34, 35, 36, 39 | 0, 1, 3, 4 | 1–10 (ADC1) | 1–10 (ADC1) |
| I2C (SDA/SCL) | 21 / 22 | 6 / 7 | 8 / 9 | 8 / 9 |
| NeoPixel data | 4, 16, 18 | 10 | 38 | 48 |
| PWM output | 4, 5, 16, 17, 18, 25, 26 | 0, 1, 3, 4, 5, 10 | 4, 5, 6, 7, 38 | 4, 5, 6, 7, 38, 47, 48 |
| SPI (CLK/MOSI/MISO) | 18 / 23 / 19 | Software SPI | Software SPI | Software SPI |