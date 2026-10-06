from otp_common import *
import base64
import json
import os
import socket
import struct
import threading

HOST = "127.0.0.1"
PORT = 5000

def input_loop(sock, key):
    offset = len(key) // 2
    end = len(key)

    while True:
        try:
            text = input("\nВи: ")
        except (EOFError, KeyboardInterrupt):
            text = "/exit"

        if text.strip().lower() == "/exit":
            try:
                send_packet(sock, {"type": "close"})
            except OSError:
                pass
            print("\nЗ'єднання завершено.")
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()
            return

        if not text:
            continue

        data = text.encode("utf-8")
        if offset + len(data) > end:
            print("\nЗапас ключа для CLIENT -> SERVER вичерпано.")
            print("Для нового сеансу перезапустіть server.py: буде створено новий ключ.")
            continue

        pad = key[offset:offset + len(data)]
        cipher = xor_data(data, pad)

        packet = {
            "type": "message",
            "direction": "client",
            "offset": offset,
            "data": base64.b64encode(cipher).decode("ascii"),
        }

        try:
            send_packet(sock, packet)
        except OSError:
            print("\nЗ'єднання втрачено.")
            return

        print("Зашифровано (hex):", cipher.hex())
        offset += len(data)


def receive_loop(sock, key):
    while True:
        try:
            packet = recv_packet(sock)
        except (OSError, ValueError, json.JSONDecodeError) as e:
            print(f"\nПомилка отримання: {e}")
            return

        if packet is None or packet.get("type") == "close":
            print("\nСервер завершив з'єднання.")
            return

        if packet.get("type") != "message":
            continue

        if packet.get("direction") != "server":
            print("\nОтримано пакет із невірним напрямком.")
            continue

        try:
            cipher = base64.b64decode(packet["data"], validate=True)
            offset = int(packet["offset"])
        except (KeyError, ValueError, TypeError):
            print("\nНекоректний пакет.")
            continue

        half = len(key) // 2
        if offset < 0 or offset + len(cipher) > half:
            print("\nНевірна позиція ключа в отриманому пакеті.")
            continue

        pad = key[offset:offset + len(cipher)]
        try:
            plain = xor_data(cipher, pad).decode("utf-8")
        except UnicodeDecodeError:
            print("\nНе вдалося розшифрувати повідомлення.")
            continue

        print("\nОтримано зашифроване (hex):", cipher.hex())
        print("Розшифровано:", plain)


def main():
    try:
        key = load_key()
    except Exception as e:
        print("Помилка:", e)
        return

    print("=== OTP CHAT — CLIENT ===")
    print(f"Підключення до {HOST}:{PORT} ...")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.connect((HOST, PORT))
        except OSError as e:
            print("Не вдалося підключитися:", e)
            print("Спочатку запустіть server.py.")
            return

        print("Підключено.")
        print("Напишіть повідомлення. Для виходу введіть /exit")

        receiver = threading.Thread(target=receive_loop, args=(sock, key), daemon=True)
        receiver.start()
        input_loop(sock, key)


if __name__ == "__main__":
    main()
