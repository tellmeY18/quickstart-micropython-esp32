# sensor_handler.py — ADC, I2C & temperature API routes for ESP32-C3
#
# Extracted from the monolithic gpio_api.py for the sensors template.
# Provides analog reading, I2C bus communication, and internal temperature
# sensing over a REST API.  No GPIO digital I/O, no PWM, no WebSocket.
#
# Usage from main.py:
#     from sensor_handler import register_routes
#     register_routes(app, config)

import esp32
import gc
import time

from machine import Pin, ADC, SoftI2C

# ---------- ESP32-C3 ADC pin set ----------

# ADC1 channels only — ADC2 does not exist on the C3.
ADC_PINS = {0, 1, 2, 3, 4}

# ---------- ADC attenuation maps ----------

_ATTEN_MAP = {
    "0db": ADC.ATTN_0DB,
    "2.5db": ADC.ATTN_2_5DB,
    "6db": ADC.ATTN_6DB,
    "11db": ADC.ATTN_11DB,
}

_ATTEN_REVERSE = {v: k for k, v in _ATTEN_MAP.items()}

# ---------- Module-level runtime state ----------

# Lazily-initialised ADC entries: pin_num -> {"mode": "ADC", "obj": ADC, "atten": int}
_adc_registry = {}

# Lazily-initialised I2C bus instance
_i2c = None

# Filled by register_routes from config
_pin_aliases = {}


# ---------- Helpers ----------

def _resolve_pin(pin_arg):
    """Resolve a pin argument to an integer GPIO number.

    Accepts an integer, a numeric string, or a string alias defined in
    the config's ``pin_aliases`` map.  Raises ``ValueError`` with a
    descriptive message when the pin cannot be resolved.
    """
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


def _check_memory():
    """Run GC and warn on serial console if free memory drops below 50 KB."""
    gc.collect()
    free = gc.mem_free()
    if free < 51200:
        print("WARNING: Low memory — {} bytes free".format(free))
    return free


# ---------- Route registration ----------

