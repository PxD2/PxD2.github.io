// PXD2 LINK WAN - tablet / phone side. PXD2's own wide-area link to BASE1: sealed envelopes (AES-256-GCM) through the
// private repo PxD2/astrocoms (branch "mesh"). Works on any network; nothing on GitHub is readable without the mesh key.
"use strict";
window.addEventListener("error", e => showErr(e.message + (e.filename ? " @ " + e.filename.split("/").pop() + ":" + e.lineno : "")));
window.addEventListener("unhandledrejection", e => showErr("async: " + ((e.reason && e.reason.message) || e.reason)));
function showErr(t) {                                  // faults show on screen instead of silently freezing the app
  let b = document.getElementById("errbar");
  if (!b) { b = document.createElement("div"); b.id = "errbar"; b.style.cssText = "position:fixed;left:8px;right:8px;top:8px;z-index:70;background:#7a1d1d;color:#fff;padding:8px 12px;border-radius:8px;font:12px/1.4 monospace;white-space:pre-wrap"; b.onclick = () => b.remove(); (document.body || document.documentElement).appendChild(b); }
  b.textContent = "PXD2 error (tap to hide) - " + String(t).slice(0, 300);
}
const $ = s => document.querySelector(s);
const REPO = "PxD2/astrocoms", BRANCH = "mesh", HUB = "BASE1", API = "https://api.github.com";
const AAD = new TextEncoder().encode("pxd2-wan-v1");
const CHUNK = 8 * 1024 * 1024;
let S = { token: "", key: null, dev: "" };           // session, restored from IndexedDB
let online = false, draining = false, again = false;

function toast(t) { const e = $("#toast"); e.textContent = t; e.classList.add("show"); clearTimeout(toast.t); toast.t = setTimeout(() => e.classList.remove("show"), 3200); }
const fmt = n => n > 1e9 ? (n / 1e9).toFixed(2) + " GB" : n > 1e6 ? (n / 1e6).toFixed(1) + " MB" : n > 1e3 ? (n / 1e3).toFixed(0) + " KB" : n + " B";
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const b64 = buf => { let s = "", a = new Uint8Array(buf); for (let i = 0; i < a.length; i += 0x8000) s += String.fromCharCode.apply(null, a.subarray(i, i + 0x8000)); return btoa(s); };
const unb64 = s => Uint8Array.from(atob(s.replace(/\s/g, "")), c => c.charCodeAt(0));
const stamp = () => String(Date.now()).padStart(13, "0") + "_" + [...crypto.getRandomValues(new Uint8Array(4))].map(b => b.toString(16).padStart(2, "0")).join("");
const uid = () => [...crypto.getRandomValues(new Uint8Array(12))].map(b => b.toString(16).padStart(2, "0")).join("");

// ------------------------------------------------------------------ storage (IndexedDB: session + outgoing queue)
let BC = null; try { BC = new BroadcastChannel("pxd2"); BC.onmessage = e => { if (e.data === "close-old" && window.__db) { window.__db.close(); location.reload(); } }; } catch (e) { }
const DB = new Promise((ok, bad) => {
  const r = indexedDB.open("pxd2_wan", 3);
  r.onupgradeneeded = () => {
    const d = r.result, have = n => d.objectStoreNames.contains(n);
    if (!have("q")) d.createObjectStore("q", { keyPath: "id" });
    if (!have("kv")) d.createObjectStore("kv");
    if (!have("parts")) d.createObjectStore("parts");                 // pieces of files BASE1 is sending
    if (!have("got")) d.createObjectStore("got", { keyPath: "id" });  // files received from BASE1
    if (!have("kit")) d.createObjectStore("kit");                      // unpacked client kits for the PITCH desktop
  };
  r.onsuccess = () => {
    const db = r.result;
    db.onversionchange = () => { db.close(); location.reload(); };
    window.__db = db; const bl = document.getElementById("blocked"); if (bl) bl.remove();   // a newer PXD2 window is updating: step aside
    try { BC.postMessage("ready"); } catch (e) { }
    ok(db);
  };
  r.onerror = () => bad(r.error);
  r.onblocked = () => {                                              // an older PXD2 window/tab still holds storage open
    try { BC.postMessage("close-old"); } catch (e) { }
    const b = document.createElement("div");
    b.id = "blocked";
    b.style.cssText = "position:fixed;inset:auto 12px 12px 12px;z-index:60;background:#7a1d1d;color:#fff;padding:14px;border-radius:10px;font-weight:600";
    b.textContent = "PXD2 is updating - close the other PXD2 window (the sticky pop-out or another tab), then this screen loads by itself.";
    (document.body || document.documentElement).appendChild(b);
  };
});
async function tx(store, mode, fn) { const db = await DB; return new Promise((ok, bad) => { const t = db.transaction(store, mode); const r = fn(t.objectStore(store)); t.oncomplete = () => ok(r && r.result); t.onerror = () => bad(t.error); }); }
const kvGet = k => tx("kv", "readonly", s => s.get(k));
const kvSet = (k, v) => tx("kv", "readwrite", s => s.put(v, k));
const qAll = async () => ((await tx("q", "readonly", s => s.getAll())) || []).sort((a, b) => a.t - b.t);
const qPut = x => tx("q", "readwrite", s => s.put(x));
const qDel = id => tx("q", "readwrite", s => s.delete(id));
const gotAll = async () => ((await tx("got", "readonly", s => s.getAll())) || []).sort((a, b) => b.t - a.t);

