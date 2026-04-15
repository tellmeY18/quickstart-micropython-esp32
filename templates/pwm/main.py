"""
PWM Template — LED dimming / servo control over HTTP.

Provides a web dashboard with a duty-cycle slider and REST API
for starting, stopping, and tuning PWM outputs.
"""

import gc
import time
import network
import ujson

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
with open("config.json") as f:
    config = ujson.load(f)

DEVICE_NAME = config.get("device_name", "ESP32-PWM")
WEB_PORT = config.get("web_port", 80)
DEFAULT_PIN = config.get("pin_aliases", {}).get("led", 5)

# ---------------------------------------------------------------------------
# Microdot
# ---------------------------------------------------------------------------
from lib.microdot import Microdot, Response

Response.default_content_type = "text/html"

app = Microdot()
BOOT_TICKS = time.ticks_ms()

# ---------------------------------------------------------------------------
# PWM routes
# ---------------------------------------------------------------------------
from pwm_handler import register_routes

register_routes(app, config)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rssi_quality(rssi):
    """Convert RSSI dBm to a human-readable quality string."""
    if rssi >= -50:
        return "Excellent"
    if rssi >= -60:
        return "Good"
    if rssi >= -70:
        return "Fair"
    return "Weak"


def get_wifi_info():
    """Return a dict of current WiFi connection details."""
    sta = network.WLAN(network.STA_IF)
    if sta.active() and sta.isconnected():
        ip, subnet, gateway, dns = sta.ifconfig()
        rssi = sta.status("rssi") if hasattr(sta, "status") else 0
        return {
            "mode": "STA",
            "ip": ip,
            "subnet": subnet,
            "gateway": gateway,
            "dns": dns,
            "rssi": rssi,
            "quality": _rssi_quality(rssi),
        }
    ap = network.WLAN(network.AP_IF)
    if ap.active():
        ip = ap.ifconfig()[0]
        return {"mode": "AP", "ip": ip}
    return {"mode": "DISCONNECTED"}


# ---------------------------------------------------------------------------
# Before-request GC
# ---------------------------------------------------------------------------

@app.before_request
def _gc_collect(req):
    gc.collect()


# ---------------------------------------------------------------------------
# Status API
# ---------------------------------------------------------------------------

@app.get("/api/status")
def api_status(req):
    wifi = get_wifi_info()
    uptime_s = time.ticks_diff(time.ticks_ms(), BOOT_TICKS) // 1000
    gc.collect()
    return {
        "device": DEVICE_NAME,
        "uptime_s": uptime_s,
        "free_mem": gc.mem_free(),
        "wifi": wifi,
    }


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{device} — PWM Control</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
      background:#0f172a;color:#e2e8f0;padding:1rem;max-width:640px;margin:0 auto}}
