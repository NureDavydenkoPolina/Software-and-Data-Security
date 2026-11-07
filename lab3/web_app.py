import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from lab3 import bits_str, file_kind, my_hash

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
MAX_SIZE = 100 * 1024 * 1024
BASE = os.path.dirname(os.path.abspath(__file__))
KIND_TITLES = {
    "docx": "Документ Word",
    "png": "Зображення (PNG)",
    "jpeg": "Зображення (JPEG)",
    "image": "Зображення",
    "source": "Вихідний код / інший файл",
}


def find_index():
    for d in (os.path.join(BASE, "web"), BASE):
        p = os.path.join(d, "index.html")
        if os.path.isfile(p):
            return p
    return None


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

    def do_GET(self):
        if urlparse(self.path).path not in ("/", "/index.html"):
            return self.send_json(404, {"error": "Не знайдено"})
        path = find_index()
        if path is None:
            return self.send_json(404, {"error": "index.html не знайдено поруч із web_app.py"})
        with open(path, "rb") as fh:
            self.send_bytes(200, fh.read(), "text/html; charset=utf-8")

    def do_POST(self):
        url = urlparse(self.path)
        if url.path != "/api/hash":
            return self.send_json(404, {"error": "Не знайдено"})
        q = parse_qs(url.query)
        try:
            bits = int(q.get("bits", ["8"])[0])
            if bits not in (2, 4, 8):
                raise ValueError
        except ValueError:
            return self.send_json(400, {"error": "Довжина хешу має бути 2, 4 або 8 біт"})
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_SIZE:
            return self.send_json(400, {"error": "Файл порожній або завеликий (максимум 100 МБ)"})
        data = self.rfile.read(length)
        name = q.get("name", ["file"])[0]
        h = my_hash(data, bits)
        kind = file_kind(name)
        result = {"name": name, "size": len(data), "kind": KIND_TITLES[kind],
                  "bits": bits, "hash": bits_str(h, bits), "decimal": h, "match": None}
        expected = q.get("expected", [""])[0].strip()
        if expected:
            if len(expected) != bits or set(expected) - {"0", "1"}:
                return self.send_json(400, {"error": "Еталонний хеш має складатися з %d символів 0 і 1" % bits})
            result["expected"] = expected
            result["match"] = expected == result["hash"]
        self.send_json(200, result)


if __name__ == "__main__":
    print("Веб-інтерфейс: http://localhost:%d" % PORT)
    try:
        ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nЗупинено")
