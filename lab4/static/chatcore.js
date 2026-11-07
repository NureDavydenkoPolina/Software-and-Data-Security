// Клієнтська частина безпечного чату (працює в браузері та в Node.js).
// Групова схема Діффі-Хеллмана (кільце) + AES-256-GCM (WebCrypto).
(function (root) {
  "use strict";

  const subtle = root.crypto.subtle;
  const enc = new TextEncoder();
  const dec = new TextDecoder();

  // ------------------------------------------------------------------
  // Допоміжні функції
  // ------------------------------------------------------------------
  function toHex(buf) {
    return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, "0")).join("");
  }

  function toB64(buf) {
    const bytes = new Uint8Array(buf);
    let s = "";
    for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
    return btoa(s);
  }

  function fromB64(str) {
    const s = atob(str);
    const out = new Uint8Array(s.length);
    for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
    return out;
  }

  function bigToBytes(n, len) {
    let hex = n.toString(16);
    hex = hex.padStart(len * 2, "0");
    const out = new Uint8Array(len);
    for (let i = 0; i < len; i++) out[i] = parseInt(hex.substr(i * 2, 2), 16);
    return out;
  }

  // ------------------------------------------------------------------
  // Алгоритм Діффі-Хеллмана: піднесення до степеня за модулем
  // ------------------------------------------------------------------
  function modPow(base, exp, mod) {
    let result = 1n;
    base %= mod;
    while (exp > 0n) {
      if (exp & 1n) result = (result * base) % mod;
      exp >>= 1n;
      base = (base * base) % mod;
    }
    return result;
  }

  // Закритий ключ X: випадкове число, 2 <= X < Q (256 біт)
  function randomSecret(q) {
    const a = new Uint8Array(32);
    root.crypto.getRandomValues(a);
    const x = BigInt("0x" + toHex(a));
    return (x % (q - 3n)) + 2n;
  }

  async function sha256(bytes) {
    return new Uint8Array(await subtle.digest("SHA-256", bytes));
  }

  // ------------------------------------------------------------------
  // Клієнт чату
  // ------------------------------------------------------------------
  class ChatClient {
    constructor(opts) {
      this.base = opts.base || "";
      this.name = opts.name;
      this.onLog = opts.onLog || function () {};
      this.onRoster = opts.onRoster || function () {};
      this.onState = opts.onState || function () {};
      this.onMessage = opts.onMessage || function () {};
      this.onClosed = opts.onClosed || function () {};
      this.keys = new Map();      // епоха -> ключ AES
      this.pending = [];          // повідомлення, що чекають на ключ
      this.epoch = 0;
      this.members = [];
      this.ready = false;
      this.chain = Promise.resolve();
      this.abort = new AbortController();
    }

    async connect() {
      const params = await (await fetch(this.base + "/api/params")).json();
      this.Q = BigInt("0x" + params.q);
      this.A = BigInt(params.a);

      const resp = await fetch(this.base + "/api/join", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: this.name })
      });
      const body = await resp.json();
      if (!resp.ok) throw new Error(body.error || "Не вдалося увійти");
      this.id = body.id;
      this.token = body.token;
      this.params = { qBits: this.Q.toString(2).length, a: params.a };
      this._listen();
      return this.params;
    }

    async _post(path, obj) {
      const resp = await fetch(this.base + path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(Object.assign({ id: this.id, token: this.token }, obj))
      });
      return resp.json();
    }

    async _listen() {
      try {
        const url = this.base + "/api/events?id=" + this.id + "&token=" + this.token;
        const resp = await fetch(url, { signal: this.abort.signal });
        const reader = resp.body.getReader();
        const td = new TextDecoder();
        let buf = "";
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += td.decode(value, { stream: true });
          let idx;
          while ((idx = buf.indexOf("\n\n")) >= 0) {
            const block = buf.slice(0, idx);
            buf = buf.slice(idx + 2);
            for (const line of block.split("\n")) {
              if (line.startsWith("data: ")) {
                const ev = JSON.parse(line.slice(6));
                this.chain = this.chain.then(() => this._handle(ev)).catch(e => this.onLog("error", String(e)));
              }
            }
          }
        }
      } catch (e) { /* з'єднання закрито */ }
      this.onClosed();
    }

    async leave() {
      try { await this._post("/api/leave", {}); } catch (e) { /* ignore */ }
      this.abort.abort();
    }

    // ----------------------------------------------------------------
    async _handle(ev) {
      if (ev.type === "roster") return this._onRoster(ev);
      if (ev.type === "dh") return this._onDh(ev);
      if (ev.type === "chat") return this._onChat(ev);
    }

    async _onRoster(ev) {
      const old = this.members;
      this.epoch = ev.epoch;
      this.members = ev.members;
      this.index = ev.index;
      this.ready = false;
      this.fingerprint = null;
      this.onRoster({ epoch: ev.epoch, members: ev.members, previous: old });
      const n = ev.members.length;
      if (n < 2) {
        this.onState("waiting", {});
        this.onLog("info", "Епоха " + ev.epoch + ": ви єдиний учасник, чекаємо на інших");
        return;
      }
      this.onState("exchange", { epoch: ev.epoch, n });
      this.x = randomSecret(this.Q);
      const Y = modPow(this.A, this.x, this.Q);
      this.onLog("info", "Епоха " + ev.epoch + ": " + n + " учасників. Згенеровано закритий ключ X (він нікуди не передається)");
      this.onLog("dh", "Відкритий ключ Y = A^X mod Q = " + Y.toString(16).slice(0, 24) + "… → надсилаємо наступному в кільці");
      await this._post("/api/dh", { epoch: ev.epoch, round: 0, value: Y.toString(16) });
    }

    async _onDh(ev) {
      if (ev.epoch !== this.epoch || this.ready) return;
      const w = BigInt("0x" + ev.value);
      if (w <= 1n || w >= this.Q - 1n) {
        this.onLog("error", "Отримано некоректне значення від " + ev.from + ", відхилено");
        return;
      }
      const n = this.members.length;
      const v = modPow(w, this.x, this.Q);
      this.onLog("dh", "Раунд " + ev.round + ": отримано " + w.toString(16).slice(0, 24) + "… від " + ev.from +
        ", піднесено до X → " + v.toString(16).slice(0, 24) + "…");
      if (ev.round + 1 < n - 1) {
        await this._post("/api/dh", { epoch: ev.epoch, round: ev.round + 1, value: v.toString(16) });
        return;
      }
      // кінець кільця: v = A^(x1*x2*...*xn) mod Q - спільний секрет групи
      const keyBytes = await sha256(bigToBytes(v, 256));
      const key = await subtle.importKey("raw", keyBytes, { name: "AES-GCM" }, false, ["encrypt", "decrypt"]);
      this.keys.set(ev.epoch, key);
      for (const e of Array.from(this.keys.keys())) if (e < ev.epoch - 4) this.keys.delete(e);
      this.ready = true;
      const fp = toHex((await sha256(keyBytes)).slice(0, 8)).replace(/(.{4})/g, "$1 ").trim();
      this.fingerprint = fp;
      this.onLog("key", "Спільний ключ групи готовий. Відбиток: " + fp);
      this.onState("ready", { epoch: ev.epoch, fingerprint: fp });
      const queued = this.pending.splice(0);
      for (const q of queued) await this._onChat(q);
    }

    async _onChat(ev) {
      const key = this.keys.get(ev.epoch);
      if (!key) {
        if (ev.epoch >= this.epoch) this.pending.push(ev);
        else this.onLog("error", "Повідомлення від " + ev.from + " зашифроване ключем епохи, якої ви не знаєте");
        return;
      }
      try {
        const aad = enc.encode(ev.epoch + "|" + ev.from);
        const plain = await subtle.decrypt({ name: "AES-GCM", iv: fromB64(ev.iv), additionalData: aad }, key, fromB64(ev.ct));
        this.onMessage({ from: ev.from, text: dec.decode(plain), epoch: ev.epoch, ct: ev.ct, own: false });
      } catch (e) {
        this.onLog("error", "Не вдалося розшифрувати повідомлення від " + ev.from);
      }
    }

    // Шифрування AES-256-GCM спільним ключем групи і відправка
    async send(text) {
      const key = this.keys.get(this.epoch);
      if (!this.ready || !key) throw new Error("Спільний ключ ще не готовий");
      const iv = new Uint8Array(12);
      root.crypto.getRandomValues(iv);
      const aad = enc.encode(this.epoch + "|" + this.name);
      const ct = await subtle.encrypt({ name: "AES-GCM", iv, additionalData: aad }, key, enc.encode(text));
      const ctB64 = toB64(ct);
      await this._post("/api/chat", { epoch: this.epoch, iv: toB64(iv), ct: ctB64 });
      this.onMessage({ from: this.name, text, epoch: this.epoch, ct: ctB64, own: true });
    }
  }

  const api = { ChatClient, modPow, randomSecret, toHex, toB64 };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ChatCore = api;
})(typeof globalThis !== "undefined" ? globalThis : window);
