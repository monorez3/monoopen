"""MonoOpen - HTTP-клиент на голых сокетах, без сторонних зависимостей.

    from monoopen import MonoOpen, Session

    r = MonoOpen("example.com")
    print(r.code, r.text()[:50])

    s = Session()                     # помнит печеньки + держит соединение (keep-alive)
    s.open("site.ru/login", method="POST", data="user=vlad&pass=123")
    s.open("site.ru/profile")         # по тому же соединению, печеньки сами
"""
import socket, ssl
import sys
import gzip
import json
import zlib

__version__ = "0.2.0"
__all__ = ["MonoOpen", "Session", "Response", "read_json", "to_text",
           "get_cookies", "stream"]

try:
    import brotli
except ImportError:
    brotli = None
try:
    import zstandard
except ImportError:
    zstandard = None


def _accept_encoding():
    enc = "gzip, deflate"
    if brotli is not None:
        enc += ", br"
    if zstandard is not None:
        enc += ", zstd"
    return enc


def _default_headers():
    return {"User-Agent": "Mozilla/5.0", "Accept-Encoding": _accept_encoding()}


###################################################################################
#Support
def read_json(t):
    return json.loads(t)


def to_text(t):
    start = t.lower().find(b"charset")
    if start == -1:
        return t.decode("utf-8", errors="replace")
    start += len(b"charset")
    while start < len(t) and t[start:start + 1] in (b" ", b"="):
        start += 1
    raw = t[start:start + 20]
    raw = raw.lstrip(b'"\' ')
    for sep in [b'"', b"'", b">", b";", b" "]:
        raw = raw.split(sep)[0]
    charset = raw.decode(errors="replace")
    return t.decode(charset, errors="replace")


def get_cookies(z):
    cookies = {}
    start = 0
    while True:
        pos = z.lower().find(b"set-cookie:", start)
        if pos == -1:
            break
        pos += len(b"set-cookie:")
        end = z.find(b"\r\n", pos)
        if end == -1:
            end = len(z)
        one = z[pos:end].split(b";")[0]
        if b"=" in one:
            name, value = one.split(b"=", 1)
            cookies[name.strip().decode(errors="replace")] = value.strip().decode(errors="replace")
        start = end
    return cookies


def _content_length(head):
    low = head.lower()
    pos = low.find(b"content-length:")
    if pos == -1:
        return None
    pos += len(b"content-length:")
    end = head.find(b"\r\n", pos)
    if end == -1:
        end = len(head)
    try:
        return int(head[pos:end].strip())
    except Exception:
        return None


def _decompress_content(z, t):
    low = z.lower()
    if b"content-encoding: gzip" in low:
        try:
            t = gzip.decompress(t)
        except Exception as e:
            print(f"[MonoOpen] gzip отвалился: {e}", file=sys.stderr)
    if b"content-encoding: deflate" in low:
        try:
            t = zlib.decompress(t)
        except Exception as e:
            print(f"[MonoOpen] deflate отвалился: {e}", file=sys.stderr)
    if b"content-encoding: br" in low and brotli is not None:
        try:
            t = brotli.decompress(t)
        except Exception as e:
            print(f"[MonoOpen] brotli отвалился: {e}", file=sys.stderr)
    if b"content-encoding: zstd" in low and zstandard is not None:
        try:
            t = zstandard.ZstdDecompressor().decompress(t)
        except Exception as e:
            print(f"[MonoOpen] zstd отвалился: {e}", file=sys.stderr)
    return t


###################################################################################
class Response:
    def __init__(self, code, headers, body):
        self.code = code
        self.headers = headers
        self.body = body

    def text(self):
        return to_text(self.body)

    def json(self):
        return read_json(self.body)

    def cookies(self):
        return get_cookies(self.headers)


def split_adres(adres):
    adres = adres.replace("https://", "").replace("http://", "")
    pos = adres.find("/")
    if pos == -1:
        return adres, "/"
    host = adres[:pos]
    path = adres[pos:]
    return host, path


def Open_Door(host, timeout=10):
    Mono_open_door = socket.create_connection((host, 443), timeout=timeout)
    Mono_open_x_door = ssl.create_default_context()
    Mono_OXD = Mono_open_x_door.wrap_socket(Mono_open_door, server_hostname=host)
    Mono_OXD.settimeout(timeout)
    return Mono_OXD


