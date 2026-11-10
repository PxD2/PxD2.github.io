// PXD2 LINK - PITCH desktop: every client kit on the rep's tablet, offline. Websites, QR codes, proposal, print pieces,
// inventory tags and social images, one tap each. Kits come from BASE1 (All-Client-Kits.zip or one *-Client-Kit.zip)
// and are unpacked into IndexedDB, so a shop with no signal still gets the full pitch.
"use strict";
const KITS_ZIP = { root: "Client Kits", path: "All-Client-Kits.zip" };
let kitUrls = [], curClient = null;

const kitPut = (k, blob) => tx("kit", "readwrite", s => s.put(blob, k));
const kitGet = k => tx("kit", "readonly", s => s.get(k));
const pretty = slug => slug.replace(/-/g, " ").replace("Time E ", "Time E-").replace(/Its a/, "It's a").replace(/Suzys/, "Suzy's");

async function importKits(blob, name) {
  if (!window.fflate) return toast("unzip tool missing - reload the app");
  toast(`unpacking ${name}…`);
  const outer = fflate.unzipSync(new Uint8Array(await blob.arrayBuffer()));
  const inner = Object.keys(outer).some(n => /-Client-Kit\.zip$/i.test(n))
    ? Object.entries(outer).filter(([n]) => /-Client-Kit\.zip$/i.test(n)).map(([n, b]) => [n.replace(/-Client-Kit\.zip$/i, "").split("/").pop(), fflate.unzipSync(b)])
    : [[name.replace(/-Client-Kit\.zip$/i, ""), outer]];
  const kits = (await kvGet("kits")) || {};
  for (const [slug, files] of inner) {
    const list = [];
    for (const [path, bytes] of Object.entries(files)) {
      if (path.endsWith("/") || !bytes.length) continue;
      const clean = path.replace(/^[^/]*-Client-Kit\//i, "");
      await kitPut(`${slug}/${clean}`, new Blob([bytes], { type: mime(clean) }));
      list.push([clean, bytes.length]);
    }
    let links = {};
    const lt = files[Object.keys(files).find(p => /qr\/links\.txt$/i.test(p))];
    if (lt) new TextDecoder().decode(lt).split("\n").forEach(l => { const m = l.match(/^([a-z-]+)\s+(\S.*)$/); if (m) links[m[1]] = m[2].trim(); });
    const site = ((links.website || "").match(/opens (https:\/\/\S+?)\)/) || [])[1] || (links.website || "").split(/\s/)[0] || "";
    kits[slug] = { slug, name: pretty(slug), files: list, links, site, at: Date.now() };
  }
  await kvSet("kits", kits);
  toast(`${inner.length} client kit(s) ready on this tablet`);
  renderPitch();
}
window.importKits = importKits;

async function autoImport() {
  const kits = (await kvGet("kits")) || {};
  if (Object.keys(kits).length) return false;
  const z = (await gotAll()).find(g => /client-kit/i.test(g.name) && /\.zip$/i.test(g.name));
  if (z) { await importKits(z.blob, z.name); return true; }
  return false;
}

function blobUrl(b) { const u = URL.createObjectURL(b); kitUrls.push(u); return u; }
const has = (k, re) => k.files.filter(([p]) => re.test(p));
const label = p => p.split("/").pop().replace(/\.[a-z0-9]+$/i, "").replace(/^\d+-/, "").replace(/[-_]/g, " ");

async function renderPitch() {
  kitUrls.forEach(u => URL.revokeObjectURL(u)); kitUrls = [];
  const kits = Object.values((await kvGet("kits")) || {}).sort((a, b) => a.name.localeCompare(b.name));
  const el = $("#pitchBody");
  if (!kits.length) {
    el.innerHTML = `<div class="card"><h3>NO CLIENT KITS ON THIS TABLET YET</h3><p>Get them from BASE1 once (about 45 MB) - after that the pitch works with no signal.</p>
      <button class="primary" id="kGet">⇩ GET ALL CLIENT KITS FROM BASE1</button></div>`;
    $("#kGet").onclick = () => { pull(KITS_ZIP.root, KITS_ZIP.path); $("#kGet").textContent = "✓ asked BASE1 - unpacks itself when it lands"; $("#kGet").disabled = true; };
    return;
  }
  if (curClient && kits.find(k => k.slug === curClient)) return renderClient(kits.find(k => k.slug === curClient));
  const tiles = [];
  for (const k of kits) {
    const ic = has(k, /site\/[^/]+\/icon\.png$/i)[0] || has(k, /social\/profile/i)[0];
    const b = ic && await kitGet(`${k.slug}/${ic[0]}`);
    tiles.push(`<button class="ptile" data-client="${esc(k.slug)}">${b ? `<img src="${blobUrl(b)}" alt="">` : `<span class="pfb">${esc(k.name[0])}</span>`}<span>${esc(k.name)}</span></button>`);
  }
  el.innerHTML = `<div class="pgrid">${tiles.join("")}</div>
    <div class="row" style="margin-top:12px"><button id="kRefresh" style="min-height:36px">⟳ GET LATEST KITS FROM BASE1</button><span class="dim" style="font-size:12px">${kits.length} clients on this tablet · works offline</span></div>`;
  document.querySelectorAll("[data-client]").forEach(b => b.onclick = () => { curClient = b.dataset.client; renderPitch(); });
  $("#kRefresh").onclick = () => { pull(KITS_ZIP.root, KITS_ZIP.path); $("#kRefresh").textContent = "✓ asked BASE1"; };
}

