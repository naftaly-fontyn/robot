import network
import time

# A helper dictionary to make the security mode human-readable
AUTH_MODES = {
    0: "OPEN",
    1: "WEP",
    2: "WPA-PSK",
    3: "WPA2-PSK",
    4: "WPA/WPA2-PSK",
    5: "WPA2-Enterprise" # Available on some boards
}

print("Activating Wi-Fi station interface...")
# Ensure the station interface is active
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

print("Scanning for Wi-Fi networks...")
print("This can take a few seconds...")

try:
    # The scan() method returns a list of tuples
    # Each tuple contains: (ssid, bssid, channel, RSSI, authmode, hidden)
    networks = wlan.scan()

    if not networks:
        print("No networks found.")
    else:
        print(f"Found {len(networks)} networks:")
        print("---------------------------------")
        
        # Sort by signal strength (RSSI), strongest first
        # RSSI is a negative number, so we sort from high to low (e.g., -30 is better than -80)
        networks.sort(key=lambda x: x[3], reverse=True)
        
        for net in networks:
            # net[0] = ssid (as bytes)
            # net[1] = bssid (MAC address, as bytes)
            # net[2] = channel
            # net[3] = RSSI (signal strength)
            # net[4] = authmode (security)
            # net[5] = hidden (0=False, 1=True)
            
            ssid = net[0].decode('utf-8')
            rssi = net[3]
            channel = net[2]
            authmode_num = net[4]
            authmode_str = AUTH_MODES.get(authmode_num, "UNKNOWN")
            
            # Don't print hidden networks (where ssid is empty)
            if ssid:
                print(f"SSID:     {ssid}")
                print(f"  Signal:   {rssi} dBm")
                print(f"  Channel:  {channel}")
                print(f"  Security: {authmode_str} ({authmode_num})")
                print("") # Add a blank line

except OSError as e:
    print(f"Error during scan: {e}")
    print("Device may be busy. Try again.")

finally:
    # You can leave the interface active if you plan to connect,
    # or deactivate it to save power.
    # wlan.active(False) 
    print("Scan complete.")
