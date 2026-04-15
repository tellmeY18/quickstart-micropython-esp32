# gpio_handler.py — Digital GPIO control routes for ESP32-C3
#
# Registers REST API routes for reading and writing digital GPIO pins.
# This is the GPIO template's feature module — import register_routes()
# from main.py and call it before app.run().
#
# All pin sets are for the ESP32-C3. Adjust if targeting a different chip.

from machine import Pin
import esp32
import gc

# ---------- ESP32-C3 pin sets ----------

# All usable digital GPIO pins
DIGITAL_PINS = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 18, 19}

# Pins that can be driven as outputs
OUTPUT_PINS = DIGITAL_PINS

# Pins that can be read as inputs (GPIO 20 is input-only UART RX)
INPUT_PINS = DIGITAL_PINS | {20}

# UART0 pins used by the REPL — never allow output configuration
FORBIDDEN_PINS = {20, 21}

# ---------- Runtime state ----------

# Maps pin number -> {"mode": str, "obj": Pin object}
# Populated lazily on first API access to each pin
PIN_REGISTRY = {}


# ---------- Helpers ----------

def _resolve_pin(pin_arg, pin_aliases):
    """Resolve a pin argument to an integer GPIO number.

    Accepts an integer, a numeric string, or a string alias from
    config.json's pin_aliases map. Raises ValueError with a
    descriptive message if the pin cannot be resolved.
    """
    if isinstance(pin_arg, str):
        if pin_arg in pin_aliases:
            pin_num = pin_aliases[pin_arg]
        else:
            try:
                pin_num = int(pin_arg)
            except ValueError:
                valid = ", ".join(sorted(pin_aliases.keys())) if pin_aliases else "none defined"
                raise ValueError(
                    "'{}' is not a valid pin number or alias. Known aliases: {}".format(
                        pin_arg, valid))
    else:
        pin_num = int(pin_arg)

    return pin_num


def _validate_digital_pin(pin_num):
    """Check that a pin number is in the valid digital set.

    Returns None on success, or a (error_dict, status_code) tuple on failure.
    """
    if pin_num not in DIGITAL_PINS and pin_num not in FORBIDDEN_PINS:
        return (
            {"error": "GPIO {} is not a valid pin on the ESP32-C3. Valid digital pins: {}".format(
                pin_num, sorted(DIGITAL_PINS))},
            400
        )
    return None


def _check_forbidden_output(pin_num):
    """Check if a pin is forbidden from being used as output.

    Returns None if allowed, or (error_dict, status_code) on refusal.
    """
    if pin_num == 21:
        return (
            {"error": "GPIO 21 is the UART0 TX pin (REPL output). It cannot be used by the API."},
            403
        )
    if pin_num == 20:
        return (
            {"error": "GPIO 20 is the UART0 RX pin (REPL input). It is input-only and cannot be configured as output."},
            403
        )
    return None


def _pin_state(pin_num):
    """Build a state dict for a pin currently in the registry.

    Only handles IN and OUT modes (no ADC/PWM branches in this template).
    Returns None if the pin is not registered.
    """
    entry = PIN_REGISTRY.get(pin_num)
    if entry is None:
        return None

    mode = entry["mode"]
    result = {"pin": pin_num, "mode": mode}

    if mode in ("IN", "OUT"):
        result["value"] = entry["obj"].value()

    return result


def _check_memory():
    """Run GC and warn on serial console if free memory is low."""
    gc.collect()
    free = gc.mem_free()
    if free < 51200:  # 50 KB threshold
        print("WARNING: Low memory — {} bytes free".format(free))
    return free


# ---------- Route registration ----------

