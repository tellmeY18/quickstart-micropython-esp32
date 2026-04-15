"""
pwm_fade.py — Fade an LED using PWM duty cycle

Smoothly ramps an LED from off to full brightness and back down,
using hardware PWM at 1 kHz. Runs 3 full cycles then stops.

Wiring:
    - Connect an LED's anode (long leg) to GPIO 5
    - Connect a 330 ohm resistor from the LED's cathode (short leg) to GND
    - No other components needed

Run:
    esp run examples/pwm_fade.py
"""

from machine import Pin, PWM
import time

LED_PIN = 5
FREQ = 1000       # PWM frequency in Hz
STEPS = 50        # number of steps per ramp direction
STEP_DELAY = 40   # milliseconds between steps (2s per ramp = 50 * 40ms)
CYCLES = 3

pwm = PWM(Pin(LED_PIN), freq=FREQ)
print("PWM fade on GPIO {} — {} Hz, {} cycles".format(LED_PIN, FREQ, CYCLES))

try:
    for cycle in range(CYCLES):
        print("Cycle {}/{}".format(cycle + 1, CYCLES))

        # Ramp up: 0% -> 100%
        for i in range(STEPS + 1):
            duty = i * 65535 // STEPS
            pwm.duty_u16(duty)
            pct = i * 100 // STEPS
            print("  UP   duty={:5d}  ({}%)".format(duty, pct))
            time.sleep_ms(STEP_DELAY)

        # Ramp down: 100% -> 0%
        for i in range(STEPS, -1, -1):
            duty = i * 65535 // STEPS
            pwm.duty_u16(duty)
            pct = i * 100 // STEPS
            print("  DOWN duty={:5d}  ({}%)".format(duty, pct))
            time.sleep_ms(STEP_DELAY)

    print("Done — {} cycles complete".format(CYCLES))
finally:
    pwm.deinit()
    print("PWM deinitialized on GPIO {}".format(LED_PIN))