// ------------------------------------------------------------------ GitHub
async function gh(method, path, body, raw) {
  const h = { Authorization: "Bearer " + S.token, Accept: raw ? "application/vnd.github.raw" : "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28" };
  if (body) h["Content-Type"] = "application/json";
  const r = await fetch(API + path, { method, headers: h, body: body ? JSON.stringify(body) : undefined, cache: "no-store" });
  if (r.status === 404) return null;
  if (!r.ok) { let m = r.statusText; try { m = (await r.json()).message || m; } catch (e) { } throw Object.assign(new Error(m), { status: r.status }); }
  return raw ? new Uint8Array(await r.arrayBuffer()) : r.status === 204 ? {} : r.json();
}
// exact bytes: the "raw" media type re-encodes small binary files, so read base64 (contents API, or the blob API past 1 MB)
const ghGet = async p => {
  const r = await gh("GET", `/repos/${REPO}/contents/${p}?ref=${BRANCH}`);
  if (!r) return null;
  if (r.encoding === "base64" && r.content) return unb64(r.content);
  const b = await gh("GET", `/repos/${REPO}/git/blobs/${r.sha}`);
  return b ? unb64(b.content) : null;
};
const ghLs = async p => (await gh("GET", `/repos/${REPO}/contents/${p}?ref=${BRANCH}`)) || [];
const ghPut = (p, bytes, msg) => gh("PUT", `/repos/${REPO}/contents/${p}`, { message: msg, content: b64(bytes), branch: BRANCH });
const ghDel = (p, sha) => gh("DELETE", `/repos/${REPO}/contents/${p}`, { message: "read", sha, branch: BRANCH });

// ------------------------------------------------------------------ sealing (AES-256-GCM, PBKDF2-SHA256 600k)
async function deriveKey(pass, salt) {
  const base = await crypto.subtle.importKey("raw", new TextEncoder().encode(pass), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey({ name: "PBKDF2", hash: "SHA-256", salt, iterations: 600000 }, base, { name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"]);
}
async function seal(header, body = new Uint8Array()) {
  const head = new TextEncoder().encode(JSON.stringify(header) + "\n");
  const plain = new Uint8Array(head.length + body.byteLength); plain.set(head); plain.set(new Uint8Array(body), head.length);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv, additionalData: AAD }, S.key, plain));
  const out = new Uint8Array(12 + ct.length); out.set(iv); out.set(ct, 12);
  return new TextEncoder().encode(ARMOR + b64(out));   // ASCII on GitHub: it re-encodes short binary files
}
const ARMOR = "PXD2A1:";
async function unseal(blob) {
  const tag = new TextDecoder().decode(blob.slice(0, ARMOR.length));
  if (tag === ARMOR) blob = unb64(new TextDecoder().decode(blob.slice(ARMOR.length)));
  const plain = new Uint8Array(await crypto.subtle.decrypt({ name: "AES-GCM", iv: blob.slice(0, 12), additionalData: AAD }, S.key, blob.slice(12)));
  const nl = plain.indexOf(10);
  return [JSON.parse(new TextDecoder().decode(plain.slice(0, nl))), plain.slice(nl + 1)];
}
const send = async (header, body, to = HUB) => ghPut(`to/${to}/${stamp()}.env`, await seal(Object.assign({ from: S.dev }, header), body), `${S.dev} -> ${to}`);

