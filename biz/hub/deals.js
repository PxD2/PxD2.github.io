// PXD2 DESKTOP - DEALS: service contracts and receipts (cash, card, check, trade), e-signed on the tablet.
// One document model -> PDF, Word (.docx), HTML and plain text. Signed copies go sealed to BASE1, which files them,
// adds a ledger line and emails the PDF to the client with copies to every party.
"use strict";
const DEFAULT_CFG = {
  sellers: ["PXD2 Enterprises", "PXD2 Studios", "PXD2 Hosting", "PXD2 Data Systems"],
  founder: "Chad Aaron Peters", founderTitle: "Founder",
  head: "Angie Wood", headTitle: "CEO", headEmail: "pxd2angi@gmail.com",
  rep: "Angie Wood", repEmail: "pxd2angi@gmail.com", ownerEmail: "pxdsquared@gmail.com",   // 11/11: Angie is the rep and CEO for now
  addr: "PO Box 514, Concho, AZ 85924", phone: "928-457-6404", email: "pxdsquared@gmail.com"
};
const PACKAGES = [
  { id: "web", label: "Client website", amount: 500, desc: "Custom website for the business: design, build, mobile layout, hours/location/contact, QR code kit and print-ready pieces, launch on the Client's own .pxd name on the PXD2 network (free, no renewals), lifetime hosting by PXD2 with no monthly or yearly hosting fee, and a free in-game advertisement for the business on the Times Square ad screens in Global Theaters: Mud for Blood (limited spots, first signed first placed), carried into Rouge Racer: Route 66." },
  { id: "order", label: "Online ordering + full menu", amount: 1500, ordering: true, desc: "Online menu with current items and prices, connected to the Client's own online-ordering/point-of-sale provider for pickup orders, with Order buttons across the site, plus setup support and staff walkthrough." },
  { id: "custom", label: "Custom line", amount: 0, desc: "" }
];
const TERMS = ["Paid in full at signing", "50% deposit at signing, 50% at launch", "Paid in full at launch", "Trade (goods/services) for the full amount", "Part trade, part payment"];
const METHODS = ["Cash", "Check", "Card", "Trade", "Cash + trade", "Card + trade", "Check + trade"];
const $d = s => document.querySelector(s);
const usd = n => "$" + (Math.round((+n || 0) * 100) / 100).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
const today = () => new Date().toLocaleDateString("en-US", { timeZone: "America/Phoenix", year: "numeric", month: "long", day: "numeric" });
const cfg = async () => {
  const saved = (await kvGet("dealCfg")) || {};
  if (!saved.rep) saved.rep = "Angie Wood";
  if (!saved.headEmail) saved.headEmail = "pxd2angi@gmail.com";
  if (!saved.repEmail && /angie/i.test(saved.rep || "")) saved.repEmail = "pxd2angi@gmail.com";
  if (saved.v !== 2) { if (saved.headTitle === "CFO") saved.headTitle = "CEO"; if (/owner/i.test(saved.founderTitle || "")) saved.founderTitle = "Founder"; saved.v = 2; await kvSet("dealCfg", saved); }
  return Object.assign({}, DEFAULT_CFG, saved);
};
const emailsIn = s => String(s || "").split(/[,;\s]+/).map(x => x.trim()).filter(x => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(x));

function defaultClauses(ordering) {
  const c = [];
  if (ordering) c.push({ h: "Merchant and ordering-platform fees", b: "Card processing fees, online-ordering platform subscriptions and any other merchant fees are charged to the Client directly by the Client's own provider (for example Toast, Square or Clover) under the Client's agreement with that provider. PXD2 does not process the Client's customer payments, does not hold customer card data, and receives no portion of those fees." });
  c.push({ h: "Lifetime hosting", b: "PXD2 hosts the Client's website for the life of the site at no monthly or yearly hosting charge, included in the price above. The Client's .pxd name on the PXD2 network is included for life with no renewals. If the Client also chooses its own domain name (for example a .com), the domain registration is renewed by the Client with its registrar, and PXD2 connects it at no charge." });
  c.push({ h: "What the Client provides", b: "Business details, menu/products and prices, photos or permission to take them, and any account access PXD2 needs to connect services. The Client reviews and approves the work before launch." });
  c.push({ h: "Ownership", b: "The Client owns its business name, logo, content, photos, menu and customer data. PXD2 keeps ownership of its own code, templates and tools and grants the Client a license to use them for the Client's site for as long as the Client uses it." });
  c.push({ h: "Changes and support", b: "Work listed above is included. Changes outside that list are quoted before they are done." });
  c.push({ h: "Ending this agreement", b: "Either party may end this agreement in writing. Work delivered and payments earned up to that point stay due; payments for work already delivered are not refunded." });
  c.push({ h: "Electronic signatures and copies", b: "Both parties agree to sign electronically. An electronic signature and an emailed copy of this agreement have the same effect as a signed paper original." });
  c.push({ h: "Governing law", b: "This agreement is governed by the laws of the State of Arizona." });
  return c;
}

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
  const r0 = canvas.getBoundingClientRect(); canvas.width = r0.width * 2; canvas.height = r0.height * 2; ctx.scale(2, 2);
  ctx.lineWidth = 2.4; ctx.lineCap = "round"; ctx.strokeStyle = "#111";
  const pt = e => { const r = canvas.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
  canvas.onpointerdown = e => { down = true; last = pt(e); canvas.setPointerCapture(e.pointerId); };
  canvas.onpointermove = e => { if (!down) return; const p = pt(e); ctx.beginPath(); ctx.moveTo(...last); ctx.lineTo(...p); ctx.stroke(); last = p; inked = true; };
  canvas.onpointerup = canvas.onpointercancel = () => { down = false; };
  return {
    clear() { ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.clearRect(0, 0, canvas.width, canvas.height); ctx.scale(2, 2); inked = false; },
    get inked() { return inked; },
    jpg() { const c = document.createElement("canvas"); c.width = 440; c.height = 140; const x = c.getContext("2d"); x.fillStyle = "#fff"; x.fillRect(0, 0, 440, 140); x.drawImage(canvas, 0, 0, 440, 140); return c.toDataURL("image/jpeg", 0.8); }
  };
}