def Go_To_OXD(host, path, headers, method="GET", data=None, keep_alive=False):
    lines = f"{method} {path} HTTP/1.1\r\n"
    lines += f"Host: {host}\r\n"
    for name, value in headers.items():
        lines += f"{name}: {value}\r\n"
    if data is not None:
        lines += f"Content-Length: {len(data.encode())}\r\n"
    conn = "keep-alive" if keep_alive else "close"
    lines += f"Connection: {conn}\r\n\r\n"
    if data is not None:
        lines += data
    return lines


def Go_To_OXD_X(tunel, get):
    tunel.send(get.encode())
    AX = b""
    while True:
        piece = tunel.recv(4096)
        if not piece:
            break
        AX += piece
    tunel.close()
    return AX


def decoding(get):
    piece = get.split(b"\r\n\r\n", 1)
    tittls = piece[0]
    body = piece[1]
    return tittls, body


def get_code(gc):
    first = gc.split(b"\r\n")[0]
    code = int(first.split(b" ")[1])
    return code


def get_location(z):
    point = b"location: "
    start = z.lower().find(point) + len(point)
    end = z.find(b"\r\n", start)
    return z[start:end].decode()


def unchunk(body):
    fresh = b""
    i = 0
    while True:
        pos = body.find(b"\r\n", i)
        xv = body[i:pos].split(b";")[0]
        x = int(xv.decode(), 16)
        if x == 0:
            break
        start = pos + 2
        end = start + x
        fresh += body[start:end]
        i = end + 2
    return fresh


def MonoOpen(adres, timeout=10, xn=0, headers=None, method="GET", data=None, follow=True):
    if headers is None:
        headers = _default_headers()
    try:
        host, path = split_adres(adres)
        tunel = Open_Door(host, timeout)
        get = Go_To_OXD(host, path, headers, method, data)
        AX = Go_To_OXD_X(tunel, get)
        try:
            z, t = decoding(AX)
        except Exception as e:
            print(f"[MonoOpen] decoding отвалился: {e}", file=sys.stderr)
            z, t = b"", AX
        try:
            code = get_code(z)
        except Exception as e:
            print(f"[MonoOpen] get_code отвалился: {e}", file=sys.stderr)
            code = 200
        if code // 100 == 3:
            if not follow:
                return Response(code, z, t)
            if xn >= 10:
                return b"too many redirects"
            new = get_location(z)
            if "://" not in new:
                new = host + new
            return MonoOpen(new, timeout, xn + 1, headers, method, data, follow)
        if b"chunked" in z.lower():
            try:
                t = unchunk(t)
            except Exception as e:
                print(f"[MonoOpen] unchunk отвалился: {e}", file=sys.stderr)
        t = _decompress_content(z, t)
        return Response(code, z, t)
    except Exception as e:
        return f"Ошибка сети: {e}".encode()


def stream(adres, timeout=10, headers=None, method="GET", data=None, chunk=4096):
    """Отдаёт тело кусками (генератор), не держа всё в памяти.

    Байты сырые (без распаковки): просим identity.

        with open("file.bin", "wb") as f:
            for piece in stream("site.ru/big.bin"):
                f.write(piece)
    """
    if headers is None:
        headers = {"User-Agent": "Mozilla/5.0", "Accept-Encoding": "identity"}
    host, path = split_adres(adres)
    tunel = Open_Door(host, timeout)
    get = Go_To_OXD(host, path, headers, method, data)
    tunel.send(get.encode())
    buf = b""
    header_done = False
    try:
        while True:
            piece = tunel.recv(chunk)
            if not piece:
                break
            if header_done:
                yield piece
            else:
                buf += piece
                if b"\r\n\r\n" in buf:
                    header_done = True
                    body_start = buf.split(b"\r\n\r\n", 1)[1]
                    if body_start:
                        yield body_start
    finally:
        tunel.close()


###################################################################################
# KEEP-ALIVE: соединение, которое читает ровно один ответ и остаётся открытым
###################################################################################

