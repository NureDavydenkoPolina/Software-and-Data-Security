import math

IP = [58, 50, 42, 34, 26, 18, 10, 2, 60, 52, 44, 36, 28, 20, 12, 4,
      62, 54, 46, 38, 30, 22, 14, 6, 64, 56, 48, 40, 32, 24, 16, 8,
      57, 49, 41, 33, 25, 17, 9, 1, 59, 51, 43, 35, 27, 19, 11, 3,
      61, 53, 45, 37, 29, 21, 13, 5, 63, 55, 47, 39, 31, 23, 15, 7]

FP = [40, 8, 48, 16, 56, 24, 64, 32, 39, 7, 47, 15, 55, 23, 63, 31,
      38, 6, 46, 14, 54, 22, 62, 30, 37, 5, 45, 13, 53, 21, 61, 29,
      36, 4, 44, 12, 52, 20, 60, 28, 35, 3, 43, 11, 51, 19, 59, 27,
      34, 2, 42, 10, 50, 18, 58, 26, 33, 1, 41, 9, 49, 17, 57, 25]

E = [32, 1, 2, 3, 4, 5, 4, 5, 6, 7, 8, 9,
     8, 9, 10, 11, 12, 13, 12, 13, 14, 15, 16, 17,
     16, 17, 18, 19, 20, 21, 20, 21, 22, 23, 24, 25,
     24, 25, 26, 27, 28, 29, 28, 29, 30, 31, 32, 1]

P = [16, 7, 20, 21, 29, 12, 28, 17, 1, 15, 23, 26, 5, 18, 31, 10,
     2, 8, 24, 14, 32, 27, 3, 9, 19, 13, 30, 6, 22, 11, 4, 25]

PC1 = [57, 49, 41, 33, 25, 17, 9, 1, 58, 50, 42, 34, 26, 18,
       10, 2, 59, 51, 43, 35, 27, 19, 11, 3, 60, 52, 44, 36,
       63, 55, 47, 39, 31, 23, 15, 7, 62, 54, 46, 38, 30, 22,
       14, 6, 61, 53, 45, 37, 29, 21, 13, 5, 28, 20, 12, 4]

PC2 = [14, 17, 11, 24, 1, 5, 3, 28, 15, 6, 21, 10, 23, 19, 12, 4,
       26, 8, 16, 7, 27, 20, 13, 2, 41, 52, 31, 37, 47, 55, 30, 40,
       51, 45, 33, 48, 44, 49, 39, 56, 34, 53, 46, 42, 50, 36, 29, 32]

SHIFTS = [1, 1, 2, 2, 2, 2, 2, 2, 1, 2, 2, 2, 2, 2, 2, 1]

SBOX = [
    [[14, 4, 13, 1, 2, 15, 11, 8, 3, 10, 6, 12, 5, 9, 0, 7],
     [0, 15, 7, 4, 14, 2, 13, 1, 10, 6, 12, 11, 9, 5, 3, 8],
     [4, 1, 14, 8, 13, 6, 2, 11, 15, 12, 9, 7, 3, 10, 5, 0],
     [15, 12, 8, 2, 4, 9, 1, 7, 5, 11, 3, 14, 10, 0, 6, 13]],
    [[15, 1, 8, 14, 6, 11, 3, 4, 9, 7, 2, 13, 12, 0, 5, 10],
     [3, 13, 4, 7, 15, 2, 8, 14, 12, 0, 1, 10, 6, 9, 11, 5],
     [0, 14, 7, 11, 10, 4, 13, 1, 5, 8, 12, 6, 9, 3, 2, 15],
     [13, 8, 10, 1, 3, 15, 4, 2, 11, 6, 7, 12, 0, 5, 14, 9]],
    [[10, 0, 9, 14, 6, 3, 15, 5, 1, 13, 12, 7, 11, 4, 2, 8],
     [13, 7, 0, 9, 3, 4, 6, 10, 2, 8, 5, 14, 12, 11, 15, 1],
     [13, 6, 4, 9, 8, 15, 3, 0, 11, 1, 2, 12, 5, 10, 14, 7],
     [1, 10, 13, 0, 6, 9, 8, 7, 4, 15, 14, 3, 11, 5, 2, 12]],
    [[7, 13, 14, 3, 0, 6, 9, 10, 1, 2, 8, 5, 11, 12, 4, 15],
     [13, 8, 11, 5, 6, 15, 0, 3, 4, 7, 2, 12, 1, 10, 14, 9],
     [10, 6, 9, 0, 12, 11, 7, 13, 15, 1, 3, 14, 5, 2, 8, 4],
     [3, 15, 0, 6, 10, 1, 13, 8, 9, 4, 5, 11, 12, 7, 2, 14]],
    [[2, 12, 4, 1, 7, 10, 11, 6, 8, 5, 3, 15, 13, 0, 14, 9],
     [14, 11, 2, 12, 4, 7, 13, 1, 5, 0, 15, 10, 3, 9, 8, 6],
     [4, 2, 1, 11, 10, 13, 7, 8, 15, 9, 12, 5, 6, 3, 0, 14],
     [11, 8, 12, 7, 1, 14, 2, 13, 6, 15, 0, 9, 10, 4, 5, 3]],
    [[12, 1, 10, 15, 9, 2, 6, 8, 0, 13, 3, 4, 14, 7, 5, 11],
     [10, 15, 4, 2, 7, 12, 9, 5, 6, 1, 13, 14, 0, 11, 3, 8],
     [9, 14, 15, 5, 2, 8, 12, 3, 7, 0, 4, 10, 1, 13, 11, 6],
     [4, 3, 2, 12, 9, 5, 15, 10, 11, 14, 1, 7, 6, 0, 8, 13]],
    [[4, 11, 2, 14, 15, 0, 8, 13, 3, 12, 9, 7, 5, 10, 6, 1],
     [13, 0, 11, 7, 4, 9, 1, 10, 14, 3, 5, 12, 2, 15, 8, 6],
     [1, 4, 11, 13, 12, 3, 7, 14, 10, 15, 6, 8, 0, 5, 9, 2],
     [6, 11, 13, 8, 1, 4, 10, 7, 9, 5, 0, 15, 14, 2, 3, 12]],
    [[13, 2, 8, 4, 6, 15, 11, 1, 10, 9, 3, 14, 5, 0, 12, 7],
     [1, 15, 13, 8, 10, 3, 7, 4, 12, 5, 6, 11, 0, 14, 9, 2],
     [7, 11, 4, 1, 9, 12, 14, 2, 0, 6, 10, 13, 15, 3, 5, 8],
     [2, 1, 14, 7, 4, 10, 8, 13, 15, 12, 9, 0, 3, 5, 6, 11]],
]

