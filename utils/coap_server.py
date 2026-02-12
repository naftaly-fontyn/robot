import usocket as socket
import struct
import ujson
import uasyncio as asyncio
import random
import time
import gc
from micropython import mem_info, qstr_info
import utils.t_logger as t_logger

log = t_logger.get_logger()

# --- CoAP Constants ---
COAP_PORT = 5683
COAP_VER = 1

# Message Types
TYPE_CON = 0; TYPE_NON = 1; TYPE_ACK = 2; TYPE_RST = 3
CODE_TO_METHOD = {1: "GET", 2: "POST", 3: "PUT", 4: "DELETE"}

# Methods
METHOD_GET = 1; METHOD_POST = 2; METHOD_PUT = 3; METHOD_DELETE = 4

# Response Codes
RESP_CONTENT     = 69  # 2.05 (Success Data)
RESP_CHANGED     = 68  # 2.04 (Success Action)
RESP_BAD_REQ     = 128 # 4.00
RESP_NOT_FOUND   = 132 # 4.04
RESP_METHOD_NOT_ALLOWED = 133 # 4.05
RESP_ENTITY_INCOMPLETE = 136 # 4.08
RESP_INTERNAL_ERR = 160 # 5.00
RESP_SERVICE_UNAVAILABLE = 163 # 5.03

# Options
OPT_OBSERVE = 6; OPT_URI_PATH = 11; OPT_URI_QUERY = 15; OPT_BLOCK1 = 27

class CoAPRequest:
    """
    Holds request context + reference to the Server instance.
    """
    def __init__(self, server, addr, packet=None):
        self.server = server       # <--- ACCESS TO COAP SERVER
        self.addr = addr           # (IP, Port)
        self.ip = addr[0]

        # Default / Parsed fields
        self.method = 0
        self.payload = b''
        self.query = {}
        self.token = b''
        self.msg_id = 0
        self.type = 0
        self.is_observation = False
        self.path = ""
        self.block1 = None
        self.valid = False
        self._json = None
        self.ack_sent = False

        if packet:
            self.valid = self.parse(packet)

    def parse(self, packet):
        if len(packet) < 4: return False

        idx = self._parse_header(packet)
        if idx is None: return False

        idx = self._parse_options(packet, idx)
        self._parse_payload(packet, idx)
        return True

    def _parse_header(self, packet):
        h = packet[0]
        ver = (h >> 6) & 0x03
        if ver != 1: return None

        self.type = (h >> 4) & 0x03
        token_len = h & 0x0F
        self.method = packet[1]
        self.msg_id = struct.unpack('!H', packet[2:4])[0]
        self.token = bytes(packet[4 : 4+token_len])
        return 4 + token_len

    def _parse_options(self, packet, idx):
        path_segments = []
        query_segments = []
        opt_num = 0

        while idx < len(packet):
            byte = packet[idx]
            if byte == 0xFF:   # option terminator next is data
                break

            idx += 1
            delta = (byte >> 4) & 0x0F
            length = byte & 0x0F

            if delta == 13:    # more than 13 counts
                delta = packet[idx] + 13
                idx += 1
            elif delta == 14:  # more than 269 counts
                delta = struct.unpack('!H', packet[idx:idx+2])[0] + 269
                idx += 2

            opt_num += delta

            opt_val_view = packet[idx : idx+length]
            idx += length

            if opt_num == OPT_URI_PATH: path_segments.append(str(opt_val_view, 'utf-8'))
            elif opt_num == OPT_URI_QUERY: query_segments.append(str(opt_val_view, 'utf-8'))
            elif opt_num == OPT_OBSERVE: self.is_observation = True
            elif opt_num == OPT_BLOCK1:
                val = 0
                for b in opt_val_view:
                    val = (val << 8) | b
                self.block1 = val

        self.path = "/" + "/".join(path_segments)

        for q in query_segments:
            if '=' in q:
                k, v = q.split('=', 1)
                self.query[k] = int(v) if v.isdigit() else v
            else: self.query[q] = True

        return idx

    def _parse_payload(self, packet, idx):
        if idx < len(packet):
            if packet[idx] == 0xFF:
                self.payload = bytes(packet[idx+1:])
            else:
                self.payload = bytes(packet[idx:])

    def send_ack(self):
        """Send an Empty ACK to signal separate response will follow."""
        if not self.ack_sent and self.type == TYPE_CON:
            self.server._send_ack(self.addr, self.token, self.msg_id, 0) # 0 = EMPTY
            self.ack_sent = True

    @property
    def json(self):
        """Lazy load JSON payload"""
        if self._json is None and self.payload:
            try: self._json = ujson.loads(self.payload)
            except: self._json = {}
        return self._json or {}

    @property
    def context(self):
        """Returns context dict for async replies"""
        return {'addr': self.addr, 'token': self.token}

