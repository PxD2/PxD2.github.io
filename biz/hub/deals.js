// PXD2 DESKTOP - DEALS: service contracts and receipts (cash, card, check, trade) signed on the tablet.
// Makes a PDF, keeps a copy on the device, and sends it sealed to BASE1 (filed in Desktop\PXD2 Deals + ledger.csv).
"use strict";
const PXD2 = { name: "PXD2 Enterprises", who: "Chad Aaron Peters, owner", cfo: "Angie Wood, CFO", addr: "PO Box 514, Concho, AZ 85924", phone: "928-457-6404", email: "pxdsquared@gmail.com" };
const PACKAGES = [
  { id: "web", label: "Client website", amount: 500, desc: "Custom website for the business: design, build, mobile layout, hours/location/contact, QR code kit and print-ready pieces, and launch on a PXD2 address." },
  { id: "order", label: "Online ordering + full menu", amount: 1500, ordering: true, desc: "Online menu with current items and prices, connected to the Client's own online-ordering/point-of-sale provider for pickup orders, with Order buttons across the site, plus setup support and staff walkthrough." },
  { id: "custom", label: "Custom line", amount: 0, desc: "" }
];
const TERMS = ["Paid in full at signing", "50% deposit at signing, 50% at launch", "Paid in full at launch", "Trade (goods/services) for the full amount", "Part trade, part payment"];
const METHODS = ["Cash", "Check", "Card", "Trade", "Cash + trade", "Card + trade", "Check + trade"];
const $d = s => document.querySelector(s);
const usd = n => "$" + (Math.round(n * 100) / 100).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
const today = () => new Date().toLocaleDateString("en-US", { timeZone: "America/Phoenix", year: "numeric", month: "long", day: "numeric" });

async function nextNo(kind) {
  const n = ((await kvGet("dealSeq")) || 0) + 1; await kvSet("dealSeq", n);
  const d = new Date(new Date().toLocaleString("en-US", { timeZone: "America/Phoenix" }));
  const ymd = String(d.getFullYear()).slice(2) + String(d.getMonth() + 1).padStart(2, "0") + String(d.getDate()).padStart(2, "0");
  return `PXD2-${kind === "contract" ? "C" : "R"}-${ymd}-${String(n).padStart(3, "0")}`;
}
async function clientNames() {
  const kits = Object.values((await kvGet("kits")) || {}).map(k => k.name);
  return [...new Set(kits.concat(["Scrub Hub Laundry & Showers", "Stanford General Store & Y-Bar"]))].sort();
}