class _Conn:
    def __init__(self, host, timeout):
        self.host = host
        self.timeout = timeout
        self.sock = Open_Door(host, timeout)
        self.buf = b""
        self.alive = True

    def _recv_more(self):
        piece = self.sock.recv(4096)
        if not piece:
            self.alive = False
            return False
        self.buf += piece
        return True

    def _read_until(self, marker):
        while marker not in self.buf:
            if not self._recv_more():
                break
        head, sep, rest = self.buf.partition(marker)
        if sep:
            self.buf = rest
            return head
        out = self.buf
        self.buf = b""
        return out

    def _read_n(self, n):
        while len(self.buf) < n:
            if not self._recv_more():
                break
        out = self.buf[:n]
        self.buf = self.buf[n:]
        return out

    def _read_chunked(self):
        body = b""
        while True:
            line = self._read_until(b"\r\n")
            try:
                size = int(line.split(b";")[0].strip(), 16)
            except Exception:
                break
            if size == 0:
                self._read_until(b"\r\n")      # финальный CRLF (пустые трейлеры)
                break
            body += self._read_n(size)
            self._read_n(2)                    # CRLF после куска
        return body

    def request(self, path, headers, method, data):
        req = Go_To_OXD(self.host, path, headers, method, data, keep_alive=True)
        self.sock.sendall(req.encode())
        head = self._read_until(b"\r\n\r\n")
        if not head:
            self.alive = False
            raise ConnectionError("пустой ответ (соединение закрыто сервером)")
        try:
            code = get_code(head)
        except Exception:
            code = 200
        low = head.lower()
        if b"transfer-encoding: chunked" in low:
            body = self._read_chunked()
        else:
            n = _content_length(head)
            if n is not None:
                body = self._read_n(n)
            else:
                while self._recv_more():       # длины нет -> читаем до закрытия
                    pass
                body = self.buf
                self.buf = b""
                self.alive = False
        if b"connection: close" in low:
            self.alive = False
        body = _decompress_content(head, body)
        return Response(code, head, body)

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass
        self.alive = False


class Session:
    def __init__(self, keep_alive=True):
        self.cookies = {}
        self.keep_alive = keep_alive
        self._conns = {}                       # host -> _Conn

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def _get_conn(self, host, timeout):
        c = self._conns.get(host)
        if c is not None and c.alive:
            return c
        c = _Conn(host, timeout)
        self._conns[host] = c
        return c

    def _once(self, host, path, headers, method, data, timeout):
        try:
            return self._get_conn(host, timeout).request(path, headers, method, data)
        except Exception:
            old = self._conns.pop(host, None)
            if old is not None:
                old.close()
            return self._get_conn(host, timeout).request(path, headers, method, data)

    def open(self, adres, timeout=10, headers=None, method="GET", data=None):
        if not self.keep_alive:
            return self._open_simple(adres, timeout, headers, method, data)
        if headers is None:
            headers = _default_headers()
        for _ in range(10):
            host, path = split_adres(adres)
            if self.cookies:
                headers["Cookie"] = "; ".join(f"{name}={value}" for name, value in self.cookies.items())
            try:
                r = self._once(host, path, headers, method, data, timeout)
            except Exception as e:
                return f"Ошибка сети: {e}".encode()
            self.cookies.update(r.cookies())
            if r.code // 100 == 3:
                new = get_location(r.headers)
                if "://" not in new:
                    new = host + new
                adres = new
                continue
            return r
        return b"too many redirects"

    def _open_simple(self, adres, timeout, headers, method, data):
        if headers is None:
            headers = _default_headers()
        for _ in range(10):
            if self.cookies:
                headers["Cookie"] = "; ".join(f"{name}={value}" for name, value in self.cookies.items())
            r = MonoOpen(adres, timeout=timeout, headers=headers, method=method, data=data, follow=False)
            if not isinstance(r, Response):
                return r
            self.cookies.update(r.cookies())
            if r.code // 100 == 3:
                new = get_location(r.headers)
                if "://" not in new:
                    host, path = split_adres(adres)
                    new = host + new
                adres = new
                continue
            return r
        return b"too many redirects"

    def close(self):
        for c in self._conns.values():
            c.close()
        self._conns = {}
