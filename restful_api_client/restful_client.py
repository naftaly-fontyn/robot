import time

import urequests.urequests as urequests
import json

SERVER_IP = "192.168.1.80"  # replace with your device’s IP or test server
# --- GET
"""
resp = urequests.get(f"http://{SERVER_IP}/hello")
if resp:
    print("GET response:", resp.text)
    resp.close()
else:
    print("GET response: Timeout")

# --- POST example ---
data = {"name": "sensor", "value": 42}
resp = urequests.post(f"http://{SERVER_IP}/hello", json=data)
if resp:
    print("POST response:", resp.text)
    resp.close()
else:
    print("POST response: Timeout" )

# --- PUT example ---
update = {"status": "ok"}
resp = urequests.put(f"http://{SERVER_IP}/update", json=update)
if resp:
    print("PUT response:", resp.text)
    resp.close()
else:
    print("PUT response: Timeout")

data = {'topic': 'LED', 'payload': {'state': 'ON', 'id': 0, 'color': 'red'},
        }
resp = urequests.post(f"http://{SERVER_IP}/messagebus", json=data)
if resp:
    print("POST response:", resp.text)
    resp.close()
else:
    print("POST response: Timeout")
"""


def post_to_messagebus(topic, payload, reply_topic=None, reply_timeout=2, wait_timeout=2):
    data = {'topic': topic,
            'payload': payload,
            'reply_topic': reply_topic,
            'reply_timeout': reply_timeout}
    resp = urequests.post(f"http://{SERVER_IP}/app/messagebus", json=data, timeout=wait_timeout)
    s = None
    r = None
    j = None
    if resp:
        s = resp.status_code
        r = resp.reason
        j = resp.json() if reply_topic else None
        resp.close()
    return s, r, j

def post_to_robot(path, payload=None, reply_topic=None, reply_timeout=2, wait_timeout=2):
    resp = urequests.post(f"http://{SERVER_IP}{path}", json=payload, timeout=wait_timeout)
    s = None
    r = None
    j = None
    if resp:
        s = resp.status_code
        r = resp.reason
        j = resp.json() if reply_topic else None
        resp.close()
    return s, r, j




if __name__ == "__main__":
    print(post_to_messagebus('led_task', {'led_list': [{'led_id': 0, 'color': 'red'}, {'led_id': 1, 'color': 'green'}]}))
    time.sleep(5)
    print(post_to_messagebus('led_task', {'led_list': [{'led_id': 0, 'color': (0,0,0)}, {'led_id': 1, 'color': 0x000000}]}))
    time.sleep(5)
    print(post_to_messagebus('us_scan', {'start_angle': 0, 'stop_angle': 180, 'step': 30}, reply_topic='us_scan_report', reply_timeout=60, wait_timeout=60))
    time.sleep(5)

    # print(post_to_messagebus('quit', {}))
    time.sleep(5)