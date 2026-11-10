// PXD2 LINK WAN - tablet / phone side. PXD2's own wide-area link to BASE1: sealed envelopes (AES-256-GCM) through the
// private repo PxD2/astrocoms (branch "mesh"). Works on any network; nothing on GitHub is readable without the mesh key.
"use strict";
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
const DB = new Promise((ok, bad) => {
  const r = indexedDB.open("pxd2_wan", 1);
  r.onupgradeneeded = () => { r.result.createObjectStore("q", { keyPath: "id" }); r.result.createObjectStore("kv"); };
  r.onsuccess = () => ok(r.result); r.onerror = () => bad(r.error);
});
async function tx(store, mode, fn) { const db = await DB; return new Promise((ok, bad) => { const t = db.transaction(store, mode); const r = fn(t.objectStore(store)); t.oncomplete = () => ok(r && r.result); t.onerror = () => bad(t.error); }); }
const kvGet = k => tx("kv", "readonly", s => s.get(k));
const kvSet = (k, v) => tx("kv", "readwrite", s => s.put(v, k));
const qAll = async () => ((await tx("q", "readonly", s => s.getAll())) || []).sort((a, b) => a.t - b.t);
const qPut = x => tx("q", "readwrite", s => s.put(x));
const qDel = id => tx("q", "readwrite", s => s.delete(id));

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
const send = async (header, body) => ghPut(`to/${HUB}/${stamp()}.env`, await seal(Object.assign({ from: S.dev }, header), body), `${S.dev} -> ${HUB}`);

// ------------------------------------------------------------------ queue
async function addFiles(list) {
  const note = $("#fNote").value.trim();
  for (const f of list) await qPut({ id: uid(), t: Date.now(), type: "file", name: f.name, size: f.size, blob: f, note, sent: 0 });
  $("#fNote").value = ""; toast(`${list.length} file(s) queued`); renderQueue(); drain();
}
async function sha256(blob) { return blob.size <= 512 * 1024 * 1024 ? [...new Uint8Array(await crypto.subtle.digest("SHA-256", await blob.arrayBuffer()))].map(b => b.toString(16).padStart(2, "0")).join("") : ""; }
async function sendFile(it) {
  if (it.sha === undefined) { it.sha = await sha256(it.blob); await qPut(it); }
  const total = Math.max(1, Math.ceil(it.size / CHUNK));
  for (let i = Math.floor((it.sent || 0) / CHUNK); i < total; i++) {
    const piece = new Uint8Array(await it.blob.slice(i * CHUNK, Math.min((i + 1) * CHUNK, it.size)).arrayBuffer());
    await send({ type: "file", id: it.id, name: it.name, idx: i, total, sha256: it.sha, note: it.note || "" }, piece);
    it.sent = Math.min((i + 1) * CHUNK, it.size); await qPut(it); renderQueue();
  }
}
async function drain() {
  if (!S.key) return; if (draining) { again = true; return; } draining = true; again = false;
  try {
    for (const it of await qAll()) {
      if (!navigator.onLine) break;
      try {
        if (it.type === "note") await send({ type: "note", id: it.id }, new TextEncoder().encode(it.text));
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
    ? `<li><span class="n">${it.type === "task" ? "⚙ " + esc(it.kind) : "✎ " + esc(it.text.slice(0, 80))}</span><span class="m">${navigator.onLine ? "sending" : "waiting for signal"}</span></li>`
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
    setNet(true);
  } catch (e) { setNet(false, e.message); if (e.name === "OperationError") $("#hubState").textContent = "Mesh key does not match BASE1's - sign out and sign in with the right key."; }
}
async function loadReplies() {
  try {
    const list = (await ghLs(`to/${S.dev}`)).filter(x => x.name.endsWith(".env")).sort((a, b) => a.name < b.name ? -1 : 1);
    const keep = (await kvGet("replies")) || [];
    for (const it of list) {
      try { const [h] = await unseal(await ghGet(it.path)); keep.unshift({ t: Date.now(), h }); if (h.type === "ack") toast(h.text); } catch (e) { }
      await ghDel(it.path, it.sha);
    }
    await kvSet("replies", keep.slice(0, 60));
    $("#outList").innerHTML = keep.slice(0, 60).map(r => `<li><span class="n">${esc(r.h.text || (r.h.type === "task_queued" ? "task queued on " + r.h.node : r.h.type === "pong" ? "BASE1 answered" : r.h.type))}</span><span class="m">${new Date(r.t).toLocaleTimeString()}</span></li>`).join("") || `<li class="dim">nothing yet</li>`;
  } catch (e) { }
}
async function tick() { if (!S.key) return; if (!navigator.onLine) return setNet(false); await loadStatus(); await loadReplies(); drain(); }
window.addEventListener("online", tick); window.addEventListener("offline", () => setNet(false));
setInterval(tick, 20000);

// ------------------------------------------------------------------ UI
const loaders = { queue: renderQueue, outbox: loadReplies, fleet: loadStatus, task: loadStatus, note: () => { $("#notes").textContent = "notes go into BASE1's ASTRO Inbox\\notes.md"; } };
document.querySelectorAll("nav button").forEach(b => b.onclick = () => {
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
    show(); tick();
  } catch (e) { S.key = null; $("#pMsg").textContent = e.message; $("#pMsg").className = "bad"; }
};
function show() { $("#pairView").classList.toggle("hide", !!S.key); $("#appView").classList.toggle("hide", !S.key); }

(async () => {
  const s = await kvGet("session"); if (s) S = s;
  show(); renderQueue(); tick();
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => { });
  if (navigator.storage && navigator.storage.persist) navigator.storage.persist();
})();
