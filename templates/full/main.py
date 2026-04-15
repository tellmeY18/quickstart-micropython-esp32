# main.py — Microdot web server: serves dashboard + /api/status
# Instrumented with verbose flash-safe debug logging for crash diagnostics.

import gc
import time

# --- Bootstrap the logger FIRST (before any heavy imports) ---
# This must succeed or we have no visibility at all.
try:
    from debuglog import log, section, log_exception, mem
    log("main.py: debuglog imported OK")
except Exception as e:
    # Fallback: define no-op stubs so the rest of the file still runs
    def log(msg, also_print=True):
        print("LOG(fallback): {}".format(msg))
    def section(h):
        log("--- {} ---".format(h))
    def log_exception(ctx, exc):
        print("EXCEPTION in {}: {}".format(ctx, exc))
    def mem(label=""):
        gc.collect()
        print("MEM: {} bytes free".format(gc.mem_free()))
    print("WARNING: debuglog import failed: {}".format(e))

section("MAIN.PY START")
mem("before any imports")

# --- Import network (lightweight) ---
try:
    log("importing network...")
    import network
    log("network imported OK")
except Exception as e:
    log_exception("import network", e)

mem("after network import")

# --- Import ujson ---
try:
    log("importing ujson...")
    import ujson
    log("ujson imported OK")
except Exception as e:
    log_exception("import ujson", e)

# --- Load config (before heavy imports so we know it works) ---
section("CONFIG LOAD")
config = {}
try:
    log("opening config.json...")
    with open("config.json") as f:
        config = ujson.load(f)
    log("config.json loaded OK — keys: {}".format(list(config.keys())))
except Exception as e:
    log_exception("config.json load", e)
    log("WARNING: running with empty config defaults")

DEVICE_NAME = config.get("device_name", "ESP32-Dashboard")
WEB_PORT = config.get("web_port", 80)
log("DEVICE_NAME={}, WEB_PORT={}".format(DEVICE_NAME, WEB_PORT))

# --- Feature flags summary ---
_features = config.get("features", {})
_feature_names = ["gpio", "adc", "pwm", "i2c", "batch", "websocket"]
_enabled = [f for f in _feature_names if _features.get(f, False)]
log("FEATURES enabled: {}".format(_enabled if _enabled else "none (all disabled)"))

mem("after config load")

# --- Import Microdot (this is ~1500 lines, major memory consumer) ---
section("MICRODOT IMPORT")
try:
    log("importing lib.microdot (this is the big one)...")
    gc.collect()
    free_before = gc.mem_free()
    from lib.microdot import Microdot, Response
    gc.collect()
    free_after = gc.mem_free()
    log("Microdot imported OK — cost {} bytes".format(free_before - free_after))
except Exception as e:
    log_exception("import Microdot", e)
    log("FATAL: cannot continue without Microdot")
    raise

mem("after microdot import")

# --- Import gpio_api (another ~1100 lines, imports machine/esp32/websocket) ---
section("GPIO_API IMPORT")
try:
    log("importing gpio_api (imports machine, esp32, websocket internally)...")
    gc.collect()
    free_before = gc.mem_free()
    from gpio_api import register_routes
    gc.collect()
    free_after = gc.mem_free()
    log("gpio_api imported OK — cost {} bytes".format(free_before - free_after))
    _gpio_api_available = True
except MemoryError as e:
    log_exception("import gpio_api (OUT OF MEMORY)", e)
    log("CRITICAL: gpio_api import failed due to memory exhaustion!")
    log("The board does not have enough RAM for the full GPIO API module.")
    log("Will start WITHOUT gpio_api routes.")
    _gpio_api_available = False
except Exception as e:
    log_exception("import gpio_api", e)
    log("WARNING: gpio_api import failed — will start without GPIO routes")
    _gpio_api_available = False

mem("after gpio_api import")

# --- Create the app ---
section("APP INIT")
try:
    log("creating Microdot() app instance...")
    app = Microdot()
    log("Microdot app created OK")
