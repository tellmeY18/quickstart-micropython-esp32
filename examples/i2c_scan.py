# i2c_scan.py — Scan the I2C bus and list discovered devices
#
# Wiring:
#   - Connect your I2C device's SDA line to GPIO 6
#   - Connect your I2C device's SCL line to GPIO 7
#   - Connect GND to GND
#   - Add 4.7kΩ pull-up resistors from SDA to 3.3V and SCL to 3.3V
#     (many breakout boards include these already)
#
# Run:  esp run examples/i2c_scan.py

from machine import Pin, SoftI2C
import time

# Common I2C device addresses for quick identification
KNOWN_DEVICES = {
    0x20: "PCF8574 I/O Expander",
    0x23: "BH1750 Light Sensor",
    0x27: "PCF8574A I/O Expander / LCD Backpack",
    0x3C: "SSD1306 OLED Display",
    0x3D: "SSD1306 OLED Display (alt)",
    0x40: "INA219 Current Sensor / HDC1080 Temp/Humidity",
    0x44: "SHT30/SHT31 Temp/Humidity",
    0x48: "ADS1115 ADC / TMP102 Temp Sensor",
    0x50: "AT24C32 EEPROM",
    0x57: "AT24C32 EEPROM (alt) / MAX30102 Pulse Oximeter",
    0x68: "DS3231 RTC / MPU6050 IMU",
    0x76: "BME280 / BMP280 Pressure Sensor",
    0x77: "BME280 / BMP280 (alt address)",
}

SDA_PIN = 6
SCL_PIN = 7

print("I2C Bus Scanner")
print("===============")
print("SDA: GPIO {}".format(SDA_PIN))
print("SCL: GPIO {}".format(SCL_PIN))
print()

try:
    i2c = SoftI2C(sda=Pin(SDA_PIN), scl=Pin(SCL_PIN), freq=100000)
except Exception as e:
    print("ERROR: Failed to initialize I2C bus: {}".format(e))
    print("Check your wiring and pull-up resistors.")
    raise SystemExit

print("Scanning...")
time.sleep_ms(100)

devices = i2c.scan()

if not devices:
    print("No I2C devices found.")
    print()
    print("Troubleshooting:")
    print("  - Check wiring: SDA to GPIO {}, SCL to GPIO {}".format(SDA_PIN, SCL_PIN))
    print("  - Ensure pull-up resistors are present (4.7k to 3.3V)")
    print("  - Verify the device is powered")
else:
    print("Found {} device(s):".format(len(devices)))
    print()
    print("  Addr (dec)  Addr (hex)  Device")
    print("  ----------  ----------  ------")
    for addr in devices:
        name = KNOWN_DEVICES.get(addr, "(unknown)")
        print("  {:>10d}  0x{:02X}        {}".format(addr, addr, name))

print()
print("Scan complete.")
