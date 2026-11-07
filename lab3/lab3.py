import io
import json
import math
import os
import random
import re
import secrets
import struct
import zipfile
import zlib

M64 = (1 << 64) - 1
SEED = 0x243F6A8885A308D3
K1 = 0x9E3779B97F4A7C15
K2 = 0xBF58476D1CE4E5B9
K3 = 0x94D049BB133111EB


def _step(h, w):
    h = ((h ^ w) * K1) & M64
    return h ^ (h >> 31)


class HashState:

    def __init__(self):
        self.h = SEED
        self.buf = b""
        self.n = 0

    def copy(self):
        s = HashState()
        s.h, s.buf, s.n = self.h, self.buf, self.n
        return s

    def update(self, data):
        self.n += len(data)
        data = self.buf + data
        m = len(data) & ~7
        h = self.h
        if m:
            for (w,) in struct.iter_unpack("<Q", data[:m]):
                h = ((h ^ w) * K1) & M64
                h ^= h >> 31
        self.h = h
        self.buf = data[m:]

    def digest(self, bits):
        h = self.h
        if self.buf:
            w = int.from_bytes(self.buf, "little") | (len(self.buf) << 56)
            h = _step(h, w)
        h ^= (self.n * K3) & M64
        h ^= h >> 33
        h = (h * K2) & M64
        h ^= h >> 29
        h = (h * K3) & M64
        h ^= h >> 32
        mask = (1 << bits) - 1
        out = 0
        while h:
            out ^= h & mask
            h >>= bits
        return out


def my_hash(data, bits=8):
    st = HashState()
    st.update(data)
    return st.digest(bits)


def bits_str(value, bits):
    return format(value, "0%db" % bits)



def pattern(k):
    return "".join(" " if c == "0" else "\t" for c in bin(k)[3:])


def file_kind(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        return "docx"
    if ext == ".png":
        return "png"
    if ext in (".jpg", ".jpeg"):
        return "jpeg"
    return "source"


def make_builder(path, data):
    kind = file_kind(path)

    if kind == "docx":
        zin = zipfile.ZipFile(io.BytesIO(data))
        infos = zin.infolist()
        payload = {i.filename: zin.read(i.filename) for i in infos}
        if "docProps/core.xml" not in payload:
            raise ValueError("У документі немає docProps/core.xml (властивостей)")
        core = payload["docProps/core.xml"].decode("utf-8")

        def build(k):
            pat = pattern(k)
            m = re.search(r"<dc:description>(.*?)</dc:description>", core, re.S)
            if m:
                new = core[:m.end(1)] + pat + core[m.end(1):]
            elif re.search(r"<dc:description\s*/>", core):
                new = re.sub(r"<dc:description\s*/>", "<dc:description>%s</dc:description>" % pat, core, 1)
            else:
                new = core.replace("</cp:coreProperties>",
                                   "<dc:description>%s</dc:description></cp:coreProperties>" % pat)
            out = io.BytesIO()
            with zipfile.ZipFile(out, "w") as z:
                for i in infos:
                    ni = zipfile.ZipInfo(i.filename, i.date_time)
                    ni.compress_type = i.compress_type
                    ni.external_attr = i.external_attr
                    z.writestr(ni, new.encode("utf-8") if i.filename == "docProps/core.xml" else payload[i.filename])
            return out.getvalue()
        return build, "Властивість документа «Коментарі» (docProps/core.xml): додано пробіли й табуляції"

    if kind == "png":
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Файл не є коректним PNG")
        pos, iend = 8, None
        while pos + 8 <= len(data):
            ln = struct.unpack(">I", data[pos:pos + 4])[0]
            if data[pos + 4:pos + 8] == b"IEND":
                iend = pos
                break
            pos += 12 + ln
        if iend is None:
            raise ValueError("У PNG не знайдено блок IEND")

        def build(k):
            body = b"Comment\x00" + pattern(k).encode("latin-1")
            typ = b"tEXt"
            chunk = struct.pack(">I", len(body)) + typ + body + struct.pack(">I", zlib.crc32(typ + body) & 0xFFFFFFFF)
            return data[:iend] + chunk + data[iend:]
        return build, "Текстовий блок PNG (tEXt, поле «Comment»): додано пробіли й табуляції"

    if kind == "jpeg":
        def build(k):
            return data + pattern(k).encode("latin-1")
        return build, "Дані після маркера кінця зображення (EOI): додано пробіли й табуляції"

    idx = len(data.rstrip(b"\r\n"))

    def build(k):
        return data[:idx] + pattern(k).encode("latin-1") + data[idx:]
    return build, "Додано пробіли й табуляції в кінець останнього рядка коду"


def find_collision(path, data, bits, max_tries=200000):
    target = my_hash(data, bits)
    build, desc = make_builder(path, data)
    first, second = build(2), build(3)
    lcp = 0
    for a, b in zip(first, second):
        if a != b:
            break
        lcp += 1
    prefix = first[:lcp]
    base = HashState()
    base.update(prefix)
    for k in range(2, max_tries):
        cand = build(k)
        if cand[:lcp] == prefix:
            st = base.copy()
            st.update(cand[lcp:])
        else:
            st = HashState()
            st.update(cand)
        if st.digest(bits) == target and cand != data:
            return cand, k - 1, desc
    raise RuntimeError("Колізію не знайдено")


def avalanche(data, bits, trials=1000, seed=1):
    data = data[:4096]
    if not data:
        raise ValueError("Порожні дані")
    rnd = random.Random(seed)
    base = my_hash(data, bits)
    changed_sum = ge30 = same = 0
    for _ in range(trials):
        pos = rnd.randrange(len(data))
        nb = rnd.randrange(256)
        while nb == data[pos]:
            nb = rnd.randrange(256)
        h = my_hash(data[:pos] + bytes([nb]) + data[pos + 1:], bits)
        diff = bin(h ^ base).count("1")
        changed_sum += diff
        same += diff == 0
        ge30 += diff / bits >= 0.3
    return {"trials": trials,
            "mean_pct": 100.0 * changed_sum / (trials * bits),
            "ge30_pct": 100.0 * ge30 / trials,
            "same_pct": 100.0 * same / trials}


SMALL_PRIMES = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97]