// ---------------------------------------------------------------- the document model (shared by every format)
function model(d) {
  const C = d.kind === "contract", B = [];
  B.push({ t: "brand", seller: d.seller, right: [d.co.addr, d.co.phone + " · " + d.co.email, `${d.co.founderTitle || "Founder"}: ${d.co.founder || "Chad Aaron Peters"}`, `${d.co.headTitle}: ${d.co.head}`] });
  B.push({ t: "title", text: C ? "SERVICE AGREEMENT" : "RECEIPT" }, { t: "meta", text: `${d.no}  ·  ${d.date}` }, { t: "rule" });
  B.push({ t: "label", text: C ? "Between" : "Received from" }, { t: "strong", text: `${d.client}${d.owner ? " (" + d.owner + ")" : ""}` });
  B.push({ t: "p", text: [d.addr, d.phone, d.email].filter(Boolean).join("  ·  ") || " " });
  if (C) { B.push({ t: "label", text: "and" }, { t: "p", text: `${d.seller}, founded by ${d.co.founder || "Chad Aaron Peters"}, represented by ${d.co.head}, ${d.co.headTitle}. ${d.co.addr}.` }); }
  if (d.ref) B.push({ t: "p", text: `For contract ${d.ref}` });
  B.push({ t: "rule" }, { t: "h", text: C ? "1. Services" : "Paid for" }, { t: "lines", lines: d.lines }, { t: "total", label: "Total", value: usd(d.total) });
  if (C) {
    B.push({ t: "h", text: "2. Price and payment" });
    B.push({ t: "p", text: `Total price ${usd(d.total)}. Payment terms: ${d.terms}.` + (d.trade ? ` Trade: ${d.tradeDesc || "goods/services as described"}, agreed by both parties at a value of ${usd(d.trade)}, applied toward the total. Remaining balance payable in money: ${usd(Math.max(0, d.total - d.trade))}.` : "") });
    (d.clauses || []).forEach((c, i) => { if (c.h || c.b) B.push({ t: "h", text: `${i + 3}. ${c.h}` }, { t: "p", text: c.b }); });
    if (d.start) B.push({ t: "p", text: `Planned start date: ${d.start}` });
  } else {
    const paid = [];
    if (d.cash) paid.push(`${d.method.split(" + ")[0]} ${usd(d.cash)}${d.refNo ? " (" + d.refNo + ")" : ""}`);
    if (d.trade) paid.push(`Trade valued at ${usd(d.trade)}: ${d.tradeDesc || "goods/services"}`);
    B.push({ t: "h", text: "Payment received" }, { t: "p", text: paid.join("\n") || d.method }, { t: "total", label: "Balance remaining", value: usd(d.balance) });
    if (d.trade) B.push({ t: "small", text: "Trade note: both parties agree the traded goods/services have the value shown above. Keep this receipt for your records." });
    B.push({ t: "small", text: `Questions about this account: ${d.co.head}, ${d.co.headTitle}, ${d.seller}, ${d.co.phone}.` });
  }
  if (d.notes) B.push({ t: "h", text: "Notes" }, { t: "p", text: d.notes });
  B.push({ t: "sigs", sigs: C ? [{ label: "Client", name: d.owner, img: d.sig1 }, { label: `For ${d.seller}`, name: d.rep, img: d.sig2 }] : [{ label: `Received for ${d.seller}`, name: d.rep, img: d.sig1 }], date: d.date });
  return B;
}

// ---------------------------------------------------------------- PDF
function toPDF(d) {
  const { jsPDF } = window.jspdf; const doc = new jsPDF({ unit: "pt", format: "letter", compress: true });
  const W = 612, M = 54; let y = 56;
  const need = h => { if (y + h > 740) { doc.addPage(); y = 56; } };
  const text = (t, size = 10.5, style = "normal", gap = 4) => {
    doc.setFont("helvetica", style); doc.setFontSize(size);
    const ls = doc.splitTextToSize(String(t), W - 2 * M); need(ls.length * size * 1.25 + gap); doc.text(ls, M, y + size); y += ls.length * size * 1.25 + gap;
  };
  doc.setFillColor(17, 17, 17); doc.rect(0, 0, W, 6, "F");
  for (const b of model(d)) {
    if (b.t === "brand") {
      doc.setFont("helvetica", "bold"); doc.setFontSize(20); doc.text(b.seller, M, y + 18);
      doc.setFontSize(9); doc.setFont("helvetica", "normal"); doc.text(b.right, W - M, y + 6, { align: "right" }); y += 40;
    } else if (b.t === "title") text(b.text, 16, "bold", 2);
    else if (b.t === "meta") text(b.text, 10, "normal", 10);
    else if (b.t === "rule") { need(10); doc.setDrawColor(200); doc.line(M, y, W - M, y); y += 10; }
    else if (b.t === "label") text(b.text, 9, "bold", 2);
    else if (b.t === "strong") text(b.text, 11.5, "bold", 2);
    else if (b.t === "h") text(b.text, 11, "bold", 4);
    else if (b.t === "p") text(b.text, 10.5, "normal", 8);
    else if (b.t === "small") text(b.text, 9.5, "italic", 6);
    else if (b.t === "lines") b.lines.forEach(l => {
      doc.setFont("helvetica", "normal"); doc.setFontSize(10.5);
      const ls = doc.splitTextToSize(l.desc || "-", W - 2 * M - 90); need(ls.length * 13 + 6);
      doc.text(ls, M, y + 10.5); doc.text(usd(l.amount), W - M, y + 10.5, { align: "right" }); y += ls.length * 13 + 6;
    });
    else if (b.t === "total") { need(22); doc.setFont("helvetica", "bold"); doc.setFontSize(11.5); doc.text(b.label, M, y + 12); doc.text(b.value, W - M, y + 12, { align: "right" }); y += 24; }
    else if (b.t === "sigs") {
      need(130); y += 6; doc.setDrawColor(200); doc.line(M, y, W - M, y); y += 10;
      b.sigs.forEach((s, i) => {
        const x = i ? W - M - 220 : M;
        if (s.img) doc.addImage(s.img, "JPEG", x, y, 220, 70);
        doc.setDrawColor(60); doc.line(x, y + 74, x + 220, y + 74);
        doc.setFont("helvetica", "normal"); doc.setFontSize(9); doc.text(`${s.label}: ${s.name || ""}`, x, y + 88); doc.text(`Signed electronically ${b.date}`, x, y + 100);
      });
      y += 112;
    }
  }
  doc.setFontSize(8); doc.setTextColor(120);
  const pages = doc.getNumberOfPages();
  for (let i = 1; i <= pages; i++) { doc.setPage(i); doc.text(`${d.no} · page ${i} of ${pages}`, W / 2, 770, { align: "center" }); }
  return doc.output("blob");
}

