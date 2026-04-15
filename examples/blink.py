"""blink.py — Toggle the on-board LED on and off.

Wiring: No external wiring needed. Uses the on-board LED connected to GPIO 8
        (active-low on most ESP32-C3 dev boards).

Usage:  esp run examples/blink.py
"""

from machine import Pin
import time

LED_PIN = 8
INTERVAL_MS = 500
CYCLES = 20

led = Pin(LED_PIN, Pin.OUT)

print("Blinking LED on GPIO {} — {} cycles, {}ms interval".format(LED_PIN, CYCLES, INTERVAL_MS))

for i in range(CYCLES):
    led.value(1)
    print("LED ON  (cycle {}/{})".format(i + 1, CYCLES))
    time.sleep_ms(INTERVAL_MS)

    led.value(0)
    print("LED OFF (cycle {}/{})".format(i + 1, CYCLES))
    time.sleep_ms(INTERVAL_MS)

led.value(0)
print("Done — LED off.")
