"""
PWM control routes for ESP32 MicroPython.

Provides REST API endpoints for PWM output control including
frequency and duty cycle adjustment.

Usage:
    from pwm_handler import register_routes
    register_routes(app, config)
"""

from machine import Pin, PWM
import gc

# ESP32-C3 valid output pins
OUTPUT_PINS = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 18, 19}

# UART pins — never allow output on these
FORBIDDEN_PINS = {20, 21}

# Module-level pin registry: {pin_num: {"mode": "PWM", "pwm": PWM, "pin": Pin}}
PIN_REGISTRY = {}


def _resolve_pin(pin_arg, config):
    """Resolve a pin argument to an integer pin number.

    Accepts a raw integer, a numeric string, or a named alias
    defined in config["pin_aliases"].
    """
    # Try numeric first
    try:
        return int(pin_arg)
    except (ValueError, TypeError):
        pass

    # Try alias lookup
    aliases = config.get("pin_aliases", {})
    if pin_arg in aliases:
        return int(aliases[pin_arg])

    return None


def _check_forbidden_output(pin_num):
    """Check if a pin is forbidden for output use.

    Returns an error message string if forbidden, or None if the pin is safe.
    """
    if pin_num == 20:
        return "Pin 20 is the UART RX line and cannot be used for output. Using it would break your serial connection to the board."
    if pin_num == 21:
        return "Pin 21 is the UART TX line and cannot be used for output. Using it would break your serial connection to the board."
    return None


def _check_memory():
    """Run garbage collection and return a low-memory warning if free RAM is below 50 KB.

    Returns a warning string or None.
    """
    gc.collect()
    free = gc.mem_free()
    if free < 51200:
        return "Warning: free memory is low ({} bytes). Consider releasing unused PWM pins.".format(free)
    return None


def _pin_state(pin_num):
    """Build a state dictionary for a pin currently in PWM mode.

    Returns a dict with pin number, mode, frequency, duty_u16, and duty percentage.
    If the pin is not registered in PWM mode, returns a minimal dict indicating it is inactive.
    """
    entry = PIN_REGISTRY.get(pin_num)
    if entry is None or entry.get("mode") != "PWM":
        return {
            "pin": pin_num,
            "mode": "inactive",
            "freq": 0,
            "duty_u16": 0,
            "duty_pct": 0.0,
        }

    pwm = entry["pwm"]
    freq = pwm.freq()
    duty = pwm.duty_u16()
    duty_pct = round(duty / 65535 * 100, 2)

    return {
        "pin": pin_num,
        "mode": "PWM",
        "freq": freq,
        "duty_u16": duty,
        "duty_pct": duty_pct,
    }


