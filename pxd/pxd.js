/* pxd.js — PXDZ runtime for any modern browser (and the PXD Browser).
 *   const b = await PXDZ.open("site.pxdz", { key: "passphrase if sealed" });
 *   b.manifest; b.list(); await b.bytes(path); await b.text(path); await b.json(path); await b.sql(path)
 * Every part is verified against its SHA-256 before it is handed back.
 * COG books are append-only, so they are cached forever and only grow.
 */
(function (root) {
  "use strict";
  var MAGIC = "PXDZ", MARK = "\u00a7cog:", PUBLIC_CATALOG = "https://pxd2.github.io/cog/books/catalog.json";
  var dec = new TextDecoder(), enc = new TextEncoder();

  function hex(buf) { return Array.prototype.map.call(new Uint8Array(buf), function (b) { return b.toString(16).padStart(2, "0"); }).join(""); }
  async function sha256(u8) { return hex(await crypto.subtle.digest("SHA-256", u8)); }
  async function inflateRaw(u8) {
    var ds = new DecompressionStream("deflate-raw");
    var out = new Response(new Blob([u8]).stream().pipeThrough(ds));
    return new Uint8Array(await out.arrayBuffer());
  }
  async function deriveKey(pass, saltB64, iter) {
    var salt = Uint8Array.from(atob(saltB64), function (c) { return c.charCodeAt(0); });
    var base = await crypto.subtle.importKey("raw", enc.encode(pass), "PBKDF2", false, ["deriveKey"]);
    return crypto.subtle.deriveKey({ name: "PBKDF2", hash: "SHA-256", salt: salt, iterations: iter }, base, { name: "AES-GCM", length: 256 }, false, ["decrypt"]);
  }
  async function unseal(u8, key) {
    try { return new Uint8Array(await crypto.subtle.decrypt({ name: "AES-GCM", iv: u8.slice(0, 12) }, key, u8.slice(12))); }
    catch (e) { throw new Error("Wrong key, or the bundle was altered."); }
  }

  // ---------- COG ----------
  function decodeText(code, look) {
    var res = [], sepNext = false;
    code.split(" ").forEach(function (t) {
      if (t === "|") { res.push("\n\n"); sepNext = false; return; }
      if (t.charAt(0) === "~") { res.push(JSON.parse(t.slice(1))); sepNext = false; return; }
      if (res.length && sepNext) res.push(" ");
      if (t !== "=") { var s = look(t); if (s == null) throw new Error("Unknown COG address " + t); res.push(s); }
      sepNext = true;
    });
    return res.join("");
  }
  function uncog(obj, look) {
    if (Array.isArray(obj)) return obj.map(function (v) { return uncog(v, look); });
    if (obj && typeof obj === "object") { var o = {}; Object.keys(obj).forEach(function (k) { o[k] = uncog(obj[k], look); }); return o; }
    if (typeof obj === "string" && obj.indexOf(MARK) === 0) return decodeText(obj.slice(MARK.length), look);
    return obj;
  }
  function canon(v) {
    if (Array.isArray(v)) return "[" + v.map(canon).join(",") + "]";
    if (v && typeof v === "object") return "{" + Object.keys(v).sort().map(function (k) { return JSON.stringify(k) + ":" + canon(v[k]); }).join(",") + "}";
    return JSON.stringify(v);
  }
  var publicBook = null;
  async function loadPublic() {
    if (publicBook) return publicBook;
    var cache = ("caches" in root) ? await caches.open("pxd-cog-books") : null;
    async function get(url) {
      var hit = cache && await cache.match(url);
      if (hit && !/catalog\.json$/.test(url)) return hit.json();       // packs never change: append-only
      var r = await fetch(url, { cache: "no-store" }); if (cache) cache.put(url, r.clone()); return r.json();
    }
    var cat = await get(PUBLIC_CATALOG), map = {};
    var base = PUBLIC_CATALOG.replace(/books\/catalog\.json$/, "");
    var files = (cat.books || []).map(function (b) { return b.file; }).filter(function (f) { return /core-m-\d+\.json$/.test(f); });
    (await Promise.all(files.map(function (f) { return get(base + f); }))).forEach(function (p) {
      (p.s || []).forEach(function (r) { r[3].forEach(function (s, i) { map[r[0] + "." + (r[2][0] + i)] = s; }); });
    });
    return (publicBook = map);
  }

  /* Try each source in order until one answers (multi-main repositories, gateways). */
  async function fetchAny(urls, as) {
    var list = Array.isArray(urls) ? urls : [urls], last = null;
    for (var i = 0; i < list.length; i++) {
      try { var r = await fetch(list[i], { cache: "no-store" }); if (!r.ok) throw new Error(r.status + " " + list[i]); return as === "json" ? await r.json() : await r.arrayBuffer(); }
      catch (e) { last = e; }
    }
    throw last || new Error("No source answered.");
  }

  /* ---------- transfer: fetch only what is shown, keep every verified part ---------- */
  var stats = { network: 0, cache: 0, lit: 0, requests: 0 };
  /* Lit: ask nodes on your own network (lit.pxd, base1, a Pi, the shop's box) before the origin,
     and give them what had to come from the origin, so the next device nearby gets it locally. */
  var litNodes = [], litDead = {};
  function lit(nodes) { litNodes = (nodes || []).map(function (n) { return String(n).replace(/\/+$/, ""); }); litDead = {}; return litNodes; }
  async function litGet(h) {
    for (var i = 0; i < litNodes.length; i++) {
      var n = litNodes[i]; if (litDead[n]) continue;
      try {
        var ctl = new AbortController(), t = setTimeout(function () { ctl.abort(); }, 1500);
        var r = await fetch(n + "/lit/s/" + h, { signal: ctl.signal }); clearTimeout(t);
        if (r.status === 404) continue;
        if (!r.ok) throw new Error(r.status);
        var d = new Uint8Array(await r.arrayBuffer());
        if (await sha256(d) === h) { stats.lit += d.length; return d; }  // a neighbor can carry data, never fake it
      } catch (e) { litDead[n] = true; }
    }
    return null;
  }
  function litGive(h, d) {
    var n = litNodes.find(function (x) { return !litDead[x]; });
    if (n) fetch(n + "/lit/s/" + h, { method: "PUT", body: d }).catch(function () {});
  }
  var whole = {};  // url -> bytes, for servers that ignore Range
  var partStore = null;
  async function parts() {
    if (partStore !== null) return partStore;
    try { partStore = ("caches" in root) ? await caches.open("pxd-parts") : false; } catch (e) { partStore = false; }
    return partStore;
  }
  async function rangeGet(urls, a, b) {  // bytes a..b inclusive, from the first source that answers
    var last = null;
    for (var i = 0; i < urls.length; i++) {
      var u = urls[i];
      if (whole[u]) return whole[u].slice(a, b + 1);
      try {
        stats.requests++;
        var r = await fetch(u, { headers: { Range: "bytes=" + a + "-" + b }, cache: "no-store" });
        if (r.status === 206) { var part = new Uint8Array(await r.arrayBuffer()); stats.network += part.length; return part; }
        if (!r.ok) throw new Error(r.status + " " + u);
        var all = new Uint8Array(await r.arrayBuffer()); stats.network += all.length; whole[u] = all;
        return all.slice(a, b + 1);
      } catch (e) { last = e; }
    }
    throw last || new Error("No source answered.");
  }
  function concat(x, y) { var o = new Uint8Array(x.length + y.length); o.set(x); o.set(y, x.length); return o; }

  /* open: whole bundle (ArrayBuffer, URL or URL list). openLazy: header first, each part on demand. */
  async function open(src, opts) {
    var buf = src instanceof ArrayBuffer ? src : await fetchAny(src);
    var u8 = new Uint8Array(buf);
    return build(u8, function (a, len) { return Promise.resolve(u8.slice(a, a + len)); }, opts || {}, false);
  }
  async function openLazy(src, opts) {
    var urls = Array.isArray(src) ? src : [src];
    var head = await rangeGet(urls, 0, 16383);  // header + manifest; small sites arrive whole
    if (dec.decode(head.slice(0, 4)) !== MAGIC) throw new Error("Not a PXDZ file.");
    var need = 9 + new DataView(head.buffer, head.byteOffset).getUint32(5, true);
    if (head.length < need) head = concat(head, await rangeGet(urls, head.length, need - 1));
    return build(head, function (a, len) {
      return a + len <= head.length ? Promise.resolve(head.slice(a, a + len)) : rangeGet(urls, a, a + len - 1);
    }, opts || {}, true);
  }

  async function build(u8, slice, opts, lazy) {
    if (dec.decode(u8.slice(0, 4)) !== MAGIC) throw new Error("Not a PXDZ file.");
    var mlen = new DataView(u8.buffer, u8.byteOffset).getUint32(5, true);
    var header = u8.slice(0, 9 + mlen);
    var manifest = JSON.parse(dec.decode(u8.slice(9, 9 + mlen))), base = 9 + mlen, key = null;
    if (manifest.encryption) {
      if (!opts.key) { var err = new Error("This bundle is sealed. A key is required."); err.sealed = true; throw err; }
      key = await deriveKey(opts.key, manifest.encryption.salt, manifest.encryption.iter);
    }
    async function undo(data, codec) {
      for (var i = codec.length - 1; i >= 0; i--) {
        if (codec[i] === "aes-gcm") data = await unseal(data, key);
        else if (codec[i] === "deflate") data = await inflateRaw(data);
      }
      return data;
    }
    var hubInfo = manifest.books.find(function (b) { return b.kind === "hub"; }), hub = {};
    if (hubInfo) {
      var rows = JSON.parse(dec.decode(await undo(await slice(base + hubInfo.offset, hubInfo.length), hubInfo.codec))).rows;
      if (hubInfo.sha256 && await sha256(enc.encode(JSON.stringify(rows))) !== hubInfo.sha256) throw new Error("Integrity check failed: hub book");
      rows.forEach(function (r) { r[2].forEach(function (s, i) { hub["h" + r[0] + "." + (r[1][0] + i)] = s; }); });
    }
    var usesPublic = manifest.books.some(function (b) { return b.kind === "public"; }), pub = null;
    async function look() {
      if (usesPublic && !pub) { try { pub = await loadPublic(); } catch (e) { pub = {}; } }
      return function (a) { return a.charAt(0) === "h" ? hub[a] : (pub || {})[a]; };
    }
    var mem = {}, shareable = !manifest.encryption;  // sealed parts never leave memory
    var bundle = {
      manifest: manifest, header: header, lazy: lazy,
      list: function () { return manifest.parts.slice(); },
      bytes: async function (path) {
        if (mem[path]) return mem[path];
        var p = manifest.parts.find(function (x) { return x.path === path; });
        if (!p) throw new Error("No part " + path);
        var store = shareable && p.sha256 ? await parts() : false, ckey = store && "https://parts.pxd/" + p.sha256;
        if (store) {
          var hit = await store.match(ckey);
          if (hit) { var c = new Uint8Array(await hit.arrayBuffer()); if (await sha256(c) === p.sha256) { stats.cache += c.length; return (mem[path] = c); } }
        }
        var viaLit = shareable && p.sha256 && p.codec.indexOf("cog-json") < 0 && litNodes.length > 0;
        if (viaLit) {
          var near = await litGet(p.sha256);
          if (near) { if (store) { try { await store.put(ckey, new Response(near)); } catch (e) {} } return (mem[path] = near); }
        }
        var data = await undo(await slice(base + p.offset, p.length), p.codec);
        if (p.codec.indexOf("cog-json") > -1) {
          var obj = uncog(JSON.parse(dec.decode(data)), await look());
          if (await sha256(enc.encode(canon(obj))) !== p.sha256_json) throw new Error("Integrity check failed: " + path);
          data = enc.encode(JSON.stringify(obj, null, 2));
        } else if (await sha256(data) !== p.sha256) throw new Error("Integrity check failed: " + path);
        if (store && p.codec.indexOf("cog-json") < 0) { try { await store.put(ckey, new Response(data)); } catch (e) {} }
        if (viaLit) litGive(p.sha256, data);
        return (mem[path] = data);
      },
      text: async function (path) { return dec.decode(await bundle.bytes(path)); },
      json: async function (path) { return JSON.parse(await bundle.text(path)); },
      url: async function (path, type) { return URL.createObjectURL(new Blob([await bundle.bytes(path)], { type: type || "application/octet-stream" })); },
      sql: async function (path, sqlJsOpts) {
        if (!root.initSqlJs) throw new Error("Load sql-wasm.js first.");
        var SQL = await root.initSqlJs(sqlJsOpts || {}); return new SQL.Database(await bundle.bytes(path));
      }
    };
    return bundle;
  }
  // ---------- merchant authentication: authority -> certificate -> bundle (ECDSA P-256 / SHA-256) ----------
  function canonJSON(v) { return canon(v); }
  function b64u(s) { s = s.replace(/-/g, "+").replace(/_/g, "/"); while (s.length % 4) s += "="; return Uint8Array.from(atob(s), function (c) { return c.charCodeAt(0); }); }
  async function ecKey(jwk) { return crypto.subtle.importKey("jwk", { kty: "EC", crv: "P-256", x: jwk.x, y: jwk.y, ext: true }, { name: "ECDSA", namedCurve: "P-256" }, false, ["verify"]); }
  async function ecVerify(jwk, obj, sig) { return crypto.subtle.verify({ name: "ECDSA", hash: "SHA-256" }, await ecKey(jwk), b64u(sig), enc.encode(canonJSON(obj))); }
  function hostOf(u) { try { return new URL(u).hostname; } catch (e) { return ""; } }
  /* verify(bundleBytes, sigObject, authorityRecord, payLinks?) -> {ok, merchant, checks:[{check, ok, detail}]} */
  async function verify(bytes, sig, authority, payLinks) {
    var checks = [], ok = true, cert = sig && sig.cert && sig.cert.cert;
    function chk(name, pass, detail) { checks.push({ check: name, ok: !!pass, detail: detail || "" }); ok = ok && !!pass; }
    if (!cert) { chk("signature present", false); return { ok: false, checks: checks }; }
    chk("certificate issued by this authority", cert.issuer === authority.kid, cert.issuer);
    chk("authority signature on certificate", await ecVerify(authority.key, cert, sig.cert.sig));
    var today = new Date().toISOString().slice(0, 10);
    chk("certificate in date", cert.issued <= today && today <= cert.expires, cert.issued + " to " + cert.expires);
    if (bytes && bytes.header) {  // a lazily opened bundle: the signed manifest pins every part's SHA-256
      chk("manifest unchanged since signing", !!sig.sig.manifest_sha256 && (await sha256(bytes.header)) === sig.sig.manifest_sha256,
          sig.sig.manifest_sha256 ? "each part checked against it as it arrives" : "signature has no manifest hash: re-sign, or open the whole bundle");
    } else chk("bundle unchanged since signing", (await sha256(bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes))) === sig.sig.sha256);
    chk("merchant signature on bundle", await ecVerify(cert.key, sig.sig, sig.signature));
    if (payLinks) {
      var bad = payLinks.filter(function (u) { return cert.pay_hosts.indexOf(hostOf(u)) < 0; });
      chk("pay links within certificate", !bad.length, bad.join(", ") || payLinks.length + " link(s) allowed");
    }
    return { ok: ok, merchant: { id: cert.merchant, name: cert.name, expires: cert.expires, pay_hosts: cert.pay_hosts }, checks: checks };
  }
  function collectPayLinks(obj) {
    var out = [];
    (function walk(o, pay) {
      if (Array.isArray(o)) o.forEach(function (v) { walk(v, pay); });
      else if (o && typeof o === "object") Object.keys(o).forEach(function (k) { walk(o[k], pay || k === "pay"); });
      else if (typeof o === "string" && pay && /^https?:/.test(o)) out.push(o);
    })(obj, false);
    return out;
  }

  root.PXDZ = { open: open, openLazy: openLazy, lit: lit, stats: stats, verify: verify, payLinks: collectPayLinks, fetchAny: fetchAny, version: 1 };
})(typeof window !== "undefined" ? window : self);