except Exception as e:
    log_exception("Microdot() creation", e)
    raise

@app.before_request
async def _gc_before_request(request):
    gc.collect()

log("before_request GC handler installed")

# Record boot time for uptime calculation
BOOT_TICKS = time.ticks_ms()
log("BOOT_TICKS recorded: {}".format(BOOT_TICKS))

mem("after app creation")


# ---------- Helper functions ----------

def _rssi_quality(rssi):
    """Map RSSI dBm to a human-readable quality label."""
    if rssi >= -50:
        return "excellent"
    if rssi >= -60:
        return "good"
    if rssi >= -70:
        return "fair"
    if rssi >= -80:
        return "weak"
    return "unusable"


def get_wifi_info():
    """Return (ip, mode, rssi, quality) tuple."""
    sta = network.WLAN(network.STA_IF)
    ap = network.WLAN(network.AP_IF)

    if sta.active() and sta.isconnected():
        rssi = sta.status("rssi")
        return sta.ifconfig()[0], "STA", rssi, _rssi_quality(rssi)
    elif ap.active():
        return ap.ifconfig()[0], "AP", 0, "n/a"
    else:
        return "0.0.0.0", "NONE", 0, "n/a"


# ---------- Inline HTML dashboard ----------

section("HTML BUILD")
log("building inline HTML string...")

HTML = (
    """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>"""
    + DEVICE_NAME
    + """</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    background: #0d1117;
    color: #39d353;
    font-family: 'Courier New', Courier, monospace;
    padding: 2rem;
    line-height: 1.6;
}
h1 {
    color: #58a6ff;
    margin-bottom: 1.5rem;
    border-bottom: 1px solid #30363d;
    padding-bottom: 0.5rem;
}
.stat-container {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 1.5rem;
    max-width: 400px;
}
.stat-row {
    display: flex;
    justify-content: space-between;
    margin-bottom: 0.5rem;
}
.label { color: #8b949e; }
.value { font-weight: bold; }
</style>
</head>
<body>
    <h1>"""
    + DEVICE_NAME
    + """</h1>
    <div class="stat-container" id="status">
        <p>Connecting to device...</p>
    </div>

<script>
async function updateStatus() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();

        document.getElementById('status').innerHTML = `
            <div class="stat-row"><span class="label">IP Address:</span> <span class="value">${data.ip}</span></div>
            <div class="stat-row"><span class="label">WiFi Mode:</span> <span class="value">${data.wifi_mode}</span></div>
            <div class="stat-row"><span class="label">Uptime:</span> <span class="value">${data.uptime_s} s</span></div>
            <div class="stat-row"><span class="label">Free Memory:</span> <span class="value">${data.free_mem_kb} KB</span></div>
        `;
    } catch (err) {
        document.getElementById('status').innerHTML = '<p style="color: #f85149;">Error fetching status. Device offline?</p>';
    }
}

// Initial fetch and poll every 5 seconds
updateStatus();
setInterval(updateStatus, 5000);
</script>
</body>
</html>
"""
)

log("HTML string built OK — length={} chars".format(len(HTML)))
mem("after HTML build")

# ---------- Routes ----------

section("ROUTE REGISTRATION")

try:
    log("registering GET / (dashboard) route...")

    @app.route("/")
    async def index(request):
        """Serve the single-page HTML dashboard."""
        log("REQ: GET /")
        return Response(HTML, headers={"Content-Type": "text/html"})

    log("GET / registered OK")
except Exception as e:
    log_exception("register GET /", e)

try:
    log("registering GET /api/status route...")

    @app.route("/api/status")
    async def api_status(request):
        """Return JSON health check data."""
        log("REQ: GET /api/status")
        gc.collect()
        free_mem = gc.mem_free()

        uptime_ms = time.ticks_diff(time.ticks_ms(), BOOT_TICKS)
        uptime_s = uptime_ms // 1000

        ip, mode, rssi, quality = get_wifi_info()

        return {
            "device_name": DEVICE_NAME,
            "ip": ip,
            "wifi_mode": mode,
            "rssi_dbm": rssi,
            "wifi_quality": quality,
            "uptime_s": uptime_s,
            "free_mem": free_mem,
            "free_mem_kb": free_mem // 1024,
        }

    log("GET /api/status registered OK")