def bytes_to_bits(data):
    bits = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits


def bits_to_bytes(bits):
    out = bytearray()
    for i in range(0, len(bits), 8):
        v = 0
        for b in bits[i:i + 8]:
            v = (v << 1) | b
        out.append(v)
    return bytes(out)


def permute(bits, table):
    return [bits[i - 1] for i in table]


def xor(a, b):
    return [x ^ y for x, y in zip(a, b)]

def add_parity(key8):
    out = bytearray()
    for byte in key8:
        high7 = byte & 0xFE
        ones = bin(high7).count("1")
        out.append(high7 | (0 if ones % 2 == 1 else 1))
    return bytes(out)


def generate_keys(key8):
    key_bits = bytes_to_bits(add_parity(key8))
    cd = permute(key_bits, PC1)
    c, d = cd[:28], cd[28:]
    keys = []
    for s in SHIFTS:
        c = c[s:] + c[:s]
        d = d[s:] + d[:s]
        keys.append(permute(c + d, PC2))
    return keys

def f(r, k):
    x = xor(permute(r, E), k)
    out = []
    for j in range(8):
        b = x[j * 6:(j + 1) * 6]
        row = (b[0] << 1) | b[5]
        col = (b[1] << 3) | (b[2] << 2) | (b[3] << 1) | b[4]
        val = SBOX[j][row][col]
        out += [(val >> 3) & 1, (val >> 2) & 1, (val >> 1) & 1, val & 1]
    return permute(out, P)

def process_block(block8, keys, trace=None):
    bits = bytes_to_bits(block8)
    if trace is not None:
        trace[0].extend(block8)
    bits = permute(bits, IP)
    if trace is not None:
        trace[1].extend(bits_to_bytes(bits))
    l, r = bits[:32], bits[32:]
    for i in range(16):
        l, r = r, xor(l, f(r, keys[i]))
        if trace is not None:
            trace[2 + i].extend(bits_to_bytes(l + r))
    out = permute(r + l, FP)               # R16 L16 -> IP^-1
    res = bits_to_bytes(out)
    if trace is not None:
        trace[18].extend(res)
    return res


STAGE_NAMES = (["Вхідні дані", "Після початкової перестановки IP"]
               + ["Після раунду %d" % i for i in range(1, 17)]
               + ["Після кінцевої перестановки IP^-1 (результат)"])

def pad(data):
    n = 8 - len(data) % 8
    return data + bytes([n]) * n


def unpad(data):
    if not data or len(data) % 8:
        raise ValueError("Некоректна довжина шифротексту")
    n = data[-1]
    if n < 1 or n > 8 or data[-n:] != bytes([n]) * n:
        raise ValueError("Невірний ключ або пошкоджені дані")
    return data[:-n]


