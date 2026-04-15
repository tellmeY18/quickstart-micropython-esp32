# gpio_api.py — GPIO & peripheral API routes for ESP32-C3
#
# This module registers all hardware-control routes onto the Microdot app.
# Import register_routes(app) from main.py and call it before app.run().
#
# Feature flags in config.json control which route groups are registered.
# Disabled features save memory by skipping route closures, regex patterns,
# and heavy imports (e.g. lib.websocket, uasyncio).

import esp32
import gc
import time
import ujson

# ---------- Config ----------

try:
    with open("config.json") as f:
        _config = ujson.load(f)
except Exception:
    _config = {}

_pin_aliases = _config.get("pin_aliases", {})

# ---------- Feature flags ----------

_features = _config.get("features", {})
_F_GPIO = _features.get("gpio", False)
_F_ADC = _features.get("adc", False)
_F_PWM = _features.get("pwm", False)
_F_I2C = _features.get("i2c", False)
_F_BATCH = _features.get("batch", False)
_F_WS = _features.get("websocket", False)

print("gpio_api: feature flags — gpio={}, adc={}, pwm={}, i2c={}, batch={}, websocket={}".format(
    _F_GPIO, _F_ADC, _F_PWM, _F_I2C, _F_BATCH, _F_WS))

# ---------- Conditional machine imports ----------

from machine import Pin

if _F_ADC:
    from machine import ADC
if _F_PWM:
    from machine import PWM
if _F_I2C:
    from machine import SoftI2C

# NOTE: uasyncio and lib.websocket are imported lazily inside register_routes
# only when _F_WS is True, to avoid wasting memory on the WebSocket stack.

# ---------- ESP32-C3 pin sets ----------

# All usable digital GPIO pins
DIGITAL_PINS = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 18, 19}

# Pins with ADC capability (ADC1 only, no ADC2 on C3)
ADC_PINS = {0, 1, 2, 3, 4}

# Pins that can be driven as outputs
OUTPUT_PINS = DIGITAL_PINS  # all digital pins support output

# Pins that can be read as inputs (GPIO 20 is input-only UART RX)
INPUT_PINS = DIGITAL_PINS | {20}

# UART0 pins used by the REPL — never allow output configuration
FORBIDDEN_PINS = {20, 21}

# ---------- Runtime state ----------

# Maps pin number -> {"mode": str, "obj": machine object}
# Populated lazily on first API access to each pin
PIN_REGISTRY = {}

# WebSocket stream configuration
STREAM_CONFIG = {
    "pins": [],         # pins to include in stream (empty = all registered)
    "interval_ms": 100  # broadcast interval in milliseconds
}

# Active WebSocket client connections
_ws_clients = []

# I2C bus instance (initialized lazily on first I2C endpoint call)
_i2c = None

# ---------- ADC attenuation (only when ADC feature is enabled) ----------

if _F_ADC:
    _ATTEN_MAP = {
        "0db": ADC.ATTN_0DB,
        "2.5db": ADC.ATTN_2_5DB,
        "6db": ADC.ATTN_6DB,
        "11db": ADC.ATTN_11DB,
    }

    _ATTEN_REVERSE = {v: k for k, v in _ATTEN_MAP.items()}

    _default_atten_str = _config.get("adc_atten", "11db")
    _default_atten = _ATTEN_MAP.get(_default_atten_str, ADC.ATTN_11DB)
else:
    _ATTEN_MAP = {}
    _ATTEN_REVERSE = {}
    _default_atten = None


# ---------- Helpers ----------

def _resolve_pin(pin_arg):
    """Resolve a pin argument to an integer GPIO number.

    Accepts an integer, a numeric string, or a string alias from
    config.json's pin_aliases map. Raises ValueError with a
    descriptive message if the pin is invalid.
    """
    # Handle alias lookup
    if isinstance(pin_arg, str):
        if pin_arg in _pin_aliases:
            pin_num = _pin_aliases[pin_arg]
        else:
            try:
                pin_num = int(pin_arg)
            except ValueError:
                valid = ", ".join(sorted(_pin_aliases.keys())) if _pin_aliases else "none defined"
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
    """Build a state dict for a pin currently in the registry."""
    entry = PIN_REGISTRY.get(pin_num)
    if entry is None:
        return None

    mode = entry["mode"]
    result = {"pin": pin_num, "mode": mode}

    if mode in ("IN", "OUT"):
        result["value"] = entry["obj"].value()
    elif mode == "PWM":
        obj = entry["obj"]
        result["freq"] = obj.freq()
        duty = obj.duty_u16()
        result["duty_u16"] = duty
        result["duty_pct"] = round(duty / 65535 * 100, 1)
    elif mode == "ADC":
        obj = entry["obj"]
        raw = obj.read_u16()
        uv = obj.read_uv()
        voltage_v = round(uv / 1_000_000, 3)
        result["raw"] = raw
        result["voltage_uv"] = uv
        result["voltage_v"] = voltage_v
        result["atten"] = _ATTEN_REVERSE.get(entry.get("atten"), "unknown")

    return result


