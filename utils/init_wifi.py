import time
import gc
import network

from config import WIP, WIS

def init_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    time.sleep(1)
    # set static address
    wlan.ifconfig(('192.168.1.80', '255.255.255.0', '0.0.0.0', '8.8.8.8'))
#     print(wlan.scan())
    wlan.connect(WIS, WIP)

    while not wlan.isconnected():
        time.sleep(0.05)
    ifcfg = wlan.ifconfig()
#     PRINT("Wi-Fi connected:", ifcfg)
    print(ifcfg[0])
    gc.collect()