class AsyncCoAPServer:
    def __init__(self, port=COAP_PORT, max_workers=10):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.bind(('0.0.0.0', port))

        self.msg_id = random.randint(0, 60000)

        # Route Table: path -> {'methods': [], 'handler': func}
        self.routes = {}

        self.partial_blocks = {}
        self.pending_requests = {}
        self.observers = {}
        self.obs_seq = 0
        self.last_cleanup = time.time()

        self.max_workers = max_workers
        self.active_workers = 0

        log.info(f"[CoAP] Server Active on :{port}")

    def route(self, path, methods=['GET']):
        """Decorator to register a handler."""
        def decorator(handler):
            clean_path = "/" + path.strip("/")
            self.routes[clean_path] = {
                'methods': methods,
                'handler': handler
            }
            return handler
        return decorator

    async def run(self):
        while True:
            try:
                data, addr = self.sock.recvfrom(1500)

                # 1. Parse Synchronously & Free Data
                req = CoAPRequest(self, addr, packet=data)
                del data, addr

                # 2. Process if valid
                if req.valid:
                    if self.active_workers < self.max_workers:
                        self.active_workers += 1
                        asyncio.create_task(self._run_worker(req))
                    else:
                        log.warning(f"[CoAP] Server Busy: Rejecting {req.addr}")
                        if req.type == TYPE_CON:
                            self._send_ack(req.addr, req.token, req.msg_id, RESP_SERVICE_UNAVAILABLE)
                        elif req.type == TYPE_NON:
                            self.send_response_raw(req.addr, req.token, RESP_SERVICE_UNAVAILABLE, b'')

                if time.time() - self.last_cleanup > 10:
                    self._cleanup_partials()
                gc.collect()
                mem_info()
                log.warning(t_logger.mem_info_str())
                # print(qstr_info(), len(self.pending_requests))
            except OSError:
                await asyncio.sleep(0.01)
            except Exception as e:
                log.critical(f"[CoAP] Critical: {e}")
                await asyncio.sleep(0.1)

    async def _run_worker(self, req):
        try:
            await self._process_request(req)
        finally:
            self.active_workers -= 1

    def _cleanup_partials(self):
        now = time.time()
        keys = [k for k, v in self.partial_blocks.items() if now - v['time'] > 15]
        for k in keys: del self.partial_blocks[k]
        self.last_cleanup = now

    async def _process_request(self, req):
        try:
            # --- 2. Check ACKs (Client Role) ---
            if (req.type == TYPE_ACK or req.type == TYPE_RST) and req.msg_id in self.pending_requests:
                future = self.pending_requests.pop(req.msg_id)
                if not future.done(): future.set_result(req.method)
                return

            # --- 5. Block-Wise Reassembly ---
            if req.block1 is not None:
                num = req.block1 >> 4
                more = (req.block1 & 0x08) >> 3
                block_key = (req.addr, req.token)

                if block_key not in self.partial_blocks:
                    if num != 0:
                        self._send_ack(req.addr, req.token, req.msg_id, RESP_ENTITY_INCOMPLETE)
                        return
                    self.partial_blocks[block_key] = {'buf': bytearray(), 'time': time.time(), 'next_num': 0}

                state = self.partial_blocks[block_key]
                if num != state['next_num']:
                    self._send_ack(req.addr, req.token, req.msg_id, RESP_ENTITY_INCOMPLETE)
                    return

                state['buf'].extend(req.payload)
                state['time'] = time.time()

                if more:
                    state['next_num'] += 1
                    self._send_block_ack(req.addr, req.token, req.msg_id, RESP_CONTINUE, req.block1)
                    return
                else:
                    full_payload = self.partial_blocks.pop(block_key)['buf']
                    req.payload = bytes(full_payload)
                    req._json = None # Reset cached JSON

            # --- 6. Routing & Dispatch ---
            # A. Auto-Register Observers
            if req.method == METHOD_GET and req.is_observation:
                self._add_observer(req.path, req.addr, req.token)
                # NOTE: We do NOT return here. We let the handler run
                # to generate the initial "Current State" response.

            # B. Execute Route
            if req.path in self.routes:
                route_def = self.routes[req.path]
                if CODE_TO_METHOD.get(req.method) not in route_def['methods']:
                    if req.type == TYPE_CON: self._send_ack(req.addr, req.token, req.msg_id, RESP_METHOD_NOT_ALLOWED)
                    else:
                        log.warning(f"[CoAP] Method {CODE_TO_METHOD.get(req.method)} not allowed on {req.path} - Ignoring request")

                    return

                try:
                    # Call User Handler
                    result = await route_def['handler'](req)

                    # Handle Return Values
                    if result is not None:
                        # Determine correct success code
                        default_code = RESP_CHANGED if req.method == METHOD_POST else RESP_CONTENT

                        # 1. Tuple: (CODE, DATA)
                        if isinstance(result, tuple) or isinstance(result, list):
                            r_code, r_data = result[0], result[1]

                        # 2. Int: CODE Only
                        elif isinstance(result, int):
                            r_code, r_data = result, None

                        # 3. Dict/Str: Content
                        else:
                            r_code, r_data = default_code, result

                        if req.ack_sent:
                            self._send_separate_response(req.addr, req.token, r_code, r_data)
                        else:
                            if r_data is None:
                                self._send_ack(req.addr, req.token, req.msg_id, r_code)
                            else:
                                self._send_response_packet(req.addr, req.token, req.msg_id, r_code, r_data, req.is_observation)

                    # If result is None, we assume handler sent its own reply or will later

                except Exception as e:
                    log.error(f"[CoAP] Handler Err: {e}")
                    if req.ack_sent:
                        self._send_separate_response(req.addr, req.token, RESP_INTERNAL_ERR, {'text': str(e)})
                    elif req.type == TYPE_CON:
                        self._send_ack(req.addr, req.token, req.msg_id, RESP_INTERNAL_ERR)
            else:
                log.info(f"[CoAP] Unhandled: {req.addr} T:{req.type} C:{req.method} P:'{req.path}'")

                if req.type == TYPE_CON: self._send_ack(req.addr, req.token, req.msg_id, RESP_NOT_FOUND)

        except Exception as e:
            log.error(f"[CoAP] Parse Error: {e}")

    # --- Helpers ---

    def _send_response_packet(self, addr, token, msg_id, code, payload_data, is_obs=False):
        """Sends Response. Adds Observe Option if needed for initial ACK."""
        if isinstance(payload_data, dict): payload = ujson.dumps(payload_data).encode('utf-8')
        elif isinstance(payload_data, str): payload = payload_data.encode('utf-8')
        else: payload = payload_data

        h = (1 << 6) | (TYPE_ACK << 4) | (len(token) & 0x0F)
        header = struct.pack('!BBH', h, code, msg_id)

        # If this is an Observe response, we should technically add Option 6
        # But for initial ACK, many clients accept plain data.
        # Adding minimal Observe option (seq 0) for correctness:
        opts = b''
        if is_obs:
            # Option 6 (Observe), Length 0 (Value 0) -> 0x60
            opts = b'\x60'

        self.sock.sendto(header + token + opts + b'\xFF' + payload, addr)

    def _send_ack(self, addr, token, msg_id, code):
        h = (1 << 6) | (TYPE_ACK << 4) | (len(token) & 0x0F)
        self.sock.sendto(struct.pack('!BBH', h, code, msg_id) + token, addr)

    def _send_separate_response(self, addr, token, code, payload_data):
        """Sends a Separate Response (NON) after an Empty ACK was sent."""
        if payload_data is None: payload_data = b''
        if isinstance(payload_data, dict): payload = ujson.dumps(payload_data).encode('utf-8')
        elif isinstance(payload_data, str): payload = payload_data.encode('utf-8')
        else: payload = payload_data

        self.send_response_raw(addr, token, code, payload)

    def _add_observer(self, path, addr, token):
        if path not in self.observers: self.observers[path] = {}
        self.observers[path][addr] = token

    def notify_observers(self, path, payload_dict):
        if path not in self.observers or not self.observers[path]: return
        try:
            payload = ujson.dumps(payload_dict).encode('utf-8')
            self.obs_seq = (self.obs_seq + 1) % 0xFFFFFF
            obs_val = struct.pack('!H', self.obs_seq & 0xFFFF)
            for addr, token in self.observers[path].items():
                self._send_notification(addr, token, payload, obs_val)
        except: pass

    def _send_notification(self, addr, token, payload, obs_val):
        h = (1 << 6) | (TYPE_NON << 4) | (len(token) & 0x0F)
        self.msg_id = (self.msg_id + 1) % 65535
        # Opt 6 (Observe) & Opt 12 (JSON)
        pkt = struct.pack('!BBH', h, RESP_CONTENT, self.msg_id) + token + \
              struct.pack('B', (6<<4)|len(obs_val)) + obs_val + \
              struct.pack('B', (6<<4)|1) + b'\x32' + \
              b'\xFF' + payload
        self.sock.sendto(pkt, addr)

    def send_response(self, data, context):
        try:
            payload = ujson.dumps(data).encode('utf-8')
            self.msg_id = (self.msg_id + 1) % 65535
            self.send_response_raw(context['addr'], context['token'], RESP_CONTENT, payload)
        except: pass

    def send_response_raw(self, addr, token, code, payload):
        self.msg_id = (self.msg_id + 1) % 65535
        h = (1 << 6) | (TYPE_NON << 4) | (len(token) & 0x0F)
        header = struct.pack('!BBH', h, code, self.msg_id)
        if payload:
            self.sock.sendto(header + token + b'\xFF' + payload, addr)
        else:
            self.sock.sendto(header + token, addr)

    def broadcast_presence(self):
        self.transmit('255.255.255.255', 'announce', {"id": "esp32_robot"}, confirmable=False)

    def transmit(self, ip, path, payload, method=METHOD_POST, confirmable=False, port=COAP_PORT):
        try:
            log.info(f"[CoAP] TX {CODE_TO_METHOD.get(method, method)} {ip}:{port}/{path}")
            if isinstance(payload, dict): payload = ujson.dumps(payload).encode('utf-8')
            elif isinstance(payload, str): payload = payload.encode('utf-8')
            t_type = TYPE_CON if confirmable else TYPE_NON
            self.msg_id = (self.msg_id + 1) % 65535
            h = (1 << 6) | (t_type << 4) | 0
            header = struct.pack('!BBH', h, method, self.msg_id)
            options = bytearray()

            # Split path and query
            path_parts = path.split('?', 1)
            path_root = path_parts[0]
            query_str = path_parts[1] if len(path_parts) > 1 else ""

            segments = [s for s in path_root.strip('/').split('/') if s]
            last_opt = 0
            for seg in segments:
                delta = 11 - last_opt; last_opt = 11
                sb = seg.encode('utf-8')
                options.extend(self._encode_opt_head(delta, len(sb)))
                options.extend(sb)

            if query_str:
                queries = query_str.split('&')
                for q in queries:
                    delta = 15 - last_opt; last_opt = 15
                    sb = q.encode('utf-8')
                    options.extend(self._encode_opt_head(delta, len(sb)))
                    options.extend(sb)

            if payload:
                self.sock.sendto(header + options + b'\xFF' + payload, (ip, port))
            else:
                self.sock.sendto(header + options, (ip, port))
        except Exception as e:
            log.error(f"[CoAP] Transmit Error: {e}")

    def _encode_opt_head(self, delta, length):
        b = bytearray()
        d = 13 if delta >= 13 else delta
        l = 13 if length >= 13 else length
        b.append((d << 4) | l)
        if delta >= 269: b.extend(struct.pack('!H', delta-269))
        elif delta >= 13: b.append(delta-13)
        if length >= 269: b.extend(struct.pack('!H', length-269))
        elif length >= 13: b.append(length-13)
        return b


    def _send_block_ack(self, addr, token, msg_id, code, block_val):
        h = (1 << 6) | (TYPE_ACK << 4) | (len(token) & 0x0F)
        b_bytes = bytearray()
        val = block_val
        while val > 0: b_bytes.insert(0, val & 0xFF); val >>= 8
        if not b_bytes: b_bytes = b'\x00'
        opt_head = (13 << 4) | len(b_bytes)
        packet = struct.pack('!BBH', h, code, msg_id) + token + \
                 struct.pack('B', opt_head) + b'\x0E' + b_bytes
        self.sock.sendto(packet, addr)