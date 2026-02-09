import time
import json
import threading
import asyncio
from aiocoap import Message, Code, Context

# CoAP Configuration
ROBOT_IP = "192.168.1.80"  # Robot IP Address
COAP_PORT = 5683

class CoapInterface:
    def __init__(self, robot_ip):
        self.robot_ip = robot_ip
        self.loop = asyncio.new_event_loop()
        self.context = None
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        # Wait for context to be ready
        future = asyncio.run_coroutine_threadsafe(self._init_context(), self.loop)
        try:
            future.result(timeout=5)
        except Exception as e:
            print(f"[CoAP] Failed to initialize context: {e}")

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def _init_context(self):
        self.context = await Context.create_client_context()
        print("[CoAP] Context initialized")

    def close(self):
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join()

    async def _send_request_async(self, path, payload):
        uri = f"coap://{self.robot_ip}/{path.lstrip('/')}"
        encoded_payload = json.dumps(payload).encode('utf-8')

        request = Message(code=Code.POST, uri=uri, payload=encoded_payload)

        try:
            response = await self.context.request(request).response
            return response.code, response.payload
        except Exception as e:
            print(f"[CoAP] Request failed: {e}")
            return None, None

    def send_rpc(self, path, payload, timeout=5):
        """
        Sends a CoAP POST request and waits for the response.
        Returns: (status_code, reason, json_data)
        """
        future = asyncio.run_coroutine_threadsafe(
            self._send_request_async(path, payload),
            self.loop
        )

        try:
            code, resp_payload = future.result(timeout=timeout)
            if code is None:
                return 500, "Internal Error", None

            # Parse response
            resp_data = {}
            if resp_payload:
                try:
                    resp_data = json.loads(resp_payload.decode('utf-8'))
                except:
                    resp_data = resp_payload.decode('utf-8')

            # Map CoAP codes to HTTP-like status for compatibility
            if hasattr(code, 'class_') and hasattr(code, 'detail'):
                status_int = code.class_ * 100 + code.detail
            else:
                c = int(code)
                status_int = (c >> 5) * 100 + (c & 0x1F)
            return status_int, str(code), resp_data

        except TimeoutError:
            return 504, "Timeout", None
        except Exception as e:
            return 500, str(e), None


# --- Global Instance (Lazy Load) ---
_interface = None

def get_interface():
    global _interface
    if _interface is None:
        print(f"[Client] Initializing CoAP Interface to {ROBOT_IP}...")
        _interface = CoapInterface(ROBOT_IP)
    return _interface

# --- Drop-in Replacements (Updated to use get_interface) ---

def post_to_messagebus(topic, payload, reply_topic=None, reply_timeout=2, wait_timeout=2):
    # In CoAP, 'topic' becomes the resource path (e.g., 'messagebus' or specific task)
    # We ignore reply_topic as CoAP is Request/Response
    timeout = max(reply_timeout, wait_timeout)
    # If the topic is a task name (e.g. 'led_task'), we might want to send to 'messagebus'
    # with the task in payload, OR send directly to 'led_task'.
    # Based on previous MQTT logic, it sent to 'device/messagebus' with 'cmd': topic.
    # Let's adapt: Send to 'messagebus' resource, wrapping the payload.

    # Wrapper for compatibility with existing robot logic if it expects {cmd: ..., params: ...}
    wrapped_payload = {
        "topic": topic,
        "reply_topic": reply_topic,
        "wait_timeout": wait_timeout,
        "payload": payload
    }
    wrapped_payload["reply_timeout"] = reply_timeout
    # Or if the robot CoAP server exposes resources directly:
    # return get_interface().send_rpc(topic, payload, timeout=timeout)

    # Assuming we send to a generic messagebus resource:
    return get_interface().send_rpc("/app/messagebus", wrapped_payload, timeout=timeout)

def post_to_robot(path, payload=None, reply_topic=None, reply_timeout=2, wait_timeout=2):
    cmd = path.strip("/")
    timeout = max(reply_timeout, wait_timeout)
    return get_interface().send_rpc(cmd, payload, timeout=timeout)

def init_client():
    """Call this explicitly to start the connection"""
    get_interface()

def cleanup():
    if _interface:
        _interface.close()

# b'B\x02PoZs\xbamessagebus\xff{"cmd":