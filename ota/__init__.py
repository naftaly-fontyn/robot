"""
This is the main module for OTA use, it setup a dedicated REST server
for OTA functionality. I support basic functions as list the esp32
file system, upload/download and delete files, m ove/rename files.

TODO
-[ ] display som status on the display or LED
"""
import os
import sys
import io
import binascii
import json
import gc
import deflate
import asyncio
import machine
from utils.async_restful_server import AsyncRestfulServer, CHUNK_SIZE
from app import init_wifi

HAS_DEFLATE = True

def main():
    print('=== OTA Main ===')
    asyncio.run(async_main())

async def async_main():
    print('OTA')
    init_wifi()
    ota_app = AsyncRestfulServer()
    running = True

    @ota_app.route('/ota/ping', ('GET',))
    async def ping_handler(server, writer, query, body):
        await server.send_json(writer, {'ping': 'OK'})

    @ota_app.route("/ota/ls", methods=("GET",))
    async def ls_handler(server, writer, query, body):
        import os
        path = query.get("path", "/")
#         print(query, body)
        # get file+size and directory names return in json
        # "entries":[{"name":<fname>}, "size": int|"<DIR>"}, ...]
        response = {"entries": [], 'cwd': os.getcwd()}
        for f in os.listdir(path):
            response["entries"].append({"name": f})
            try:
                # on the micropython esp directories have size so incorrectly
                # classifying a directory as a file
                # response["entries"][-1]["size"] = os.stat(f)[6]
                if os.stat(f'{path}/{f}')[0] & 0x4000:
                    response["entries"][-1]["size"] = "<DIR>"
                else:
                    response["entries"][-1]["size"] = os.stat(f'{path}/{f}')[6]
            except OSError:
                print(f'{path}/{f}')
                print(os.stat(f'{path}/{f}'))
                response["entries"][-1]["size"] = "<DIR>"
        await server.send_json(writer, response)

    @ota_app.route("/ota/upload", ("POST",))
    async def upload_handler(server, writer, query, request):
        filename = query.get("filename")
        if not filename:
            await server._send_response(writer, 400, "Missing filename")
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

            await server.send_json(writer, {"status": "ok", "saved": filename})
        except Exception as e:
            sys.print_exception(e)
            await server._send_response(writer, 500, "Write Error")

    # Routes for the REST server
    @ota_app.route("/ota/download", methods=("GET",))
    async def download_handler(srv, writer, query, request):
        """Streams a file back to the client."""
        print(query)
        filename = query.get("file")
        if not filename:
            await srv._send_response(writer, 400, "Missing file param")
            return
        await srv.send_file(writer, filename)

    @ota_app.route("/ota/rm", methods=("POST",))
    async def rm_handler(srv, writer, query, request):
        import os
        try:
            req = await request.json()
            path = req.get("path")
            os.remove(path)
            await srv.send_json(writer, {"status": "deleted"})
        except Exception as e:
            await srv._send_response(writer, 500, str(e))

    @ota_app.route("/ota/exit", ("POST",))
    async def quit_handler(server, writer, query, body):
        global running
        await server._send_response(writer, 200, "OTA Shutting down restarting")
        print("OTA stop restarting")
        await asyncio.sleep(0.5)
        running = False
        machine.soft_reset()

    @ota_app.route("/ota/rm", ("POST",))
    async def rm_handler(server, writer, query, request):
        req = await request.json()
        path = req.get("path")
        os.remove(path)
        await server.send_json(writer, {"status": "deleted"})

    @ota_app.route("/ota/mv", ("POST",))
    async def reboot_handler(server, writer, query, request):
        req = await request.json()
        src_path = req.get("src_path")
        dst_path = req.get("dst_path")
        os.rename(src_path, dst_path)
        await server.send_json(writer, {"status": "renamed"})


    try:
#         asyncio.run(ota_app.run())
        task_ota_app = asyncio.create_task(ota_app.run())
        print(running)
        while running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nServer stopped by user.")


if __name__ == '__main__':
    main()