def _check_memory():
    """Run GC and warn on serial console if free memory is low."""
    gc.collect()
    free = gc.mem_free()
    if free < 51200:  # 50 KB threshold
        print("WARNING: Low memory — {} bytes free".format(free))
    return free


# ---------- Route registration ----------

def register_routes(app):
    """Attach all GPIO/peripheral API routes to the Microdot app."""

    _active_count = 0

    # ---- System endpoints (always registered, no flag) ----

    @app.route("/api/gpio/capabilities")
    async def gpio_capabilities(request):
        return {
            "digital_pins": sorted(DIGITAL_PINS),
            "adc_pins": sorted(ADC_PINS),
            "pwm_pins": sorted(OUTPUT_PINS),
            "output_pins": sorted(OUTPUT_PINS),
            "input_pins": sorted(INPUT_PINS),
            "forbidden_pins": sorted(FORBIDDEN_PINS),
            "i2c_default": {"sda": 8, "scl": 9},
            "has_dac": False,
            "has_touch": False,
            "chip": "ESP32-C3",
            "features": {
                "gpio": _F_GPIO,
                "adc": _F_ADC,
                "pwm": _F_PWM,
                "i2c": _F_I2C,
                "batch": _F_BATCH,
                "websocket": _F_WS,
            },
            "notes": [
                "ADC only on GPIO 0-4 (ADC1, no conflict with WiFi)",
                "No DAC hardware — use PWM for analog output",
                "No capacitive touch hardware",
                "GPIO 20 is UART0 RX (input-only), GPIO 21 is UART0 TX — both reserved for REPL",
                "GPIO 0 and 2 are strapping pins — safe after boot but avoid driving during reset",
                "Internal temperature via esp32.mcu_temperature() (Celsius)"
            ]
        }

    @app.route("/api/gpio/temperature")
    async def gpio_temperature(request):
        try:
            temp = esp32.mcu_temperature()
            return {"temp_c": temp}
        except Exception as e:
            return {"error": "Failed to read temperature: {}".format(e)}, 500

    print("gpio_api:   [system] capabilities + temperature routes registered")

    # ---- GPIO routes ----

    if _F_GPIO:
        _active_count += 1

        @app.route("/api/gpio/pins")
        async def gpio_pins(request):
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

        # ---- Single pin read ----

        @app.route("/api/gpio/<pin_arg>")
        async def gpio_read(request, pin_arg):
            try:
                pin_num = _resolve_pin(pin_arg)
            except ValueError as e:
                return {"error": str(e)}, 400

            # Allow reading forbidden pin 20 (UART RX) but not 21
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

        # ---- Pin mode configuration ----

        @app.route("/api/gpio/<pin_arg>/mode", methods=["POST"])
        async def gpio_set_mode(request, pin_arg):
            try:
                pin_num = _resolve_pin(pin_arg)
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

            # Validate pin
            err = _validate_digital_pin(pin_num)
            if err:
                return err

            # Check forbidden
            if mode == "OUT":
                err = _check_forbidden_output(pin_num)
                if err:
                    return err
            elif mode == "IN":
                # GPIO 21 cannot be used at all
                if pin_num == 21:
                    return {"error": "GPIO 21 is the UART0 TX pin (REPL output). It cannot be used by the API."}, 403

            # Check mode conflict — if already in a non-digital mode, refuse
            existing = PIN_REGISTRY.get(pin_num)
            if existing and existing["mode"] not in ("IN", "OUT"):
                return {
                    "error": "GPIO {} is currently in {} mode. Release it first (e.g. POST /api/pwm/{}/stop).".format(
                        pin_num, existing["mode"], pin_num)
                }, 409

            # Create the pin object
            try:
                if mode == "IN":
                    pin_obj = Pin(pin_num, Pin.IN, pull)
                else:
                    pin_obj = Pin(pin_num, Pin.OUT)
            except Exception as e:
                return {"error": "Failed to configure GPIO {}: {}".format(pin_num, e)}, 500

            PIN_REGISTRY[pin_num] = {"mode": mode, "obj": pin_obj}

            return _pin_state(pin_num)

        # ---- Set pin value ----

        @app.route("/api/gpio/<pin_arg>/value", methods=["POST"])
        async def gpio_set_value(request, pin_arg):
            try:
                pin_num = _resolve_pin(pin_arg)
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

        # ---- Toggle pin ----

        @app.route("/api/gpio/<pin_arg>/toggle", methods=["POST"])
        async def gpio_toggle(request, pin_arg):
            try:
                pin_num = _resolve_pin(pin_arg)
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

        print("gpio_api:   [gpio] routes registered")
    else:
        print("gpio_api:   [gpio] DISABLED")

    # ---- ADC endpoints ----

    if _F_ADC:
        _active_count += 1

        def _init_adc(pin_num, atten=None):
            """Lazily create or return an existing ADC object for a pin.

            Returns (adc_entry, error_tuple). On success error_tuple is None.
            On failure adc_entry is None and error_tuple is (dict, status_code).
            """
            if atten is None:
                atten = _default_atten

            existing = PIN_REGISTRY.get(pin_num)
            if existing and existing["mode"] == "ADC":
                return existing, None
            if existing:
                return None, (
                    {"error": "GPIO {} is currently in {} mode. Release it first before using as ADC.".format(
                        pin_num, existing["mode"])},
                    409
                )

            try:
                adc_obj = ADC(Pin(pin_num))
                adc_obj.atten(atten)
            except Exception as e:
                return None, (
                    {"error": "Failed to initialize ADC on GPIO {}: {}".format(pin_num, e)},
                    500
                )

            entry = {"mode": "ADC", "obj": adc_obj, "atten": atten}
            PIN_REGISTRY[pin_num] = entry
            return entry, None

        def _read_adc(pin_num, entry):
            """Take a reading from an ADC entry and return a result dict."""
            obj = entry["obj"]
            raw = obj.read_u16()
            uv = obj.read_uv()
            voltage_v = round(uv / 1_000_000, 3)
            return {
                "pin": pin_num,
                "raw": raw,
                "voltage_uv": uv,
                "voltage_v": voltage_v,
                "atten": _ATTEN_REVERSE.get(entry.get("atten"), "unknown")
            }

        @app.route("/api/adc/all")
        async def adc_read_all(request):
            _check_memory()
            readings = {}
            for pin_num in sorted(ADC_PINS):
                entry, err = _init_adc(pin_num)
                if err:
                    readings[str(pin_num)] = {"error": err[0]["error"]}
                    continue
                readings[str(pin_num)] = _read_adc(pin_num, entry)
            return {"readings": readings}

        @app.route("/api/adc/<pin_arg>/config", methods=["POST"])
        async def adc_config(request, pin_arg):
            try:
                pin_num = _resolve_pin(pin_arg)
            except ValueError as e:
                return {"error": str(e)}, 400

            if pin_num not in ADC_PINS:
                return {
                    "error": "GPIO {} does not have ADC capability. ADC pins: {}".format(
                        pin_num, sorted(ADC_PINS))
                }, 400

            body = request.json
            if body is None or "atten" not in body:
                return {
                    "error": "Request body must be JSON with an 'atten' field. Valid values: {}".format(
                        list(_ATTEN_MAP.keys()))
                }, 400

            atten_str = body["atten"]
            if atten_str not in _ATTEN_MAP:
                return {
                    "error": "'atten' must be one of {}. Got: '{}'".format(
                        list(_ATTEN_MAP.keys()), atten_str)
                }, 400

            atten_val = _ATTEN_MAP[atten_str]

            entry, err = _init_adc(pin_num, atten_val)
            if err:
                return err

            try:
                entry["obj"].atten(atten_val)
                entry["atten"] = atten_val
            except Exception as e:
                return {"error": "Failed to set attenuation on GPIO {}: {}".format(pin_num, e)}, 500

            return {"pin": pin_num, "atten": atten_str, "status": "ok"}

        @app.route("/api/adc/<pin_arg>")
        async def adc_read(request, pin_arg):
            try:
                pin_num = _resolve_pin(pin_arg)
            except ValueError as e:
                return {"error": str(e)}, 400

            if pin_num not in ADC_PINS:
                return {
                    "error": "GPIO {} does not have ADC capability. ADC pins: {}".format(
                        pin_num, sorted(ADC_PINS))
                }, 400

            entry, err = _init_adc(pin_num)
            if err:
                return err

            return _read_adc(pin_num, entry)

        print("gpio_api:   [adc] routes registered")
    else:
        print("gpio_api:   [adc] DISABLED")

    # ---- PWM endpoints ----

    if _F_PWM:
        _active_count += 1

        @app.route("/api/pwm/<pin_arg>/start", methods=["POST"])
        async def pwm_start(request, pin_arg):
            try:
                pin_num = _resolve_pin(pin_arg)
            except ValueError as e:
                return {"error": str(e)}, 400

            if pin_num not in OUTPUT_PINS:
                return {
                    "error": "GPIO {} is not an output-capable pin. Valid pins: {}".format(
                        pin_num, sorted(OUTPUT_PINS))
                }, 400

            err = _check_forbidden_output(pin_num)
            if err:
                return err

            body = request.json
            if body is None:
                return {"error": "Request body must be JSON with 'freq' and 'duty_u16' fields."}, 400

            freq = body.get("freq")
            duty = body.get("duty_u16")

            if freq is None or not isinstance(freq, int):
                return {"error": "'freq' is required and must be an integer."}, 400
            if freq < 1 or freq > 40_000_000:
                return {"error": "'freq' must be between 1 and 40000000. Got: {}".format(freq)}, 400

            if duty is None or not isinstance(duty, int):
                return {"error": "'duty_u16' is required and must be an integer (0-65535)."}, 400
            if duty < 0 or duty > 65535:
                return {"error": "'duty_u16' must be between 0 and 65535. Got: {}".format(duty)}, 400

            existing = PIN_REGISTRY.get(pin_num)
            if existing and existing["mode"] != "PWM":
                return {
                    "error": "GPIO {} is currently in {} mode. Release it first before starting PWM.".format(
                        pin_num, existing["mode"])
                }, 409

            try:
                if existing and existing["mode"] == "PWM":
                    obj = existing["obj"]
                    obj.freq(freq)
                    obj.duty_u16(duty)
                else:
                    obj = PWM(Pin(pin_num), freq=freq)
                    obj.duty_u16(duty)
                    PIN_REGISTRY[pin_num] = {"mode": "PWM", "obj": obj}
            except Exception as e:
                return {"error": "Failed to start PWM on GPIO {}: {}".format(pin_num, e)}, 500

            return _pin_state(pin_num)

        @app.route("/api/pwm/<pin_arg>/duty", methods=["POST"])
        async def pwm_duty(request, pin_arg):
            try:
                pin_num = _resolve_pin(pin_arg)
            except ValueError as e:
                return {"error": str(e)}, 400

            entry = PIN_REGISTRY.get(pin_num)
            if entry is None or entry["mode"] != "PWM":
                return {
                    "error": "GPIO {} is not in PWM mode. Use POST /api/pwm/{}/start first.".format(
                        pin_num, pin_num)
                }, 400

            body = request.json
            if body is None or "duty_u16" not in body:
                return {"error": "Request body must be JSON with a 'duty_u16' field (0-65535)."}, 400

            duty = body["duty_u16"]
            if not isinstance(duty, int) or duty < 0 or duty > 65535:
                return {"error": "'duty_u16' must be an integer between 0 and 65535. Got: {}".format(duty)}, 400

            try:
                entry["obj"].duty_u16(duty)
            except Exception as e:
                return {"error": "Failed to set duty on GPIO {}: {}".format(pin_num, e)}, 500

            return _pin_state(pin_num)

        @app.route("/api/pwm/<pin_arg>/freq", methods=["POST"])
        async def pwm_freq(request, pin_arg):
            try:
                pin_num = _resolve_pin(pin_arg)
            except ValueError as e:
                return {"error": str(e)}, 400

            entry = PIN_REGISTRY.get(pin_num)
            if entry is None or entry["mode"] != "PWM":
                return {
                    "error": "GPIO {} is not in PWM mode. Use POST /api/pwm/{}/start first.".format(
                        pin_num, pin_num)
                }, 400

            body = request.json
            if body is None or "freq" not in body:
                return {"error": "Request body must be JSON with a 'freq' field (1-40000000)."}, 400

            freq = body["freq"]
            if not isinstance(freq, int) or freq < 1 or freq > 40_000_000:
                return {"error": "'freq' must be an integer between 1 and 40000000. Got: {}".format(freq)}, 400

            try:
                entry["obj"].freq(freq)
            except Exception as e:
                return {"error": "Failed to set frequency on GPIO {}: {}".format(pin_num, e)}, 500

            return _pin_state(pin_num)

        @app.route("/api/pwm/<pin_arg>/stop", methods=["POST"])
        async def pwm_stop(request, pin_arg):
            try:
                pin_num = _resolve_pin(pin_arg)
            except ValueError as e:
                return {"error": str(e)}, 400

            entry = PIN_REGISTRY.get(pin_num)
            if entry is None or entry["mode"] != "PWM":
                return {
                    "error": "GPIO {} is not in PWM mode. Nothing to stop.".format(pin_num)
                }, 400

            try:
                entry["obj"].deinit()
            except Exception as e:
                return {"error": "Failed to stop PWM on GPIO {}: {}".format(pin_num, e)}, 500

            del PIN_REGISTRY[pin_num]

            return {"pin": pin_num, "status": "stopped", "mode": "released"}

        @app.route("/api/pwm/<pin_arg>")
        async def pwm_read(request, pin_arg):
            try:
                pin_num = _resolve_pin(pin_arg)
            except ValueError as e:
                return {"error": str(e)}, 400

            entry = PIN_REGISTRY.get(pin_num)
            if entry is None or entry["mode"] != "PWM":
                return {
                    "error": "GPIO {} is not in PWM mode.".format(pin_num)
                }, 404

            return _pin_state(pin_num)

        print("gpio_api:   [pwm] routes registered")
    else:
        print("gpio_api:   [pwm] DISABLED")

    # ---- I2C endpoints ----

    if _F_I2C:
        _active_count += 1

        def _get_i2c():
            """Return the cached I2C bus instance, creating it on first call."""
            global _i2c
            if _i2c is None:
                sda = _config.get("i2c_sda", 8)
                scl = _config.get("i2c_scl", 9)
                freq = _config.get("i2c_freq", 100000)
                _i2c = SoftI2C(sda=Pin(sda), scl=Pin(scl), freq=freq)
            return _i2c

        @app.route("/api/i2c/scan")
        async def i2c_scan(request):
            try:
                gc.collect()
                bus = _get_i2c()
                devices = bus.scan()
            except OSError as e:
                return {"error": "I2C scan failed: {}".format(e)}, 500
            except Exception as e:
                return {"error": "I2C initialization failed: {}".format(e)}, 500

            return {
                "devices": devices,
                "hex": ["0x{:02x}".format(a) for a in devices],
                "count": len(devices)
            }

        @app.route("/api/i2c/read", methods=["POST"])
        async def i2c_read(request):
            body = request.json
            if body is None:
                return {"error": "Request body must be JSON with 'addr' and 'nbytes' fields."}, 400

            addr = body.get("addr")
            nbytes = body.get("nbytes")

            if addr is None or not isinstance(addr, int):
                return {"error": "'addr' is required and must be an integer (0-127)."}, 400
            if addr < 0 or addr > 127:
                return {"error": "'addr' must be between 0 and 127. Got: {}".format(addr)}, 400

            if nbytes is None or not isinstance(nbytes, int):
                return {"error": "'nbytes' is required and must be a positive integer."}, 400
            if nbytes < 1:
                return {"error": "'nbytes' must be at least 1. Got: {}".format(nbytes)}, 400

            gc.collect()
            try:
                bus = _get_i2c()
                data = bus.readfrom(addr, nbytes)
            except OSError as e:
                return {"error": "I2C read from address {} failed: {}".format(addr, e)}, 500

            data_list = list(data)
            hex_str = "".join("{:02x}".format(b) for b in data_list)
            return {
                "addr": addr,
                "data": data_list,
                "hex": hex_str,
                "length": len(data_list)
            }

        @app.route("/api/i2c/write", methods=["POST"])
        async def i2c_write(request):
            body = request.json
            if body is None:
                return {"error": "Request body must be JSON with 'addr' and 'data' fields."}, 400

            addr = body.get("addr")
            data = body.get("data")

            if addr is None or not isinstance(addr, int):
                return {"error": "'addr' is required and must be an integer (0-127)."}, 400
            if addr < 0 or addr > 127:
                return {"error": "'addr' must be between 0 and 127. Got: {}".format(addr)}, 400

            if data is None or not isinstance(data, list):
                return {"error": "'data' is required and must be a list of integers (0-255)."}, 400
            if len(data) == 0:
                return {"error": "'data' must contain at least one byte."}, 400

            for i, b in enumerate(data):
                if not isinstance(b, int) or b < 0 or b > 255:
                    return {"error": "'data[{}]' must be an integer 0-255. Got: {}".format(i, b)}, 400

            gc.collect()
            try:
                bus = _get_i2c()
                bus.writeto(addr, bytes(data))
            except OSError as e:
                return {"error": "I2C write to address {} failed: {}".format(addr, e)}, 500

            return {
                "addr": addr,
                "bytes_written": len(data),
                "status": "ok"
            }

        @app.route("/api/i2c/write_read", methods=["POST"])
        async def i2c_write_read(request):
            body = request.json
            if body is None:
                return {"error": "Request body must be JSON with 'addr', 'write', and 'read' fields."}, 400

            addr = body.get("addr")
            write_data = body.get("write")
            read_count = body.get("read")

            if addr is None or not isinstance(addr, int):
                return {"error": "'addr' is required and must be an integer (0-127)."}, 400
            if addr < 0 or addr > 127:
                return {"error": "'addr' must be between 0 and 127. Got: {}".format(addr)}, 400

            if write_data is None or not isinstance(write_data, list):
                return {"error": "'write' is required and must be a list of integers (0-255)."}, 400
            if len(write_data) == 0:
                return {"error": "'write' must contain at least one byte."}, 400

            for i, b in enumerate(write_data):
                if not isinstance(b, int) or b < 0 or b > 255:
                    return {"error": "'write[{}]' must be an integer 0-255. Got: {}".format(i, b)}, 400

            if read_count is None or not isinstance(read_count, int):
                return {"error": "'read' is required and must be a positive integer."}, 400
            if read_count < 1:
                return {"error": "'read' must be at least 1. Got: {}".format(read_count)}, 400

            gc.collect()
            try:
                bus = _get_i2c()
                bus.writeto(addr, bytes(write_data), False)
                data = bus.readfrom(addr, read_count)
            except OSError as e:
                return {"error": "I2C write_read on address {} failed: {}".format(addr, e)}, 500

            data_list = list(data)
            hex_str = "".join("{:02x}".format(b) for b in data_list)
            return {
                "addr": addr,
                "wrote": write_data,
                "data": data_list,
                "hex": hex_str,
                "length": len(data_list)
            }

        @app.route("/api/i2c/config", methods=["POST"])
        async def i2c_config(request):
            global _i2c

            body = request.json
            if body is None:
                return {"error": "Request body must be JSON with at least one of: 'sda', 'scl', 'freq'."}, 400

            sda = body.get("sda", 8)
            scl = body.get("scl", 9)
            freq = body.get("freq", 100000)

            if not isinstance(sda, int) or sda not in OUTPUT_PINS:
                return {"error": "'sda' must be a valid output-capable GPIO pin. Got: {}".format(sda)}, 400
            if not isinstance(scl, int) or scl not in OUTPUT_PINS:
                return {"error": "'scl' must be a valid output-capable GPIO pin. Got: {}".format(scl)}, 400
            if not isinstance(freq, int) or freq < 1:
                return {"error": "'freq' must be a positive integer (Hz). Got: {}".format(freq)}, 400
            if sda == scl:
                return {"error": "'sda' and 'scl' must be different pins. Both are GPIO {}.".format(sda)}, 400

            try:
                if _i2c is not None:
                    del _i2c
                _i2c = SoftI2C(sda=Pin(sda), scl=Pin(scl), freq=freq)
            except Exception as e:
                _i2c = None
                return {"error": "Failed to configure I2C bus: {}".format(e)}, 500

            return {
                "sda": sda,
                "scl": scl,
                "freq": freq,
                "status": "ok"
            }

        print("gpio_api:   [i2c] routes registered")
    else:
        print("gpio_api:   [i2c] DISABLED")

    # ---- Batch endpoints ----

    if _F_BATCH:
        _active_count += 1

        @app.route("/api/gpio/batch/read", methods=["POST"])
        async def batch_read(request):
            gc.collect()
            body = request.json
            if body is None or "pins" not in body:
                return {"error": "Request body must be JSON with a 'pins' field (list of pin numbers or aliases)."}, 400

            pin_list = body["pins"]
            if not isinstance(pin_list, list) or len(pin_list) == 0:
                return {"error": "'pins' must be a non-empty list."}, 400

            results = {}
            errors = {}
            for p in pin_list:
                try:
                    pin_num = _resolve_pin(p)
                except ValueError as e:
                    errors[str(p)] = str(e)
                    continue

                entry = PIN_REGISTRY.get(pin_num)
                if entry is None:
                    errors[str(pin_num)] = "GPIO {} has not been configured yet.".format(pin_num)
                    continue

                state = _pin_state(pin_num)
                if state:
                    results[str(pin_num)] = state

            resp = {"results": results}
            if errors:
                resp["errors"] = errors
            return resp

        @app.route("/api/gpio/batch/write", methods=["POST"])
        async def batch_write(request):
            gc.collect()
            body = request.json
            if body is None or "pins" not in body:
                return {"error": "Request body must be JSON with a 'pins' field (object mapping pin to value)."}, 400

            pins_map = body["pins"]
            if not isinstance(pins_map, dict) or len(pins_map) == 0:
                return {"error": "'pins' must be a non-empty object mapping pin numbers/aliases to values (0 or 1)."}, 400

            results = {}
            errors = []
            for p, val in pins_map.items():
                try:
                    pin_num = _resolve_pin(p)
                except ValueError as e:
                    errors.append({"pin": p, "error": str(e)})
                    continue

                if val not in (0, 1):
                    errors.append({"pin": pin_num, "error": "'value' must be 0 or 1. Got: {}".format(val)})
                    continue

                err = _check_forbidden_output(pin_num)
                if err:
                    errors.append({"pin": pin_num, "error": err[0]["error"]})
                    continue

                entry = PIN_REGISTRY.get(pin_num)
                if entry is None:
                    errors.append({"pin": pin_num, "error": "GPIO {} has not been configured yet.".format(pin_num)})
                    continue

                if entry["mode"] != "OUT":
                    errors.append({"pin": pin_num, "error": "GPIO {} is in {} mode. Only OUT mode pins can be written.".format(pin_num, entry["mode"])})
                    continue

                try:
                    entry["obj"].value(val)
                    results[str(pin_num)] = {"value": val, "status": "ok"}
                except Exception as e:
                    errors.append({"pin": pin_num, "error": "Failed to set GPIO {}: {}".format(pin_num, e)})

            resp = {"results": results}
            if errors:
                resp["errors"] = errors
            return resp

        print("gpio_api:   [batch] routes registered")
    else:
        print("gpio_api:   [batch] DISABLED")

    # ---- WebSocket real-time stream ----

    if _F_WS:
        _active_count += 1

        # Deferred imports — only loaded when WebSocket feature is enabled
        import uasyncio as asyncio
        from lib.websocket import with_websocket

        def _build_stream_frame():
            """Build a snapshot frame of all monitored pins for WebSocket broadcast."""
            _check_memory()
            pins_to_stream = STREAM_CONFIG["pins"] if STREAM_CONFIG["pins"] else list(PIN_REGISTRY.keys())

            gpio_data = {}
            adc_data = {}
            for pin_num in pins_to_stream:
                entry = PIN_REGISTRY.get(pin_num)
                if entry is None:
                    continue

                mode = entry["mode"]
                if mode in ("IN", "OUT"):
                    gpio_data[str(pin_num)] = {"mode": mode, "value": entry["obj"].value()}
                elif mode == "PWM":
                    obj = entry["obj"]
                    gpio_data[str(pin_num)] = {
                        "mode": "PWM",
                        "freq": obj.freq(),
                        "duty_u16": obj.duty_u16()
                    }
                elif mode == "ADC":
                    obj = entry["obj"]
                    uv = obj.read_uv()
                    adc_data[str(pin_num)] = {
                        "raw": obj.read_u16(),
                        "voltage_v": round(uv / 1_000_000, 3)
                    }

            try:
                temp = esp32.mcu_temperature()
            except Exception:
                temp = None

            return {
                "ts": time.ticks_ms(),
                "gpio": gpio_data,
                "adc": adc_data,
                "temp_c": temp,
                "mem_free_kb": gc.mem_free() // 1024
            }

        async def _handle_ws_command(ws, msg):
            """Parse and dispatch a client command received over WebSocket."""
            try:
                cmd_data = ujson.loads(msg)
            except Exception:
                await ws.send(ujson.dumps({"error": "Invalid JSON"}))
                return

            cmd = cmd_data.get("cmd")

            if cmd == "ping":
                await ws.send(ujson.dumps({"cmd": "pong", "ts": time.ticks_ms()}))

            elif cmd == "set":
                pin_arg = cmd_data.get("pin")
                val = cmd_data.get("value")
                try:
                    pin_num = _resolve_pin(pin_arg)
                except (ValueError, TypeError) as e:
                    await ws.send(ujson.dumps({"error": str(e), "cmd": "set", "pin": pin_arg}))
                    return

                entry = PIN_REGISTRY.get(pin_num)
                if entry is None or entry["mode"] != "OUT":
                    await ws.send(ujson.dumps({
                        "error": "GPIO {} is not in OUT mode.".format(pin_num),
                        "cmd": "set", "pin": pin_num
                    }))
                    return

                if val not in (0, 1):
                    await ws.send(ujson.dumps({
                        "error": "'value' must be 0 or 1. Got: {}".format(val),
                        "cmd": "set", "pin": pin_num
                    }))
                    return

                try:
                    entry["obj"].value(val)
                except Exception as e:
                    await ws.send(ujson.dumps({
                        "error": "Failed to set GPIO {}: {}".format(pin_num, e),
                        "cmd": "set", "pin": pin_num
                    }))
                    return
                await ws.send(ujson.dumps({"cmd": "set", "pin": pin_num, "value": val, "status": "ok"}))

            elif cmd == "pwm_duty":
                pin_arg = cmd_data.get("pin")
                duty = cmd_data.get("duty_u16")
                try:
                    pin_num = _resolve_pin(pin_arg)
                except (ValueError, TypeError) as e:
                    await ws.send(ujson.dumps({"error": str(e), "cmd": "pwm_duty", "pin": pin_arg}))
                    return

                entry = PIN_REGISTRY.get(pin_num)
                if entry is None or entry["mode"] != "PWM":
                    await ws.send(ujson.dumps({
                        "error": "GPIO {} is not in PWM mode.".format(pin_num),
                        "cmd": "pwm_duty", "pin": pin_num
                    }))
                    return

                if not isinstance(duty, int) or duty < 0 or duty > 65535:
                    await ws.send(ujson.dumps({
                        "error": "'duty_u16' must be an integer 0-65535. Got: {}".format(duty),
                        "cmd": "pwm_duty", "pin": pin_num
                    }))
                    return

                try:
                    entry["obj"].duty_u16(duty)
                except Exception as e:
                    await ws.send(ujson.dumps({
                        "error": "Failed to set PWM duty on GPIO {}: {}".format(pin_num, e),
                        "cmd": "pwm_duty", "pin": pin_num
                    }))
                    return
                await ws.send(ujson.dumps({
                    "cmd": "pwm_duty", "pin": pin_num, "duty_u16": duty, "status": "ok"
                }))

            elif cmd == "stream_config":
                pins = cmd_data.get("pins", STREAM_CONFIG["pins"])
                interval = cmd_data.get("interval_ms", STREAM_CONFIG["interval_ms"])

                if not isinstance(interval, int):
                    await ws.send(ujson.dumps({
                        "error": "'interval_ms' must be an integer.",
                        "cmd": "stream_config"
                    }))
                    return

                warning = None
                if interval < 50:
                    interval = 50
                    warning = "interval_ms clamped to minimum of 50ms"

                STREAM_CONFIG["pins"] = pins if isinstance(pins, list) else []
                STREAM_CONFIG["interval_ms"] = interval

                resp = {
                    "cmd": "stream_config",
                    "pins": STREAM_CONFIG["pins"],
                    "interval_ms": interval,
                    "status": "ok"
                }
                if warning:
                    resp["warning"] = warning
                await ws.send(ujson.dumps(resp))

            else:
                await ws.send(ujson.dumps({
                    "error": "Unknown command: '{}'".format(cmd),
                    "cmd": cmd
                }))

        @app.route("/ws/stream")
        @with_websocket
        async def ws_stream(request, ws):
            """WebSocket endpoint for real-time pin state streaming."""
            _ws_clients.append(ws)
            last_broadcast = time.ticks_ms()
            try:
                while True:
                    # Non-blocking receive with timeout equal to broadcast interval
                    try:
                        msg = await asyncio.wait_for(
                            ws.receive(),
                            STREAM_CONFIG["interval_ms"] / 1000
                        )
                        await _handle_ws_command(ws, msg)
                    except asyncio.TimeoutError:
                        pass

                    # Broadcast if enough time has elapsed
                    now = time.ticks_ms()
                    if time.ticks_diff(now, last_broadcast) >= STREAM_CONFIG["interval_ms"]:
                        frame = _build_stream_frame()
                        await ws.send(ujson.dumps(frame))
                        last_broadcast = now
            except Exception:
                pass
            finally:
                if ws in _ws_clients:
                    _ws_clients.remove(ws)

        print("gpio_api:   [websocket] routes registered")
    else:
        print("gpio_api:   [websocket] DISABLED")

    print("gpio_api: done — {} feature(s) active".format(_active_count))


print("gpio_api: module loaded")
