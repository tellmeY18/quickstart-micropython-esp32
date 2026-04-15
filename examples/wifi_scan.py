# examples/wifi_scan.py — Scan nearby WiFi networks
#
# Displays SSID, channel, RSSI (signal strength), and security type
# for all visible access points, sorted by signal strength (strongest first).
#
# Wiring: None required — uses the ESP32's built-in WiFi radio.
#
# Usage:
#   esp run examples/wifi_scan.py

import network

# Security type lookup table
AUTH_NAMES = {
    0: "OPEN",
    1: "WEP",
    2: "WPA-PSK",
    3: "WPA2-PSK",
    4: "WPA/WPA2-PSK",
    5: "WPA2-ENTERPRISE",
    6: "WPA3-PSK",
    7: "WPA2/WPA3-PSK",
}

sta = network.WLAN(network.STA_IF)
was_active = sta.active()
sta.active(True)

print("Scanning WiFi networks...")
results = sta.scan()

# Sort by RSSI descending (index 3 in scan tuple)
results.sort(key=lambda r: r[3], reverse=True)

print()
print("{:<32s} {:>4s} {:>6s}  {}".format("SSID", "CH", "RSSI", "SECURITY"))
print("-" * 60)

for ssid, bssid, channel, rssi, authmode, hidden in results:
    ssid_str = ssid.decode("utf-8") if ssid else "(hidden)"
    if hidden:
        ssid_str = "(hidden)"
    auth_str = AUTH_NAMES.get(authmode, "AUTH={}".format(authmode))
    print("{:<32s} {:>4d} {:>4d} dBm  {}".format(ssid_str, channel, rssi, auth_str))

print()
print("Found {} network(s).".format(len(results)))

# Restore previous WiFi state
if not was_active:
    sta.active(False)