def register_routes(app, config):
    """Register all PWM control routes on the given Microdot app."""

    @app.post("/api/pwm/<pin>/start")
    async def pwm_start(request, pin):
        """Initialize PWM on a pin with the given frequency and duty cycle."""
        pin_num = _resolve_pin(pin, config)
        if pin_num is None:
            return {"error": "Could not resolve '{}' to a valid pin number. Check your pin_aliases in config.json.".format(pin)}, 400

        # Forbidden pin check
        err = _check_forbidden_output(pin_num)
        if err:
            return {"error": err}, 403

        # Valid output pin check
        if pin_num not in OUTPUT_PINS:
            return {"error": "Pin {} is not a valid output pin on this board. Valid output pins are: {}".format(pin_num, sorted(OUTPUT_PINS))}, 400

        # Mode conflict check — pin already in use for something other than PWM
        existing = PIN_REGISTRY.get(pin_num)
        if existing and existing.get("mode") != "PWM":
            return {
                "error": "Pin {} is already in use as {} mode. Stop the current mode before starting PWM.".format(pin_num, existing.get("mode")),
            }, 409

        # Parse body
        body = request.json if request.json else {}
        freq = body.get("freq", 1000)
        duty_u16 = body.get("duty_u16", 0)

        # Validate frequency
        try:
            freq = int(freq)
        except (ValueError, TypeError):
            return {"error": "Frequency must be an integer, got '{}'.".format(freq)}, 400

        if freq < 1 or freq > 40000000:
            return {"error": "Frequency must be between 1 and 40000000 Hz, got {}.".format(freq)}, 400

        # Validate duty_u16
        try:
            duty_u16 = int(duty_u16)
        except (ValueError, TypeError):
            return {"error": "Duty cycle (duty_u16) must be an integer, got '{}'.".format(duty_u16)}, 400

        if duty_u16 < 0 or duty_u16 > 65535:
            return {"error": "Duty cycle (duty_u16) must be between 0 and 65535, got {}.".format(duty_u16)}, 400

        # If already running PWM on this pin, deinit first
        if existing and existing.get("mode") == "PWM":
            try:
                existing["pwm"].deinit()
            except Exception:
                pass

        # Initialize PWM
        try:
            p = Pin(pin_num, Pin.OUT)
            pwm = PWM(p, freq=freq, duty_u16=duty_u16)
        except Exception as e:
            return {"error": "Failed to initialize PWM on pin {}: {}".format(pin_num, str(e))}, 500

        PIN_REGISTRY[pin_num] = {"mode": "PWM", "pwm": pwm, "pin": p}

        mem_warn = _check_memory()
        result = _pin_state(pin_num)
        result["status"] = "started"
        if mem_warn:
            result["warning"] = mem_warn

        return result

    @app.post("/api/pwm/<pin>/duty")
    async def pwm_set_duty(request, pin):
        """Set the duty cycle on a pin already running PWM."""
        pin_num = _resolve_pin(pin, config)
        if pin_num is None:
            return {"error": "Could not resolve '{}' to a valid pin number.".format(pin)}, 400

        entry = PIN_REGISTRY.get(pin_num)
        if entry is None or entry.get("mode") != "PWM":
            return {"error": "Pin {} is not currently in PWM mode. Start PWM first with POST /api/pwm/{}/start.".format(pin_num, pin_num)}, 400

        body = request.json if request.json else {}
        duty_u16 = body.get("duty_u16")

        if duty_u16 is None:
            return {"error": "Missing required field 'duty_u16' in request body."}, 400

        try:
            duty_u16 = int(duty_u16)
        except (ValueError, TypeError):
            return {"error": "Duty cycle (duty_u16) must be an integer, got '{}'.".format(duty_u16)}, 400

        if duty_u16 < 0 or duty_u16 > 65535:
            return {"error": "Duty cycle (duty_u16) must be between 0 and 65535, got {}.".format(duty_u16)}, 400

        try:
            entry["pwm"].duty_u16(duty_u16)
        except Exception as e:
            return {"error": "Failed to set duty cycle on pin {}: {}".format(pin_num, str(e))}, 500

        return _pin_state(pin_num)

    @app.post("/api/pwm/<pin>/freq")
    async def pwm_set_freq(request, pin):
        """Set the frequency on a pin already running PWM."""
        pin_num = _resolve_pin(pin, config)
        if pin_num is None:
            return {"error": "Could not resolve '{}' to a valid pin number.".format(pin)}, 400

        entry = PIN_REGISTRY.get(pin_num)
        if entry is None or entry.get("mode") != "PWM":
            return {"error": "Pin {} is not currently in PWM mode. Start PWM first with POST /api/pwm/{}/start.".format(pin_num, pin_num)}, 400

        body = request.json if request.json else {}
        freq = body.get("freq")

        if freq is None:
            return {"error": "Missing required field 'freq' in request body."}, 400

        try:
            freq = int(freq)
        except (ValueError, TypeError):
            return {"error": "Frequency must be an integer, got '{}'.".format(freq)}, 400

        if freq < 1 or freq > 40000000:
            return {"error": "Frequency must be between 1 and 40000000 Hz, got {}.".format(freq)}, 400

        try:
            entry["pwm"].freq(freq)
        except Exception as e:
            return {"error": "Failed to set frequency on pin {}: {}".format(pin_num, str(e))}, 500

        return _pin_state(pin_num)

    @app.post("/api/pwm/<pin>/stop")
    async def pwm_stop(request, pin):
        """Stop PWM on a pin, deinitialize and release it from the registry."""
        pin_num = _resolve_pin(pin, config)
        if pin_num is None:
            return {"error": "Could not resolve '{}' to a valid pin number.".format(pin)}, 400

        entry = PIN_REGISTRY.get(pin_num)
        if entry is None or entry.get("mode") != "PWM":
            return {"error": "Pin {} is not currently in PWM mode. Nothing to stop.".format(pin_num)}, 400

        try:
            entry["pwm"].deinit()
        except Exception:
            pass

        del PIN_REGISTRY[pin_num]

        return {"pin": pin_num, "status": "stopped", "mode": "released"}

    @app.get("/api/pwm/<pin>")
    async def pwm_get_state(request, pin):
        """Read the current PWM state (frequency, duty cycle) for a pin."""
        pin_num = _resolve_pin(pin, config)
        if pin_num is None:
            return {"error": "Could not resolve '{}' to a valid pin number.".format(pin)}, 400

        entry = PIN_REGISTRY.get(pin_num)
        if entry is None or entry.get("mode") != "PWM":
            return {"error": "Pin {} is not currently in PWM mode. Start PWM first with POST /api/pwm/{}/start.".format(pin_num, pin_num)}, 404

        return _pin_state(pin_num)
