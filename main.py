# main.py — Microdot web server: serves dashboard + /api/status

import gc
import time

import network
import ujson

from lib.microdot import Microdot, Response

# Load config
try:
    with open("config.json") as f:
        config = ujson.load(f)
except Exception:
    config = {}

DEVICE_NAME = config.get("device_name", "ESP32-Dashboard")
WEB_PORT = config.get("web_port", 80)

app = Microdot()

# Record boot time for uptime calculation
BOOT_TICKS = time.ticks_ms()


def get_wifi_info():
    """Return (ip_address, wifi_mode) tuple."""
    sta = network.WLAN(network.STA_IF)
    ap = network.WLAN(network.AP_IF)

    if sta.active() and sta.isconnected():
        return sta.ifconfig()[0], "STA"
    elif ap.active():
        return ap.ifconfig()[0], "AP"
    else:
        return "0.0.0.0", "NONE"


# ---------- inline HTML dashboard ----------

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

# ---------- Routes ----------


@app.route("/")
async def index(request):
    """Serve the single-page HTML dashboard."""
    return Response(HTML, headers={"Content-Type": "text/html"})


@app.route("/api/status")
async def api_status(request):
    """Return JSON health check data."""
    gc.collect()
    free_mem = gc.mem_free()

    # Handle uptime (ticks wrap around after ~12 days, but fine for simple dashboard)
    uptime_ms = time.ticks_diff(time.ticks_ms(), BOOT_TICKS)
    uptime_s = uptime_ms // 1000

    ip, mode = get_wifi_info()

    return {
        "device_name": DEVICE_NAME,
        "ip": ip,
        "wifi_mode": mode,
        "uptime_s": uptime_s,
        "free_mem": free_mem,
        "free_mem_kb": free_mem // 1024,
    }


# ---------- Main ----------

if __name__ == "__main__":
    print(f"Starting web server on port {WEB_PORT}...")
    app.run(port=WEB_PORT, debug=True)
