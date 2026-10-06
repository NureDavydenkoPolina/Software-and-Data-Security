import os
import json
import struct

KEY_FILE = "otp_key.bin"
KEY_SIZE = 32 * 1024
HEADER_SIZE = 4

def load_key():
    if not os.path.exists(KEY_FILE):
        raise FileNotFoundError(
            "otp_key.bin не знайдено. Спочатку запустіть server.py "
        )

    with open(KEY_FILE, "rb") as f:
        key = f.read()

    if len(key) != KEY_SIZE:
        raise ValueError(f"otp_key.bin повинен мати розмір {KEY_SIZE} байт.")

    return key


def xor_data(data, key):
    return bytes(a ^ b for a, b in zip(data, key))


def send_packet(sock, packet):
    raw = json.dumps(packet, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    sock.sendall(struct.pack("!I", len(raw)) + raw)


def recv_exact(sock, size):
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            return None
        data.extend(chunk)
    return bytes(data)


def recv_packet(sock):
    header = recv_exact(sock, HEADER_SIZE)
    if header is None:
        return None

    size = struct.unpack("!I", header)[0]
    if size > 10 * 1024 * 1024:
        raise ValueError("Завеликий пакет.")

    raw = recv_exact(sock, size)
    if raw is None:
        return None

    return json.loads(raw.decode("utf-8"))