// ------------------------------------------------------------------ queue
async function addFiles(list, dest) {
  const note = dest ? "" : $("#fNote").value.trim();
  for (const f of list) await qPut({ id: uid(), t: Date.now(), type: "file", name: f.name, size: f.size, blob: f, note, sent: 0, dest: dest || null });
  $("#fNote").value = ""; toast(`${list.length} file(s) queued`); renderQueue(); drain();
}
async function sha256(blob) { return blob.size <= 512 * 1024 * 1024 ? [...new Uint8Array(await crypto.subtle.digest("SHA-256", await blob.arrayBuffer()))].map(b => b.toString(16).padStart(2, "0")).join("") : ""; }
async function sendFile(it) {
  if (it.sha === undefined) { it.sha = await sha256(it.blob); await qPut(it); }
  const total = Math.max(1, Math.ceil(it.size / CHUNK));
  for (let i = Math.floor((it.sent || 0) / CHUNK); i < total; i++) {
    const piece = new Uint8Array(await it.blob.slice(i * CHUNK, Math.min((i + 1) * CHUNK, it.size)).arrayBuffer());
    await send({ type: "file", id: it.id, name: it.name, idx: i, total, sha256: it.sha, note: it.note || "", dest: it.dest || null }, piece);
    it.sent = Math.min((i + 1) * CHUNK, it.size); await qPut(it); renderQueue();
  }
}
async function drain() {
  if (!S.key) return; if (draining) { again = true; return; } draining = true; again = false;
  try {
    for (const it of await qAll()) {
      if (!navigator.onLine) break;
      try {
        if (it.type === "chat" && it.to === "AI") { await send({ type: "ask", id: it.id }, new TextEncoder().encode(it.text)); await chatMark(it.id, "sent"); }
        else if (it.type === "chat") {
          for (const d of chatTargets(it.to).filter(d => !(it.done || []).includes(d))) {
            await send({ type: "chat", id: it.id, to: it.to }, new TextEncoder().encode(it.text), d);
            it.done = (it.done || []).concat(d); await qPut(it);
          }
          await chatMark(it.id, "sent");
        }
        else if (it.type === "fetch") await send({ type: "fetch", id: it.id, root: it.root, path: it.path });
        else if (it.type === "note") await send({ type: "note", id: it.id }, new TextEncoder().encode(it.text));
        else if (it.type === "task") await send({ type: "task", id: it.id, node: it.node, kind: it.kind, name: it.name, params: it.params });
        else await sendFile(it);
        await qDel(it.id);
      } catch (e) { it.err = e.message; await qPut(it); setNet(false, e.message); break; }
    }
  } finally { draining = false; renderQueue(); if (again && navigator.onLine) setTimeout(drain, 200); }
}
async function renderQueue() {
  const all = await qAll();
  $("#qCount").textContent = all.length ? `(${all.length})` : "";
  $("#qList").innerHTML = all.length ? all.map(it => it.type !== "file"
    ? `<li><span class="n">${it.type === "task" ? "⚙ " + esc(it.kind) : it.type === "fetch" ? "⇩ ask BASE1 for " + esc(it.path || it.root) : "✎ " + esc((it.text || "").slice(0, 80))}</span><span class="m">${navigator.onLine ? "sending" : "waiting for signal"}</span></li>`
    : `<li style="display:block"><div class="row"><span class="n">${esc(it.name)}</span><span class="m">${fmt(it.sent || 0)} / ${fmt(it.size)}</span>
       <button data-del="${it.id}" style="min-height:32px;padding:4px 10px">✕</button></div><div class="bar"><i style="width:${(100 * (it.sent || 0) / Math.max(1, it.size)).toFixed(1)}%"></i></div></li>`).join("")
    : `<li class="dim">nothing waiting</li>`;
  document.querySelectorAll("[data-del]").forEach(b => b.onclick = async () => { await qDel(b.dataset.del); renderQueue(); });
}

