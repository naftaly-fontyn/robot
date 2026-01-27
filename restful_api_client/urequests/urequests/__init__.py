#
import socket


class Request:
    pass


class Response:

    def __init__(self, f):
        self.raw = f
        self.encoding = "utf-8"
        self.status_code = None
        self.reason = None
        self.headers = None
        self._cached = None

    def close(self):
        if self.raw:
            self.raw.close()
            self.raw = None
        self._cached = None

    @property
    def content(self):
        if self._cached is None:
            try:
                self._cached = self.raw.read()
            finally:
                self.raw.close()
                self.raw = None
        return self._cached

    @property
    def text(self):
        return str(self.content, self.encoding)

    def json(self):
        import json as _json
        return _json.loads(self.content)


def _parse_url(url):
    """Splits a URL into protocol, host, port, and path."""
    try:
        proto, _, host, path = url.split("/", 3)
    except ValueError:
        proto, _, host = url.split("/", 2)
        path = ""

    if proto == "http:":
        port = 80
    elif proto == "https:":
        port = 443
    else:
        raise ValueError("Unsupported protocol: " + proto)

    if ":" in host:
        host, port = host.split(":", 1)
        port = int(port)

    return proto, host, port, path


def _send_request(sock, method, path, headers, data, json):
    """Sends the HTTP request headers and body."""
    sock.send(b"%s /%s HTTP/1.0\r\n" % (method.encode(), path.encode()))
    if not "Host" in headers:
        sock.send(("Host: %s\r\n" % headers["_host"]).encode())
    # Iterate over keys to avoid tuple alloc
    for k in headers:
        if k == "_host":
            continue
        sock.send(k)
        sock.send(b": ")
        sock.send(headers[k])
        sock.send(b"\r\n")
    if json is not None:
        sock.send(b"Content-Type: application/json\r\n")
    if data:
        sock.send(b"Content-Length: %d\r\n" % len(data))
    sock.send(b"Connection: close\r\n\r\n")
    if data:
        if isinstance(data, str):
            data = data.encode()
        sock.send(data)


def _read_response(sock, parse_headers):
    """Reads and parses the HTTP response."""
    l = sock.readline()
    if not l:
        raise ValueError("Empty response")

    l = l.split(None, 2)
    status = int(l[1])
    reason = l[2].rstrip() if len(l) > 2 else ""

    resp_d = {} if parse_headers else None

    while True:
        l = sock.readline()
        if not l or l == b"\r\n":
            break

        if l.startswith(b"Transfer-Encoding:"):
            if b"chunked" in l:
                raise ValueError("Unsupported " + l.decode())
        elif l.startswith(b"Location:") and 300 <= status <= 399:
            return status, l[9:].decode().strip(), None

        if parse_headers:
            l = l.decode()
            k, v = l.split(":", 1)
            resp_d[k] = v.strip()

    return status, reason, resp_d


def request(method, url, data=None, json=None, headers={}, auth=None, stream=None, parse_headers=True, timeout=2):
    redir_cnt = 1
    if json is not None:
        assert data is None
        import json as _json
        data = _json.dumps(json)

    while True:
        proto, host, port, path = _parse_url(url)

        if auth:
            # This part can be further refactored if auth methods get complex
            req = Request()
            req.method = method
            req.url = url
            req.headers = headers if headers else {}
            req = auth(req)
            headers = req.headers

        headers["_host"] = host # Store host for _send_request

        ai = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)[0]
        s = socket.socket(ai[0], ai[1], ai[2])
        try:
            s.settimeout(timeout)
            s.connect(ai[-1])
            if proto == "https:":
                import ssl
                s = ssl.wrap_socket(s, server_hostname=host)

            _send_request(s, method, path, headers, data, json)
            s = s.makefile("rwb")
            status, reason, resp_d = _read_response(s, parse_headers)

            if status == 300: # Redirection
                if not redir_cnt:
                    raise ValueError("Too many redirects")
                redir_cnt -= 1
                url = reason # reason is the new URL on redirect
                continue

        except OSError as e:
            s.close()
            print("Connection failed", e)
            return None
        finally:
            # Clean up the temporary host entry
            if "_host" in headers:
                del headers["_host"]

        break

    resp = Response(s)
    resp.status_code = status
    resp.reason = reason
    if resp_d is not None:
        resp.headers = resp_d
    return resp


def head(url, **kw):
    return request("HEAD", url, **kw)

# Use GET requests to retrieve resource representation/information only (ret JSON) send query data
def get(url, **kw):
    return request("GET", url, **kw)
# Use POST APIs to create new subordinate resources, used to create a new resource (w/r JSON)
def post(url, **kw):
    return request("POST", url, **kw)
# Use PUT APIs primarily to update an existing resource (if the resource does not
# exist, then API may decide to create a new resource or not (r/w JSON)
def put(url, **kw):
    return request("PUT", url, **kw)
# HTTP PATCH requests are to make a partial update on a resource.
def patch(url, **kw):
    return request("PATCH", url, **kw)
# As the name applies, DELETE APIs delete the resource send query data
def delete(url, **kw):
    return request("DELETE", url, **kw)