def is_prime(n, rounds=40):
    if n < 2:
        return False
    for p in SMALL_PRIMES:
        if n % p == 0:
            return n == p
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for _ in range(rounds):
        a = secrets.randbelow(n - 3) + 2
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def gen_prime(bits):
    while True:
        c = secrets.randbits(bits) | (1 << (bits - 1)) | (1 << (bits - 2)) | 1
        if is_prime(c):
            return c


def rsa_generate(bits=2048):
    e = 65537
    while True:
        p, q = gen_prime(bits // 2), gen_prime(bits // 2)
        phi = (p - 1) * (q - 1)
        if p != q and math.gcd(e, phi) == 1:
            n = p * q
            return {"n": n, "e": e}, {"n": n, "d": pow(e, -1, phi)}


def encode_digest(value, nbits, n):
    k = (n.bit_length() + 7) // 8
    tail = bytes([nbits, value])
    return int.from_bytes(b"\x00\x01" + b"\xff" * (k - len(tail) - 3) + b"\x00" + tail, "big")


def sign_digest(value, nbits, priv):
    return pow(encode_digest(value, nbits, priv["n"]), priv["d"], priv["n"])


def verify_digest(value, nbits, signature, pub):
    return pow(signature, pub["e"], pub["n"]) == encode_digest(value, nbits, pub["n"])


def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({k: (format(v, "x") if isinstance(v, int) and k != "bits" else v)
                   for k, v in obj.items()}, fh, indent=2)


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    return {k: (int(v, 16) if isinstance(v, str) else v) for k, v in raw.items()}


def read_file(path):
    with open(path, "rb") as fh:
        return fh.read()


def run_gui():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    root = tk.Tk()
    root.title("Лабораторна робота №3 — власна хеш-функція")
    root.geometry("900x660")

    bits_var = tk.IntVar(value=8)
    top = ttk.Frame(root, padding=8)
    top.pack(fill="x")
    ttk.Label(top, text="Довжина хешу (біт):").pack(side="left")
    for b in (2, 4, 8):
        ttk.Radiobutton(top, text=str(b), variable=bits_var, value=b,
                        command=lambda: refresh_all()).pack(side="left", padx=6)

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=8, pady=6)

    def out_box(parent, height=10):
        t = tk.Text(parent, height=height, wrap="word", font=("Consolas", 11))
        t.pack(fill="both", expand=True, pady=6)
        return t

    def put(box, text):
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        box.configure(state="disabled")

    ftypes = [("Усі файли", "*.*")]

    t1 = ttk.Frame(nb, padding=10)
    nb.add(t1, text="Хеш файлу")
    st1 = {"path": None}
    ttk.Button(t1, text="Обрати файл…", command=lambda: pick1()).pack(anchor="w")
    box1 = out_box(t1, 8)

    def show1():
        p = st1["path"]
        if not p:
            put(box1, "Файл не обрано")
            return
        data = read_file(p)
        n = bits_var.get()
        h = my_hash(data, n)
        put(box1, "Файл: %s\nТип: %s\nРозмір: %d байт\n\nХеш (%d біт): %s\nДесяткове значення: %d"
            % (p, file_kind(p), len(data), n, bits_str(h, n), h))

    def pick1():
        p = filedialog.askopenfilename(filetypes=ftypes)
        if p:
            st1["path"] = p
            show1()

    t2 = ttk.Frame(nb, padding=10)
    nb.add(t2, text="Колізія вручну")
    st2 = {"a": None, "b": None}
    ttk.Label(t2, text="Оберіть два файли одного типу і порівняйте їх хеші.").pack(anchor="w")
    row = ttk.Frame(t2)
    row.pack(fill="x", pady=6)
    la = ttk.Label(row, text="Файл A: —")
    lb = ttk.Label(row, text="Файл B: —")

    def pick2(which, lbl):
        p = filedialog.askopenfilename(filetypes=ftypes)
        if p:
            st2[which] = p
            lbl.configure(text="Файл %s: %s" % (which.upper(), os.path.basename(p)))
            compare()
    ttk.Button(row, text="Файл A…", command=lambda: pick2("a", la)).grid(row=0, column=0, padx=4)
    la.grid(row=0, column=1, sticky="w")
    ttk.Button(row, text="Файл B…", command=lambda: pick2("b", lb)).grid(row=1, column=0, padx=4, pady=4)
    lb.grid(row=1, column=1, sticky="w")
    box2 = out_box(t2, 10)

    def compare():
        if not (st2["a"] and st2["b"]):
            return
        n = bits_var.get()
        da, db = read_file(st2["a"]), read_file(st2["b"])
        ha, hb = my_hash(da, n), my_hash(db, n)
        if da == db:
            verdict = "Файли ідентичні — це не колізія."
        elif ha == hb:
            verdict = "КОЛІЗІЯ: вміст різний, а хеші збігаються!"
        else:
            verdict = "Хеші різні."
        put(box2, "Файл A: %d байт, хеш %s (%d)\nФайл B: %d байт, хеш %s (%d)\n\n%s"
            % (len(da), bits_str(ha, n), ha, len(db), bits_str(hb, n), hb, verdict))

    t3 = ttk.Frame(nb, padding=10)
    nb.add(t3, text="Автоматична колізія")
    st3 = {"path": None}
    lbl3 = ttk.Label(t3, text="Файл не обрано")

    def pick3():
        p = filedialog.askopenfilename(filetypes=ftypes)
        if p:
            st3["path"] = p
            lbl3.configure(text=p)
    ttk.Button(t3, text="Обрати файл…", command=pick3).pack(anchor="w")
    lbl3.pack(anchor="w", pady=4)
    box3 = out_box(t3, 14)

    def make_collision():
        p = st3["path"]
        if not p:
            messagebox.showinfo("Увага", "Спочатку оберіть файл")
            return
        n = bits_var.get()
        try:
            data = read_file(p)
            new, tries, desc = find_collision(p, data, n)
            base, ext = os.path.splitext(os.path.basename(p))
            save = filedialog.asksaveasfilename(initialfile=base + "_collision" + ext, defaultextension=ext)
            if not save:
                return
            with open(save, "wb") as fh:
                fh.write(new)
            check = read_file(save)
            h1, h2 = my_hash(data, n), my_hash(check, n)
            put(box3, "Оригінал: %s\n  розмір %d байт, хеш %s (%d)\n\nНовий файл: %s\n  розмір %d байт, хеш %s (%d)\n\n"
                      "Збіг хешів: %s\nВміст однаковий: %s\nКількість спроб: %d\nЩо змінено: %s\n"
                % (p, len(data), bits_str(h1, n), h1, save, len(check), bits_str(h2, n), h2,
                   "ТАК" if h1 == h2 else "НІ", "так" if data == check else "ні", tries, desc))
        except Exception as e:
            messagebox.showerror("Помилка", str(e))
    ttk.Button(t3, text="Створити файл з таким самим хешем", command=make_collision).pack(anchor="w")

    t4 = ttk.Frame(nb, padding=10)
    nb.add(t4, text="Перевірка вимоги 30%")
    ttk.Label(t4, text="Тест: у випадковому місці файлу змінюється один байт, порівнюється хеш до і після.").pack(anchor="w")
    box4 = out_box(t4, 14)

    def avl_file():
        p = filedialog.askopenfilename(filetypes=ftypes)
        if not p:
            return
        n = bits_var.get()
        try:
            r = avalanche(read_file(p), n)
        except Exception as e:
            messagebox.showerror("Помилка", str(e))
            return
        put(box4, "Файл: %s (перші %d байт)\nДовжина хешу: %d біт, випробувань: %d\n\n"
                  "Середня частка змінених бітів результату: %.1f %%\n"
                  "Випадків зі зміною не менше 30%% результату: %.1f %%\n"
                  "Випадків, коли хеш не змінився: %.1f %%"
            % (p, min(os.path.getsize(p), 4096), n, r["trials"], r["mean_pct"], r["ge30_pct"], r["same_pct"]))
    ttk.Button(t4, text="Перевірити на файлі…", command=avl_file).pack(anchor="w")

    t5 = ttk.Frame(nb, padding=10)
    nb.add(t5, text="Цифровий підпис RSA")
    here = os.path.dirname(os.path.abspath(__file__))
    pub_path = os.path.join(here, "public_key.json")
    priv_path = os.path.join(here, "private_key.json")
    ttk.Label(t5, text="Підписується дайджест файлу (довжина обирається вгорі). Підпис зберігається у файлі «ім'я.sig».").pack(anchor="w")
    box5 = out_box(t5, 14)

    def gen_keys():
        put(box5, "Генерація ключів RSA 2048 біт, зачекайте…")
        root.update_idletasks()
        pub, priv = rsa_generate(2048)
        save_json(pub_path, pub)
        save_json(priv_path, priv)
        put(box5, "Ключі створено (2048 біт):\n  %s\n  %s" % (pub_path, priv_path))

    def sign_file():
        if not os.path.exists(priv_path):
            messagebox.showinfo("Увага", "Спочатку згенеруйте ключі")
            return
        p = filedialog.askopenfilename(filetypes=ftypes)
        if not p:
            return
        n = bits_var.get()
        h = my_hash(read_file(p), n)
        sig = sign_digest(h, n, load_json(priv_path))
        save_json(p + ".sig", {"bits": n, "signature": sig})
        put(box5, "Файл: %s\nДайджест (%d біт): %s\n\nПідпис збережено: %s.sig\nПідпис (hex, початок): %s…"
            % (p, n, bits_str(h, n), p, format(sig, "x")[:64]))

    def verify_file():
        if not os.path.exists(pub_path):
            messagebox.showinfo("Увага", "Немає public_key.json — спочатку згенеруйте ключі")
            return
        p = filedialog.askopenfilename(filetypes=ftypes)
        if not p:
            return
        sp = p + ".sig"
        if not os.path.exists(sp):
            sp = filedialog.askopenfilename(title="Оберіть файл підпису", filetypes=[("Підпис", "*.sig")])
            if not sp:
                return
        sig = load_json(sp)
        n = int(sig["bits"])
        h = my_hash(read_file(p), n)
        ok = verify_digest(h, n, sig["signature"], load_json(pub_path))
        put(box5, "Файл: %s\nДайджест (%d біт): %s\n\nРезультат: %s"
            % (p, n, bits_str(h, n), "ПІДПИС ВІРНИЙ, файл не змінено" if ok else "ПІДПИС НЕВІРНИЙ, цілісність порушена"))
    bt5 = ttk.Frame(t5)
    bt5.pack(anchor="w")
    ttk.Button(bt5, text="Згенерувати ключі RSA", command=gen_keys).pack(side="left", padx=4)
    ttk.Button(bt5, text="Підписати файл…", command=sign_file).pack(side="left", padx=4)
    ttk.Button(bt5, text="Перевірити підпис…", command=verify_file).pack(side="left", padx=4)

    def refresh_all():
        show1()
        compare()
    put(box1, "Файл не обрано")
    put(box2, "")
    put(box3, "")
    put(box4, "")
    put(box5, "")
    root.mainloop()


if __name__ == "__main__":
    run_gui()
