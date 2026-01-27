import uasyncio as asyncio
import json
import ure  # MicroPython regex module (used to help parse URLs)

from utils.messagebus import Publisher


"""
current_clients = 0
MAX_CLIENTS = 5

async def handle_client(reader, writer):
    global current_clients

    if current_clients >= MAX_CLIENTS:
        writer.write(b"HTTP/1.1 503 Busy\r\n\r\n")
        await writer.drain()
        writer.close()
        return

    current_clients += 1
    try:
        ...
    finally:
        current_clients -= 1
        writer.close()

"""
_PUBLISH = Publisher("RESTFUL server")


async def handle_client(reader, writer):
    # ---- Read request line, e.g. "GET /hello?name=Bob HTTP/1.1"
    request_line = await reader.readline()
    print("Request:", request_line)

    method, full_path, _ = request_line.decode().split()

    # Split path and query string manually
    path, query_string = parse_path(full_path)

    # ---- Read headers ----
    content_length = 0
    while True:
        header = await reader.readline()
        if header == b"\r\n":
            break
        if header.lower().startswith(b"content-length"):
            content_length = int(header.decode().split(":")[1].strip())

    # ---- Read body (if exists) ----
    body = b""
    if content_length > 0:
        body = await reader.read(content_length)

    # ---- Parse JSON (if any) ----
    data = None
    if body:
        try:
            data = json.loads(body)
        except Exception as e:
            data = {"error": str(e), "raw": body.decode()}

    # ---- Routing / example endpoints ----
    if method == "GET" and path == "/hello":
        response = {
            "message": "Hello from MicroPython",
            "query": query_string,  # shows what was sent in URL
        }
        await send_json(writer, response)

    if method == "GET" and path == "/quit":
        writer.write(b"Shutting down...\r\n")
        await writer.drain()
        writer.close()
        _PUBLISH.event("quit")

        print("Server stopped.")
        return


    elif method == "POST" and path == "/data":
        response = {
            "method": "POST",
            "received_payload": data,
            "query": query_string,
        }
        await send_json(writer, response)

    elif method == "PUT" and path == "/update":
        response = {
            "method": "PUT",
            "received_payload": data,
            "query": query_string,
        }
        await send_json(writer, response)

    else:
        await send_response(writer, 404, "Not found")

    await writer.aclose()


# ---- Utility functions ----
def parse_path(full_path):
    """Split path and query string manually."""
    if "?" in full_path:
        path, qs = full_path.split("?", 1)
        return path, parse_query(qs)
    else:
        return full_path, {}

def parse_query(qs):
    """Turn 'a=1&b=2' into {'a': '1', 'b': '2'}."""
    params = {}
    parts = qs.split("&")
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            params[k] = v
    return params

async def send_json(writer, data, status=200):
    body = json.dumps(data)
    await send_response(writer, status, body, "application/json")

async def send_response(writer, status, body, content_type="text/plain"):
    status_msg = "OK" if status == 200 else "Not Found"
    headers = [
        f"HTTP/1.0 {status} {status_msg}",
        f"Content-Type: {content_type}",
        f"Content-Length: {len(body)}",
        "Connection: close",
        "",
        "",
    ]
    await writer.awrite("\r\n".join(headers) + body)

async def async_restful_server(srv_ip: str = "0.0.0.0", port: int = 80):
    server = await asyncio.start_server(handle_client, srv_ip, port)
    print(f'Server running on http://{srv_ip}:{port}/')
    # async with server:
    #     await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(async_restful_server())

"""
import uasyncio as asyncio
import machine

# ---------- Robot tasks ----------

async def motor_task():
    motor = machine.PWM(machine.Pin(13))
    speed = 0

    while True:
        # Example: update motor speed every 20ms
        motor.duty(speed)
        speed = (speed + 10) % 1024
        await asyncio.sleep(0.02)   # yield to other tasks

async def sensor_task():
    adc = machine.ADC(machine.Pin(34))

    while True:
        value = adc.read()
        print("Sensor:", value)
        await asyncio.sleep(0.1)    # yield often

# ---------- Network server ----------

async def handle_client(reader, writer):
    req = await reader.readline()
    print("Client:", req)

    writer.write(b"HTTP/1.1 200 OK\r\n\r\nRobot OK")
    await writer.drain()

    writer.close()
    await writer.wait_closed()

async def http_server():
    server = await asyncio.start_server(handle_client, "0.0.0.0", 80)
    print("HTTP server running")
    async with server:
        await server.serve_forever()

# ---------- System startup ----------

async def main():
    # Start robot tasks
    asyncio.create_task(motor_task())
    asyncio.create_task(sensor_task())

    # Start server
    asyncio.create_task(http_server())

    # Keep main alive
    while True:
        await asyncio.sleep(1)

asyncio.run(main())

"""