// ------------------------------------------------------------------ hub status + replies
let lastStatus = null;
function setNet(ok, why) {
  online = ok; const n = $("#net");
  n.textContent = !navigator.onLine ? "● NO SIGNAL" : ok ? "● PXD2 LINK UP" : "● LINK ERROR";
  n.className = ok ? "ok" : "warn"; if (why) n.title = why;
}
async function loadStatus() {
  try {
    const blob = await ghGet(`status/${HUB}.env`);
    if (!blob) { $("#hubState").textContent = "BASE1 hub has not reported yet - is Run_PXD2_WAN.bat running?"; setNet(true); return; }
    const [, body] = await unseal(blob); const st = JSON.parse(new TextDecoder().decode(body)); lastStatus = st;
    const age = (Date.now() - Date.parse(st.t)) / 1000;
    $("#hubState").innerHTML = age < 150 ? `<span class="ok">● BASE1 hub online</span> · reported ${Math.round(age)} s ago` : `<span class="warn">● BASE1 hub quiet</span> · last report ${esc(st.t.replace("T", " "))}`;
    $("#fleet").innerHTML = (st.fleet || []).map(n => `<div class="card"><h3>${esc(n.name)}</h3><div class="big ${n.online ? "ok" : "bad"}">${n.online ? (n.running.length ? "BUSY" : "IDLE") : "OFFLINE"}</div>
      <div class="dim">${esc(n.gpu || "")} ${n.util ?? ""}${n.util != null ? "%" : ""} ${n.temp != null ? "· " + n.temp + "°C" : ""}<br>${n.running.map(esc).join("<br>") || "no job running"} · queued ${n.queued}</div></div>`).join("") || `<div class="card dim">${esc(st.fleet_error || "no fleet data")}</div>`;
    $("#act").innerHTML = (st.activity || []).slice().reverse().map(a => `<li><span class="n">${esc(a.text)}</span><span class="m">${esc(a.t.slice(11, 16))}</span></li>`).join("") || `<li class="dim">quiet</li>`;
    $("#inList").innerHTML = (st.inbox || []).map(f => `<li><span class="n">${esc(f.name)}</span><span class="m">${esc(f.folder)} · ${fmt(f.size)}</span></li>`).join("") || `<li class="dim">empty</li>`;
    $("#tNode").innerHTML = `<option value="auto">auto (idlest)</option>` + (st.fleet || []).filter(n => n.online).map(n => `<option>${esc(n.name)}</option>`).join("");
    setNet(true); fillTo(); if (!pushDone) enablePush(false);
  } catch (e) { setNet(false, e.message); if (e.name === "OperationError") $("#hubState").textContent = "Mesh key does not match BASE1's - sign out and sign in with the right key."; }
}
async function receivePiece(h, body) {
  await tx("parts", "readwrite", st => st.put(new Blob([body]), `${h.id}_${String(h.idx).padStart(5, "0")}`));
  const keys = await tx("parts", "readonly", st => st.getAllKeys(IDBKeyRange.bound(h.id + "_", h.id + "_~")));
  if ((keys || []).length < h.total) { toast(`receiving ${h.name} ${keys.length}/${h.total}`); return; }
  const pieces = await tx("parts", "readonly", st => st.getAll(IDBKeyRange.bound(h.id + "_", h.id + "_~")));
  const blob = new Blob(pieces, { type: mime(h.name) });
  await tx("got", "readwrite", st => st.put({ id: h.id, t: Date.now(), name: h.name, size: blob.size, blob, isNew: true }));
  await tx("parts", "readwrite", st => st.delete(IDBKeyRange.bound(h.id + "_", h.id + "_~")));
  toast(`${h.name} arrived from BASE1`);
  if (/client-kit/i.test(h.name) && /\.zip$/i.test(h.name) && window.importKits) importKits(blob, h.name);
}
const MIME = { jpg: "image/jpeg", jpeg: "image/jpeg", png: "image/png", gif: "image/gif", webp: "image/webp", pdf: "application/pdf", mp4: "video/mp4", webm: "video/webm", mp3: "audio/mpeg", txt: "text/plain", html: "text/html", zip: "application/zip", docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" };
const mime = n => MIME[(n.split(".").pop() || "").toLowerCase()] || "application/octet-stream";
async function loadReplies() {
  try {
    const list = (await ghLs(`to/${S.dev}`)).filter(x => x.name.endsWith(".env")).sort((a, b) => a.name < b.name ? -1 : 1);
    const keep = (await kvGet("replies")) || [];
    for (const it of list) {
      try {
        const [h, body] = await unseal(await ghGet(it.path));
        if (h.type === "file") await receivePiece(h, body);
        else if (h.type === "chat" || (h.type === "note" && h.from)) { await chatAdd({ id: h.id || uid(), t: Date.now(), from: h.from || HUB, to: h.to || S.dev, text: new TextDecoder().decode(body) }); }
        else {
          if (h.type === "note") h.text = new TextDecoder().decode(body), h.isNote = true;
          keep.unshift({ t: Date.now(), h });
          if (h.type === "ack" || h.isNote) toast(h.isNote ? "message from BASE1" : h.text);
        }
      } catch (e) { }
      await ghDel(it.path, it.sha);
    }
    await kvSet("replies", keep.slice(0, 80));
    await renderFromBase(keep);
  } catch (e) { }
}
let urls = [];
async function renderFromBase(keep) {
  keep = keep || (await kvGet("replies")) || [];
  const got = await gotAll();
  const fresh = got.filter(g => g.isNew).length + keep.filter(r => r.h.isNote && !r.seen).length;
  $("#fbCount").textContent = fresh ? `(${fresh})` : "";
  urls.forEach(u => URL.revokeObjectURL(u)); urls = [];
  $("#gotList").innerHTML = got.map(g => {
    const u = URL.createObjectURL(g.blob); urls.push(u);
    const img = /^image\//.test(g.blob.type) ? `<img src="${u}" alt="" style="width:56px;height:56px;object-fit:cover;border-radius:6px">` : "";
    return `<li>${img}<span class="n">${g.isNew ? '<b class="ok">NEW</b> ' : ""}${esc(g.name)}</span><span class="m">${fmt(g.size)}</span>
      <a class="btn" href="${u}" target="_blank" rel="noopener" style="min-height:36px;padding:6px 10px">OPEN</a>
      <a class="btn" href="${u}" download="${esc(g.name)}" style="min-height:36px;padding:6px 10px">SAVE</a>
      <button data-rm="${g.id}" style="min-height:36px;padding:6px 10px">✕</button></li>`;
  }).join("") || `<li class="dim">nothing yet - on BASE1 drop files into Desktop\\PXD2 LINK Send\\${esc(S.dev)} (or ALL)</li>`;
  document.querySelectorAll("[data-rm]").forEach(b => b.onclick = async () => { await tx("got", "readwrite", st => st.delete(b.dataset.rm)); renderFromBase(); });
  $("#outList").innerHTML = keep.slice(0, 80).map(r => `<li style="${r.h.isNote ? "display:block" : ""}">${r.h.isNote
      ? `<div class="dim" style="font-size:12px">BASE1 · ${new Date(r.t).toLocaleString()}</div><div style="white-space:pre-wrap">${esc(r.h.text)}</div>`
      : `<span class="n">${esc(r.h.text || (r.h.type === "task_queued" ? "task queued on " + r.h.node : r.h.type === "pong" ? "BASE1 answered" : r.h.type))}</span><span class="m">${new Date(r.t).toLocaleTimeString()}</span>`}</li>`).join("") || `<li class="dim">nothing yet</li>`;
}
async function markSeen() {
  const got = await gotAll();
  for (const g of got.filter(x => x.isNew)) { g.isNew = false; await tx("got", "readwrite", st => st.put(g)); }
  const keep = (await kvGet("replies")) || []; keep.forEach(r => r.seen = true); await kvSet("replies", keep);
  $("#fbCount").textContent = "";
}
// ------------------------------------------------------------------ sticky texting
const BASES = ["BASE1", "BASE2"];
const chatTargets = to => to === "ALL" ? BASES.concat((lastStatus && lastStatus.devices) || []).filter(d => d && d !== S.dev) : [to];
const chatGet = async () => (await kvGet("chat")) || [];
async function chatAdd(m) {
  const c = await chatGet(); if (c.some(x => x.id === m.id && x.from === m.from)) return;
  c.push(m); await kvSet("chat", c.slice(-300)); renderChat();
  if (!m.mine) {
    if (navigator.vibrate) navigator.vibrate([120, 60, 120]);
    if (document.hidden && "Notification" in window && Notification.permission === "granted") new Notification("PXD2 TEXT · " + m.from, { body: m.text.slice(0, 140), tag: "pxd2text" });
    if (curTab !== "text") { unreadText++; $("#tCount").textContent = `(${unreadText})`; }
    toast(m.from + ": " + m.text.slice(0, 60));
  }
}
async function chatMark(id, st) { const c = await chatGet(); const m = c.find(x => x.id === id && x.mine); if (m) { m.st = st; await kvSet("chat", c); renderChat(); } }
let unreadText = 0, curTab = "pitch";
async function renderChat() {
  const c = await chatGet(), el = $("#thread"); if (!el) return;
  const atEnd = el.scrollTop + el.clientHeight >= el.scrollHeight - 30;
  el.innerHTML = c.map(m => `<div class="msg ${m.mine ? "me" : ""}"><div class="w">${m.mine ? "me → " + esc(m.to) : esc(m.from)} · ${new Date(m.t).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}${m.mine ? (m.st === "sent" ? " ✓" : " · waiting") : ""}</div><div class="b">${esc(m.text)}</div></div>`).join("")
    || `<div class="dim" style="color:#8a7a20">No texts yet. Anything BASE1 or BASE2 sends lands here within seconds.</div>`;
  if (atEnd) el.scrollTop = el.scrollHeight;
}
async function sendChat() {
  const text = $("#cText").value.trim(); if (!text) return;
  const to = $("#cTo").value, id = uid();
  $("#cText").value = "";
  await chatAdd({ id, t: Date.now(), from: S.dev, to, text, mine: true });
  await qPut({ id, t: Date.now(), type: "chat", to, text });
  if ("Notification" in window && Notification.permission === "default") Notification.requestPermission();
  drain();
}
function fillTo() {
  const sel = $("#cTo"), cur = sel.value, opts = ["ALL", "AI"].concat(BASES, ((lastStatus && lastStatus.devices) || []).filter(d => d !== S.dev));
  if (sel.options.length !== opts.length) { sel.innerHTML = opts.map(o => `<option>${esc(o)}</option>`).join(""); sel.value = opts.includes(cur) ? cur : "ALL"; }
}
// ------------------------------------------------------------------ FILES: browse / pull / upload BASE1 shared folders
let FX = null, fRoot = "", fDir = "";
async function loadIndex(force) {
  if (FX && !force && Date.now() - FX.at < 60000) return renderFiles();
  try {
    $("#fState").textContent = "· loading…";
    const blob = await ghGet(`status/${HUB}_files.env`);
    if (!blob) { $("#fState").textContent = "· BASE1 has not published its folders yet"; return; }
    const [, body] = await unseal(blob);
    FX = { at: Date.now(), idx: JSON.parse(new TextDecoder().decode(body)) };
    await kvSet("filesIdx", FX);
    $("#fState").textContent = "";
  } catch (e) { FX = FX || (await kvGet("filesIdx")); $("#fState").textContent = "· offline copy"; }
  renderFiles();
}
function renderFiles() {
  if (!FX) return;
  const q = $("#fFind").value.trim().toLowerCase();
  $("#fPath").textContent = fRoot ? fRoot + (fDir ? " / " + fDir.replace(/\//g, " / ") : "") : "Shared folders";
  $("#fUp").disabled = !fRoot; ["#fUpl", "#fZip"].forEach(x => $(x).classList.toggle("hide", !fRoot));
  let rows;
  if (q) rows = Object.entries(FX.idx).flatMap(([r, l]) => l.filter(x => x[0].toLowerCase().includes(q)).slice(0, 200).map(x => [r, ...x]));
  else if (!fRoot) rows = Object.keys(FX.idx).map(r => [r, "", -1, 0, true]);
  else rows = (FX.idx[fRoot] || []).filter(x => { const i = x[0].lastIndexOf("/"); return (i < 0 ? "" : x[0].slice(0, i)) === fDir; }).map(x => [fRoot, ...x]);
  rows.sort((a, b) => (b[2] < 0) - (a[2] < 0) || a[1].localeCompare(b[1]));
  $("#fList").innerHTML = rows.map(([r, p, size, mt, isRoot]) => {
    const name = isRoot ? r : (q ? r + " / " + p : p.split("/").pop());
    const dir = size < 0;
    return `<li><span class="n" ${dir ? `data-open="${esc(r)}|${esc(isRoot ? "" : p)}" style="cursor:pointer"` : ""}>${dir ? "📁" : "📄"} ${esc(name)}</span>
      <span class="m">${dir ? "" : fmt(size)}</span>
      ${dir ? `<button data-open="${esc(r)}|${esc(isRoot ? "" : p)}" style="min-height:34px;padding:4px 10px">OPEN</button>` : `<button data-get="${esc(r)}|${esc(p)}" style="min-height:34px;padding:4px 10px">⇩ GET</button>`}</li>`;
  }).join("") || `<li class="dim">empty</li>`;
  document.querySelectorAll("[data-open]").forEach(b => b.onclick = () => { [fRoot, fDir] = b.dataset.open.split("|"); $("#fFind").value = ""; renderFiles(); });
  document.querySelectorAll("[data-get]").forEach(b => b.onclick = () => { const [r, p] = b.dataset.get.split("|"); pull(r, p); b.textContent = "✓ asked"; b.disabled = true; });
}
async function pull(root, path) {
  await qPut({ id: uid(), t: Date.now(), type: "fetch", root, path });
  toast(`asked BASE1 for ${path.split("/").pop() || root} - watch FROM BASE`); drain();
}
// ------------------------------------------------------------------ pop-up alerts (Web Push from BASE1)
const u8 = b => { const s = atob(b.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((b.length + 3) % 4)); return Uint8Array.from(s, c => c.charCodeAt(0)); };
let pushDone = false;
function alertsUI() {
  const b = $("#alertBtn"); if (!b) return;
  const ok = "Notification" in window && Notification.permission === "granted" && pushDone;
  b.classList.toggle("hide", ok); $("#alertOn").classList.toggle("hide", !ok);
}
async function enablePush(ask) {
  const say = t => { if (ask) { toast(t); const b = $("#alertBtn"); if (b) b.title = t; } };
  try {
    if (!("Notification" in window) || !("serviceWorker" in navigator) || !("PushManager" in window)) return say("this browser cannot do pop-up alerts - open the app in Chrome");
    let perm = Notification.permission;
    if (perm !== "granted") {
      if (!ask) return alertsUI();
      perm = await Notification.requestPermission();             // asked first, straight from the tap
      if (perm !== "granted") {
        showErr("Pop-up alerts are blocked for this app. Fix: tap the lock/tune icon left of the address (or ⋮ > App info) > Site settings > Notifications > Allow, then tap 🔔 again.");
        return alertsUI();
      }
    }
    if (!lastStatus || !lastStatus.vapid) { say("getting BASE1's alert key…"); await loadStatus(); }
    if (!lastStatus || !lastStatus.vapid) return say("BASE1 has not sent its alert key yet - is the hub running? try again in a minute");
    say("connecting alerts…");
    const reg = await navigator.serviceWorker.ready;
    let sub = await reg.pushManager.getSubscription();
    const key = lastStatus.vapid;
    if (sub && (await kvGet("pushKey")) !== key) { await sub.unsubscribe(); sub = null; }
    if (!sub) sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: u8(key) });
    const js = JSON.stringify(sub);
    if (ask || (await kvGet("pushSent")) !== js + S.dev) { await send({ type: "push_sub" }, new TextEncoder().encode(js)); await kvSet("pushSent", js + S.dev); await kvSet("pushKey", key); }
    pushDone = true;
    say("🔔 pop-up alerts ON - BASE1 will send a test pop-up now");
  } catch (e) { if (ask) showErr("alerts: " + (e.message || e)); }
  alertsUI();
}
let helloed = false;
async function tick() {
  if (!S.key) return; if (!navigator.onLine) return setNet(false);
  if (!helloed) { try { await send({ type: "hello" }); helloed = true; } catch (e) { } }   // BASE1 makes this device a send folder
  await loadStatus(); await loadReplies(); drain();
}
window.addEventListener("online", tick); window.addEventListener("offline", () => setNet(false));
setInterval(tick, 30000);
setInterval(async () => {                         // text-message speed: check this device's mailbox every 5 s while open
  if (!S.key || !navigator.onLine || document.hidden) return;
  await loadReplies(); drain();
  $("#tState").textContent = online ? "· live" : "· no link";
}, 5000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) tick(); });

