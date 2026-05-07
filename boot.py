# boot.py — runs on power-on: connect to WiFi or fall back to AP mode
#
# This file is shared by all templates. It reads config.json from the
# working directory, attempts a WiFi STA connection with a 10-second
# timeout, and falls back to AP mode if WiFi fails.
#
# After boot.py completes, main.py runs automatically.

import time
import network
import ujson

# Load config
try:
    with open("config.json") as f:
        config = ujson.load(f)
except OSError:
    print("boot: ERROR — config.json not found. Copy config.json.example to config.json and edit it.")
    config = {}

ssid = config.get("wifi_ssid", "")
password = config.get("wifi_password", "")
ap_ssid = config.get("ap_ssid", "ESP32-Dev")
ap_password = config.get("ap_password", "12345678")

# --- Try Station (client) mode first ---
sta = network.WLAN(network.STA_IF)
sta.active(True)

if ssid:
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
    if ssid:
        print("boot: WiFi connection failed after 10s")
    else:
        print("boot: no wifi_ssid configured, skipping STA mode")

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
