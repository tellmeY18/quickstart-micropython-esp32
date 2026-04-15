# main.py — NeoPixel template: WS2812B RGB LED control over REST API
#
# WiFi status dashboard with an interactive color picker for WS2812B
# NeoPixel LEDs. Uses neopixel_handler.py for all /api/neopixel/* routes.

import gc
import time
import network
import ujson

# Load config
with open("config.json") as f:
    config = ujson.load(f)

DEVICE_NAME = config.get("device_name", "ESP32-NeoPixel")
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


# ---------- GC before every request ----------

@app.before_request
async def gc_collect(request):
    gc.collect()


# ---------- Register NeoPixel routes ----------

from neopixel_handler import register_routes
register_routes(app, config)


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
.color-section{display:flex;align-items:center;gap:1rem;margin-bottom:1rem;flex-wrap:wrap}
#colorPicker{width:80px;height:50px;border:1px solid #30363d;border-radius:4px;cursor:pointer;background:transparent;padding:0}
#colorPicker::-webkit-color-swatch-wrapper{padding:2px}
#colorPicker::-webkit-color-swatch{border:none;border-radius:2px}
#swatch{width:50px;height:50px;border:1px solid #30363d;border-radius:4px;background:#000}
.rgb-label{color:#8b949e;font-size:.85rem}
.btn{background:#21262d;color:#c9d1d9;border:1px solid #30363d;border-radius:4px;padding:.5rem 1.2rem;cursor:pointer;font-family:inherit;font-size:.9rem}
.btn:hover{background:#30363d;border-color:#58a6ff}
.btn-set{background:#238636;color:#fff;border-color:#2ea043}
.btn-set:hover{background:#2ea043}
.btn-off{background:#da3633;color:#fff;border-color:#f85149}
.btn-off:hover{background:#f85149}
.btn:disabled{opacity:.4;cursor:not-allowed}
.msg{color:#8b949e;font-size:.85rem;margin-top:.5rem;min-height:1.2em}
</style></head>
<body>
<h1>""" + DEVICE_NAME + """</h1>

<h2>System Status</h2>
<div class="card" id="status"><p>Connecting...</p></div>

<h2>NeoPixel Control</h2>
<div class="card">
  <div class="color-section">
    <div>
      <input type="color" id="colorPicker" value="#ff0000">
      <div class="rgb-label" id="rgbText">R:255 G:0 B:0</div>
    </div>
    <div id="swatch"></div>
  </div>
  <div style="display:flex;gap:.5rem;flex-wrap:wrap">
    <button class="btn btn-set" id="btnSet" onclick="setColor()">Set Color</button>
    <button class="btn btn-off" id="btnOff" onclick="clearLeds()">Off</button>
  </div>
  <div class="msg" id="msg"></div>
</div>

<script>
var picker=document.getElementById('colorPicker');
var swatch=document.getElementById('swatch');
var rgbText=document.getElementById('rgbText');
var msg=document.getElementById('msg');

function hexToRgb(h){
  var r=parseInt(h.slice(1,3),16);
  var g=parseInt(h.slice(3,5),16);
  var b=parseInt(h.slice(5,7),16);
  return{r:r,g:g,b:b};
}

picker.addEventListener('input',function(){
  var c=hexToRgb(picker.value);
  rgbText.textContent='R:'+c.r+' G:'+c.g+' B:'+c.b;
});

async function setColor(){
  var c=hexToRgb(picker.value);
  msg.textContent='Setting...';
  try{
    var r=await fetch('/api/neopixel',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(c)});
    var d=await r.json();
    if(d.ok){
      swatch.style.background=picker.value;
      msg.textContent='Color set to R:'+d.color.r+' G:'+d.color.g+' B:'+d.color.b;
    }else{
      msg.textContent='Error: '+(d.error||'Unknown error');
    }
  }catch(e){msg.textContent='Request failed: '+e;}
}

async function clearLeds(){
  msg.textContent='Clearing...';
  try{
    var r=await fetch('/api/neopixel/clear',{method:'POST'});
    var d=await r.json();
    if(d.ok){
      swatch.style.background='#000';
      msg.textContent='All LEDs off';
    }else{
      msg.textContent='Error: '+(d.error||'Unknown error');
    }
  }catch(e){msg.textContent='Request failed: '+e;}
}

async function loadCurrent(){
  try{
    var r=await fetch('/api/neopixel');
    var d=await r.json();
    if(d.pixels&&d.pixels.length>0){
      var p=d.pixels[0];
      var hex='#'+('0'+p[0].toString(16)).slice(-2)+('0'+p[1].toString(16)).slice(-2)+('0'+p[2].toString(16)).slice(-2);
      swatch.style.background='rgb('+p[0]+','+p[1]+','+p[2]+')';
    }
  }catch(e){}
}

async function updateStatus(){
  try{
    var r=await fetch('/api/status');
    var d=await r.json();
    document.getElementById('status').innerHTML=
      '<div class="stat-row"><span class="label">IP:</span><span class="value">'+d.ip+'</span></div>'+
      '<div class="stat-row"><span class="label">WiFi:</span><span class="value">'+d.wifi_mode+'</span></div>'+
      '<div class="stat-row"><span class="label">Signal:</span><span class="value">'+d.wifi_quality+'</span></div>'+
      '<div class="stat-row"><span class="label">Uptime:</span><span class="value">'+d.uptime_s+'s</span></div>'+
      '<div class="stat-row"><span class="label">Free RAM:</span><span class="value">'+d.free_mem_kb+' KB</span></div>';
  }catch(e){
    document.getElementById('status').innerHTML='<p style="color:#f85149">Device offline?</p>';
  }
}

loadCurrent();
updateStatus();
setInterval(updateStatus,5000);
</script>
</body></html>"""


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
