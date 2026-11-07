import json
import os
import queue
import secrets
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
BASE = os.path.dirname(os.path.abspath(__file__))
MAX_MEMBERS = 50
MAX_BODY = 65536

Q_HEX = (
    "ffffffffffffffffc90fdaa22168c234c4c6628b80dc1cd129024e088a67cc74"
    "020bbea63b139b22514a08798e3404ddef9519b3cd3a431b302b0a6df25f1437"
    "4fe1356d6d51c245e485b576625e7ec6f44c42e9a637ed6b0bff5cb6f406b7ed"
    "ee386bfb5a899fa5ae9f24117c4b1fe649286651ece45b3dc2007cb8a163bf05"
    "98da48361c55d39a69163fa8fd24cf5f83655d23dca3ad961c62f356208552bb"
    "9ed529077096966d670c354e4abc9804f1746c08ca18217c32905e462e36ce3b"
    "e39e772c180e86039b2783a2ec07a28fb5c55df06f4c52c9de2bcbf695581718"
    "3995497cea956ae515d2261898fa051015728e5a8aacaa68ffffffffffffffff"
)
A = 11

LOCK = threading.RLock()
MEMBERS = []
EPOCH = 0


def find_static(name):
    for d in (os.path.join(BASE, "static"), os.path.join(BASE, "web"), BASE):
        p = os.path.join(d, name)
        if os.path.isfile(p):
            return p
    return None


def short(s, n=28):
    s = str(s)
    return s if len(s) <= n else s[:n] + "…"


def push_roster():
    global EPOCH
    EPOCH += 1
    names = [m["name"] for m in MEMBERS]
    print("\n=== Епоха %d, учасники: %s" % (EPOCH, ", ".join(names) or "—"))
    for i, m in enumerate(MEMBERS):
        m["q"].put({"type": "roster", "epoch": EPOCH, "members": names, "index": i})


def find_member(mid, token):
    for m in MEMBERS:
        if m["id"] == mid and secrets.compare_digest(m["token"], token):
            return m
    return None


def remove_member(m):
    with LOCK:
        if m in MEMBERS:
            MEMBERS.remove(m)
            print("[ВИХІД] %s" % m["name"])
            push_roster()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def send_bytes(self, code, data, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, code, obj):
        self.send_bytes(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                        "application/json; charset=utf-8")

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_BODY:
            raise ValueError("розмір запиту")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        url = urlparse(self.path)
        if url.path in ("/", "/index.html"):
            return self.serve_file("index.html", "text/html; charset=utf-8")
        if url.path == "/chatcore.js":
            return self.serve_file("chatcore.js", "application/javascript; charset=utf-8")
        if url.path == "/api/params":
            return self.send_json(200, {"q": Q_HEX, "a": A})
        if url.path == "/api/events":
            return self.events(parse_qs(url.query))
        self.send_json(404, {"error": "Не знайдено"})

    def serve_file(self, name, ctype):
        path = find_static(name)
        if path is None:
            return self.send_json(404, {"error": "Файл %s не знайдено поруч із server.py" % name})
        with open(path, "rb") as fh:
            self.send_bytes(200, fh.read(), ctype)

    def events(self, q):
        """Потік подій (Server-Sent Events) для одного учасника."""
        try:
            mid, token = q["id"][0], q["token"][0]
        except (KeyError, IndexError):
            return self.send_json(400, {"error": "Некоректний запит"})
        with LOCK:
            m = find_member(mid, token)
        if m is None:
            return self.send_json(403, {"error": "Невідомий учасник"})
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        try:
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while True:
                try:
                    ev = m["q"].get(timeout=15)
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    continue
                if ev is None:
                    break
                self.wfile.write(("data: %s\n\n" % json.dumps(ev, ensure_ascii=False)).encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            remove_member(m)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            data = self.read_json()
        except Exception:
            return self.send_json(400, {"error": "Некоректний запит"})
        if path == "/api/join":
            return self.join(data)
        if path in ("/api/dh", "/api/chat", "/api/leave"):
            with LOCK:
                m = find_member(str(data.get("id", "")), str(data.get("token", "")))
                if m is None:
                    return self.send_json(403, {"error": "Невідомий учасник"})
                if path == "/api/leave":
                    m["q"].put(None)
                    return self.send_json(200, {"ok": True})
                if path == "/api/dh":
                    return self.relay_dh(m, data)
                return self.relay_chat(m, data)
        self.send_json(404, {"error": "Не знайдено"})

    def join(self, data):
        name = str(data.get("name", "")).strip()
        if not (1 <= len(name) <= 20):
            return self.send_json(400, {"error": "Ім'я має містити від 1 до 20 символів"})
        with LOCK:
            if any(m["name"].lower() == name.lower() for m in MEMBERS):
                return self.send_json(409, {"error": "Таке ім'я вже використовується"})
            if len(MEMBERS) >= MAX_MEMBERS:
                return self.send_json(503, {"error": "Чат заповнений"})
            m = {"id": secrets.token_hex(8), "token": secrets.token_hex(16), "name": name, "q": queue.Queue()}
            MEMBERS.append(m)
            print("[ВХІД] %s" % name)
            push_roster()
        self.send_json(200, {"id": m["id"], "token": m["token"], "name": name})

    def relay_dh(self, m, data):
        if data.get("epoch") != EPOCH:
            return self.send_json(200, {"ok": False, "reason": "застаріла епоха"})
        i = MEMBERS.index(m)
        nxt = MEMBERS[(i + 1) % len(MEMBERS)]
        ev = {"type": "dh", "epoch": EPOCH, "round": data.get("round"), "from": m["name"], "value": data.get("value")}
        print("[DH] %s -> %s  раунд %s  значення %s" % (m["name"], nxt["name"], data.get("round"), short(data.get("value"))))
        nxt["q"].put(ev)
        self.send_json(200, {"ok": True})

    def relay_chat(self, m, data):
        ev = {"type": "chat", "epoch": data.get("epoch"), "from": m["name"],
              "iv": data.get("iv"), "ct": data.get("ct")}
        print("[ЧАТ] %s (епоха %s) шифротекст: %s" % (m["name"], data.get("epoch"), short(data.get("ct"), 40)))
        for o in MEMBERS:
            if o is not m:
                o["q"].put(ev)
        self.send_json(200, {"ok": True})


if __name__ == "__main__":
    for fn in ("index.html", "chatcore.js"):
        p = find_static(fn)
        print("%s: %s" % (fn, p if p else "НЕ ЗНАЙДЕНО — покладіть поруч із server.py або в static/"))
    print("Q: %d біт, A = %d" % (int(Q_HEX, 16).bit_length(), A))
    print("Чат запущено: http://localhost:%d" % PORT)
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    srv.daemon_threads = True
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nЗупинено")