def entropy(data):
    if not data:
        return 0.0
    counts = [0] * 256
    for b in data:
        counts[b] += 1
    n = len(data)
    return -sum(c / n * math.log2(c / n) for c in counts if c)


def check_key(key_text):
    key = key_text.encode("utf-8")
    if len(key) != 8:
        raise ValueError("Ключ має містити рівно 8 байтів (8 ASCII-символів)")
    return key


def encrypt(data, key8):
    keys = generate_keys(key8)
    data = pad(data)
    trace = [bytearray() for _ in range(19)]
    out = bytearray()
    for i in range(0, len(data), 8):
        out += process_block(data[i:i + 8], keys, trace)
    return bytes(out), [(n, entropy(t)) for n, t in zip(STAGE_NAMES, trace)]


def decrypt(data, key8):
    if len(data) % 8 or not data:
        raise ValueError("Довжина шифротексту має бути кратна 8 байтам")
    keys = generate_keys(key8)[::-1]
    trace = [bytearray() for _ in range(19)]
    out = bytearray()
    for i in range(0, len(data), 8):
        out += process_block(data[i:i + 8], keys, trace)
    names = (["Вхідний шифротекст", "Після початкової перестановки IP"]
             + ["Після раунду %d" % i for i in range(1, 17)]
             + ["Після кінцевої перестановки IP^-1 (з доповненням)"])
    stats = [(n, entropy(t)) for n, t in zip(names, trace)]
    return unpad(bytes(out)), stats

def run_gui():
    import tkinter as tk
    from tkinter import ttk, messagebox

    root = tk.Tk()
    root.title("Лабораторна робота №1 - DES")
    root.geometry("980x760")

    top = ttk.Frame(root, padding=8)
    top.pack(fill="x")
    ttk.Label(top, text="Ключ (8 символів):").pack(side="left")
    key_var = tk.StringVar(value="mykey123")
    ttk.Entry(top, textvariable=key_var, width=14).pack(side="left", padx=6)

    mid = ttk.Frame(root, padding=8)
    mid.pack(fill="both", expand=True)
    ttk.Label(mid, text="Вхідний текст (для розшифрування — hex):").pack(anchor="w")
    inp = tk.Text(mid, height=7, wrap="word")
    inp.pack(fill="x")
    ttk.Label(mid, text="Результат:").pack(anchor="w", pady=(8, 0))
    outp = tk.Text(mid, height=7, wrap="word")
    outp.pack(fill="x")

    status = tk.StringVar()
    ttk.Label(root, textvariable=status, foreground="#555").pack(anchor="w", padx=8)

    tree = ttk.Treeview(root, columns=("stage", "h"), show="headings", height=19)
    tree.heading("stage", text="Етап")
    tree.heading("h", text="Ентропія, біт/байт")
    tree.column("stage", width=520)
    tree.column("h", width=160, anchor="center")
    tree.pack(fill="both", expand=True, padx=8, pady=8)

    def show_stats(stats):
        tree.delete(*tree.get_children())
        for name, h in stats:
            tree.insert("", "end", values=(name, "%.4f" % h))

    def set_out(text):
        outp.delete("1.0", "end")
        outp.insert("1.0", text)

    def get_key():
        return check_key(key_var.get())

    def do_encrypt():
        try:
            key = get_key()
            data = inp.get("1.0", "end-1c").encode("utf-8")
            if not data:
                raise ValueError("Введіть текст для шифрування")
            res, stats = encrypt(data, key)
            set_out(res.hex())
            show_stats(stats)
            status.set("Зашифровано. Розмір: %d байт" % len(res))
        except Exception as e:
            messagebox.showerror("Помилка", str(e))

    def do_decrypt():
        try:
            key = get_key()
            raw = "".join(inp.get("1.0", "end-1c").split())
            data = bytes.fromhex(raw)
            res, stats = decrypt(data, key)
            set_out(res.decode("utf-8", errors="replace"))
            show_stats(stats)
            status.set("Розшифровано. Розмір: %d байт" % len(res))
        except Exception as e:
            messagebox.showerror("Помилка", str(e))

    def swap():
        t = outp.get("1.0", "end-1c")
        inp.delete("1.0", "end")
        inp.insert("1.0", t)
        set_out("")

    btns = ttk.Frame(root, padding=8)
    btns.pack(fill="x")
    ttk.Button(btns, text="Зашифрувати текст", command=do_encrypt).pack(side="left", padx=3)
    ttk.Button(btns, text="Розшифрувати текст", command=do_decrypt).pack(side="left", padx=3)
    ttk.Button(btns, text="Результат → вхід", command=swap).pack(side="left", padx=3)

    root.mainloop()


if __name__ == "__main__":
    run_gui()
