"""
button_read.py — Read the BOOT button (GPIO 9) with internal pull-up.

Prints state changes (PRESSED / RELEASED) to the serial console.
Runs for 30 seconds then exits cleanly.

Wiring:
    No external wiring needed — uses the on-board BOOT button on GPIO 9.
    The BOOT button pulls GPIO 9 LOW when pressed (active-low).

Usage:
    esp run examples/button_read.py
"""

import machine
import time

BUTTON_PIN = 9
RUN_SECONDS = 30

btn = machine.Pin(BUTTON_PIN, machine.Pin.IN, machine.Pin.PULL_UP)

print("button_read: monitoring GPIO {} for {} seconds".format(BUTTON_PIN, RUN_SECONDS))
print("button_read: press the BOOT button to see state changes")
print()

last_state = btn.value()
state_name = "RELEASED" if last_state == 1 else "PRESSED"
print("  initial state: {} (raw={})".format(state_name, last_state))

start = time.ticks_ms()
press_count = 0

while time.ticks_diff(time.ticks_ms(), start) < RUN_SECONDS * 1000:
    current = btn.value()
    if current != last_state:
        if current == 0:
            state_name = "PRESSED"
            press_count += 1
        else:
            state_name = "RELEASED"
        elapsed = time.ticks_diff(time.ticks_ms(), start) // 1000
        print("  [{}s] {} (raw={})".format(elapsed, state_name, current))
        last_state = current
    time.sleep_ms(20)  # debounce delay

print()
print("button_read: done — {} presses detected in {} seconds".format(press_count, RUN_SECONDS))
