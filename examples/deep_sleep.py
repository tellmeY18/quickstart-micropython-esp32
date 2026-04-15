"""deep_sleep.py — Enter deep sleep and wake on timer.

Demonstrates ESP32 deep sleep with a 5-second timer wake-up.
Prints the reset cause and wake reason on each boot.

Wiring: No external wiring needed.
        Note: The board will disconnect from USB serial during sleep.
        It will reconnect automatically when it wakes up.
        Run with: esp run examples/deep_sleep.py

Reset cause constants (machine.reset_cause()):
    1 = PWRON_RESET   — Power-on or EN pin reset
    2 = HARD_RESET    — Hard reset (RTC watchdog, brownout, etc.)
    3 = WDT_RESET     — Watchdog timer reset
    4 = DEEPSLEEP     — Wake from deep sleep
    5 = SOFT_RESET    — Soft reset (machine.reset() or Ctrl+D)

Wake reason constants (machine.wake_reason()):
    2 = PIN_WAKE      — Woke by external GPIO pin
    4 = TIMER_WAKE    — Woke by RTC timer
"""

import machine
import time

SLEEP_SECONDS = 5

RESET_CAUSES = {
    1: "PWRON_RESET (power-on or EN pin)",
    2: "HARD_RESET (RTC watchdog / brownout)",
    3: "WDT_RESET (watchdog timer)",
    4: "DEEPSLEEP_RESET (woke from deep sleep)",
    5: "SOFT_RESET (machine.reset() or Ctrl+D)",
}

WAKE_REASONS = {
    2: "PIN_WAKE (external GPIO)",
    4: "TIMER_WAKE (RTC timer)",
}

print()
print("=" * 44)
print("  Deep Sleep Demo")
print("=" * 44)

reset_cause = machine.reset_cause()
wake_reason = machine.wake_reason()

cause_str = RESET_CAUSES.get(reset_cause, "UNKNOWN ({})".format(reset_cause))
reason_str = WAKE_REASONS.get(wake_reason, "UNKNOWN ({})".format(wake_reason))

print("Reset cause : {}".format(cause_str))
print("Wake reason : {}".format(reason_str))

if reset_cause == 4:
    print(">> Resumed from deep sleep!")
else:
    print(">> Fresh boot (not waking from sleep)")

print()
print("Entering deep sleep for {} seconds...".format(SLEEP_SECONDS))
print("The board will disconnect from serial.")
print("It will reboot automatically when the timer expires.")
print()

time.sleep(1)

machine.deepsleep(SLEEP_SECONDS * 1000)