except Exception as e:
    log_exception("register GET /api/status", e)

# --- Register a route to read/clear the debug log from the browser ---
try:
    log("registering GET /api/debug/log route...")

    @app.route("/api/debug/log")
    async def debug_log_view(request):
        """Return the debug log contents as plain text — for remote debugging."""
        log("REQ: GET /api/debug/log")
        try:
            with open("debug.log", "r") as f:
                content = f.read()
            return Response(content, headers={"Content-Type": "text/plain"})
        except OSError:
            return Response("(no debug.log found)", headers={"Content-Type": "text/plain"})

    log("GET /api/debug/log registered OK")
except Exception as e:
    log_exception("register GET /api/debug/log", e)

try:
    log("registering POST /api/debug/clear route...")

    @app.route("/api/debug/clear", methods=["POST"])
    async def debug_log_clear(request):
        """Clear the debug log file."""
        log("REQ: POST /api/debug/clear")
        try:
            import os
            os.remove("debug.log")
            return {"status": "cleared"}
        except Exception:
            return {"status": "no log to clear"}

    log("POST /api/debug/clear registered OK")
except Exception as e:
    log_exception("register POST /api/debug/clear", e)

mem("after core route registration")

# --- Register GPIO API routes (if available) ---
if _gpio_api_available:
    section("GPIO ROUTE REGISTRATION")
    try:
        log("calling register_routes(app) from gpio_api...")
        gc.collect()
        free_before = gc.mem_free()
        register_routes(app)
        gc.collect()
        free_after = gc.mem_free()
        log("gpio_api register_routes() completed OK — cost {} bytes".format(free_before - free_after))
    except MemoryError as e:
        log_exception("register_routes (OUT OF MEMORY)", e)
        log("CRITICAL: GPIO route registration failed — memory exhaustion")
    except Exception as e:
        log_exception("register_routes", e)
        log("WARNING: GPIO routes not available due to error above")
else:
    log("SKIPPING gpio_api route registration (import had failed)")

mem("after all route registration")

# --- Check WiFi status before starting server ---
section("PRE-START CHECKS")
try:
    ip, mode, rssi, quality = get_wifi_info()
    log("WiFi status: ip={}, mode={}, rssi={}, quality={}".format(ip, mode, rssi, quality))

    sta = network.WLAN(network.STA_IF)
    log("STA active={}, connected={}".format(sta.active(), sta.isconnected()))
    if sta.active():
        log("STA ifconfig={}".format(sta.ifconfig()))

    ap = network.WLAN(network.AP_IF)
    log("AP active={}".format(ap.active()))
    if ap.active():
        log("AP ifconfig={}".format(ap.ifconfig()))
except Exception as e:
    log_exception("wifi status check", e)

mem("right before app.run()")

# ---------- Main ----------

if __name__ == "__main__":
    section("SERVER START")
    log("about to call app.run(port={}, debug=True)".format(WEB_PORT))
    log("if the log stops here, the server either started OK or crashed in app.run()")
    log("(app.run() is blocking — no more log lines expected unless a request comes in)")

    try:
        app.run(port=WEB_PORT, debug=True)
    except MemoryError as e:
        log_exception("app.run() MEMORY ERROR", e)
        log("FATAL: Server crashed due to memory exhaustion!")
        log("Consider removing gpio_api import to free ~30-50KB of heap.")
        mem("after crash")
        # Try to dump log to serial before dying
        try:
            from debuglog import dump
            dump()
        except Exception:
            pass
    except Exception as e:
        log_exception("app.run() CRASHED", e)
        mem("after crash")
        try:
            from debuglog import dump
            dump()
        except Exception:
            pass
        raise
