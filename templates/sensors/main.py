# main.py — Sensors template: ADC + I2C + temperature dashboard
#
# Reads analog voltages, scans the I2C bus, and reports the ESP32's
# internal temperature — all over a REST API with a live HTML dashboard.
# No digital GPIO control, no PWM, no WebSocket streaming.

import gc
import time
import network
import ujson

# Load config
with open("config.json") as f:
    config = ujson.load(f)

DEVICE_NAME = config.get("device_name", "ESP32-Sensors")
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


# ---------- Register sensor routes ----------

from sensor_handler import register_routes
register_routes(app, config)


# ---------- GC before every request ----------

@app.before_request
async def gc_collect(request):
    gc.collect()


# ---------- Core routes ----------

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


# ---------- HTML Dashboard ----------

HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>""" + DEVICE_NAME + """ &mdash; Sensors</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0d1117;color:#c9d1d9;font-family:'Courier New',monospace;padding:1.5rem;line-height:1.5}
h1{color:#58a6ff;margin-bottom:1rem;border-bottom:1px solid #30363d;padding-bottom:.5rem}
h2{color:#58a6ff;font-size:1rem;margin:1.2rem 0 .6rem}
.panel{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:1rem;margin-bottom:1rem;max-width:600px}
.row{display:flex;justify-content:space-between;margin-bottom:.35rem}
.label{color:#8b949e}.value{color:#39d353;font-weight:bold}
.gauge{background:#21262d;border:1px solid #30363d;border-radius:4px;padding:.6rem .8rem;margin-bottom:.5rem}
.gauge .bar-bg{background:#30363d;border-radius:3px;height:10px;margin-top:.3rem;overflow:hidden}
.gauge .bar-fill{background:#39d353;height:100%;border-radius:3px;transition:width .4s ease}
.device{background:#21262d;border:1px solid #30363d;border-radius:4px;padding:.4rem .8rem;margin-bottom:.3rem;display:flex;justify-content:space-between}
.temp-val{font-size:1.6rem;color:#f0883e;font-weight:bold}
.err{color:#f85149}
.none{color:#8b949e;font-style:italic}
</style></head>
<body>
<h1>""" + DEVICE_NAME + """</h1>

<div class="panel" id="status"><p>Connecting...</p></div>

<h2>Internal Temperature</h2>
<div class="panel" id="temp"><p>Reading...</p></div>

<h2>ADC Readings <span style="color:#8b949e;font-size:.8rem">(auto-refresh 2s)</span></h2>
<div id="adc"><div class="panel">Reading...</div></div>

<h2>I2C Devices</h2>
<div class="panel" id="i2c"><p>Scanning...</p></div>

<script>
function E(id){return document.getElementById(id)}

function R(l,v){return '<div class="row"><span class="label">'+l+'</span><span class="value">'+v+'</span></div>'}

async function updateStatus(){
 try{
  var r=await fetch('/api/status');var d=await r.json();
  E('status').innerHTML=R('IP',d.ip)+R('WiFi',d.wifi_mode)+R('Signal',d.wifi_quality)+R('Uptime',d.uptime_s+'s')+R('Free RAM',d.free_mem_kb+' KB');
 }catch(e){E('status').innerHTML='<p class="err">Device offline?</p>'}
}

async function updateTemp(){
 try{
  var r=await fetch('/api/temperature');var d=await r.json();
  if(d.error){E('temp').innerHTML='<p class="err">'+d.error+'</p>';return}
  E('temp').innerHTML='<span class="temp-val">'+d.temp_c+' &deg;C</span>';
 }catch(e){E('temp').innerHTML='<p class="err">Failed to read temperature</p>'}
}

async function updateADC(){
 try{
  var r=await fetch('/api/adc/all');var d=await r.json();
  var h='';
  var pins=Object.keys(d.readings).sort();
  for(var i=0;i<pins.length;i++){
   var p=pins[i];var v=d.readings[p];
   if(v.error){h+='<div class="gauge"><b>GPIO '+p+'</b> <span class="err">'+v.error+'</span></div>';continue}
   var pct=Math.min(100,Math.round(v.raw/65535*100));
   h+='<div class="gauge"><div class="row"><span class="label">GPIO '+p+' ('+v.atten+')</span><span class="value">'+v.voltage_v+' V</span></div>';
   h+='<div class="row"><span class="label">Raw</span><span class="value">'+v.raw+'</span></div>';
   h+='<div class="bar-bg"><div class="bar-fill" style="width:'+pct+'%"></div></div></div>';
  }
  E('adc').innerHTML=h||'<div class="panel none">No ADC pins available</div>';
 }catch(e){E('adc').innerHTML='<div class="panel"><p class="err">Failed to read ADC</p></div>'}
}

async function updateI2C(){
 try{
  var r=await fetch('/api/i2c/scan');var d=await r.json();
  if(d.error){E('i2c').innerHTML='<p class="err">'+d.error+'</p>';return}
  if(d.count===0){E('i2c').innerHTML='<p class="none">No devices found on I2C bus</p>';return}
  var h='<div class="row"><span class="label">Found</span><span class="value">'+d.count+' device'+(d.count>1?'s':'')+'</span></div>';
  for(var i=0;i<d.hex.length;i++){
   h+='<div class="device"><span>'+d.hex[i]+'</span><span class="label">addr '+d.devices[i]+'</span></div>';
  }
  E('i2c').innerHTML=h;
 }catch(e){E('i2c').innerHTML='<p class="err">I2C scan failed</p>'}
}

updateStatus();updateTemp();updateADC();updateI2C();
setInterval(function(){updateStatus();updateTemp();updateADC()},2000);
setInterval(updateI2C,10000);
</script></body></html>"""


@app.route("/")
async def index(request):
    return Response(HTML, headers={"Content-Type": "text/html"})


# ---------- Start ----------

if __name__ == "__main__":
    app.run(port=WEB_PORT, debug=True)
