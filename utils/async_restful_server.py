import uasyncio as asyncio
import ujson
import os
import sys

# Try importing deflate (MicroPython v1.21+), fallback to uzlib if needed (but deflate is required for full GZIP write)
try:
    import deflate
    HAS_DEFLATE = True
except ImportError:
    HAS_DEFLATE = False
    print("Warning: 'deflate' module missing. Compression features will be limited.")

MAX_CLIENTS = 5
MAX_JSON_SIZE = 2048   # 2KB limit for JSON payloads
CHUNK_SIZE = 1024      # 1KB chunks for streaming

# --- HTTP Status Codes ---
_STATUS_CODES = {
    200: "OK",
    400: "Bad Request",
    403: "Forbidden",
    404: "Not Found",
    500: "Internal Server Error",
    503: "Service Unavailable"
}

# ============================================================================
# 1. HELPER: Compression / Decompression
# ============================================================================

def compress_file(input_filename, output_filename=None):
    """
    Compresses a file using GZIP format.
    Input: 'data.txt' -> Output: 'data.txt.gz'
    """
    if not HAS_DEFLATE:
        raise OSError("Deflate module not supported")

    if not output_filename:
        output_filename = input_filename + ".gz"

    print(f"Compressing {input_filename} -> {output_filename}...")
    try:
        with open(input_filename, "rb") as f_in, open(output_filename, "wb") as f_out:
            # window_bits=10 (1KB RAM) is a safe balance for ESP32
            with deflate.DeflateIO(f_out, deflate.GZIP, window_bits=10) as zf:
                while True:
                    chunk = f_in.read(CHUNK_SIZE)
                    if not chunk: break
                    zf.write(chunk)
        return True
    except Exception as e:
        print(f"Compression failed: {e}")
        return False

def decompress_file(input_filename, output_filename=None):
    """
    Decompresses a GZIP file.
    Input: 'data.txt.gz' -> Output: 'data.txt'
    """
    if not HAS_DEFLATE:
        raise OSError("Deflate module not supported")

    if not output_filename:
        # Strip .gz if present
        if input_filename.endswith(".gz"):
            output_filename = input_filename[:-3]
        else:
            output_filename = input_filename + ".out"

    print(f"Decompressing {input_filename} -> {output_filename}...")
    try:
        with open(input_filename, "rb") as f_in, open(output_filename, "wb") as f_out:
            with deflate.DeflateIO(f_in, deflate.GZIP) as zf:
                while True:
                    chunk = zf.read(CHUNK_SIZE) # Standard read works on DeflateIO
                    if not chunk: break
                    f_out.write(chunk)
        return True
    except Exception as e:
        print(f"Decompression failed: {e}")
        return False


# ============================================================================
# 2. CLASS: ClientRequest (The Wrapper)
# ============================================================================

class ClientRequest:
    def __init__(self, reader, content_length):
        self._reader = reader
        self.content_length = content_length

    async def json(self):
        """Read body and parse as JSON. Safe limit applied."""
        if self.content_length > MAX_JSON_SIZE:
            raise ValueError(f"JSON too large ({self.content_length} bytes)")
        if self.content_length == 0:
            return {}

        data = await self._reader.readexactly(self.content_length)
        return ujson.loads(data)

    def stream(self):
        """Return the raw reader stream for manual chunked reading."""
        return self._reader


# ============================================================================
# 3. CLASS: AsyncRestfulServer
# ============================================================================

