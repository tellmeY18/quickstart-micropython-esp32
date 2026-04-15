# main.py — GPIO template: digital pin control over REST API
#
# WiFi status dashboard with a GPIO toggle panel. Each pin listed in
# gpio_whitelist gets a row with current state and toggle button.
# Uses gpio_handler.py for all /api/gpio/* routes.

import gc
import time
import network
import ujson

# Load config
with open("config.json") as f:
    config = ujson.load(f)

DEVICE_NAME = config.get("device_name", "ESP32-GPIO")
WEB_PORT = config.get("web_port", 80)
GPIO_WHITELIST = config.get("gpio_whitelist", [])

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


# ---------- GC before every request ----------

@app.before_request
async def gc_collect(request):
    gc.collect()


# ---------- Build pin list for HTML ----------

_pin_js_array = ujson.dumps(GPIO_WHITELIST)


# ---------- HTML Dashboard ----------

HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>""" + DEVICE_NAME + """</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0d1117;color:#39d353;font-family:'Courier New',monospace;padding:2rem;line-height:1.6}
h1{color:#58a6ff;margin-bottom:1.5rem;border-bottom:1px solid #30363d;padding-bottom:.5rem}
h2{color:#58a6ff;margin:1.5rem 0 1rem;font-size:1.1rem}
.card{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:1.5rem;max-width:500px;margin-bottom:1rem}
.stat-row{display:flex;justify-content:space-between;margin-bottom:.5rem}
.label{color:#8b949e}.value{font-weight:bold}
.pin-row{display:flex;justify-content:space-between;align-items:center;padding:.5rem 0;border-bottom:1px solid #21262d}
.pin-row:last-child{border-bottom:none}
.pin-name{color:#8b949e;min-width:80px}
.pin-state{min-width:50px;text-align:center;font-weight:bold}
.pin-state.high{color:#39d353}
.pin-state.low{color:#8b949e}
.pin-state.unconfigured{color:#484f58;font-style:italic}
.btn{background:#21262d;color:#c9d1d9;border:1px solid #30363d;border-radius:4px;padding:.3rem .8rem;cursor:pointer;font-family:inherit;font-size:.85rem}
.btn:hover{background:#30363d;border-color:#58a6ff}
.btn:disabled{opacity:.4;cursor:not-allowed}
.btn-on{background:#238636;border-color:#2ea043;color:#fff}
.btn-off{background:#21262d;border-color:#30363d}
.error{color:#f85149}
.setup-hint{color:#484f58;font-size:.8rem;margin-top:.5rem}
</style></head>
<body>
<h1>""" + DEVICE_NAME + """</h1>

<div class="card" id="status"><p>Connecting...</p></div>

<h2>GPIO Control</h2>
<div class="card" id="gpio-panel"><p>Loading pins...</p></div>
<p class="setup-hint">Pins are auto-configured as OUT on first toggle. Use the API for IN mode or pull resistors.</p>

<script>
var PINS=""" + _pin_js_array + """;

async function updateStatus(){
 try{
  var r=await fetch('/api/status');var d=await r.json();
  document.getElementById('status').innerHTML=
   '<div class="stat-row"><span class="label">IP:</span><span class="value">'+d.ip+'</span></div>'+
   '<div class="stat-row"><span class="label">WiFi:</span><span class="value">'+d.wifi_mode+'</span></div>'+
   '<div class="stat-row"><span class="label">Signal:</span><span class="value">'+d.wifi_quality+'</span></div>'+
   '<div class="stat-row"><span class="label">Uptime:</span><span class="value">'+d.uptime_s+'s</span></div>'+
   '<div class="stat-row"><span class="label">Free RAM:</span><span class="value">'+d.free_mem_kb+' KB</span></div>';
 }catch(e){document.getElementById('status').innerHTML='<p class="error">Device offline?</p>';}
}

async function updatePins(){
 try{
  var r=await fetch('/api/gpio/pins');var d=await r.json();
  var html='';
  for(var i=0;i<PINS.length;i++){
   var p=PINS[i];
   var s=d.pins[String(p)];
   var stateClass='unconfigured';
   var stateText='--';
   var btnText='Setup';
   var btnClass='btn';
   if(s){
    if(s.mode==='OUT'){
     stateClass=s.value?'high':'low';
     stateText=s.value?'HIGH':'LOW';
     btnText=s.value?'Turn OFF':'Turn ON';
     btnClass=s.value?'btn btn-on':'btn btn-off';
    }else{
     stateClass=s.value?'high':'low';
     stateText=s.value?'HIGH':'LOW';
     btnText='IN mode';
     btnClass='btn';
    }
   }
   html+='<div class="pin-row">'+
    '<span class="pin-name">GPIO '+p+'</span>'+
    '<span class="pin-state '+stateClass+'">'+stateText+'</span>'+
    '<button class="'+btnClass+'" onclick="togglePin('+p+','+(!s?'true':'false')+')"'+(s&&s.mode!=='OUT'?' disabled':'')+'>'+btnText+'</button>'+
    '</div>';
  }
  if(!html)html='<p style="color:#484f58">No pins in gpio_whitelist. Edit config.json to add pins.</p>';
  document.getElementById('gpio-panel').innerHTML=html;
 }catch(e){document.getElementById('gpio-panel').innerHTML='<p class="error">Failed to load pin states.</p>';}
}

async function togglePin(pin,needsSetup){
 try{
  if(needsSetup){
   await fetch('/api/gpio/'+pin+'/mode',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:'OUT'})});
  }
  await fetch('/api/gpio/'+pin+'/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
  await updatePins();
 }catch(e){console.error('Toggle failed:',e);}
}

updateStatus();updatePins();
setInterval(updateStatus,5000);
setInterval(updatePins,2000);
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


# ---------- Register GPIO routes ----------

from gpio_handler import register_routes
register_routes(app, config)


# ---------- Start ----------

if __name__ == "__main__":
    app.run(port=WEB_PORT, debug=True)
