import base64
import hashlib
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

KEY_BITS = int(sys.argv[1]) if len(sys.argv) > 1 else 2048
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
MIN_CLIENT_BITS = 2048
MAX_SKEW = 300
BASE = os.path.dirname(os.path.abspath(__file__))
SEARCH_DIRS = [os.path.join(BASE, "static"), os.path.join(BASE, "web"), BASE]


def find_static(name):
    for d in SEARCH_DIRS:
        p = os.path.join(d, name)
        if os.path.isfile(p):
            return p
    return None

OAEP = padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),
                    algorithm=hashes.SHA256(), label=None)

print("Генерація RSA-ключа сервера (%d біт)..." % KEY_BITS)
PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=KEY_BITS)
PUBLIC_DER = PRIVATE_KEY.public_key().public_bytes(
    serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
PUBLIC_B64 = base64.b64encode(PUBLIC_DER).decode()
print("Готово. Відбиток відкритого ключа: %s" % hashlib.sha256(PUBLIC_DER).hexdigest()[:16])

LOCK = threading.Lock()
USERS = {}
SEEN_NONCES = {}


def make_hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)


def add_user(name, password):
    salt = os.urandom(16)
    USERS[name] = (salt, make_hash(password, salt))


add_user("student", "Secret123")
add_user("admin", "admin2026")


def check_password(name, password):
    rec = USERS.get(name)
    if rec is None:
        make_hash(password, b"0" * 16)
        return False
    salt, h = rec
    return make_hash(password, salt) == h


def process(payload):
    """payload - розшифрований словник запиту; повертає (ok, повідомлення)."""
    now = time.time()
    t = payload.get("t")
    n = payload.get("n")
    if not isinstance(t, (int, float)) or abs(now - t / 1000.0) > MAX_SKEW:
        return False, "Запит прострочено"
    if not isinstance(n, str) or not (8 <= len(n) <= 64):
        return False, "Некоректний запит"
    with LOCK:
        for k in [k for k, v in SEEN_NONCES.items() if now - v > 2 * MAX_SKEW]:
            del SEEN_NONCES[k]
        if n in SEEN_NONCES:
            return False, "Повторний запит відхилено"
        SEEN_NONCES[n] = now

    action = payload.get("a")
    user = payload.get("u")
    pwd = payload.get("p")
    if not isinstance(user, str) or not isinstance(pwd, str) or not user or not pwd:
        return False, "Введіть логін і пароль"
    if len(user) > 20 or len(pwd) > 40:
        return False, "Занадто довгий логін або пароль"

    if action == "register":
        if len(pwd) < 6:
            return False, "Пароль має містити щонайменше 6 символів"
        with LOCK:
            if user in USERS:
                return False, "Такий користувач уже існує"
            add_user(user, pwd)
        return True, "Користувача %s зареєстровано" % user
    if action == "login":
        with LOCK:
            ok = check_password(user, pwd)
        if ok:
            return True, "Вітаю, %s! Автентифікація успішна" % user
        return False, "Невірний логін або пароль"
    return False, "Невідома дія"


def short(b, n=24):
    s = b.hex()
    return s[:n] + "…" if len(s) > n else s


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
        self.send_bytes(code, json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self.serve_file("index.html", "text/html; charset=utf-8")
        elif path == "/client.js":
            self.serve_file("client.js", "application/javascript; charset=utf-8")
        elif path == "/api/pubkey":
            self.send_json(200, {"publicKey": PUBLIC_B64, "keyBits": KEY_BITS,
                                 "scheme": "RSA-OAEP-SHA256"})
        else:
            self.send_json(404, {"error": "Не знайдено"})

    def serve_file(self, name, ctype):
        path = find_static(name)
        if path is None:
            return self.send_json(404, {"error": "Файл %s не знайдено поруч із server.py" % name})
        with open(path, "rb") as fh:
            self.send_bytes(200, fh.read(), ctype)

    def do_POST(self):
        if self.path != "/api/auth":
            return self.send_json(404, {"error": "Не знайдено"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 16384:
                raise ValueError("розмір запиту")
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            cipher = base64.b64decode(body["data"])
            client_pub = serialization.load_der_public_key(base64.b64decode(body["clientKey"]))
            if not isinstance(client_pub, rsa.RSAPublicKey):
                raise ValueError("ключ клієнта не RSA")
            if client_pub.key_size < MIN_CLIENT_BITS:
                return self.send_json(400, {"error": "Ключ клієнта замалий (потрібно щонайменше %d біт)" % MIN_CLIENT_BITS})
        except Exception:
            return self.send_json(400, {"error": "Некоректний запит"})

        print("\n[ІЗ МЕРЕЖІ] шифротекст запиту (%d байт): %s" % (len(cipher), short(cipher)))
        try:
            plain = PRIVATE_KEY.decrypt(cipher, OAEP)
            payload = json.loads(plain.decode("utf-8"))
        except Exception:
            return self.send_json(400, {"error": "Не вдалося розшифрувати запит"})
        safe = dict(payload)
        if "p" in safe:
            safe["p"] = "*" * len(str(safe["p"]))
        print("[РОЗШИФРОВАНО] %s" % json.dumps(safe, ensure_ascii=False))

        ok, msg = process(payload)
        answer = json.dumps({"ok": ok, "msg": msg, "n": payload.get("n")},
                            ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        try:
            out = client_pub.encrypt(answer, OAEP)
        except Exception:
            return self.send_json(400, {"error": "Відповідь завелика для ключа клієнта"})
        print("[ДО МЕРЕЖІ] шифротекст відповіді (%d байт): %s  (ok=%s)" % (len(out), short(out), ok))
        self.send_json(200, {"data": base64.b64encode(out).decode()})


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    for fn in ("index.html", "client.js"):
        p = find_static(fn)
        print("%s: %s" % (fn, p if p else "НЕ ЗНАЙДЕНО - покладіть поруч із server.py"))
    print("Сервер запущено: http://localhost:%d" % PORT)
    print("Тестові користувачі: student / Secret123,  admin / admin2026")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nЗупинено")
