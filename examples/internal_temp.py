# examples/internal_temp.py — Read the ESP32 internal temperature sensor
#
# Wiring: No external wiring needed.
#         Uses the built-in temperature sensor inside the ESP32 chip.
#
# Usage:  esp run examples/internal_temp.py
#
# Prints the chip's internal (die) temperature in Celsius every 2 seconds
# for 20 seconds, then exits. Note: this measures the silicon die temperature,
# NOT ambient room temperature. Expect values 30-60°C under normal operation.

import esp32
import time

print("=== ESP32 Internal Temperature Sensor ===")
print("Reading every 2 seconds for 20 seconds...\n")

DURATION_S = 20
INTERVAL_S = 2
readings = DURATION_S // INTERVAL_S

for i in range(readings):
    try:
        temp_c = esp32.mcu_temperature()
        temp_f = temp_c * 9.0 / 5.0 + 32.0
        elapsed = i * INTERVAL_S
        print("[{:>2d}s] Temperature: {:.1f} C  /  {:.1f} F".format(elapsed, temp_c, temp_f))
    except Exception as e:
        print("[{:>2d}s] Failed to read temperature: {}".format(i * INTERVAL_S, e))

    if i < readings - 1:
        time.sleep(INTERVAL_S)

print("\nDone. {} readings taken.".format(readings))