class AsyncRestfulServer:
    def __init__(self, ip="0.0.0.0", port=80):
        self._ip = ip
        self._port = port
        self._routes = {}
        self._client_count = 0

    def route(self, path, methods=("GET",)):
        """Decorator to register a route."""
        def decorator(handler):
            self._routes[(path, tuple(sorted(methods)))] = handler
            return handler
        return decorator

    async def run(self):
        print(f'Starting Server on {self._ip}:{self._port}')
        return await asyncio.start_server(self._handle_client, self._ip, self._port)

    # --- Internal Handling ---

    async def _handle_client(self, reader, writer):
        try:
            if self._client_count >= MAX_CLIENTS:
                await self._send_response(writer, 503, "Server Busy")
                return
            self._client_count += 1
            await self._handle_request(reader, writer)
        except Exception as e:
            sys.print_exception(e)
        finally:
            self._client_count -= 1
            await writer.aclose()

    async def _handle_request(self, reader, writer):
        try:
            # 1. Read Request Line
            req = await reader.readline()
            if not req or req == b"\r\n": return
            method, full_path, _ = req.decode().split()

            # 2. Read Headers to find Content-Length
            length = 0
            while True:
                h = await reader.readline()
                if h == b"" or h == b"\r\n": break
                if h.lower().startswith(b"content-length:"):
                    length = int(h.decode().split(":")[1].strip())

            # 3. Parse Path & Query
            path, query = self._parse_path(full_path)

            # 4. Find Handler
            handler = self._find_handler(path, method)
            if handler:
                # Wrap the request safely
                request = ClientRequest(reader, length)
                await handler(self, writer, query, request)
            else:
                # Drain reader if 404 to avoid connection issues
                if length > 0:
                    try: await reader.read(min(length, 1024))
                    except: pass
                print(f"No handler for {path} method {method} ? {query}")
                await self._send_response(writer, 404, "Not Found")

        except Exception as e:
            sys.print_exception(e)
            await self._send_response(writer, 500, "Internal Error")

    # --- Helpers ---

    def _find_handler(self, path, method):
        for (r_path, r_methods), handler in self._routes.items():
            if r_path == path and method in r_methods:
                return handler
        return None

    def _parse_path(self, full_path):
        if "?" in full_path:
            p, q = full_path.split("?", 1)
            qs = {}
            for pair in q.split("&"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    qs[self._unquote(k)] = self._unquote(v)
            return p, qs
        return full_path, {}

    def _unquote(self, s):
        s = s.replace('+', ' ')
        parts = s.split('%')
        if len(parts) == 1: return s
        res = [parts[0]]
        for item in parts[1:]:
            try: res.append(chr(int(item[:2], 16)) + item[2:])
            except: res.append('%' + item)
        return "".join(res)

    # --- Response Methods ---

    async def send_json(self, writer, data, status=200):
        body = ujson.dumps(data)
        await self._send_response(writer, status, body, "application/json")

    async def send_file(self, writer, filename, content_type="application/octet-stream"):
        """Streams a file to the client. Handles GZIP automatically."""
        # Check for .gz version first
        f_send = filename
        is_gz = False
        # dirname in micropython there is no path in os
        pth = filename.replace("\\", "/").rsplit("/", 1)
        if len(pth) == 1:
            dirname = "/"
        else:
            dirname = pth[0]
            filename = pth[1]


        if f"{filename}.gz" in os.listdir(dirname):
            f_send = f"{filename}.gz"
            is_gz = True
        elif filename not in os.listdir(dirname):
            await self._send_response(writer, 404, "File Not Found")
            return

        size = os.stat(f_send)[6]
        writer.write(f"HTTP/1.0 200 OK\r\n".encode())
        writer.write(f"Content-Type: {content_type}\r\n".encode())
        writer.write(f"Content-Length: {size}\r\n".encode())
        if is_gz:
            writer.write(b"Content-Encoding: gzip\r\n")
        writer.write(b"Connection: close\r\n\r\n")
        await writer.drain()

        with open(f_send, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk: break
                writer.write(chunk)
                await writer.drain()

    async def _send_response(self, writer, status, body=None, ctype="text/plain"):
        msg = _STATUS_CODES.get(status, "Unknown")
        writer.write(f"HTTP/1.0 {status} {msg}\r\n".encode())
        writer.write(f"Content-Type: {ctype}\r\n".encode())
        if body:
            writer.write(f"Content-Length: {len(body)}\r\n".encode())
        writer.write(b"Connection: close\r\n\r\n")
        if body:
            writer.write(body.encode())
        await writer.drain()


# ============================================================================
# 4. Standard Routes (Upload / Download)
# ============================================================================

def register_system_routes(server):

    @server.route("/api/upload", methods=("POST", "PUT"))
    async def upload_handler(srv, writer, query, request):
        """
        Uploads a file.
        Query Params:
          - filename: (required) Name of file to save.
          - compress: (optional) 'true' to gzip while saving.
        Body: Raw file content.
        """
        filename = query.get("filename")
        if not filename:
            await srv._send_response(writer, 400, "Missing filename")
            return

        # Security: Strip leading slashes and parent dir
        filename = filename.lstrip("/").replace("..", "")

        should_compress = query.get("compress", "false") == "true"
        if should_compress and HAS_DEFLATE:
            filename += ".gz"

        print(f"Receiving {filename} ({request.content_length} bytes)...")

        try:
            stream = request.stream()
            remaining = request.content_length

            with open(filename, "wb") as f_out:
                # If compression requested, wrap the file object
                if should_compress and HAS_DEFLATE:
                    ctx = deflate.DeflateIO(f_out, deflate.GZIP, window_bits=10)
                else:
                    ctx = f_out # Just write directly

                # Write Loop
                try:
                    while remaining > 0:
                        chunk = await stream.read(min(CHUNK_SIZE, remaining))
                        if not chunk: break
                        ctx.write(chunk)
                        remaining -= len(chunk)
                finally:
                    # If we used DeflateIO, we must close it to write the footer
                    if should_compress and HAS_DEFLATE:
                        ctx.close()

            await srv.send_json(writer, {"status": "ok", "saved": filename})
        except Exception as e:
            sys.print_exception(e)
            await srv._send_response(writer, 500, "Write Error")

    @server.route("/api/download", methods=("GET",))
    async def download_handler(srv, writer, query, request):
        """
        Downloads a file.
        Query Params:
          - file: (required) Name of file.
        """
        target = query.get("file")
        if not target:
            await srv._send_response(writer, 400, "Missing file param")
            return

        # Security
        target = target.lstrip("/").replace("..", "")

        # Helper handles GZIP detection and Streaming
        await srv.send_file(writer, target)

    @server.route("/api/compress", methods=("POST",))
    async def trigger_compress(srv, writer, query, request):
        """Trigger manual compression of an existing file via JSON command."""
        try:
            data = await request.json()
            fname = data.get("file")
            if not fname: raise ValueError("No file specified")

            success = compress_file(fname)
            if success:
                await srv.send_json(writer, {"status": "compressed", "file": fname+".gz"})
            else:
                await srv._send_response(writer, 500, "Compression Failed")
        except ValueError as e:
            await srv._send_response(writer, 400, str(e))