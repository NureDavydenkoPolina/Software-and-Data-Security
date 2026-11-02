(function (root) {
  "use strict";
  const subtle = root.crypto.subtle;
  const enc = new TextEncoder();
  const dec = new TextDecoder();

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
  function hex(buf) {
    return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, "0")).join("");
  }

  async function generateKeyPair(bits) {
    return subtle.generateKey(
      { name: "RSA-OAEP", modulusLength: bits, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" },
      true, ["encrypt", "decrypt"]);
  }
  async function exportPublic(key) {
    return toB64(await subtle.exportKey("spki", key));
  }
  async function importPublic(b64) {
    return subtle.importKey("spki", fromB64(b64), { name: "RSA-OAEP", hash: "SHA-256" }, true, ["encrypt"]);
  }
  async function fingerprint(b64) {
    return hex(await subtle.digest("SHA-256", fromB64(b64))).slice(0, 16);
  }
  async function encryptText(pubKey, text) {
    return toB64(await subtle.encrypt({ name: "RSA-OAEP" }, pubKey, enc.encode(text)));
  }
  async function decryptText(privKey, b64) {
    return dec.decode(await subtle.decrypt({ name: "RSA-OAEP" }, privKey, fromB64(b64)));
  }
  function maxPlain(bits) { return bits / 8 - 66; }
  function randomNonce() {
    const a = new Uint8Array(16);
    root.crypto.getRandomValues(a);
    return hex(a);
  }

  async function readJson(resp, what) {
    const text = await resp.text();
    try { return JSON.parse(text); }
    catch (e) {
      throw new Error("Сервер не відповів на " + what + " у форматі JSON (код " + resp.status + "). " +
        "Запустіть python server.py і відкрийте http://localhost:8000 (не через Live Server чи файл).");
    }
  }

  const keyCache = {};
  async function getKeyPair(bits) {
    if (!keyCache[bits]) keyCache[bits] = generateKeyPair(bits);
    return keyCache[bits];
  }

  async function authenticate(opts) {
    const base = opts.base || "";
    const step = opts.onStep || function () {};
    const bits = opts.bits;

    let t0 = Date.now();
    const pair = await getKeyPair(bits);
    const clientPub = await exportPublic(pair.publicKey);
    step("keys", { bits, fingerprint: await fingerprint(clientPub), ms: Date.now() - t0 });

    const sr = await fetch(base + "/api/pubkey");
    const info = await readJson(sr, "/api/pubkey");
    const serverKey = await importPublic(info.publicKey);
    step("serverKey", { bits: info.keyBits, fingerprint: await fingerprint(info.publicKey), scheme: info.scheme });

    const nonce = randomNonce();
    const plain = JSON.stringify({ a: opts.action, u: opts.username, p: opts.password, n: nonce, t: Date.now() });
    const plainLen = enc.encode(plain).length;
    if (plainLen > maxPlain(info.keyBits)) throw new Error("Логін або пароль занадто довгі");
    const cipher = await encryptText(serverKey, plain);
    step("encrypt", { plainLen, cipher });

    const resp = await fetch(base + "/api/auth", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data: cipher, clientKey: clientPub })
    });
    const body = await readJson(resp, "/api/auth");
    if (!resp.ok) throw new Error(body.error || "Помилка сервера");
    step("response", { cipher: body.data });

    const answer = JSON.parse(await decryptText(pair.privateKey, body.data));
    if (answer.n !== nonce) throw new Error("Відповідь не відповідає запиту (nonce)");
    step("decrypt", { answer });
    return answer;
  }

  const api = { generateKeyPair, exportPublic, importPublic, encryptText, decryptText, authenticate, maxPlain, toB64, fromB64, subtle };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.RsaClient = api;
})(typeof globalThis !== "undefined" ? globalThis : window);