async function renderClient(k) {
  const el = $("#pitchBody");
  const get = async p => kitGet(`${k.slug}/${p}`);
  const share = has(k, /site\/[^/]+\/share\.png$/i)[0];
  const shareU = share && blobUrl(await get(share[0]));
  const qrs = has(k, /^qr\/.*\.png$/i);
  const qrTiles = [];
  for (const [p] of qrs) {
    const key = label(p).replace(/ /g, "-");
    qrTiles.push(`<button class="pqr" data-qr="${esc(p)}" data-link="${esc(k.links[key] || "")}"><img src="${blobUrl(await get(p))}" alt=""><span>${esc(label(p))}</span></button>`);
  }
  const docs = [
    ...has(k, /proposal\.(docx|pdf)$/i).map(f => ["📋 Proposal", f]),
    ...has(k, /print-pack\.pdf$/i).map(f => ["🖨 Print pack (all pieces)", f]),
    ...has(k, /^print\/.*\.pdf$/i).map(f => ["🖨 " + label(f[0]), f]),
    ...has(k, /^inventory\//i).map(f => ["🏷 " + label(f[0]), f]),
  ];
  const social = has(k, /^social\/.*\.(png|jpg)$/i);
  const socialT = [];
  for (const [p] of social) socialT.push(`<a href="${blobUrl(await get(p))}" target="_blank" class="psoc"><img src="${kitUrls[kitUrls.length - 1]}" alt=""><span>${esc(label(p))}</span></a>`);
  el.innerHTML = `
    <div class="row" style="margin-bottom:10px"><button id="pBack" style="min-height:38px">← ALL CLIENTS</button><span class="big" style="flex:1">${esc(k.name)}</span></div>
    <div class="card"><h3>🌐 THEIR NEW WEBSITE</h3>
      ${shareU ? `<img src="${shareU}" alt="" style="width:100%;border-radius:8px;margin-bottom:8px">` : ""}
      <div class="row">${k.site ? `<a class="btn primary" href="${esc(k.site)}" target="_blank" rel="noopener" style="text-decoration:none">OPEN LIVE SITE</a>` : ""}
        ${k.site ? `<a class="btn" href="${esc(k.site)}tags/" target="_blank" rel="noopener" style="text-decoration:none">TAG MAKER</a>` : ""}
        <span class="dim" style="font-size:12px">${navigator.onLine ? "" : "no signal - show the preview above; the live site opens when there is signal"}</span></div></div>
    <div class="card"><h3>▦ QR CODES - TAP ONE TO SHOW IT BIG</h3><div class="pqrs">${qrTiles.join("") || '<span class="dim">none in kit</span>'}</div></div>
    <div class="card"><h3>📄 PROPOSAL · PRINT · TAGS</h3><ul class="list">${docs.map(([t, [p, n]]) => `<li><span class="n">${esc(t)}</span><span class="m">${fmt(n)}</span>
      <button data-doc="${esc(p)}" style="min-height:34px;padding:4px 10px">OPEN</button><button data-dl="${esc(p)}" style="min-height:34px;padding:4px 10px">SAVE</button></li>`).join("") || '<li class="dim">none</li>'}</ul></div>
    ${socialT.length ? `<div class="card"><h3>📣 SOCIAL MEDIA SET</h3><div class="pqrs">${socialT.join("")}</div></div>` : ""}
    <div class="card"><h3>✎ TELL BASE</h3><div class="row"><button data-say="Pitching ${esc(k.name)} now">PITCHING NOW</button><button data-say="${esc(k.name)} said YES - send sign-off">THEY SAID YES</button><button data-say="${esc(k.name)} wants changes - call me">WANTS CHANGES</button></div></div>`;
  $("#pBack").onclick = () => { curClient = null; renderPitch(); };
  document.querySelectorAll("[data-qr]").forEach(b => b.onclick = () => bigQR(b.querySelector("img").src, b.querySelector("span").textContent, b.dataset.link, k.name));
  document.querySelectorAll("[data-doc]").forEach(b => b.onclick = async () => window.open(blobUrl(await get(b.dataset.doc)), "_blank"));
  document.querySelectorAll("[data-dl]").forEach(b => b.onclick = async () => { const a = document.createElement("a"); a.href = blobUrl(await get(b.dataset.dl)); a.download = b.dataset.dl.split("/").pop(); a.click(); });
  document.querySelectorAll("[data-say]").forEach(b => b.onclick = async () => {
    const id = uid(), text = b.dataset.say;
    await chatAdd({ id, t: Date.now(), from: S.dev, to: "BASE1", text, mine: true });
    await qPut({ id, t: Date.now(), type: "chat", to: "BASE1", text }); drain(); toast("sent to BASE1");
  });
}

function bigQR(src, name, link, client) {
  const o = document.createElement("div");
  o.className = "pbig";
  o.innerHTML = `<div class="pbn">${esc(client)} · ${esc(name)}</div><img src="${src}" alt=""><div class="pbl">${esc((link || "").split(/\s+\(/)[0])}</div><div class="pbx">tap anywhere to close</div>`;
  o.onclick = () => { o.remove(); if (document.fullscreenElement) document.exitFullscreen().catch(() => { }); };
  document.body.appendChild(o);
  if (o.requestFullscreen) o.requestFullscreen().catch(() => { });
}

loaders.pitch = async () => { if (!(await autoImport())) renderPitch(); };
