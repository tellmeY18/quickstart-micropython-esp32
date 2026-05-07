# main.py — Minimal template: WiFi status dashboard + health-check API
#
# The smallest possible MicroPython web server for ESP32.
# Serves an HTML dashboard at GET / and a JSON status endpoint at GET /api/status.
# No GPIO, no peripherals, no debug logging.

import gc
import time
import network
import ujson

# Load config
with open("config.json") as f:
    config = ujson.load(f)

DEVICE_NAME = config.get("device_name", "ESP32-Dev")
WEB_PORT = config.get("web_port", 80)

# Import Microdot
from lib.microdot import Microdot, Response

app = Microdot()

# Record boot time for uptime calculation
BOOT_TICKS = time.ticks_ms()


# ---------- Helpers ----------

def _rssi_quality(rssi):
    if rssi >= -50: return "excellent"
    if rssi >= -60: return "good"
    if rssi >= -70: return "fair"
    if rssi >= -80: return "weak"
    return "unusable"


def get_wifi_info():
    sta = network.WLAN(network.STA_IF)
    ap = network.WLAN(network.AP_IF)
    if sta.active() and sta.isconnected():
        rssi = sta.status("rssi")
        return sta.ifconfig()[0], "STA", rssi, _rssi_quality(rssi)
    elif ap.active():
        return ap.ifconfig()[0], "AP", 0, "n/a"
    return "0.0.0.0", "NONE", 0, "n/a"


# ---------- HTML Dashboard ----------

HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>""" + DEVICE_NAME + """</title>
<style>*{margin:0;padding:0;box-sizing:border-box}body{background:#0d1117;color:#39d353;font-family:'Courier New',monospace;padding:2rem;line-height:1.6}h1{color:#58a6ff;margin-bottom:1.5rem;border-bottom:1px solid #30363d;padding-bottom:.5rem}.stat-container{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:1.5rem;max-width:400px}.stat-row{display:flex;justify-content:space-between;margin-bottom:.5rem}.label{color:#8b949e}.value{font-weight:bold}</style></head>
<body><h1>""" + DEVICE_NAME + """</h1>
<div class="stat-container" id="status"><p>Connecting...</p></div>
<script>
async function u(){try{const r=await fetch('/api/status');const d=await r.json();
document.getElementById('status').innerHTML=
'<div class="stat-row"><span class="label">IP:</span><span class="value">'+d.ip+'</span></div>'+
'<div class="stat-row"><span class="label">WiFi:</span><span class="value">'+d.wifi_mode+'</span></div>'+
'<div class="stat-row"><span class="label">Signal:</span><span class="value">'+d.wifi_quality+'</span></div>'+
'<div class="stat-row"><span class="label">Uptime:</span><span class="value">'+d.uptime_s+'s</span></div>'+
'<div class="stat-row"><span class="label">Free RAM:</span><span class="value">'+d.free_mem_kb+' KB</span></div>'
}catch(e){document.getElementById('status').innerHTML='<p style="color:#f85149">Device offline?</p>'}}
u();setInterval(u,5000);
</script></body></html>"""


# ---------- Routes ----------

@app.route("/")
async def index(request):
    return Response(HTML, headers={"Content-Type": "text/html"})


@app.route("/api/status")
async def api_status(request):
    gc.collect()
    free = gc.mem_free()
    ip, mode, rssi, quality = get_wifi_info()
    return {
        "device_name": DEVICE_NAME,
        "ip": ip,
        "wifi_mode": mode,
        "rssi_dbm": rssi,
        "wifi_quality": quality,
        "uptime_s": time.ticks_diff(time.ticks_ms(), BOOT_TICKS) // 1000,
        "free_mem": free,
        "free_mem_kb": free // 1024,
    }


# ---------- Start ----------

if __name__ == "__main__":
    app.run(port=WEB_PORT, debug=True)
