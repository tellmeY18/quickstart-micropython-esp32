"""adc_read.py — Read analog voltage from an ADC pin.

Wiring:
    Connect a potentiometer (or voltage divider) wiper to GPIO 4.
    Potentiometer outer pins go to 3.3V and GND.
    No wiring needed if you just want to see noise readings on a floating pin.

Run:
    esp run examples/adc_read.py

Reads ADC on GPIO 4 every second for 30 seconds.
Uses 11dB attenuation for full 0–3.3V range.
Prints both raw (0–65535) and calculated voltage.
"""

from machine import Pin, ADC
import time

PIN = 4
DURATION_S = 30
INTERVAL_S = 1

adc = ADC(Pin(PIN))
adc.atten(ADC.ATTN_11DB)  # Full range: 0 — 3.3V

print("ADC reader — GPIO {} with 11dB attenuation".format(PIN))
print("Reading every {}s for {}s".format(INTERVAL_S, DURATION_S))
print("{:<6} {:>8} {:>10}".format("Time", "Raw", "Voltage"))
print("-" * 28)

for i in range(DURATION_S // INTERVAL_S):
    raw = adc.read_u16()          # 0–65535
    uv = adc.read_uv()           # microvolts
    voltage = round(uv / 1_000_000, 3)
    print("{:<6} {:>8} {:>8.3f} V".format(i, raw, voltage))
    time.sleep(INTERVAL_S)

print("Done.")
