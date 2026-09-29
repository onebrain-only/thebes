"""JSON-RPC to a SHARED `codex app-server --listen unix://PATH` over WebSocket.

The stdio client (`codex_appserver.CodexAppServerClient`) owns its child
process. This one owns nothing but a connection: many short-lived Thebes
clients connect to the ONE long-lived app-server on its Unix socket, speak the
same JSON-RPC, and disconnect without stopping it. The protocol logic —
request/response matching, declining every approval, awaiting one turn — is
inherited unchanged; only the wire differs.

Wire: RFC 6455 over AF_UNIX. The client sends an HTTP/1.1 Upgrade on the
socket, verifies `Sec-WebSocket-Accept`, then exchanges masked text frames
(client → server) and unmasked frames (server → client), one JSON-RPC message
per text message. Ping is answered with pong; close ends the reader.
"""
import base64
import hashlib
import json
import os
import socket
import struct
import threading
import time

from agent.execution.codex_appserver import CodexAppServerClient, _Inbox, _EOF

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
OP_CONT, OP_TEXT, OP_BIN, OP_CLOSE, OP_PING, OP_PONG = 0x0, 0x1, 0x2, 0x8, 0x9, 0xA


class WsHandshakeError(Exception):
    pass


def accept_key(key):
    return base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()


def encode_frame(payload, opcode=OP_TEXT, mask=True, mask_key=None):
    """One FIN frame. Client frames are masked (RFC 6455 §5.3)."""
    data = payload.encode("utf-8") if isinstance(payload, str) else payload
    head = bytearray([0x80 | opcode])
    n = len(data)
    bit = 0x80 if mask else 0
    if n < 126:
        head.append(bit | n)
    elif n < 65536:
        head.append(bit | 126); head += struct.pack("!H", n)
    else:
        head.append(bit | 127); head += struct.pack("!Q", n)
    if not mask:
        return bytes(head) + data
    key = mask_key or os.urandom(4)
    return bytes(head) + key + bytes(b ^ key[i % 4] for i, b in enumerate(data))


def _read_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise EOFError("socket closed")
        buf += chunk
    return buf


def read_frame(sock):
    """Return (fin, opcode, payload). Unmasks if the peer masked."""
    b1, b2 = _read_exact(sock, 2)
    fin, opcode = bool(b1 & 0x80), b1 & 0x0F
    masked, n = bool(b2 & 0x80), b2 & 0x7F
    if n == 126:
        n = struct.unpack("!H", _read_exact(sock, 2))[0]
    elif n == 127:
        n = struct.unpack("!Q", _read_exact(sock, 8))[0]
    key = _read_exact(sock, 4) if masked else None
    data = _read_exact(sock, n) if n else b""
    if key:
        data = bytes(b ^ key[i % 4] for i, b in enumerate(data))
    return fin, opcode, data


def handshake(sock, host="localhost", path="/"):
    key = base64.b64encode(os.urandom(16)).decode()
    sock.sendall(("GET %s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                  "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n"
                  % (path, host, key)).encode())
    raw = b""
    while b"\r\n\r\n" not in raw:
        chunk = sock.recv(4096)
        if not chunk:
            raise WsHandshakeError("socket closed during handshake")
        raw += chunk
        if len(raw) > 16384:
            raise WsHandshakeError("handshake response too large")
    head = raw.split(b"\r\n\r\n", 1)[0].decode("latin-1").split("\r\n")
    if " 101 " not in head[0] + " ":
        raise WsHandshakeError("upgrade refused: %s" % head[0])
    headers = {h.split(":", 1)[0].strip().lower(): h.split(":", 1)[1].strip()
               for h in head[1:] if ":" in h}
    if headers.get("sec-websocket-accept") != accept_key(key):
        raise WsHandshakeError("bad Sec-WebSocket-Accept")


class CodexWsClient(CodexAppServerClient):
    """A connection to the shared app-server. `close()` disconnects only."""

    def __init__(self, socket_path, log_path, connect_timeout=10):
        self._args = ["unix://" + socket_path]
        self._log = open(log_path, "a", encoding="utf-8")
        self._proc = None
        self._send_lock = threading.Lock()
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.settimeout(connect_timeout)
        self._sock.connect(socket_path)
        handshake(self._sock)
        self._sock.settimeout(None)
        self._inbox = _Inbox()
        self._next_id = 0
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _send_frame(self, payload, opcode=OP_TEXT):
        with self._send_lock:
            self._sock.sendall(encode_frame(payload, opcode))

    def send(self, obj):
        self._record("out", obj)
        self._send_frame(json.dumps(obj))

    def _read_loop(self):
        parts = []
        try:
            while True:
                fin, opcode, data = read_frame(self._sock)
                if opcode == OP_PING:
                    self._send_frame(data, OP_PONG)
                    continue
                if opcode == OP_CLOSE:
                    break
                if opcode in (OP_TEXT, OP_CONT):
                    parts.append(data)
                    if not fin:
                        continue
                    text, parts = b"".join(parts).decode("utf-8"), []
                    try:
                        obj = json.loads(text)
                    except ValueError:
                        obj = {"_raw": text}
                    self._record("in", obj)
                    self._inbox.put(obj)
        except (EOFError, OSError):
            pass
        self._inbox.put(_EOF)

    def close(self):
        try:
            self._send_frame(b"", OP_CLOSE)
        except OSError:
            pass
        try:
            self._sock.close()
        except OSError:
            pass
        self._log.close()
        return 0


def socket_alive(path, timeout=2):
    """True when something accepts connections on the Unix socket."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(path)
        return True
    except OSError:
        return False
    finally:
        s.close()


def wait_for_socket(path, timeout=20, sleep=time.sleep):
    """Bounded startup wait for a freshly spawned server's socket. Not a poll
    of any model or worker: it ends when the socket accepts or at the deadline."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if socket_alive(path, timeout=1):
            return True
        sleep(0.2)
    return False
