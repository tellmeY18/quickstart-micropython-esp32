# boot.py — runs on power-on: connect to WiFi or fall back to AP mode

import time

import network
import ujson

# Load config
with open("config.json") as f:
    config = ujson.load(f)

ssid = config["wifi_ssid"]
password = config["wifi_password"]
ap_ssid = config.get("ap_ssid", "ESP32-Dashboard")
ap_password = config.get("ap_password", "12345678")

# --- Try Station (client) mode first ---
sta = network.WLAN(network.STA_IF)
sta.active(True)

print("boot: connecting to WiFi '{}'...".format(ssid))
sta.connect(ssid, password)

timeout = 10
start = time.time()
while not sta.isconnected() and (time.time() - start) < timeout:
    time.sleep(0.5)

if sta.isconnected():
    ip = sta.ifconfig()[0]
    print("boot: connected! IP = {}".format(ip))
else:
    # --- WiFi failed, start AP mode ---
    sta.active(False)
    print("boot: WiFi connection failed after {}s".format(timeout))
    print("boot: starting AP '{}' ...".format(ap_ssid))

    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid=ap_ssid, password=ap_password, authmode=network.AUTH_WPA_WPA2_PSK)

    # Wait for AP to be active
    while not ap.active():
        time.sleep(0.1)

    ip = ap.ifconfig()[0]
    print("boot: AP active! Connect to '{}' and open http://{}".format(ap_ssid, ip))

print("boot: done")