// ---------------------------------------------------------------- signature pad
function sigPad(canvas) {
  const ctx = canvas.getContext("2d"); let down = false, last = null, inked = false;
  const fit = () => { const r = canvas.getBoundingClientRect(); canvas.width = r.width * 2; canvas.height = r.height * 2; ctx.scale(2, 2); ctx.lineWidth = 2.4; ctx.lineCap = "round"; ctx.strokeStyle = "#111"; };
  fit();
  const pt = e => { const r = canvas.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
  canvas.onpointerdown = e => { down = true; last = pt(e); canvas.setPointerCapture(e.pointerId); };
  canvas.onpointermove = e => { if (!down) return; const p = pt(e); ctx.beginPath(); ctx.moveTo(...last); ctx.lineTo(...p); ctx.stroke(); last = p; inked = true; };
  canvas.onpointerup = canvas.onpointercancel = () => { down = false; };
  return { clear() { ctx.clearRect(0, 0, canvas.width, canvas.height); inked = false; }, get inked() { return inked; }, png: () => { const c = document.createElement("canvas"); c.width = 440; c.height = 140; const x = c.getContext("2d"); x.fillStyle = "#fff"; x.fillRect(0, 0, 440, 140); x.drawImage(canvas, 0, 0, 440, 140); return c.toDataURL("image/jpeg", 0.8); } };
}

// ---------------------------------------------------------------- views
async function renderDeals() {
  const list = ((await kvGet("deals")) || []).slice().reverse();
  $d("#dealsBody").innerHTML = `
    <div class="row" style="gap:10px;margin-bottom:12px"><button class="primary" id="dNewC">+ NEW CONTRACT</button><button class="primary" id="dNewR">+ NEW RECEIPT</button></div>
    <div class="card"><h3>SIGNED ON THIS TABLET</h3><ul class="list">${list.map(d => `<li><span class="n">${d.kind === "contract" ? "📝" : "🧾"} ${esc(d.no)} · ${esc(d.client)}</span>
      <span class="m">${usd(d.total)}${d.trade ? " · trade " + usd(d.trade) : ""} · ${d.sent ? "✓ at BASE1" : "sending…"}</span>
      <button data-open="${d.id}" style="min-height:34px;padding:4px 10px">OPEN</button></li>`).join("") || `<li class="dim">No contracts or receipts yet.</li>`}</ul></div>
    <p class="dim" style="font-size:12px">Contract wording is a plain-language PXD2 template. Have Chad's advisor review it before relying on it for large jobs.</p>`;
  $d("#dNewC").onclick = () => form("contract");
  $d("#dNewR").onclick = () => form("receipt");
  document.querySelectorAll("[data-open]").forEach(b => b.onclick = async () => { const blob = await kvGet("dealpdf:" + b.dataset.open); if (blob) window.open(URL.createObjectURL(blob), "_blank"); });
}

async function form(kind) {
  const names = await clientNames();
  const contracts = ((await kvGet("deals")) || []).filter(d => d.kind === "contract");
  const C = kind === "contract";
  $d("#dealsBody").innerHTML = `
    <div class="card">
      <h3>${C ? "NEW SERVICE CONTRACT" : "NEW RECEIPT"}</h3>
      <label>CLIENT BUSINESS</label><input id="fBiz" list="fBizList" placeholder="Business name"><datalist id="fBizList">${names.map(n => `<option value="${esc(n)}">`).join("")}</datalist>
      <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px">
        <div><label>OWNER / SIGNER NAME</label><input id="fOwner" autocomplete="off"></div>
        <div><label>PHONE</label><input id="fPhone" type="tel"></div>
        <div><label>EMAIL</label><input id="fEmail" type="email"></div>
      </div>
      <label>BUSINESS ADDRESS</label><input id="fAddr">
      ${C ? "" : `<label>FOR CONTRACT (optional)</label><select id="fRef"><option value="">none</option>${contracts.map(c => `<option value="${esc(c.no)}">${esc(c.no)} · ${esc(c.client)} · ${usd(c.total)}</option>`).join("")}</select>`}
      <label>${C ? "SERVICES" : "WHAT WAS PAID FOR"}</label>
      <div id="fLines"></div>
      <div class="row" style="gap:8px;margin-top:6px">${PACKAGES.map(p => `<button type="button" data-pkg="${p.id}" style="min-height:36px;padding:6px 12px">+ ${esc(p.label)}${p.amount ? " " + usd(p.amount) : ""}</button>`).join("")}</div>
      <div class="big" style="margin-top:12px">Total <span id="fTotal">$0.00</span></div>
      ${C ? `<label>PAYMENT TERMS</label><select id="fTerms">${TERMS.map(t => `<option>${esc(t)}</option>`).join("")}</select>`
          : `<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px">
               <div><label>PAID WITH</label><select id="fMethod">${METHODS.map(t => `<option>${esc(t)}</option>`).join("")}</select></div>
               <div><label>MONEY RECEIVED ($)</label><input id="fCash" type="number" inputmode="decimal" min="0" step="0.01" value="0"></div>
               <div><label>CHECK # / CARD LAST 4</label><input id="fRefNo"></div>
             </div>`}
      <div id="fTradeBox">
        <label>TRADE: WHAT IS BEING TRADED (goods or services)</label><input id="fTrade" placeholder="e.g. 3 antique display cases, delivered">
        <label>TRADE: AGREED VALUE ($)</label><input id="fTradeVal" type="number" inputmode="decimal" min="0" step="0.01" value="0">
      </div>
      ${C ? `<label>START DATE</label><input id="fStart" type="date">` : ""}
      <label>NOTES</label><textarea id="fNotes" style="min-height:70px"></textarea>
      <label>${C ? "CLIENT SIGNATURE" : "RECEIVED BY (PXD2) SIGNATURE"}</label>
      <canvas id="sig1" style="width:100%;height:140px;background:#fff;border-radius:8px;touch-action:none"></canvas>
      <div class="row" style="gap:8px"><button type="button" id="sig1c" style="min-height:32px;padding:4px 10px">Clear</button><span class="dim" style="font-size:12px">sign with a finger or stylus</span></div>
      ${C ? `<label>PXD2 REPRESENTATIVE NAME</label><input id="fRep" placeholder="Your name">
      <label>PXD2 REPRESENTATIVE SIGNATURE</label>
      <canvas id="sig2" style="width:100%;height:140px;background:#fff;border-radius:8px;touch-action:none"></canvas>
      <div class="row" style="gap:8px"><button type="button" id="sig2c" style="min-height:32px;padding:4px 10px">Clear</button></div>` : `<label>PXD2 REPRESENTATIVE NAME</label><input id="fRep" placeholder="Your name">`}
      <p id="fErr" class="bad" style="min-height:1em;margin-top:8px"></p>
      <div class="row" style="gap:10px;margin-top:6px"><button class="primary" id="fMake">${C ? "SIGN &amp; SAVE CONTRACT" : "SAVE RECEIPT"}</button><button id="fCancel">Cancel</button></div>
    </div>`;
  const rep = await kvGet("repName"); if (rep) $d("#fRep").value = rep;
  const lines = [];
  const drawLines = () => {
    $d("#fLines").innerHTML = lines.map((l, i) => `<div class="row" style="gap:8px;margin-bottom:8px;flex-wrap:nowrap;align-items:flex-start">
      <textarea data-i="${i}" data-k="desc" style="min-height:52px;flex:1">${esc(l.desc)}</textarea>
      <input data-i="${i}" data-k="amount" type="number" inputmode="decimal" step="0.01" value="${l.amount}" style="width:120px">
      <button type="button" data-rm="${i}" style="min-height:40px;padding:4px 10px">✕</button></div>`).join("") || `<p class="dim">Add a package below.</p>`;
    $d("#fLines").querySelectorAll("[data-k]").forEach(el => el.oninput = () => { lines[el.dataset.i][el.dataset.k] = el.dataset.k === "amount" ? +el.value || 0 : el.value; total(); });
    $d("#fLines").querySelectorAll("[data-rm]").forEach(b => b.onclick = () => { lines.splice(b.dataset.rm, 1); drawLines(); });
    total();
  };
  const total = () => { $d("#fTotal").textContent = usd(lines.reduce((a, l) => a + (+l.amount || 0), 0)); };
  document.querySelectorAll("[data-pkg]").forEach(b => b.onclick = () => { const p = PACKAGES.find(x => x.id === b.dataset.pkg); lines.push({ pkg: p.id, desc: p.id === "custom" ? "" : p.label + ": " + p.desc, amount: p.amount, ordering: !!p.ordering }); drawLines(); });
  drawLines();
  const s1 = sigPad($d("#sig1")); $d("#sig1c").onclick = () => s1.clear();
  const s2 = C ? sigPad($d("#sig2")) : null; if (s2) $d("#sig2c").onclick = () => s2.clear();
  $d("#fCancel").onclick = renderDeals;
  $d("#fMake").onclick = async () => {
    const v = id => ($d(id) ? $d(id).value.trim() : "");
    const err = t => { $d("#fErr").textContent = t; };
    const biz = v("#fBiz"), owner = v("#fOwner");
    if (!biz) return err("Add the client business name.");
    if (!lines.length || !lines.some(l => l.desc.trim())) return err("Add at least one service or item.");
    if (C && !owner) return err("Add the owner's name.");
    if (!s1.inked) return err(C ? "The client needs to sign." : "Sign the receipt.");
    if (C && !s2.inked) return err("Add the PXD2 representative's signature.");
    const totalAmt = lines.reduce((a, l) => a + (+l.amount || 0), 0), tradeVal = +v("#fTradeVal") || 0, cash = C ? 0 : +v("#fCash") || 0;
    const d = {
      id: uid(), kind, no: await nextNo(kind), date: today(), at: Date.now(), client: biz, owner, phone: v("#fPhone"), email: v("#fEmail"), addr: v("#fAddr"),
      lines: lines.map(l => ({ desc: l.desc.trim(), amount: +l.amount || 0, ordering: !!l.ordering })), total: totalAmt,
      terms: C ? v("#fTerms") : "", method: C ? "" : v("#fMethod"), cash, refNo: v("#fRefNo"), ref: v("#fRef"),
      tradeDesc: v("#fTrade"), trade: tradeVal, start: v("#fStart"), notes: v("#fNotes"), rep: v("#fRep") || S.dev, device: S.dev,
      sig1: s1.png(), sig2: s2 ? s2.png() : ""
    };
    d.balance = Math.max(0, totalAmt - cash - tradeVal);
    if (d.rep) kvSet("repName", d.rep);
    $d("#fMake").disabled = true; $d("#fMake").textContent = "making PDF…";
    try {
      const blob = makePdf(d);
      await kvSet("dealpdf:" + d.id, blob);
      const meta = Object.assign({}, d); delete meta.sig1; delete meta.sig2;
      const all = (await kvGet("deals")) || []; all.push({ id: d.id, kind, no: d.no, client: biz, total: totalAmt, trade: tradeVal, at: d.at, sent: false }); await kvSet("deals", all);
      await qPut({ id: d.id, t: Date.now(), type: "deal", kind, meta, blob, name: d.no + ".pdf" });
      drain(); renderDeals();
      window.open(URL.createObjectURL(blob), "_blank");
      toast(`${d.no} saved - sending to BASE1`);
    } catch (e) { err("Could not make the PDF: " + e.message); $d("#fMake").disabled = false; }
  };
  $d("#fBiz").focus();
}

// ---------------------------------------------------------------- PDF
function makePdf(d) {
  const { jsPDF } = window.jspdf; const doc = new jsPDF({ unit: "pt", format: "letter", compress: true });
  const W = 612, M = 54; let y = 56;
  const C = d.kind === "contract";
  const need = h => { if (y + h > 740) { doc.addPage(); y = 56; } };
  const text = (t, size = 10.5, style = "normal", gap = 4, x = M, w = W - 2 * M) => {
    doc.setFont("helvetica", style); doc.setFontSize(size);
    const ls = doc.splitTextToSize(String(t), w); need(ls.length * size * 1.25 + gap); doc.text(ls, x, y + size); y += ls.length * size * 1.25 + gap;
  };
  const rule = () => { need(10); doc.setDrawColor(200); doc.line(M, y, W - M, y); y += 10; };
  doc.setFillColor(17, 17, 17); doc.rect(0, 0, W, 6, "F");
  doc.setFont("helvetica", "bold"); doc.setFontSize(22); doc.text("PXD2", M, y + 18);
  doc.setFontSize(10); doc.text("ENTERPRISES", M + 62, y + 18);
  doc.setFontSize(9); doc.setFont("helvetica", "normal"); doc.text([PXD2.addr, PXD2.phone + " · " + PXD2.email, "Accounts: " + PXD2.cfo], W - M, y + 6, { align: "right" });
  y += 36;
  text(C ? "SERVICE AGREEMENT" : "RECEIPT", 16, "bold", 2);
  text(`${d.no}  ·  ${d.date}`, 10, "normal", 10);
  rule();
  text(C ? "Between" : "Received from", 9, "bold", 2);
  text(`${d.client}${d.owner ? " (" + d.owner + ")" : ""}`, 11.5, "bold", 2);
  text([d.addr, d.phone, d.email].filter(Boolean).join("  ·  ") || " ", 10, "normal", 6);
  if (C) { text("and", 9, "bold", 2); text(`${PXD2.name} (${PXD2.who}), ${PXD2.addr}. Billing and accounts: ${PXD2.cfo}.`, 10.5, "normal", 8); }
  if (d.ref) text(`For contract ${d.ref}`, 10, "normal", 6);
  rule();
  text(C ? "1. Services" : "Paid for", 11, "bold", 4);
  d.lines.forEach(l => {
    doc.setFont("helvetica", "normal"); doc.setFontSize(10.5);
    const ls = doc.splitTextToSize(l.desc || "-", W - 2 * M - 90); need(ls.length * 13 + 6);
    doc.text(ls, M, y + 10.5); doc.text(usd(l.amount), W - M, y + 10.5, { align: "right" }); y += ls.length * 13 + 6;
  });
  need(20); doc.setFont("helvetica", "bold"); doc.setFontSize(11.5); doc.text("Total", M, y + 12); doc.text(usd(d.total), W - M, y + 12, { align: "right" }); y += 24;
  if (C) {
    text("2. Price and payment", 11, "bold", 4);
    text(`Total price ${usd(d.total)}. Payment terms: ${d.terms}.` + (d.trade ? ` Trade: ${d.tradeDesc || "goods/services as described"}, agreed by both parties at a value of ${usd(d.trade)}, applied toward the total. Remaining balance payable in money: ${usd(Math.max(0, d.total - d.trade))}.` : ""), 10.5, "normal", 8);
    let n = 3;
    if (d.lines.some(l => l.ordering)) {
      text(`${n++}. Merchant and ordering-platform fees`, 11, "bold", 4);
      text("Card processing fees, online-ordering platform subscriptions and any other merchant fees are charged to the Client directly by the Client's own provider (for example Toast, Square or Clover) under the Client's agreement with that provider. PXD2 does not process the Client's customer payments, does not hold customer card data, and receives no portion of those fees.", 10.5, "normal", 8);
    }
    const sec = (t, b) => { text(`${n++}. ${t}`, 11, "bold", 4); text(b, 10.5, "normal", 8); };
    sec("What the Client provides", "Business details, menu/products and prices, photos or permission to take them, and any account access PXD2 needs to connect services. The Client reviews and approves the work before launch.");
    sec("Ownership", "The Client owns its business name, logo, content, photos, menu and customer data. PXD2 keeps ownership of its own code, templates and tools and grants the Client a license to use them for the Client's site for as long as the Client uses it.");
    sec("Changes and support", "Work listed above is included. Changes outside that list are quoted before they are done.");
    sec("Ending this agreement", "Either party may end this agreement in writing. Work delivered and payments earned up to that point stay due; payments for work already delivered are not refunded.");
    sec("Governing law", "This agreement is governed by the laws of the State of Arizona.");
    if (d.start) text(`Planned start date: ${d.start}`, 10.5, "normal", 6);
  } else {
    const paid = [];
    if (d.cash) paid.push(`${d.method.split(" + ")[0]} ${usd(d.cash)}${d.refNo ? " (" + d.refNo + ")" : ""}`);
    if (d.trade) paid.push(`Trade valued at ${usd(d.trade)}: ${d.tradeDesc || "goods/services"}`);
    text("Payment received", 11, "bold", 4);
    text(paid.join("\n") || d.method, 10.5, "normal", 6);
    need(18); doc.setFont("helvetica", "bold"); doc.setFontSize(11); doc.text("Balance remaining", M, y + 11); doc.text(usd(d.balance), W - M, y + 11, { align: "right" }); y += 22;
    if (d.trade) text("Trade note: both parties agree the traded goods/services have the value shown above. Keep this receipt for your records.", 9.5, "italic", 6);
    text(`Questions about this account: ${PXD2.cfo}, ${PXD2.name}, ${PXD2.phone}.`, 9.5, "normal", 6);
  }
  if (d.notes) { text("Notes", 11, "bold", 4); text(d.notes, 10.5, "normal", 8); }
  need(170); y += 6; rule();
  const sig = (label, name, png, x) => {
    if (png) doc.addImage(png, "JPEG", x, y, 220, 70);
    doc.setDrawColor(60); doc.line(x, y + 74, x + 220, y + 74);
    doc.setFont("helvetica", "normal"); doc.setFontSize(9); doc.text(`${label}: ${name || ""}`, x, y + 88); doc.text(`Date: ${d.date}`, x, y + 100);
  };
  if (C) { sig("Client", d.owner, d.sig1, M); sig("PXD2", d.rep, d.sig2, W - M - 220); }
  else sig("Received by (PXD2)", d.rep, d.sig1, M);
  y += 112;
  doc.setFontSize(8); doc.setTextColor(120);
  const pages = doc.getNumberOfPages();
  for (let i = 1; i <= pages; i++) { doc.setPage(i); doc.text(`${d.no} · page ${i} of ${pages}`, W / 2, 770, { align: "center" }); }
  return doc.output("blob");
}

loaders.deals = renderDeals;
window.dealSent = async id => { const all = (await kvGet("deals")) || []; const d = all.find(x => x.id === id); if (d) { d.sent = true; await kvSet("deals", all); if (curTab === "deals") renderDeals(); } };