def register_routes(app, config):
    """Attach all sensor API routes to the Microdot *app*.

    Parameters
    ----------
    app : Microdot
        The application instance to register routes on.
    config : dict
        Parsed ``config.json`` contents.  Used to read ADC attenuation
        default, I2C bus parameters, and pin aliases.
    """

    global _pin_aliases

    # ---- Read configuration ----

    _default_atten_str = config.get("adc_atten", "11db")
    _default_atten = _ATTEN_MAP.get(_default_atten_str, ADC.ATTN_11DB)

    _i2c_sda = config.get("i2c_sda", 6)
    _i2c_scl = config.get("i2c_scl", 7)
    _i2c_freq = config.get("i2c_freq", 100000)

    _pin_aliases = config.get("pin_aliases", {})

    # ---- Internal ADC helpers (closures over config) ----

    def _init_adc(pin_num, atten=None):
        """Lazily create or return an existing ADC object for *pin_num*.

        Returns ``(entry, None)`` on success or ``(None, (error_dict, status))``
        on failure.
        """
        if atten is None:
            atten = _default_atten

        existing = _adc_registry.get(pin_num)
        if existing is not None:
            return existing, None

        try:
            adc_obj = ADC(Pin(pin_num))
            adc_obj.atten(atten)
        except Exception as e:
            return None, (
                {"error": "Failed to initialise ADC on GPIO {}: {}".format(pin_num, e)},
                500,
            )

        entry = {"mode": "ADC", "obj": adc_obj, "atten": atten}
        _adc_registry[pin_num] = entry
        return entry, None

    def _read_adc(pin_num, entry):
        """Take a single reading from an ADC *entry* and return a result dict."""
        obj = entry["obj"]
        raw = obj.read_u16()
        uv = obj.read_uv()
        voltage_v = round(uv / 1_000_000, 3)
        return {
            "pin": pin_num,
            "raw": raw,
            "voltage_uv": uv,
            "voltage_v": voltage_v,
            "atten": _ATTEN_REVERSE.get(entry.get("atten"), "unknown"),
        }

    # ---- Internal I2C helper ----

    def _get_i2c():
        """Return the cached SoftI2C bus instance, creating it on first call."""
        global _i2c
        if _i2c is None:
            _i2c = SoftI2C(sda=Pin(_i2c_sda), scl=Pin(_i2c_scl), freq=_i2c_freq)
        return _i2c

    # ------------------------------------------------------------------
    # Temperature
    # ------------------------------------------------------------------

    @app.route("/api/temperature")
    async def api_temperature(request):
        """Return the ESP32 internal MCU temperature in degrees Celsius."""
        try:
            temp = esp32.mcu_temperature()
            return {"temp_c": temp}
        except Exception as e:
            return {"error": "Failed to read internal temperature: {}".format(e)}, 500

    # ------------------------------------------------------------------
    # ADC — read all
    # ------------------------------------------------------------------

    @app.route("/api/adc/all")
    async def adc_read_all(request):
        """Read every ADC-capable pin and return all readings at once."""
        _check_memory()
        readings = {}
        for pin_num in sorted(ADC_PINS):
            entry, err = _init_adc(pin_num)
            if err:
                readings[str(pin_num)] = {"error": err[0]["error"]}
                continue
            readings[str(pin_num)] = _read_adc(pin_num, entry)
        return {"readings": readings}

    # ------------------------------------------------------------------
    # ADC — configure attenuation
    # ------------------------------------------------------------------

    @app.route("/api/adc/<pin_arg>/config", methods=["POST"])
    async def adc_config(request, pin_arg):
        """Set ADC attenuation for a single pin."""
        try:
            pin_num = _resolve_pin(pin_arg)
        except ValueError as e:
            return {"error": str(e)}, 400

        if pin_num not in ADC_PINS:
            return {
                "error": "GPIO {} does not have ADC capability. Valid ADC pins are: {}".format(
                    pin_num, sorted(ADC_PINS))
            }, 400

        body = request.json
        if body is None or "atten" not in body:
            return {
                "error": "Request body must be JSON with an 'atten' field. "
                         "Valid values: {}".format(list(_ATTEN_MAP.keys()))
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
            return {
                "error": "Failed to set attenuation on GPIO {}: {}".format(pin_num, e)
            }, 500

        return {"pin": pin_num, "atten": atten_str, "status": "ok"}

    # ------------------------------------------------------------------
    # ADC — read single pin
    # ------------------------------------------------------------------

    @app.route("/api/adc/<pin_arg>")
    async def adc_read(request, pin_arg):
        """Read a single ADC pin and return raw value, micro-volts, and volts."""
        try:
            pin_num = _resolve_pin(pin_arg)
        except ValueError as e:
            return {"error": str(e)}, 400

        if pin_num not in ADC_PINS:
            return {
                "error": "GPIO {} does not have ADC capability. Valid ADC pins are: {}".format(
                    pin_num, sorted(ADC_PINS))
            }, 400

        entry, err = _init_adc(pin_num)
        if err:
            return err

        return _read_adc(pin_num, entry)

    # ------------------------------------------------------------------
    # I2C — scan
    # ------------------------------------------------------------------

    @app.route("/api/i2c/scan")
    async def i2c_scan(request):
        """Scan the I2C bus and return a list of discovered device addresses."""
        try:
            gc.collect()
            bus = _get_i2c()
            devices = bus.scan()
        except OSError as e:
            return {"error": "I2C scan failed: {}".format(e)}, 500
        except Exception as e:
            return {"error": "I2C initialisation failed: {}".format(e)}, 500

        return {
            "devices": devices,
            "hex": ["0x{:02x}".format(a) for a in devices],
            "count": len(devices),
        }

    # ------------------------------------------------------------------
    # I2C — read
    # ------------------------------------------------------------------

    @app.route("/api/i2c/read", methods=["POST"])
    async def i2c_read(request):
        """Read *nbytes* bytes from an I2C device at *addr*."""
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
            return {"error": "I2C read from address 0x{:02x} failed: {}".format(addr, e)}, 500

        data_list = list(data)
        hex_str = "".join("{:02x}".format(b) for b in data_list)
        return {
            "addr": addr,
            "data": data_list,
            "hex": hex_str,
            "length": len(data_list),
        }

    # ------------------------------------------------------------------
    # I2C — write
    # ------------------------------------------------------------------

    @app.route("/api/i2c/write", methods=["POST"])
    async def i2c_write(request):
        """Write a list of bytes to an I2C device at *addr*."""
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
            return {"error": "'data' list must contain at least one byte."}, 400

        for i, b in enumerate(data):
            if not isinstance(b, int) or b < 0 or b > 255:
                return {
                    "error": "'data[{}]' must be an integer between 0 and 255. Got: {}".format(i, b)
                }, 400

        gc.collect()
        try:
            bus = _get_i2c()
            bus.writeto(addr, bytes(data))
        except OSError as e:
            return {"error": "I2C write to address 0x{:02x} failed: {}".format(addr, e)}, 500

        return {
            "addr": addr,
            "bytes_written": len(data),
            "status": "ok",
        }

    # ------------------------------------------------------------------
    # I2C — write then read (combined transaction)
    # ------------------------------------------------------------------

    @app.route("/api/i2c/write_read", methods=["POST"])
    async def i2c_write_read(request):
        """Write bytes to a device, then immediately read back without releasing the bus."""
        body = request.json
        if body is None:
            return {
                "error": "Request body must be JSON with 'addr', 'write', and 'read' fields."
            }, 400

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
            return {"error": "'write' list must contain at least one byte."}, 400

        for i, b in enumerate(write_data):
            if not isinstance(b, int) or b < 0 or b > 255:
                return {
                    "error": "'write[{}]' must be an integer between 0 and 255. Got: {}".format(i, b)
                }, 400

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
            return {
                "error": "I2C write-then-read on address 0x{:02x} failed: {}".format(addr, e)
            }, 500

        data_list = list(data)
        hex_str = "".join("{:02x}".format(b) for b in data_list)
        return {
            "addr": addr,
            "wrote": write_data,
            "data": data_list,
            "hex": hex_str,
            "length": len(data_list),
        }

    # ------------------------------------------------------------------
    # I2C — reconfigure bus
    # ------------------------------------------------------------------

    @app.route("/api/i2c/config", methods=["POST"])
    async def i2c_config(request):
        """Reconfigure the I2C bus with new SDA/SCL pins and/or frequency."""
        global _i2c

        body = request.json
        if body is None:
            return {
                "error": "Request body must be JSON with at least one of: 'sda', 'scl', 'freq'."
            }, 400

        sda = body.get("sda", _i2c_sda)
        scl = body.get("scl", _i2c_scl)
        freq = body.get("freq", _i2c_freq)

        if not isinstance(sda, int):
            return {"error": "'sda' must be an integer GPIO pin number. Got: {}".format(sda)}, 400
        if not isinstance(scl, int):
            return {"error": "'scl' must be an integer GPIO pin number. Got: {}".format(scl)}, 400
        if not isinstance(freq, int) or freq < 1:
            return {"error": "'freq' must be a positive integer (Hz). Got: {}".format(freq)}, 400
        if sda == scl:
            return {
                "error": "'sda' and 'scl' must be different pins. Both are set to GPIO {}.".format(sda)
            }, 400

        try:
            if _i2c is not None:
                del _i2c
            _i2c = SoftI2C(sda=Pin(sda), scl=Pin(scl), freq=freq)
        except Exception as e:
            _i2c = None
            return {"error": "Failed to reconfigure I2C bus: {}".format(e)}, 500

        return {
            "sda": sda,
            "scl": scl,
            "freq": freq,
            "status": "ok",
        }

    # ---- Registration summary ----

    print("sensor_handler: temperature + ADC (pins {}) + I2C (SDA={}, SCL={}) routes registered".format(
        sorted(ADC_PINS), _i2c_sda, _i2c_scl))
