# neopixel_handler.py — WS2812B NeoPixel LED control routes for ESP32
#
# Registers REST API routes for controlling WS2812B (NeoPixel) RGB LEDs.
# This is the NeoPixel template's feature module — import register_routes()
# from main.py and call it before app.run().
#
# Supports setting all LEDs at once, individual LED addressing, and clearing.

import neopixel
from machine import Pin
import gc

# ---------- Runtime state ----------

# Lazily initialized NeoPixel instance
_np = None
_np_pin = None
_np_count = 0


# ---------- Helpers ----------

def _init_np(pin, count):
    """Create and store the NeoPixel instance. Only initializes once.

    Returns the NeoPixel object on success, or raises an exception on failure.
    """
    global _np, _np_pin, _np_count

    if _np is not None:
        return _np

    _np = neopixel.NeoPixel(Pin(pin), count)
    _np_pin = pin
    _np_count = count
    # Start with all LEDs off
    for i in range(count):
        _np[i] = (0, 0, 0)
    _np.write()
    return _np


def _validate_rgb(r, g, b):
    """Check that r, g, b are integers in 0-255 range.

    Returns an error string describing the problem, or None if valid.
    """
    for name, val in (("r", r), ("g", g), ("b", b)):
        if not isinstance(val, int):
            return "The '{}' value must be an integer, got {}.".format(name, type(val).__name__)
        if val < 0 or val > 255:
            return "The '{}' value must be between 0 and 255, got {}.".format(name, val)
    return None


def _check_memory():
    """Run GC and warn on serial console if free memory is low."""
    gc.collect()
    free = gc.mem_free()
    if free < 51200:  # 50 KB threshold
        print("WARNING: Low memory — {} bytes free".format(free))
    return free


# ---------- Route registration ----------

def register_routes(app, config):
    """Attach NeoPixel API routes to the Microdot app.

    Reads 'neopixel_pin' and 'neopixel_count' from config to determine
    the data pin and number of LEDs on the strip.
    """

    pin = config.get("neopixel_pin", 10)
    count = config.get("neopixel_count", 1)

    # Initialize the strip eagerly so wiring problems surface at boot
    try:
        _init_np(pin, count)
        print("neopixel_handler: initialized {} LED(s) on GPIO {}".format(count, pin))
    except Exception as e:
        print("neopixel_handler: init failed — {}".format(e))

    # ---- GET /api/neopixel ----

    @app.route("/api/neopixel")
    async def neopixel_status(request):
        """Return current state of all LEDs on the strip."""
        if _np is None:
            return {"error": "NeoPixel strip is not initialized. Check wiring and neopixel_pin in config.json."}, 500

        pixels = []
        for i in range(_np_count):
            r, g, b = _np[i]
            pixels.append([r, g, b])

        return {
            "pin": _np_pin,
            "count": _np_count,
            "pixels": pixels
        }

    # ---- POST /api/neopixel/clear ----
    # NOTE: This route MUST be registered before the /<index> route
    # so that "clear" is not captured as an index parameter.

    @app.route("/api/neopixel/clear", methods=["POST"])
    async def neopixel_clear(request):
        """Turn all LEDs off (set to 0, 0, 0)."""
        if _np is None:
            return {"error": "NeoPixel strip is not initialized. Check wiring and neopixel_pin in config.json."}, 500

        for i in range(_np_count):
            _np[i] = (0, 0, 0)
        _np.write()
        _check_memory()

        return {"ok": True, "status": "cleared"}

    # ---- POST /api/neopixel ----

    @app.route("/api/neopixel", methods=["POST"])
    async def neopixel_set_all(request):
        """Set ALL LEDs to the same color. Body: {"r": 255, "g": 0, "b": 128}"""
        if _np is None:
            return {"error": "NeoPixel strip is not initialized. Check wiring and neopixel_pin in config.json."}, 500

        body = request.json
        if body is None:
            return {"error": "Request body must be JSON with 'r', 'g', and 'b' fields (each 0-255)."}, 400

        r = body.get("r")
        g = body.get("g")
        b = body.get("b")

        if r is None or g is None or b is None:
            return {"error": "Missing required fields. Provide 'r', 'g', and 'b' (each 0-255)."}, 400

        err = _validate_rgb(r, g, b)
        if err:
            return {"error": err}, 400

        for i in range(_np_count):
            _np[i] = (r, g, b)
        _np.write()
        _check_memory()

        return {"ok": True, "color": {"r": r, "g": g, "b": b}}

    # ---- POST /api/neopixel/<index> ----

    @app.route("/api/neopixel/<index>", methods=["POST"])
    async def neopixel_set_one(request, index):
        """Set a single LED by index. Body: {"r": N, "g": N, "b": N}"""
        if _np is None:
            return {"error": "NeoPixel strip is not initialized. Check wiring and neopixel_pin in config.json."}, 500

        # Validate index
        try:
            idx = int(index)
        except (ValueError, TypeError):
            return {"error": "LED index must be an integer, got '{}'.".format(index)}, 400

        if idx < 0 or idx >= _np_count:
            return {
                "error": "LED index {} is out of range. Valid indices are 0 to {} (strip has {} LED{}).".format(
                    idx, _np_count - 1, _np_count, "s" if _np_count != 1 else "")
            }, 400

        body = request.json
        if body is None:
            return {"error": "Request body must be JSON with 'r', 'g', and 'b' fields (each 0-255)."}, 400

        r = body.get("r")
        g = body.get("g")
        b = body.get("b")

        if r is None or g is None or b is None:
            return {"error": "Missing required fields. Provide 'r', 'g', and 'b' (each 0-255)."}, 400

        err = _validate_rgb(r, g, b)
        if err:
            return {"error": err}, 400

        _np[idx] = (r, g, b)
        _np.write()
        _check_memory()

        return {"ok": True, "index": idx, "color": {"r": r, "g": g, "b": b}}

    print("neopixel_handler: all routes registered")