// ------------------------------------------------------------------ UI
const loaders = { queue: renderQueue, outbox: async () => { await loadReplies(); setTimeout(markSeen, 4000); }, fleet: loadStatus, task: loadStatus, note: () => { $("#notes").textContent = "notes go into BASE1's ASTRO Inbox\\notes.md"; } };
loaders.text = () => { unreadText = 0; $("#tCount").textContent = ""; renderChat(); setTimeout(() => { const t = $("#thread"); t.scrollTop = t.scrollHeight; }, 50); };
document.querySelectorAll("nav button").forEach(b => b.onclick = () => {
  curTab = b.dataset.tab;
  document.querySelectorAll("nav button").forEach(x => x.classList.toggle("on", x === b));
  document.querySelectorAll("[data-pane]").forEach(p => p.classList.toggle("hide", p.dataset.pane !== b.dataset.tab));
  (loaders[b.dataset.tab] || (() => { }))();
});
$("#files").onchange = e => { addFiles([...e.target.files]); e.target.value = ""; };
$("#cam").onchange = e => { addFiles([...e.target.files]); e.target.value = ""; };
const drop = $("#drop");
["dragenter", "dragover"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add("hot"); }));
["dragleave", "drop"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove("hot"); }));
drop.addEventListener("drop", e => addFiles([...e.dataTransfer.files]));
$("#nSend").onclick = async () => { const t = $("#nText").value.trim(); if (!t) return; await qPut({ id: uid(), t: Date.now(), type: "note", text: t }); $("#nText").value = ""; toast(navigator.onLine ? "note sending" : "note saved - goes when there is signal"); renderQueue(); drain(); };
$("#qRetry").onclick = tick;
$("#cGo").onclick = sendChat;
$("#alertBtn").onclick = () => enablePush(true);
loaders.files = () => loadIndex();
$("#fUp").onclick = () => { if (!fDir) fRoot = ""; else fDir = fDir.includes("/") ? fDir.slice(0, fDir.lastIndexOf("/")) : ""; renderFiles(); };
$("#fZip").onclick = () => pull(fRoot, fDir);
$("#fFind").oninput = renderFiles;
$("#fUplIn").onchange = e => { addFiles([...e.target.files], { root: fRoot, dir: fDir }); e.target.value = ""; toast(`uploading into ${fRoot}${fDir ? " / " + fDir : ""}`); };
$("#cText").addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); } });
function goTab(t) { const b = document.querySelector(`nav button[data-tab="${t}"]`); if (b) b.click(); }
if ("serviceWorker" in navigator) navigator.serviceWorker.addEventListener("message", e => { if (e.data && e.data.tab) { goTab(e.data.tab); tick(); } });
if (new URLSearchParams(location.search).get("tab")) setTimeout(() => goTab(new URLSearchParams(location.search).get("tab")), 300);
if (new URLSearchParams(location.search).has("mini")) { document.body.classList.add("mini"); document.title = "PXD2 TEXT"; }
$("#tGo").onclick = async () => {
  let params; try { params = JSON.parse($("#tParams").value || "{}"); } catch (e) { return toast("parameters are not valid JSON"); }
  await qPut({ id: uid(), t: Date.now(), type: "task", node: $("#tNode").value, kind: $("#tKind").value, name: $("#tName").value, params });
  toast("task queued - BASE1 answers under REPLIES"); renderQueue(); drain();
};
$("#pGo").onclick = async () => {
  const dev = ($("#pName").value || "tablet").replace(/[^A-Za-z0-9_-]/g, "").slice(0, 32) || "tablet";
  const token = $("#pTok").value.trim(), pass = $("#pCode").value.trim();
  if (!token || !pass) return ($("#pMsg").textContent = "token and mesh key are both needed");
  $("#pMsg").textContent = "checking…";
  try {
    S.token = token;
    const meta = await ghGet("meta.json"); if (!meta) throw new Error("no mesh found - wrong token?");
    const salt = unb64(JSON.parse(new TextDecoder().decode(meta)).salt);
    S.key = await deriveKey(pass, salt); S.dev = dev;
    await kvSet("session", { token, key: S.key, dev });               // the key is a non-extractable CryptoKey
    show(); tick(); if (loaders.pitch) loaders.pitch();
  } catch (e) { S.key = null; $("#pMsg").textContent = e.message; $("#pMsg").className = "bad"; }
};
function show() { $("#pairView").classList.toggle("hide", !!S.key); $("#appView").classList.toggle("hide", !S.key); }

(async () => {
  const s = await kvGet("session"); if (s) S = s;
  show(); renderQueue(); renderFromBase(); renderChat(); tick();
  if (S.key && loaders.pitch) loaders.pitch();
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js", { updateViaCache: "none" }).then(r => { r.update(); setInterval(() => r.update(), 10 * 60000); }).catch(() => { });
    let reloaded = !navigator.serviceWorker.controller;   // first install: nothing to refresh                      // a new version took over: reload once so the screen shows it
    navigator.serviceWorker.addEventListener("controllerchange", () => { if (!reloaded) { reloaded = true; location.reload(); } });
  }
  if (navigator.storage && navigator.storage.persist) navigator.storage.persist();
})();