// ---------------------------------------------------------------- HTML
function toHTML(d) {
  const e = s => esc(s).replace(/\n/g, "<br>");
  const body = model(d).map(b => {
    if (b.t === "brand") return `<header><b>${e(b.seller)}</b><span>${b.right.map(e).join("<br>")}</span></header>`;
    if (b.t === "title") return `<h1>${e(b.text)}</h1>`;
    if (b.t === "meta") return `<p class="meta">${e(b.text)}</p>`;
    if (b.t === "rule") return `<hr>`;
    if (b.t === "label") return `<p class="label">${e(b.text)}</p>`;
    if (b.t === "strong") return `<p><strong>${e(b.text)}</strong></p>`;
    if (b.t === "h") return `<h2>${e(b.text)}</h2>`;
    if (b.t === "p") return `<p>${e(b.text)}</p>`;
    if (b.t === "small") return `<p class="small">${e(b.text)}</p>`;
    if (b.t === "lines") return `<table>${b.lines.map(l => `<tr><td>${e(l.desc)}</td><td class="amt">${usd(l.amount)}</td></tr>`).join("")}</table>`;
    if (b.t === "total") return `<table class="tot"><tr><td>${e(b.label)}</td><td class="amt">${e(b.value)}</td></tr></table>`;
    if (b.t === "sigs") return `<div class="sigs">${b.sigs.map(s => `<div>${s.img ? `<img src="${s.img}" alt="signature">` : ""}<div class="line"></div><p>${e(s.label)}: ${e(s.name || "")}<br>Signed electronically ${e(b.date)}</p></div>`).join("")}</div>`;
    return "";
  }).join("\n");
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${e(d.no)} · ${e(d.client)}</title>
<style>body{font:15px/1.55 Helvetica,Arial,sans-serif;color:#111;max-width:760px;margin:30px auto;padding:0 20px;border-top:6px solid #111}
header{display:flex;justify-content:space-between;align-items:flex-start;padding-top:16px}header b{font-size:26px}header span{text-align:right;font-size:12px;color:#444}
h1{font-size:22px;margin:18px 0 2px}h2{font-size:15px;margin:16px 0 4px}.meta{color:#555;margin:0 0 10px}.label{font-size:12px;font-weight:bold;margin:8px 0 0}
hr{border:0;border-top:1px solid #ccc;margin:12px 0}table{width:100%;border-collapse:collapse}td{padding:4px 0;vertical-align:top}.amt{text-align:right;white-space:nowrap;padding-left:16px}
.tot td{font-weight:bold;border-top:1px solid #ccc;padding-top:6px}.small{font-size:13px;font-style:italic;color:#444}
.sigs{display:flex;gap:30px;flex-wrap:wrap;margin-top:24px}.sigs>div{flex:1;min-width:240px}.sigs img{width:240px;height:76px;object-fit:contain}.line{border-top:1px solid #333;margin-top:2px}.sigs p{font-size:12px}
@media print{body{margin:0}}</style></head><body>
${body}
<p class="small" style="text-align:center;margin-top:30px">${e(d.no)}</p></body></html>`;
}

// ---------------------------------------------------------------- plain text
function toTXT(d) {
  const out = [], wrap = s => String(s).replace(/(.{1,76})(\s+|$)/g, "$1\n").trimEnd();
  for (const b of model(d)) {
    if (b.t === "brand") out.push(b.seller.toUpperCase(), ...b.right, "");
    else if (b.t === "title") out.push(b.text);
    else if (b.t === "meta") out.push(b.text, "");
    else if (b.t === "rule") out.push("-".repeat(70));
    else if (b.t === "label") out.push(b.text + ":");
    else if (b.t === "h") out.push("", b.text.toUpperCase());
    else if (["strong", "p", "small"].includes(b.t)) out.push(wrap(b.text));
    else if (b.t === "lines") b.lines.forEach(l => out.push(wrap(l.desc) + "\n" + " ".repeat(56) + usd(l.amount).padStart(14)));
    else if (b.t === "total") out.push(b.label.padEnd(56) + b.value.padStart(14));
    else if (b.t === "sigs") b.sigs.forEach(s => out.push("", `${s.label}: ${s.name || ""}  (signed electronically ${b.date})`));
  }
  return out.join("\n") + "\n";
}

// ---------------------------------------------------------------- Word (.docx), built with fflate
function toDOCX(d) {
  const x = s => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const run = (t, o = {}) => String(t).split("\n").map((ln, i) => `${i ? "<w:r><w:br/></w:r>" : ""}<w:r><w:rPr>${o.b ? "<w:b/>" : ""}${o.i ? "<w:i/>" : ""}<w:sz w:val="${(o.sz || 10.5) * 2}"/></w:rPr><w:t xml:space="preserve">${x(ln)}</w:t></w:r>`).join("");
  const para = (inner, o = {}) => `<w:p><w:pPr>${o.right ? '<w:jc w:val="right"/>' : ""}${o.tab ? '<w:tabs><w:tab w:val="right" w:pos="9360"/></w:tabs>' : ""}<w:spacing w:after="${o.after ?? 100}"/>${o.border ? '<w:pBdr><w:bottom w:val="single" w:sz="4" w:space="1" w:color="BBBBBB"/></w:pBdr>' : ""}</w:pPr>${inner}</w:p>`;
  const imgs = []; let body = "";
  const drawing = (rid, n) => `<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="2794000" cy="889000"/><wp:docPr id="${n}" name="sig${n}"/><a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:nvPicPr><pic:cNvPr id="${n}" name="sig${n}.jpeg"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="${rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="2794000" cy="889000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>`;
  for (const b of model(d)) {
    if (b.t === "brand") body += para(run(b.seller, { b: 1, sz: 20 }), { after: 0 }) + para(run(b.right.join("\n"), { sz: 9 }), { after: 200 });
    else if (b.t === "title") body += para(run(b.text, { b: 1, sz: 16 }), { after: 0 });
    else if (b.t === "meta") body += para(run(b.text, { sz: 10 }), { after: 120, border: 1 });
    else if (b.t === "rule") body += para("", { after: 60, border: 1 });
    else if (b.t === "label") body += para(run(b.text, { b: 1, sz: 9 }), { after: 0 });
    else if (b.t === "strong") body += para(run(b.text, { b: 1, sz: 11.5 }), { after: 40 });
    else if (b.t === "h") body += para(run(b.text, { b: 1, sz: 11 }), { after: 40 });
    else if (b.t === "p") body += para(run(b.text));
    else if (b.t === "small") body += para(run(b.text, { i: 1, sz: 9.5 }));
    else if (b.t === "lines") b.lines.forEach(l => { body += para(run(l.desc) + `<w:r><w:tab/></w:r>` + run(usd(l.amount)), { tab: 1 }); });
    else if (b.t === "total") body += para(run(b.label, { b: 1, sz: 11.5 }) + `<w:r><w:tab/></w:r>` + run(b.value, { b: 1, sz: 11.5 }), { tab: 1, after: 160 });
    else if (b.t === "sigs") b.sigs.forEach(s => {
      if (s.img) { imgs.push(s.img); body += para(drawing("rIdImg" + imgs.length, imgs.length), { after: 0 }); }
      body += para(run(`${s.label}: ${s.name || ""}\nSigned electronically ${b.date}`, { sz: 9 }), { after: 200, border: 0 });
    });
  }
  const docXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"><w:body>${body}<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1080" w:right="1080" w:bottom="1080" w:left="1080" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr></w:body></w:document>`;
  const enc = s => new TextEncoder().encode(s), b64 = s => Uint8Array.from(atob(s.split(",")[1]), c => c.charCodeAt(0));
  const files = {
    "[Content_Types].xml": enc(`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="jpeg" ContentType="image/jpeg"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>`),
    "_rels/.rels": enc(`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>`),
    "word/document.xml": enc(docXml),
    "word/_rels/document.xml.rels": enc(`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${imgs.map((_, i) => `<Relationship Id="rIdImg${i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/sig${i + 1}.jpeg"/>`).join("")}</Relationships>`)
  };
  imgs.forEach((im, i) => files[`word/media/sig${i + 1}.jpeg`] = b64(im));
  return new Blob([fflate.zipSync(files)], { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" });
}

// ---------------------------------------------------------------- exports
async function exportAs(id, fmt) {
  const d = await kvGet("dealdata:" + id); if (!d) return toast("this one was made before exports - only the PDF is saved");
  const map = { pdf: ["application/pdf", () => toPDF(d)], docx: ["", () => toDOCX(d)], html: ["text/html", () => new Blob([toHTML(d)], { type: "text/html" })], txt: ["text/plain", () => new Blob([toTXT(d)], { type: "text/plain" })] };
  const blob = map[fmt][1](), name = `${d.no} - ${d.client}.${fmt}`.replace(/[\\/:*?"<>|]+/g, "_");
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name; a.click();
}
async function shareDeal(id) {
  const d = await kvGet("dealdata:" + id), pdf = await kvGet("dealpdf:" + id);
  const f = new File([pdf], `${d ? d.no : "PXD2"}.pdf`, { type: "application/pdf" });
  if (navigator.canShare && navigator.canShare({ files: [f] })) {
    try { await navigator.share({ files: [f], title: f.name, text: d ? `${d.kind === "contract" ? "Service agreement" : "Receipt"} ${d.no} from ${d.seller}` : "" }); } catch (e) { }
  } else toast("this device can't share files - use the PDF button and attach it");
}

// ---------------------------------------------------------------- list + settings
async function renderDeals() {
  const list = ((await kvGet("deals")) || []).slice().reverse();
  $d("#dealsBody").innerHTML = `
    <div class="row" style="gap:10px;margin-bottom:12px"><button class="primary" id="dNewC">+ NEW CONTRACT</button><button class="primary" id="dNewR">+ NEW RECEIPT</button><button id="dSet" style="margin-left:auto">⚙ NAMES &amp; EMAILS</button></div>
    <div class="card"><h3>SIGNED ON THIS TABLET</h3><ul class="list">${list.map(d => `<li style="flex-wrap:wrap"><span class="n">${d.kind === "contract" ? "📝" : "🧾"} ${esc(d.no)} · ${esc(d.client)}</span>
      <span class="m">${usd(d.total)}${d.trade ? " · trade " + usd(d.trade) : ""} · ${d.sent ? "✓ at BASE1" : "sending…"}</span>
      <span class="row" style="gap:6px;width:100%">${["pdf", "docx", "html", "txt"].map(f => `<button data-x="${f}" data-id="${d.id}" style="min-height:32px;padding:4px 10px">${f === "docx" ? "WORD" : f.toUpperCase()}</button>`).join("")}<button data-share="${d.id}" style="min-height:32px;padding:4px 10px">SHARE</button></span></li>`).join("") || `<li class="dim">No contracts or receipts yet.</li>`}</ul></div>
    <p class="dim" style="font-size:12px">Contract wording is a plain-language PXD2 template you can edit per deal. Have an advisor review it before relying on it for large jobs.</p>`;
  $d("#dNewC").onclick = () => form("contract");
  $d("#dNewR").onclick = () => form("receipt");
  $d("#dSet").onclick = settings;
  document.querySelectorAll("[data-x]").forEach(b => b.onclick = async () => {
    if (b.dataset.x === "pdf") { const blob = await kvGet("dealpdf:" + b.dataset.id); if (blob) { window.open(URL.createObjectURL(blob), "_blank"); return; } }
    exportAs(b.dataset.id, b.dataset.x);
  });
  document.querySelectorAll("[data-share]").forEach(b => b.onclick = () => shareDeal(b.dataset.share));
}

async function settings() {
  const c = await cfg();
  $d("#dealsBody").innerHTML = `<div class="card"><h3>NAMES &amp; EMAILS</h3>
    <label>OUR BUSINESS NAMES (one per line - pick one on each sale)</label><textarea id="sSell" style="min-height:90px">${esc(c.sellers.join("\n"))}</textarea>
    <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px">
      <div><label>FOUNDER / OWNER</label><input id="sFnd" value="${esc(c.founder || "Chad Aaron Peters")}"></div>
      <div><label>FOUNDER TITLE</label><input id="sFndT" value="${esc(c.founderTitle || "Founder")}"></div>
      <div><label>RUNS THE BUSINESS (signs for PXD2)</label><input id="sHead" value="${esc(c.head)}"></div>
      <div><label>TITLE</label><input id="sHeadT" value="${esc(c.headTitle)}"></div>
      <div><label>HEAD'S EMAIL (gets a copy of every deal)</label><input id="sHeadE" type="email" value="${esc(c.headEmail)}"></div>
      <div><label>YOUR NAME (rep)</label><input id="sRep" value="${esc(c.rep)}"></div>
      <div><label>YOUR EMAIL (gets a copy)</label><input id="sRepE" type="email" value="${esc(c.repEmail)}"></div>
      <div><label>OWNER EMAIL (gets a copy)</label><input id="sOwnE" type="email" value="${esc(c.ownerEmail)}"></div>
      <div><label>BUSINESS PHONE</label><input id="sPh" value="${esc(c.phone)}"></div>
      <div><label>BUSINESS EMAIL</label><input id="sEm" value="${esc(c.email)}"></div>
    </div>
    <label>BUSINESS ADDRESS</label><input id="sAddr" value="${esc(c.addr)}">
    <div class="row" style="gap:10px;margin-top:14px"><button class="primary" id="sSave">SAVE</button><button id="sBack">Back</button></div></div>`;
  $d("#sBack").onclick = renderDeals;
  $d("#sSave").onclick = async () => {
    const v = id => $d(id).value.trim();
    await kvSet("dealCfg", { v: 2, founder: v("#sFnd"), founderTitle: v("#sFndT"), sellers: v("#sSell").split("\n").map(s => s.trim()).filter(Boolean), head: v("#sHead"), headTitle: v("#sHeadT"), headEmail: v("#sHeadE"),
      rep: v("#sRep"), repEmail: v("#sRepE"), ownerEmail: v("#sOwnE"), phone: v("#sPh"), email: v("#sEm"), addr: v("#sAddr") });
    toast("saved"); renderDeals();
  };
}

// ---------------------------------------------------------------- the form
async function form(kind) {
  const co = await cfg(), names = await clientNames();
  const contracts = ((await kvGet("deals")) || []).filter(d => d.kind === "contract");
  const C = kind === "contract";
  $d("#dealsBody").innerHTML = `
    <div class="card">
      <h3>${C ? "NEW SERVICE CONTRACT" : "NEW RECEIPT"}</h3>
      <label>SELLING AS</label><input id="fSeller" list="fSellerList" value="${esc(co.sellers[0] || "PXD2 Enterprises")}"><datalist id="fSellerList">${co.sellers.map(n => `<option value="${esc(n)}">`).join("")}</datalist>
      <label>CLIENT BUSINESS</label><input id="fBiz" list="fBizList" placeholder="Business name"><datalist id="fBizList">${names.map(n => `<option value="${esc(n)}">`).join("")}</datalist>
      <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px">
        <div><label>OWNER / SIGNER NAME</label><input id="fOwner" autocomplete="off"></div>
        <div><label>PHONE</label><input id="fPhone" type="tel"></div>
        <div><label>CLIENT EMAIL (gets the signed copy)</label><input id="fEmail" type="email"></div>
      </div>
      <label>BUSINESS ADDRESS</label><input id="fAddr">
      ${C ? "" : `<label>FOR CONTRACT (optional)</label><select id="fRef"><option value="">none</option>${contracts.map(c => `<option value="${esc(c.no)}">${esc(c.no)} · ${esc(c.client)} · ${usd(c.total)}</option>`).join("")}</select>`}
      <label>${C ? "SERVICES" : "WHAT WAS PAID FOR"}</label>
      <div id="fLines"></div>
      <div class="row" style="gap:8px;margin-top:6px">${PACKAGES.map(p => `<button type="button" data-pkg="${p.id}" style="min-height:36px;padding:6px 12px">+ ${esc(p.label)}${p.amount ? " " + usd(p.amount) : ""}</button>`).join("")}</div>
      <div class="big" style="margin-top:12px">Total <span id="fTotal">$0.00</span></div>
      ${C ? `<label>PAYMENT TERMS</label><input id="fTerms" list="fTermsList" value="${esc(TERMS[0])}"><datalist id="fTermsList">${TERMS.map(t => `<option value="${esc(t)}">`).join("")}</datalist>`
          : `<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px">
               <div><label>PAID WITH</label><select id="fMethod">${METHODS.map(t => `<option>${esc(t)}</option>`).join("")}</select></div>
               <div><label>MONEY RECEIVED ($)</label><input id="fCash" type="number" inputmode="decimal" min="0" step="0.01" value="0"></div>
               <div><label>CHECK # / CARD LAST 4</label><input id="fRefNo"></div>
             </div>`}
      <label>TRADE: WHAT IS BEING TRADED (goods or services)</label><input id="fTrade" placeholder="e.g. 3 antique display cases, delivered">
      <label>TRADE: AGREED VALUE ($)</label><input id="fTradeVal" type="number" inputmode="decimal" min="0" step="0.01" value="0">
      ${C ? `<label>START DATE</label><input id="fStart" type="date">
      <h3 style="margin-top:18px">CONTRACT TERMS (edit anything for this deal)</h3><div id="fClauses"></div>
      <button type="button" id="fAddCl" style="min-height:34px;padding:4px 12px">+ Add a term</button>` : ""}
      <label>NOTES</label><textarea id="fNotes" style="min-height:70px"></textarea>
      <label>EMAIL COPIES ALSO TO (optional, comma separated)</label><input id="fCc" placeholder="partner@example.com">
      <label style="display:flex;gap:8px;align-items:center;margin-top:10px"><input type="checkbox" id="fMail" checked style="width:auto"> Email the signed copy to the client, ${esc(co.head)} (${esc(co.headTitle)}), you, and the owner</label>
      <label>${C ? "CLIENT SIGNATURE" : "RECEIVED BY (PXD2) SIGNATURE"}</label>
      <canvas id="sig1" style="width:100%;height:140px;background:#fff;border-radius:8px;touch-action:none"></canvas>
      <div class="row" style="gap:8px"><button type="button" id="sig1c" style="min-height:32px;padding:4px 10px">Clear</button><span class="dim" style="font-size:12px">sign with a finger or stylus</span></div>
      <label>PXD2 REPRESENTATIVE NAME</label><input id="fRep" value="${esc(co.rep)}" placeholder="Your name">
      ${C ? `<label>PXD2 REPRESENTATIVE SIGNATURE</label>
      <canvas id="sig2" style="width:100%;height:140px;background:#fff;border-radius:8px;touch-action:none"></canvas>
      <div class="row" style="gap:8px"><button type="button" id="sig2c" style="min-height:32px;padding:4px 10px">Clear</button></div>` : ""}
      <p id="fErr" class="bad" style="min-height:1em;margin-top:8px"></p>
      <div class="row" style="gap:10px;margin-top:6px"><button class="primary" id="fMake">${C ? "SIGN &amp; SAVE CONTRACT" : "SAVE RECEIPT"}</button><button id="fCancel">Cancel</button></div>
    </div>`;
  const lines = [];
  let clauses = C ? defaultClauses(false) : [];
  const drawClauses = () => {
    if (!C) return;
    $d("#fClauses").innerHTML = clauses.map((c, i) => `<div class="card" style="padding:10px;margin-bottom:8px">
      <div class="row" style="gap:8px;flex-wrap:nowrap"><input data-ci="${i}" data-ck="h" value="${esc(c.h)}" style="font-weight:700"><button type="button" data-crm="${i}" style="min-height:36px;padding:4px 10px">✕</button></div>
      <textarea data-ci="${i}" data-ck="b" style="min-height:70px;margin-top:6px">${esc(c.b)}</textarea></div>`).join("");
    $d("#fClauses").querySelectorAll("[data-ck]").forEach(el => el.oninput = () => { clauses[el.dataset.ci][el.dataset.ck] = el.value; });
    $d("#fClauses").querySelectorAll("[data-crm]").forEach(b => b.onclick = () => { clauses.splice(b.dataset.crm, 1); drawClauses(); });
  };
  const syncOrdering = () => {
    if (!C) return;
    const want = lines.some(l => l.ordering), has = clauses.some(c => /merchant/i.test(c.h));
    if (want && !has) { clauses = defaultClauses(true).slice(0, 1).concat(clauses); drawClauses(); }
  };
  const drawLines = () => {
    $d("#fLines").innerHTML = lines.map((l, i) => `<div class="row" style="gap:8px;margin-bottom:8px;flex-wrap:nowrap;align-items:flex-start">
      <textarea data-i="${i}" data-k="desc" style="min-height:52px;flex:1">${esc(l.desc)}</textarea>
      <input data-i="${i}" data-k="amount" type="number" inputmode="decimal" step="0.01" value="${l.amount}" style="width:120px">
      <button type="button" data-rm="${i}" style="min-height:40px;padding:4px 10px">✕</button></div>`).join("") || `<p class="dim">Add a package below.</p>`;
    $d("#fLines").querySelectorAll("[data-k]").forEach(el => el.oninput = () => { lines[el.dataset.i][el.dataset.k] = el.dataset.k === "amount" ? +el.value || 0 : el.value; total(); });
    $d("#fLines").querySelectorAll("[data-rm]").forEach(b => b.onclick = () => { lines.splice(b.dataset.rm, 1); drawLines(); });
    total(); syncOrdering();
  };
  const total = () => { $d("#fTotal").textContent = usd(lines.reduce((a, l) => a + (+l.amount || 0), 0)); };
  document.querySelectorAll("[data-pkg]").forEach(b => b.onclick = () => { const p = PACKAGES.find(x => x.id === b.dataset.pkg); lines.push({ desc: p.id === "custom" ? "" : p.label + ": " + p.desc, amount: p.amount, ordering: !!p.ordering }); drawLines(); });
  if (C) $d("#fAddCl").onclick = () => { clauses.push({ h: "New term", b: "" }); drawClauses(); };
  drawLines(); drawClauses();
  const s1 = sigPad($d("#sig1")); $d("#sig1c").onclick = () => s1.clear();
  const s2 = C ? sigPad($d("#sig2")) : null; if (s2) $d("#sig2c").onclick = () => s2.clear();
  $d("#fCancel").onclick = renderDeals;
  $d("#fMake").onclick = async () => {
    const v = id => ($d(id) ? $d(id).value.trim() : "");
    const err = t => { $d("#fErr").textContent = t; };
    const biz = v("#fBiz"), owner = v("#fOwner"), seller = v("#fSeller") || "PXD2 Enterprises";
    if (!biz) return err("Add the client business name.");
    if (!lines.length || !lines.some(l => l.desc.trim())) return err("Add at least one service or item.");
    if (C && !owner) return err("Add the owner's name.");
    if (v("#fEmail") && !emailsIn(v("#fEmail")).length) return err("The client email doesn't look right.");
    if (!s1.inked) return err(C ? "The client needs to sign." : "Sign the receipt.");
    if (C && !s2.inked) return err("Add the PXD2 representative's signature.");
    const totalAmt = lines.reduce((a, l) => a + (+l.amount || 0), 0), tradeVal = +v("#fTradeVal") || 0, cash = C ? 0 : +v("#fCash") || 0;
    const d = {
      id: uid(), kind, no: await nextNo(kind), date: today(), at: Date.now(), seller, co,
      client: biz, owner, phone: v("#fPhone"), email: v("#fEmail"), addr: v("#fAddr"),
      lines: lines.map(l => ({ desc: l.desc.trim(), amount: +l.amount || 0, ordering: !!l.ordering })), total: totalAmt,
      terms: C ? v("#fTerms") : "", method: C ? "" : v("#fMethod"), cash, refNo: v("#fRefNo"), ref: v("#fRef"),
      tradeDesc: v("#fTrade"), trade: tradeVal, start: v("#fStart"), notes: v("#fNotes"), rep: v("#fRep") || S.dev, device: S.dev,
      clauses: C ? clauses.filter(c => c.h.trim() || c.b.trim()) : [], sig1: s1.jpg(), sig2: s2 ? s2.jpg() : ""
    };
    d.balance = Math.max(0, totalAmt - cash - tradeVal);
    const mail = $d("#fMail").checked ? { to: emailsIn(d.email), cc: [...new Set(emailsIn([co.headEmail, co.repEmail, co.ownerEmail, v("#fCc")].join(",")))] } : null;
    if (d.rep && d.rep !== co.rep) kvSet("dealCfg", Object.assign({}, co, { rep: d.rep }));
    $d("#fMake").disabled = true; $d("#fMake").textContent = "making PDF…";
    try {
      const blob = toPDF(d);
      await kvSet("dealpdf:" + d.id, blob); await kvSet("dealdata:" + d.id, d);
      const meta = Object.assign({}, d, { mail }); delete meta.sig1; delete meta.sig2;
      const all = (await kvGet("deals")) || []; all.push({ id: d.id, kind, no: d.no, client: biz, total: totalAmt, trade: tradeVal, at: d.at, sent: false }); await kvSet("deals", all);
      await qPut({ id: d.id, t: Date.now(), type: "deal", kind, meta, blob, name: d.no + ".pdf" });
      drain(); renderDeals();
      window.open(URL.createObjectURL(blob), "_blank");
      toast(`${d.no} saved - BASE1 files it${mail && (mail.to.length || mail.cc.length) ? " and emails every party" : ""}`);
    } catch (e) { err("Could not make the PDF: " + e.message); $d("#fMake").disabled = false; $d("#fMake").textContent = "TRY AGAIN"; }
  };
  $d("#fBiz").focus();
}

loaders.deals = renderDeals;
window.dealSent = async id => { const all = (await kvGet("deals")) || []; const d = all.find(x => x.id === id); if (d) { d.sent = true; await kvSet("deals", all); if (curTab === "deals") renderDeals(); } };

// 11/11 same-day close: a lead on the LEADS tab opens a contract already filled in (business, phone, address, packages)
window.dealFromLead = async x => {
  goTab("deals"); await new Promise(r => setTimeout(r, 150));
  await form("contract");
  const set = (id, v) => { const e = $d(id); if (e && v) { e.value = v; e.dispatchEvent(new Event("input")); } };
  set("#fBiz", x.n); set("#fPhone", x.p); set("#fAddr", [x.a, x.t].filter(Boolean).join(", "));
  const pk = id => { const b = document.querySelector(`[data-pkg="${id}"]`); if (b) b.click(); };
  pk("web"); if (/ordering/i.test(x.o || "")) pk("order");
  window.scrollTo({ top: 0 });
};

// ---------------------------------------------------------------- 11/11 PXD2 SIGN-UP KIOSK (?kiosk=1): no rep needed. A business owner picks a
// site, fills in their details and signs on the touch screen (the R2 Pi kiosk, a tablet on a counter, any PC). The signed
// contract goes to BASE1 like a rep's, marked "awaiting PXD2 countersignature", and every party gets the email copy.
const KIOSK_PLANS = [
  { id: "site", name: "Website", price: 500, tag: "No menu",
    pts: ["Phone-first site in your own look", "Hours, directions, tap-to-call", "QR code kit + print-ready pieces", "Hosted for life, your own .pxd name", "Free ad in Mud for Blood (32 spots)"], pkgs: ["web"] },
  { id: "menu", name: "Website + menu & online ordering", price: 2000, tag: "Restaurants",
    pts: ["Everything in Website", "Your full menu with prices", "Order button tied to your own ordering system", "Card fees stay with your provider", "Free ad in Mud for Blood (32 spots)"], pkgs: ["web", "order"] }];
async function kiosk() {
  const box = $d("#kioskBody"); let plan = null, step = 0, idle = null;
  const reset = () => { clearTimeout(idle); idle = setTimeout(() => { plan = null; step = 0; draw(); }, 180000); };
  ["pointerdown", "keydown"].forEach(ev => box.addEventListener(ev, reset));
  const big = "font-size:22px;min-height:64px;padding:14px 26px";
  function draw() {
    reset();
    if (step === 0) box.innerHTML = `<div style="text-align:center;padding:6vh 4vw">
      <img src="pxd2-logo.png" alt="PXD2 Studios" style="height:90px">
      <h1 style="font-size:clamp(36px,6vw,64px);margin:18px 0 6px;font-style:italic;text-transform:uppercase;letter-spacing:-.01em">Your business online today</h1>
      <p style="font-size:22px;color:var(--dim);margin:0 0 30px">Pick a site, sign here, and PXD2 builds it. Hosted for life, no monthly bill.</p>
      <div class="row" style="justify-content:center;gap:14px"><button class="primary" id="kGo" style="${big}">START</button><button id="kEx" style="${big}">SEE EXAMPLES</button></div></div>`;
    if (step === 0) { $d("#kGo").onclick = () => { step = 1; draw(); }; $d("#kEx").onclick = examples; return; }
    if (step === 1) {
      box.innerHTML = `<h2 style="font-size:32px;margin:10px 0 18px;text-align:center">1 · Pick your site</h2>
        <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px">${KIOSK_PLANS.map(p => `<button data-plan="${p.id}" style="text-align:left;padding:24px;min-height:340px;border-radius:18px;border:2px solid ${plan === p.id ? "var(--red)" : "var(--line)"};background:var(--panel)">
          <div style="color:var(--dim);font-size:15px;letter-spacing:.1em;text-transform:uppercase">${esc(p.tag)}</div>
          <div style="font-size:28px;font-weight:800;margin:6px 0">${esc(p.name)}</div>
          <div style="font-size:52px;font-weight:900;font-style:italic;color:var(--acc)">${usd(p.price).replace(".00", "")}</div>
          <div style="font-size:15px;color:var(--dim);margin-bottom:10px">one time</div>
          <ul style="font-size:18px;line-height:1.6;padding-left:20px;margin:0">${p.pts.map(x => `<li>${esc(x)}</li>`).join("")}</ul></button>`).join("")}</div>
        <div class="row" style="justify-content:space-between;margin-top:20px"><button id="kBack" style="${big}">Back</button><button class="primary" id="kNext" style="${big}" ${plan ? "" : "disabled"}>NEXT</button></div>`;
      box.querySelectorAll("[data-plan]").forEach(b => b.onclick = () => { plan = b.dataset.plan; draw(); });
    }
    if (step === 2) {
      box.innerHTML = `<h2 style="font-size:32px;margin:10px 0 18px;text-align:center">2 · About your business</h2>
        <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px;font-size:18px">
          ${[["kBiz", "Business name", "text"], ["kOwner", "Your name (owner / signer)", "text"], ["kPhone", "Phone", "tel"], ["kEmail", "Email (your signed copy goes here)", "email"], ["kAddr", "Business address", "text"], ["kWhat", "What do you sell or do?", "text"]].map(([id, l, t]) =>
            `<div><label style="font-size:15px">${l}</label><input id="${id}" type="${t}" style="font-size:20px;min-height:56px" value="${esc((kiosk.data || {})[id] || "")}"></div>`).join("")}</div>
        <p id="kErr" class="bad" style="font-size:18px;min-height:1.2em"></p>
        <div class="row" style="justify-content:space-between;margin-top:10px"><button id="kBack" style="${big}">Back</button><button class="primary" id="kNext" style="${big}">NEXT</button></div>`;
    }
    if (step === 3) {
      const P = KIOSK_PLANS.find(p => p.id === plan), D = kiosk.data;
      box.innerHTML = `<h2 style="font-size:32px;margin:10px 0 18px;text-align:center">3 · Review and sign</h2>
        <div class="card" style="font-size:19px;line-height:1.6"><b>${esc(D.kBiz)}</b> · ${esc(D.kOwner)}<br>${esc(P.name)}: <b>${usd(P.price)}</b> one time. Angie Wood, PXD2's CEO, will call you to arrange payment: cash, card, check or part trade.
          <br>Includes lifetime hosting, your own .pxd name, and a free ad in Global Theaters: Mud for Blood while spots last.
          <details style="margin-top:8px"><summary style="cursor:pointer">Read the full terms</summary><div style="font-size:15px;color:var(--dim)">${defaultClauses(plan === "menu").map(c => `<p><b>${esc(c.h)}.</b> ${esc(c.b)}</p>`).join("")}</div></details></div>
        <label style="display:flex;gap:10px;align-items:center;font-size:18px;margin:8px 0"><input type="checkbox" id="kTradeOn" style="width:28px;height:28px"> I'd like to pay part of it in trade (goods or services)</label>
        <input id="kTrade" placeholder="What could you trade? e.g. meals, display cases, repairs" style="font-size:18px;min-height:52px;display:none">
        <label style="font-size:16px">Sign with your finger</label>
        <canvas id="kSig" style="width:100%;height:200px;background:#fff;border-radius:12px;touch-action:none"></canvas>
        <div class="row" style="gap:10px;margin-top:8px"><button id="kClr" style="${big}">Clear</button><label style="display:flex;gap:10px;align-items:center;font-size:18px;margin:0"><input type="checkbox" id="kAgree" style="width:28px;height:28px"> I agree to these terms</label></div>
        <p id="kErr" class="bad" style="font-size:18px;min-height:1.2em"></p>
        <div class="row" style="justify-content:space-between"><button id="kBack" style="${big}">Back</button><button class="primary" id="kNext" style="${big}">SIGN UP</button></div>`;
      kiosk.sig = sigPad($d("#kSig")); $d("#kClr").onclick = () => kiosk.sig.clear();
      $d("#kTradeOn").onchange = e => { $d("#kTrade").style.display = e.target.checked ? "block" : "none"; };
    }
    if (step === 4) {
      box.innerHTML = `<div style="text-align:center;padding:8vh 4vw"><div style="font-size:72px">✓</div>
        <h1 style="font-size:44px;margin:10px 0">You're signed up!</h1>
        <p style="font-size:22px;color:var(--dim)">A copy of your agreement is on its way to your email. Angie Wood from PXD2 will call you to take payment, set up any trade, and get your photos so we can start building.<br>Questions: 928-457-6404</p>
        <button class="primary" id="kDone" style="${big};margin-top:24px">DONE</button></div>`;
      $d("#kDone").onclick = () => { kiosk.data = {}; plan = null; step = 0; draw(); };
      return;
    }
    const back = $d("#kBack"), next = $d("#kNext");
    if (back) back.onclick = () => { step--; draw(); };
    if (next) next.onclick = async () => {
      const err = t => { $d("#kErr").textContent = t; };
      if (step === 1 && !plan) return;
      if (step === 2) {
        const g = id => $d("#" + id).value.trim(); kiosk.data = {}; ["kBiz", "kOwner", "kPhone", "kEmail", "kAddr", "kWhat"].forEach(id => kiosk.data[id] = g(id));
        if (!kiosk.data.kBiz) return err("Please add your business name.");
        if (!kiosk.data.kOwner) return err("Please add your name.");
        if (!kiosk.data.kPhone && !kiosk.data.kEmail) return err("Please add a phone or email so we can reach you.");
        if (kiosk.data.kEmail && !emailsIn(kiosk.data.kEmail).length) return err("That email doesn't look right.");
      }
      if (step === 3) {
        if (!kiosk.sig.inked) return err("Please sign in the white box.");
        if (!$d("#kAgree").checked) return err("Please tick 'I agree'.");
        kiosk.data.kTrade = $d("#kTradeOn").checked ? ($d("#kTrade").value.trim() || "wants to discuss a trade") : "";
        next.disabled = true; next.textContent = "SAVING…";
        try { await kioskDeal(plan, kiosk.data, kiosk.sig.jpg()); } catch (e) { next.disabled = false; next.textContent = "SIGN UP"; return err("Something went wrong saving - please ask staff. (" + (e.message || e) + ")"); }
      }
      step++; draw();
    };
  }
  function examples() {
    const ex = [["Restaurant", "stanfordstore"], ["Antique shop", "bearwallow"], ["Laundry & showers", "scrubhub"], ["Contractor", "reddirt"]];
    box.innerHTML = `<div class="row" style="gap:10px;margin-bottom:10px">${ex.map(([l, n], i) => `<button data-ex="${n}" style="${big}"${i ? "" : ' class="primary"'}>${l}</button>`).join("")}<span style="flex:1"></span><button id="kExDone" style="${big}">START MY SITE</button></div>
      <iframe id="kFrame" src="https://pxd2.github.io/${ex[0][1]}/" style="width:100%;height:78vh;border:0;border-radius:14px;background:#fff"></iframe>`;
    box.querySelectorAll("[data-ex]").forEach(b => b.onclick = () => { $d("#kFrame").src = `https://pxd2.github.io/${b.dataset.ex}/`; box.querySelectorAll("[data-ex]").forEach(x => x.classList.toggle("primary", x === b)); });
    $d("#kExDone").onclick = () => { step = 1; draw(); };
  }
  draw();
}
async function kioskDeal(planId, D, sigJpg) {
  const co = await cfg(), P = KIOSK_PLANS.find(p => p.id === planId);
  const lines = P.pkgs.map(id => { const k = PACKAGES.find(x => x.id === id); return { desc: k.label + ": " + k.desc, amount: k.amount, ordering: !!k.ordering }; });
  const total = lines.reduce((a, l) => a + l.amount, 0);
  const d = { id: uid(), kind: "contract", no: await nextNo("contract"), date: today(), at: Date.now(), seller: co.sellers[0] || "PXD2 Enterprises", co,
    client: D.kBiz, owner: D.kOwner, phone: D.kPhone, email: D.kEmail, addr: D.kAddr, lines, total, terms: D.kTrade ? "Part trade, part payment - arranged with Angie Wood (CEO)" : "Paid to PXD2 (Angie Wood, CEO) - cash, card or check, arranged after signing", method: "", cash: 0, refNo: "", ref: "",
    tradeDesc: D.kTrade || "", trade: 0, start: "", notes: `Signed by the client at the PXD2 sign-up kiosk (${S.dev}). Business: ${D.kWhat || "-"}.${D.kTrade ? " Trade offered: " + D.kTrade + " (value to be agreed with Angie)." : ""} Awaiting countersignature by ${co.rep || co.head} (${co.headTitle}).`,
    rep: `${co.rep || co.head} (awaiting countersignature)`, device: S.dev, clauses: defaultClauses(P.pkgs.includes("order")), sig1: sigJpg, sig2: "" };
  d.balance = total;
  const mail = { to: emailsIn(d.email), cc: [...new Set(emailsIn([co.headEmail, co.repEmail, co.ownerEmail].join(",")))] };
  const blob = toPDF(d);
  const meta = Object.assign({}, d, { mail, kiosk: 1 }); delete meta.sig1; delete meta.sig2;
  await qPut({ id: d.id, t: Date.now(), type: "deal", kind: "contract", meta, blob, name: d.no + ".pdf" });
  drain();
}
loaders.kiosk = kiosk;
if (new URLSearchParams(location.search).get("kiosk")) {
  document.body.classList.add("kiosk");
  const go = () => { if (!S.key) return setTimeout(go, 800); goTab("kiosk"); };
  setTimeout(go, 400);
}
