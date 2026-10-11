/* pxd.js — PXDZ runtime for any modern browser (and the PXD Browser).
 *   const b = await PXDZ.open("site.pxdz", { key: "passphrase if sealed" });
 *   b.manifest; b.list(); await b.bytes(path); await b.text(path); await b.json(path); await b.sql(path)
 * Every part is verified against its SHA-256 before it is handed back.
 * COG books are append-only, so they are cached forever and only grow.
 */
(function (root) {
  "use strict";
  var MAGIC = "PXDZ", MARK = "§cog:", PUBLIC_CATALOG = "https://pxd2.github.io/cog/books/catalog.json";
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

  async function open(src, opts) {
    opts = opts || {};
    var buf = src instanceof ArrayBuffer ? src : await (await fetch(src)).arrayBuffer();
    var u8 = new Uint8Array(buf);
    if (dec.decode(u8.slice(0, 4)) !== MAGIC) throw new Error("Not a PXDZ file.");
    var dv = new DataView(buf), mlen = dv.getUint32(5, true);
    var manifest = JSON.parse(dec.decode(u8.slice(9, 9 + mlen))), base = 9 + mlen, key = null;
    if (manifest.encryption) {
      if (!opts.key) { var err = new Error("This bundle is sealed. A key is required."); err.sealed = true; throw err; }
      key = await deriveKey(opts.key, manifest.encryption.salt, manifest.encryption.iter);
    }
    async function undo(slice, codec) {
      var data = slice;
      for (var i = codec.length - 1; i >= 0; i--) {
        if (codec[i] === "aes-gcm") data = await unseal(data, key);
        else if (codec[i] === "deflate") data = await inflateRaw(data);
      }
      return data;
    }
    var hubInfo = manifest.books.find(function (b) { return b.kind === "hub"; }), hub = {};
    if (hubInfo) {
      var rows = JSON.parse(dec.decode(await undo(u8.slice(base + hubInfo.offset, base + hubInfo.offset + hubInfo.length), hubInfo.codec))).rows;
      rows.forEach(function (r) { r[2].forEach(function (s, i) { hub["h" + r[0] + "." + (r[1][0] + i)] = s; }); });
    }
    var usesPublic = manifest.books.some(function (b) { return b.kind === "public"; }), pub = null;
    async function look() {
      if (usesPublic && !pub) { try { pub = await loadPublic(); } catch (e) { pub = {}; } }
      return function (a) { return a.charAt(0) === "h" ? hub[a] : (pub || {})[a]; };
    }
    var cache = {};
    var bundle = {
      manifest: manifest,
      list: function () { return manifest.parts.slice(); },
      bytes: async function (path) {
        if (cache[path]) return cache[path];
        var p = manifest.parts.find(function (x) { return x.path === path; });
        if (!p) throw new Error("No part " + path);
        var data = await undo(u8.slice(base + p.offset, base + p.offset + p.length), p.codec);
        if (p.codec.indexOf("cog-json") > -1) {
          var obj = uncog(JSON.parse(dec.decode(data)), await look());
          if (await sha256(enc.encode(canon(obj))) !== p.sha256_json) throw new Error("Integrity check failed: " + path);
          data = enc.encode(JSON.stringify(obj, null, 2));
        } else if (await sha256(data) !== p.sha256) throw new Error("Integrity check failed: " + path);
        return (cache[path] = data);
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
  root.PXDZ = { open: open, version: 1 };
})(typeof window !== "undefined" ? window : self);