h1{{font-size:1.4rem;margin-bottom:.5rem;color:#38bdf8}}
.card{{background:#1e293b;border-radius:12px;padding:1rem;margin-bottom:1rem}}
.card h2{{font-size:1rem;color:#94a3b8;margin-bottom:.75rem}}
.row{{display:flex;justify-content:space-between;padding:.25rem 0;font-size:.9rem}}
.row span:first-child{{color:#64748b}}
#status-dot{{display:inline-block;width:10px;height:10px;border-radius:50%;
             background:#22c55e;margin-right:6px;vertical-align:middle}}
button{{background:#2563eb;color:#fff;border:none;border-radius:8px;padding:.6rem 1.2rem;
        font-size:.95rem;cursor:pointer;width:100%;margin-top:.5rem}}
button:active{{background:#1d4ed8}}
button.stop{{background:#dc2626}}
button.stop:active{{background:#b91c1c}}
input[type=range]{{-webkit-appearance:none;width:100%;height:8px;border-radius:4px;
                   background:#334155;outline:none;margin:1rem 0}}
input[type=range]::-webkit-slider-thumb{{-webkit-appearance:none;width:24px;height:24px;
                                         border-radius:50%;background:#38bdf8;cursor:pointer}}
.val{{text-align:center;font-size:2rem;font-weight:700;color:#38bdf8;margin:.25rem 0}}
.sub{{text-align:center;font-size:.85rem;color:#64748b}}
.msg{{text-align:center;font-size:.85rem;color:#f59e0b;min-height:1.2em;margin-top:.25rem}}
</style>
</head>
<body>
<h1><span id="status-dot"></span>{device}</h1>

<div class="card">
 <h2>System</h2>
 <div class="row"><span>Uptime</span><span id="uptime">—</span></div>
 <div class="row"><span>Free memory</span><span id="mem">—</span></div>
 <div class="row"><span>WiFi</span><span id="wifi">—</span></div>
</div>

<div class="card">
 <h2>PWM — GPIO {pin}</h2>
 <div class="val" id="duty-val">0 %</div>
 <input type="range" id="slider" min="0" max="100" value="0" disabled>
 <div class="row"><span>Frequency</span><span id="freq-val">— Hz</span></div>
 <div class="sub" id="duty16-val">duty_u16: 0 / 65535</div>
 <div class="msg" id="msg"></div>
 <button id="btn-start">Start PWM (1 kHz)</button>
 <button id="btn-stop" class="stop" style="display:none">Stop PWM</button>
</div>

<script>
const PIN = {pin};
const MIN_INTERVAL = 200;
let lastSend = 0;
let pending = null;
let running = false;

const $ = id => document.getElementById(id);

async function fetchStatus() {{
  try {{
    const r = await fetch("/api/status");
    const d = await r.json();
    $("uptime").textContent = d.uptime_s + "s";
    $("mem").textContent = (d.free_mem / 1024).toFixed(1) + " KB";
    const w = d.wifi;
    $("wifi").textContent = w.mode === "STA"
      ? w.ip + " (" + w.quality + ")"
      : w.mode === "AP" ? "AP " + w.ip : "disconnected";
  }} catch(e) {{}}
}}

async function fetchPWM() {{
  try {{
    const r = await fetch("/api/pwm/" + PIN);
    if (!r.ok) return;
    const d = await r.json();
    if (d.mode === "PWM") {{
      running = true;
      $("slider").disabled = false;
      const pct = Math.round(d.duty_pct);
      $("slider").value = pct;
      $("duty-val").textContent = pct + " %";
      $("freq-val").textContent = d.freq + " Hz";
      $("duty16-val").textContent = "duty_u16: " + d.duty_u16 + " / 65535";
      $("btn-start").style.display = "none";
      $("btn-stop").style.display = "";
    }} else {{
      resetUI();
    }}
  }} catch(e) {{ resetUI(); }}
}}

function resetUI() {{
  running = false;
  $("slider").disabled = true;
  $("slider").value = 0;
  $("duty-val").textContent = "0 %";
  $("freq-val").textContent = "— Hz";
  $("duty16-val").textContent = "duty_u16: 0 / 65535";
  $("btn-start").style.display = "";
  $("btn-stop").style.display = "none";
}}

function msg(t) {{ $("msg").textContent = t; setTimeout(() => $("msg").textContent = "", 3000); }}

async function startPWM() {{
  try {{
    const r = await fetch("/api/pwm/" + PIN + "/start", {{
      method: "POST",
      headers: {{"Content-Type": "application/json"}},
      body: JSON.stringify({{freq: 1000, duty_u16: 0}})
    }});
    const d = await r.json();
    if (r.ok) {{ msg("PWM started"); fetchPWM(); }}
    else {{ msg(d.error || "Failed to start"); }}
  }} catch(e) {{ msg("Request failed"); }}
}}

async function stopPWM() {{
  try {{
    const r = await fetch("/api/pwm/" + PIN + "/stop", {{method: "POST"}});
    if (r.ok) {{ msg("PWM stopped"); resetUI(); }}
  }} catch(e) {{ msg("Request failed"); }}
}}

async function sendDuty(pct) {{
  const duty_u16 = Math.round(pct * 65535 / 100);
  $("duty-val").textContent = pct + " %";
  $("duty16-val").textContent = "duty_u16: " + duty_u16 + " / 65535";
  const now = Date.now();
  if (now - lastSend < MIN_INTERVAL) {{
    clearTimeout(pending);
    pending = setTimeout(() => sendDuty(pct), MIN_INTERVAL - (now - lastSend));
    return;
  }}
  lastSend = now;
  try {{
    await fetch("/api/pwm/" + PIN + "/duty", {{
      method: "POST",
      headers: {{"Content-Type": "application/json"}},
      body: JSON.stringify({{duty_u16: duty_u16}})
    }});
  }} catch(e) {{}}
}}

$("slider").addEventListener("input", e => {{
  if (running) sendDuty(parseInt(e.target.value));
}});
$("btn-start").addEventListener("click", startPWM);
$("btn-stop").addEventListener("click", stopPWM);

fetchStatus();
fetchPWM();
setInterval(fetchStatus, 5000);
</script>
</body>
</html>
"""


@app.get("/")
def dashboard(req):
    return DASHBOARD_HTML.format(device=DEVICE_NAME, pin=DEFAULT_PIN)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
print("[pwm] Starting", DEVICE_NAME, "on port", WEB_PORT)
app.run(port=WEB_PORT, debug=True)