def register_routes(app, config):
    """Attach digital GPIO API routes to the Microdot app.

    Unlike the full template's gpio_api.py, this module has no feature
    flags — the entire file IS the GPIO feature. All routes are always
    registered.
    """

    _pin_aliases = config.get("pin_aliases", {})

    # ---- GET /api/gpio/capabilities ----

    @app.route("/api/gpio/capabilities")
    async def gpio_capabilities(request):
        """Return pin sets, chip info, and safety notes."""
        return {
            "digital_pins": sorted(DIGITAL_PINS),
            "output_pins": sorted(OUTPUT_PINS),
            "input_pins": sorted(INPUT_PINS),
            "forbidden_pins": sorted(FORBIDDEN_PINS),
            "pin_aliases": _pin_aliases,
            "chip": "ESP32-C3",
            "notes": [
                "GPIO 20 is UART0 RX (input-only), GPIO 21 is UART0 TX — both reserved for REPL",
                "GPIO 0 and 2 are strapping pins — safe after boot but avoid driving during reset",
                "Internal temperature via GET /api/gpio/temperature (Celsius)",
            ]
        }

    # ---- GET /api/gpio/temperature ----

    @app.route("/api/gpio/temperature")
    async def gpio_temperature(request):
        """Return the ESP32's internal MCU temperature in Celsius."""
        try:
            temp = esp32.mcu_temperature()
            return {"temp_c": temp}
        except Exception as e:
            return {"error": "Failed to read internal temperature: {}".format(e)}, 500

    # ---- GET /api/gpio/pins ----

    @app.route("/api/gpio/pins")
    async def gpio_pins(request):
        """List all configured pin states from PIN_REGISTRY."""
        pins = {}
        for pin_num in sorted(PIN_REGISTRY.keys()):
            state = _pin_state(pin_num)
            if state:
                pins[str(pin_num)] = state
        return {
            "pins": pins,
            "aliases": _pin_aliases,
            "count": len(pins)
        }

    # ---- GET /api/gpio/<pin_arg> ----

    @app.route("/api/gpio/<pin_arg>")
    async def gpio_read(request, pin_arg):
        """Read the current state of a single pin."""
        try:
            pin_num = _resolve_pin(pin_arg, _pin_aliases)
        except ValueError as e:
            return {"error": str(e)}, 400

        # GPIO 21 (UART TX) cannot be read at all
        if pin_num == 21:
            return {"error": "GPIO 21 is the UART0 TX pin (REPL output). It cannot be read via the API."}, 403

        if pin_num not in DIGITAL_PINS and pin_num != 20:
            return {
                "error": "GPIO {} is not a valid pin on the ESP32-C3. Valid pins: {}".format(
                    pin_num, sorted(DIGITAL_PINS))
            }, 400

        if pin_num not in PIN_REGISTRY:
            return {
                "error": "GPIO {} has not been configured yet. Use POST /api/gpio/{}/mode first.".format(
                    pin_num, pin_num)
            }, 404

        return _pin_state(pin_num)

    # ---- POST /api/gpio/<pin_arg>/mode ----

    @app.route("/api/gpio/<pin_arg>/mode", methods=["POST"])
    async def gpio_set_mode(request, pin_arg):
        """Configure a pin as IN or OUT with optional pull resistor."""
        try:
            pin_num = _resolve_pin(pin_arg, _pin_aliases)
        except ValueError as e:
            return {"error": str(e)}, 400

        # Parse body
        body = request.json
        if body is None:
            return {"error": "Request body must be JSON with a 'mode' field ('IN' or 'OUT')."}, 400

        mode = body.get("mode")
        if mode not in ("IN", "OUT"):
            return {"error": "'mode' must be 'IN' or 'OUT'. Got: {}".format(mode)}, 400

        pull_str = body.get("pull")
        pull = None
        if pull_str == "up":
            pull = Pin.PULL_UP
        elif pull_str == "down":
            pull = Pin.PULL_DOWN
        elif pull_str is not None and pull_str != "":
            return {"error": "'pull' must be 'up', 'down', or null. Got: {}".format(pull_str)}, 400

        # Validate pin number
        err = _validate_digital_pin(pin_num)
        if err:
            return err

        # Check forbidden pins
        if mode == "OUT":
            err = _check_forbidden_output(pin_num)
            if err:
                return err
        elif mode == "IN":
            if pin_num == 21:
                return {"error": "GPIO 21 is the UART0 TX pin (REPL output). It cannot be used by the API."}, 403

        # Create the pin object
        try:
            if mode == "IN":
                pin_obj = Pin(pin_num, Pin.IN, pull)
            else:
                pin_obj = Pin(pin_num, Pin.OUT)
        except Exception as e:
            return {"error": "Failed to configure GPIO {}: {}".format(pin_num, e)}, 500

        PIN_REGISTRY[pin_num] = {"mode": mode, "obj": pin_obj}
        _check_memory()

        return _pin_state(pin_num)

    # ---- POST /api/gpio/<pin_arg>/value ----

    @app.route("/api/gpio/<pin_arg>/value", methods=["POST"])
    async def gpio_set_value(request, pin_arg):
        """Set a pin's output to HIGH (1) or LOW (0)."""
        try:
            pin_num = _resolve_pin(pin_arg, _pin_aliases)
        except ValueError as e:
            return {"error": str(e)}, 400

        body = request.json
        if body is None or "value" not in body:
            return {"error": "Request body must be JSON with a 'value' field (0 or 1)."}, 400

        val = body["value"]
        if val not in (0, 1):
            return {"error": "'value' must be 0 or 1. Got: {}".format(val)}, 400

        entry = PIN_REGISTRY.get(pin_num)
        if entry is None:
            return {
                "error": "GPIO {} has not been configured yet. Use POST /api/gpio/{}/mode first.".format(
                    pin_num, pin_num)
            }, 400

        if entry["mode"] != "OUT":
            return {
                "error": "GPIO {} is in {} mode. Only pins in OUT mode can be written to.".format(
                    pin_num, entry["mode"])
            }, 400

        try:
            entry["obj"].value(val)
        except Exception as e:
            return {"error": "Failed to set GPIO {}: {}".format(pin_num, e)}, 500

        return _pin_state(pin_num)

    # ---- POST /api/gpio/<pin_arg>/toggle ----

    @app.route("/api/gpio/<pin_arg>/toggle", methods=["POST"])
    async def gpio_toggle(request, pin_arg):
        """Toggle an output pin between HIGH and LOW."""
        try:
            pin_num = _resolve_pin(pin_arg, _pin_aliases)
        except ValueError as e:
            return {"error": str(e)}, 400

        entry = PIN_REGISTRY.get(pin_num)
        if entry is None:
            return {
                "error": "GPIO {} has not been configured yet. Use POST /api/gpio/{}/mode first.".format(
                    pin_num, pin_num)
            }, 400

        if entry["mode"] != "OUT":
            return {
                "error": "GPIO {} is in {} mode. Only pins in OUT mode can be toggled.".format(
                    pin_num, entry["mode"])
            }, 400

        try:
            current = entry["obj"].value()
            entry["obj"].value(current ^ 1)
        except Exception as e:
            return {"error": "Failed to toggle GPIO {}: {}".format(pin_num, e)}, 500

        return _pin_state(pin_num)

    print("gpio_handler: all routes registered")
