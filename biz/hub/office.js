// PXD2 OFFICE - the native multi-OS suite: WRITE (docs), SHEETS (spreadsheets), SLIDES (presentations).
// Runs offline on Windows, ChromeOS, Android, iOS and Linux (installable web app). Saves on the device; opens and exports
// Word (.docx), Excel (.xlsx / .csv) and PowerPoint (.pptx). Inside the PXD2 app it can also send any file to BASE1.
(function () {
  "use strict";
  const Q = s => document.querySelector(s), QA = s => [...document.querySelectorAll(s)];
  const H = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const say = t => (window.toast ? window.toast(t) : console.log(t));
  const rid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7);

  // ---------------------------------------------------------------- storage (its own IndexedDB, works with or without the PXD2 app)
  const DB = new Promise((ok, bad) => { const r = indexedDB.open("pxd2office", 1); r.onupgradeneeded = () => r.result.createObjectStore("files", { keyPath: "id" }); r.onsuccess = () => ok(r.result); r.onerror = () => bad(r.error); });
  const tx = async (mode, fn) => { const db = await DB; return new Promise((ok, bad) => { const t = db.transaction("files", mode); const r = fn(t.objectStore("files")); t.oncomplete = () => ok(r && r.result); t.onerror = () => bad(t.error); }); };
  const fput = f => tx("readwrite", s => s.put(Object.assign(f, { updated: Date.now() })));
  const fget = id => tx("readonly", s => s.get(id));
  const fall = () => tx("readonly", s => s.getAll());
  const fdel = id => tx("readwrite", s => s.delete(id));

  function download(blob, name) {
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1500);
  }
  async function toBase(blob, name) {
    if (typeof window.addFiles === "function") { await window.addFiles([new File([blob], name)], { root: "", dir: "" }); say(`${name} queued for BASE1`); }
    else download(blob, name);
  }
  async function share(blob, name, mime) {
    const f = new File([blob], name, { type: mime });
    if (navigator.canShare && navigator.canShare({ files: [f] })) { try { await navigator.share({ files: [f], title: name }); return; } catch (e) { } }
    download(blob, name);
  }

  let cur = null;   // the open file
  const root = () => Q("#officeBody");

  // ---------------------------------------------------------------- home: file list + new / open
  async function home() {
    cur = null;
    const files = (await fall()).sort((a, b) => b.updated - a.updated);
    const icon = { doc: "📝", sheet: "📊", deck: "📽" };
    root().innerHTML = `<div class="card">
      <h3>PXD2 OFFICE <span class="dim" style="letter-spacing:0;font-weight:400">· works offline · opens and saves Word, Excel and PowerPoint</span></h3>
      <div class="row" style="gap:8px"><button class="primary" data-new="doc">📝 New document</button><button class="primary" data-new="sheet">📊 New spreadsheet</button><button class="primary" data-new="deck">📽 New presentation</button>
        <label class="btn">📂 Open a file<input type="file" id="ofOpen" accept=".docx,.xlsx,.xls,.csv,.ods,.txt,.md,.html,.htm" class="hide"></label></div>
      <div class="row" style="gap:8px;margin-top:8px"><button data-tpl="pitch">⭐ $500 pitch deck</button>${window.LD || typeof window.ldLoad === "function" ? `<button data-tpl="leads">⭐ Leads as a spreadsheet</button>` : ""}<button data-tpl="price">⭐ Price sheet</button></div>
    </div>
    <div class="card"><h3>MY FILES (${files.length})</h3><ul class="list">${files.map(f => `<li><span class="n" data-open="${f.id}" style="cursor:pointer">${icon[f.kind]} ${H(f.name)}</span><span class="m">${new Date(f.updated).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</span><button data-del="${f.id}" style="min-height:32px;padding:2px 10px">✕</button></li>`).join("") || `<li class="dim">Nothing yet. Make one above, or open a Word, Excel or text file.</li>`}</ul></div>`;
    QA("[data-new]").forEach(b => b.onclick = () => create(b.dataset.new));
    QA("[data-open]").forEach(b => b.onclick = async () => openFile(await fget(b.dataset.open)));
    QA("[data-del]").forEach(b => b.onclick = async () => { if (confirm("Remove this file from this device?")) { await fdel(b.dataset.del); home(); } });
    QA("[data-tpl]").forEach(b => b.onclick = () => template(b.dataset.tpl));
    Q("#ofOpen").onchange = e => { const f = e.target.files[0]; e.target.value = ""; if (f) importFile(f); };
  }
  async function create(kind, extra) {
    const f = Object.assign({ id: rid(), kind, name: { doc: "Untitled document", sheet: "Untitled spreadsheet", deck: "Untitled presentation" }[kind] },
      kind === "doc" ? { html: "<h1>Title</h1><p></p>" } : kind === "sheet" ? { sheets: [{ name: "Sheet1", rows: blank(30, 10) }], at: 0 } : { slides: [slide("Title", "")] }, extra || {});
    await fput(f); openFile(f);
  }
  const blank = (r, c) => Array.from({ length: r }, () => Array(c).fill(""));
  const slide = (title, body, img) => ({ id: rid(), title, body, img: img || "", theme: "dark" });
  function openFile(f) { cur = f; ({ doc: openDoc, sheet: openSheet, deck: openDeck })[f.kind](); }
  const titleBar = (extra) => `<div class="row" style="gap:8px;margin-bottom:8px"><button id="ofHome">← Files</button><input id="ofName" value="${H(cur.name)}" style="flex:1;font-weight:700"><span id="ofSaved" class="dim" style="font-size:12px"></span></div>
    <div class="row" style="gap:6px;margin-bottom:8px">${extra}</div>`;
  let saveT = null;
  function dirty() { const f = cur, el = Q("#ofSaved"); if (el) el.textContent = "saving…"; clearTimeout(saveT); saveT = setTimeout(async () => { saveT = null; if (f) await fput(f); const s = Q("#ofSaved"); if (s) s.textContent = "saved on this device"; }, 500); }
  async function flush() { if (saveT) { clearTimeout(saveT); saveT = null; if (cur) await fput(cur); } }
  function wireTitle() { Q("#ofHome").onclick = async () => { await flush(); home(); }; Q("#ofName").oninput = e => { cur.name = e.target.value; dirty(); }; }

  // ---------------------------------------------------------------- WRITE (documents)
  function openDoc() {
    root().innerHTML = `<div class="card">${titleBar(`
      <button data-cmd="bold"><b>B</b></button><button data-cmd="italic"><i>I</i></button><button data-cmd="underline"><u>U</u></button>
      <button data-blk="h1">H1</button><button data-blk="h2">H2</button><button data-blk="p">¶</button><button data-cmd="insertUnorderedList">• list</button><button data-cmd="insertOrderedList">1. list</button>
      <span style="flex:1"></span><button data-ex="docx">⬇ Word</button><button data-ex="pdf">⬇ PDF</button><button data-ex="html">⬇ HTML</button><button data-ex="txt">⬇ TXT</button><button data-ex="base">⇪ BASE1</button>`)}
      <div id="ofDoc" contenteditable="true" style="background:#fff;color:#111;border-radius:8px;padding:28px;min-height:60vh;font:16px/1.6 Georgia,serif;outline:none">${cur.html}</div></div>`;
    wireTitle();
    const ed = Q("#ofDoc");
    ed.oninput = () => { cur.html = ed.innerHTML; dirty(); };
    QA("[data-cmd]").forEach(b => b.onmousedown = e => { e.preventDefault(); document.execCommand(b.dataset.cmd); ed.oninput(); });
    QA("[data-blk]").forEach(b => b.onmousedown = e => { e.preventDefault(); document.execCommand("formatBlock", false, b.dataset.blk); ed.oninput(); });
    QA("[data-ex]").forEach(b => b.onclick = () => exportDoc(b.dataset.ex));
  }
  function docBlocks(html) {      // the document as blocks of runs, for Word / PDF / text
    const box = document.createElement("div"); box.innerHTML = html; const out = [];
    const runs = (node, st = {}) => { const r = []; node.childNodes.forEach(n => {
      if (n.nodeType === 3) { if (n.textContent) r.push({ t: n.textContent, b: st.b, i: st.i, u: st.u }); }
      else if (n.nodeName === "BR") r.push({ t: "\n" });
      else r.push(...runs(n, { b: st.b || /^(B|STRONG)$/.test(n.nodeName) || /bold|[6-9]00/.test(n.style?.fontWeight || ""), i: st.i || /^(I|EM)$/.test(n.nodeName), u: st.u || n.nodeName === "U" }));
    }); return r; };
    const walk = el => el.childNodes.forEach(n => {
      if (n.nodeType === 3) { if (n.textContent.trim()) out.push({ k: "p", r: [{ t: n.textContent }] }); return; }
      const t = n.nodeName;
      if (t === "UL" || t === "OL") n.querySelectorAll(":scope > li").forEach((li, i) => out.push({ k: t === "UL" ? "li" : "ol", n: i + 1, r: runs(li) }));
      else if (/^H[1-3]$/.test(t)) out.push({ k: t.toLowerCase(), r: runs(n) });
      else if (t === "DIV" && n.querySelector("p,h1,h2,ul,ol,div")) walk(n);
      else out.push({ k: "p", r: runs(n) });
    });
    walk(box); return out;
  }
  const xe = s => String(s).replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  function docxBlob(blocks) {
    const run = r => r.t === "\n" ? "<w:r><w:br/></w:r>" : `<w:r><w:rPr>${r.b ? "<w:b/>" : ""}${r.i ? "<w:i/>" : ""}${r.u ? '<w:u w:val="single"/>' : ""}</w:rPr><w:t xml:space="preserve">${xe(r.t)}</w:t></w:r>`;
    const body = blocks.map(b => {
      const st = { h1: '<w:pStyle w:val="Heading1"/>', h2: '<w:pStyle w:val="Heading2"/>', h3: '<w:pStyle w:val="Heading2"/>', li: '<w:pStyle w:val="ListParagraph"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>', ol: '<w:pStyle w:val="ListParagraph"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr>' }[b.k] || "";
      return `<w:p><w:pPr>${st}</w:pPr>${b.r.map(run).join("")}</w:p>`;
    }).join("");
    const W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"';
    const files = {
      "[Content_Types].xml": `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/></Types>`,
      "_rels/.rels": `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>`,
      "word/_rels/document.xml.rels": `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/></Relationships>`,
      "word/document.xml": `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document ${W}><w:body>${body}<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr></w:body></w:document>`,
      "word/styles.xml": `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles ${W}><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style><w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="36"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="200" w:after="100"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/><w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="720"/></w:pPr></w:style></w:styles>`,
      "word/numbering.xml": `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:numbering ${W}><w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/><w:lvlJc w:val="left"/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum><w:abstractNum w:abstractNumId="1"><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/><w:lvlJc w:val="left"/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num><w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num></w:numbering>`
    };
    const enc = new TextEncoder(), z = {};
    for (const k in files) z[k] = enc.encode(files[k]);
    return new Blob([fflate.zipSync(z)], { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" });
  }
  async function exportDoc(fmt) {
    const b = docBlocks(cur.html), nm = (cur.name || "document").replace(/[\\/:*?"<>|]/g, "_");
    if (fmt === "docx") return share(docxBlob(b), nm + ".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document");
    if (fmt === "html") return share(new Blob([`<!doctype html><meta charset="utf-8"><title>${H(cur.name)}</title><body style="max-width:760px;margin:40px auto;font:16px/1.6 Georgia,serif">${cur.html}</body>`], { type: "text/html" }), nm + ".html", "text/html");
    const txt = b.map(x => (x.k === "li" ? "• " : x.k === "ol" ? x.n + ". " : "") + x.r.map(r => r.t).join("")).join("\n\n");
    if (fmt === "txt") return share(new Blob([txt], { type: "text/plain" }), nm + ".txt", "text/plain");
    if (fmt === "pdf") {
      const { jsPDF } = window.jspdf; const pdf = new jsPDF({ unit: "pt", format: "letter" }); let y = 64;
      for (const x of b) {
        const size = x.k === "h1" ? 20 : x.k === "h2" || x.k === "h3" ? 15 : 11.5;
        pdf.setFont("helvetica", /^h/.test(x.k) ? "bold" : "normal"); pdf.setFontSize(size);
        const lines = pdf.splitTextToSize((x.k === "li" ? "•  " : x.k === "ol" ? x.n + ".  " : "") + x.r.map(r => r.t).join(""), 480);
        for (const ln of lines) { if (y > 730) { pdf.addPage(); y = 64; } pdf.text(ln, x.k === "li" || x.k === "ol" ? 84 : 66, y); y += size * 1.45; }
        y += 6;
      }
      return share(pdf.output("blob"), nm + ".pdf", "application/pdf");
    }
    if (fmt === "base") return toBase(docxBlob(b), nm + ".docx");
  }

  // ---------------------------------------------------------------- SHEETS (spreadsheets, with formulas)
  const colName = i => { let s = ""; i++; while (i) { const m = (i - 1) % 26; s = String.fromCharCode(65 + m) + s; i = (i - m - 1) / 26; } return s; };
  const colIdx = s => [...s.toUpperCase()].reduce((a, c) => a * 26 + c.charCodeAt(0) - 64, 0) - 1;
  function evalSheet(rows) {
    const memo = {}, busy = {};
    const val = (r, c) => {
      const k = r + "," + c; if (k in memo) return memo[k];
      const raw = (rows[r] || [])[c]; if (raw == null || raw === "") return (memo[k] = "");
      if (typeof raw === "string" && raw[0] === "=") {
        if (busy[k]) return "#CYCLE!"; busy[k] = 1;
        let out; try { out = calc(raw.slice(1)); } catch (e) { out = "#ERROR!"; }
        busy[k] = 0; return (memo[k] = out);
      }
      const n = Number(String(raw).replace(/[$,]/g, "")); return (memo[k] = String(raw).trim() !== "" && isFinite(n) && /^[\s$\-+.,\d%]+$/.test(raw) ? (String(raw).trim().endsWith("%") ? n / 100 : n) : raw);
    };
    const range = (r1, c1, r2, c2) => { const o = [];
      for (let r = Math.min(r1, r2); r <= Math.max(r1, r2); r++) for (let c = Math.min(c1, c2); c <= Math.max(c1, c2); c++) o.push(val(r, c)); return o; };
    const nums = a => a.flat().filter(x => typeof x === "number");
    const F = { SUM: (...a) => nums(a).reduce((s, x) => s + x, 0), AVERAGE: (...a) => { const n = nums(a); return n.length ? n.reduce((s, x) => s + x, 0) / n.length : 0; },
      MIN: (...a) => Math.min(...nums(a)), MAX: (...a) => Math.max(...nums(a)), COUNT: (...a) => nums(a).length, COUNTA: (...a) => a.flat().filter(x => x !== "").length,
      ROUND: (x, d = 0) => Math.round(x * 10 ** d) / 10 ** d, IF: (c, a, b = "") => c ? a : b, ABS: Math.abs };
    function calc(expr) {
      const js = expr.toUpperCase()
        .replace(/"[^"]*"/g, m => JSON.stringify(m.slice(1, -1)))
        .replace(/\b([A-Z]+)(\d+):([A-Z]+)(\d+)\b/g, (m, c1, r1, c2, r2) => `R(${+r1 - 1},${colIdx(c1)},${+r2 - 1},${colIdx(c2)})`)
        .replace(/\b([A-Z]{1,3})(\d+)\b(?!\s*\()/g, (m, c, r) => `V(${+r - 1},${colIdx(c)})`)
        .replace(/<>/g, "!=").replace(/([^<>!=])=([^=])/g, "$1==$2").replace(/&/g, "+''+").replace(/\^/g, "**");
      if (/[^A-Z0-9_+\-*/().,"'\s<>=!:%]/.test(js.replace(/"[^"]*"/g, ""))) throw new Error("bad");
      return Function("F", "R", "V", "with(F){return (" + js + ")}")(F, range, (r, c) => { const v = val(r, c); return v === "" ? 0 : v; });
    }
    return val;
  }
  const show = v => typeof v === "number" ? (Math.abs(v) >= 1e15 || Number.isInteger(v) ? String(v) : String(+v.toFixed(6))) : String(v);
  function openSheet() {
    const sh = () => cur.sheets[cur.at || 0];
    root().innerHTML = `<div class="card">${titleBar(`
      <select id="ofTab" style="width:auto">${cur.sheets.map((s, i) => `<option value="${i}"${i === (cur.at || 0) ? " selected" : ""}>${H(s.name)}</option>`).join("")}</select>
      <button id="ofAddTab">+ sheet</button><button id="ofAddRow">+ 10 rows</button><button id="ofAddCol">+ column</button>
      <span style="flex:1"></span><button data-ex="xlsx">⬇ Excel</button><button data-ex="csv">⬇ CSV</button><button data-ex="base">⇪ BASE1</button>`)}
      <div class="row" style="gap:6px;margin-bottom:6px"><b id="ofRef" style="width:56px">A1</b><input id="ofBar" placeholder="value or =SUM(A1:A9)" style="flex:1"></div>
      <div id="ofGridWrap" style="overflow:auto;max-height:66vh;border:1px solid var(--line);border-radius:8px"><table id="ofGrid" style="border-collapse:collapse;font-size:14px"></table></div>
      <p class="dim" style="font-size:12px">Formulas: + - * / ^, SUM, AVERAGE, MIN, MAX, COUNT, COUNTA, ROUND, IF, ABS, ranges like A1:C9. Saved on this device as you type.</p></div>`;
    wireTitle();
    let sel = [0, 0];
    const draw = () => {
      const s = sh(), v = evalSheet(s.rows), nc = Math.max(...s.rows.map(r => r.length));
      Q("#ofGrid").innerHTML = `<tr><th style="position:sticky;top:0;left:0;z-index:3;background:#18181b"></th>${Array.from({ length: nc }, (_, c) => `<th style="position:sticky;top:0;z-index:2;background:#18181b;padding:4px 8px;min-width:96px;color:var(--dim)">${colName(c)}</th>`).join("")}</tr>` +
        s.rows.map((row, r) => `<tr><th style="position:sticky;left:0;z-index:1;background:#18181b;padding:2px 8px;color:var(--dim)">${r + 1}</th>${Array.from({ length: nc }, (_, c) => {
          const x = v(r, c), num = typeof x === "number";
          return `<td data-rc="${r},${c}" style="border:1px solid #2a2a2e;padding:4px 8px;white-space:nowrap;max-width:260px;overflow:hidden;text-overflow:ellipsis;${num ? "text-align:right;" : ""}${r === sel[0] && c === sel[1] ? "outline:2px solid var(--red);outline-offset:-2px;" : ""}${r === 0 ? "font-weight:700;" : ""}">${H(show(x))}</td>`;
        }).join("")}</tr>`).join("");
      QA("#ofGrid td").forEach(td => { td.onclick = () => pick(...td.dataset.rc.split(",").map(Number)); td.ondblclick = () => Q("#ofBar").focus(); });
    };
    const pick = (r, c) => { sel = [r, c]; Q("#ofRef").textContent = colName(c) + (r + 1); Q("#ofBar").value = (sh().rows[r] || [])[c] ?? ""; draw(); };
    const put = val => { const s = sh(); while (s.rows.length <= sel[0]) s.rows.push(Array(s.rows[0].length).fill("")); s.rows[sel[0]][sel[1]] = val; dirty(); };
    Q("#ofBar").oninput = e => { put(e.target.value); draw(); };
    Q("#ofBar").onkeydown = e => { if (e.key === "Enter") { e.preventDefault(); pick(Math.min(sel[0] + 1, sh().rows.length - 1), sel[1]); Q("#ofBar").focus(); } else if (e.key === "Tab") { e.preventDefault(); pick(sel[0], Math.min(sel[1] + 1, sh().rows[0].length - 1)); Q("#ofBar").focus(); } };
    Q("#ofTab").onchange = e => { cur.at = +e.target.value; dirty(); pick(0, 0); };
    Q("#ofAddTab").onclick = () => { cur.sheets.push({ name: "Sheet" + (cur.sheets.length + 1), rows: blank(30, 10) }); cur.at = cur.sheets.length - 1; dirty(); openSheet(); };
    Q("#ofAddRow").onclick = () => { const s = sh(); for (let i = 0; i < 10; i++) s.rows.push(Array(s.rows[0].length).fill("")); dirty(); draw(); };
    Q("#ofAddCol").onclick = () => { sh().rows.forEach(r => r.push("")); dirty(); draw(); };
    QA("[data-ex]").forEach(b => b.onclick = () => exportSheet(b.dataset.ex));
    pick(0, 0);
  }
  function workbook() {
    const wb = XLSX.utils.book_new();
    cur.sheets.forEach(s => {
      const v = evalSheet(s.rows), ws = {}; let maxR = 0, maxC = 0;
      s.rows.forEach((row, r) => row.forEach((raw, c) => {
        if (raw === "" || raw == null) return; maxR = Math.max(maxR, r); maxC = Math.max(maxC, c);
        const x = v(r, c), cell = typeof x === "number" ? { t: "n", v: x } : { t: "s", v: String(x) };
        if (typeof raw === "string" && raw[0] === "=") cell.f = raw.slice(1);
        ws[XLSX.utils.encode_cell({ r, c })] = cell;
      }));
      ws["!ref"] = XLSX.utils.encode_range({ s: { r: 0, c: 0 }, e: { r: maxR, c: maxC } });
      XLSX.utils.book_append_sheet(wb, ws, (s.name || "Sheet").slice(0, 31));
    });
    return wb;
  }
  function exportSheet(fmt) {
    const nm = (cur.name || "spreadsheet").replace(/[\\/:*?"<>|]/g, "_");
    if (fmt === "csv") { const s = cur.sheets[cur.at || 0], v = evalSheet(s.rows); const csv = s.rows.map((row, r) => row.map((_, c) => { const x = show(v(r, c)); return /[",\n]/.test(x) ? `"${x.replace(/"/g, '""')}"` : x; }).join(",")).join("\n"); return share(new Blob([csv], { type: "text/csv" }), nm + ".csv", "text/csv"); }
    const out = XLSX.write(workbook(), { bookType: "xlsx", type: "array" }), blob = new Blob([out], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
    return fmt === "base" ? toBase(blob, nm + ".xlsx") : share(blob, nm + ".xlsx", blob.type);
  }

  // ---------------------------------------------------------------- SLIDES (presentations)
  const THEMES = { dark: { bg: "#000000", fg: "#FFFFFF", acc: "#E10600" }, red: { bg: "#E10600", fg: "#FFFFFF", acc: "#000000" }, light: { bg: "#FFFFFF", fg: "#111111", acc: "#E10600" } };
  let si = 0;
  function slideHTML(s, big) {   // sized in container units, so the same slide fits a thumbnail, the editor and the projector
    const t = THEMES[s.theme] || THEMES.dark, lines = (s.body || "").split("\n").filter(Boolean);
    return `<div style="container-type:inline-size;width:100%"><div style="position:relative;aspect-ratio:16/9;width:100%;background:${t.bg};color:${t.fg};border-radius:${big ? 0 : 8}px;overflow:hidden;font-family:system-ui,sans-serif">
      ${s.img ? `<img src="${s.img}" style="position:absolute;right:4%;top:16%;width:40%;height:66%;object-fit:contain">` : ""}
      <div style="position:absolute;left:5%;top:8%;right:${s.img ? "48%" : "5%"};font-weight:900;font-size:4.6cqw;line-height:1.05;text-transform:uppercase;font-style:italic">${H(s.title)}</div>
      <div style="position:absolute;left:5%;top:27%;width:7cqw;height:.6cqw;background:${t.acc}"></div>
      <ul style="position:absolute;left:5%;top:33%;right:${s.img ? "48%" : "5%"};margin:0;padding-left:1.1em;font-size:2.4cqw;line-height:1.45">${lines.map(l => `<li>${H(l)}</li>`).join("")}</ul>
      <img src="pxd2-logo.png" style="position:absolute;right:3%;bottom:4%;height:5cqw" onerror="this.remove()"></div></div>`;
  }
  function openDeck() {
    si = Math.min(si, cur.slides.length - 1);
    root().innerHTML = `<div class="card">${titleBar(`<button id="ofAddSlide">+ slide</button><button id="ofDup">⧉ duplicate</button><button id="ofUp">↑</button><button id="ofDown">↓</button><button id="ofDelS">✕ slide</button>
      <span style="flex:1"></span><button class="primary" id="ofPlay">▶ Present</button><button data-ex="pptx">⬇ PowerPoint</button><button data-ex="pdf">⬇ PDF</button><button data-ex="base">⇪ BASE1</button>`)}
      <div style="display:grid;grid-template-columns:${innerWidth < 700 ? "1fr" : "minmax(120px,190px) 1fr"};gap:12px">
        <div id="ofThumbs" style="display:grid;gap:8px;${innerWidth < 700 ? "grid-auto-flow:column;grid-auto-columns:150px;overflow-x:auto" : "max-height:70vh;overflow:auto"}"></div>
        <div><div id="ofStage"></div>
          <label>TITLE</label><input id="ofST">
          <label>POINTS (one per line)</label><textarea id="ofSB" style="min-height:110px"></textarea>
          <div class="row" style="gap:8px;margin-top:8px"><label class="btn" style="margin:0">🖼 Picture<input type="file" id="ofSI" accept="image/*" class="hide"></label><button id="ofSIx">no picture</button>
            <select id="ofTheme" style="width:auto"><option value="dark">Black</option><option value="red">Red</option><option value="light">White</option></select></div></div></div></div>`;
    wireTitle();
    const s = () => cur.slides[si];
    const drawAll = () => {
      Q("#ofThumbs").innerHTML = cur.slides.map((x, i) => `<div data-si="${i}" style="cursor:pointer;outline:${i === si ? "3px solid var(--red)" : "1px solid var(--line)"};border-radius:8px">${slideHTML(x, false)}</div>`).join("");
      QA("[data-si]").forEach(d => d.onclick = () => { si = +d.dataset.si; fill(); });
      Q("#ofStage").innerHTML = slideHTML(s(), false);
    };
    const fill = () => { Q("#ofST").value = s().title; Q("#ofSB").value = s().body; Q("#ofTheme").value = s().theme; drawAll(); };
    Q("#ofST").oninput = e => { s().title = e.target.value; dirty(); drawAll(); };
    Q("#ofSB").oninput = e => { s().body = e.target.value; dirty(); drawAll(); };
    Q("#ofTheme").onchange = e => { s().theme = e.target.value; dirty(); drawAll(); };
    Q("#ofSI").onchange = e => { const f = e.target.files[0]; e.target.value = ""; if (!f) return; const img = new Image(), rd = new FileReader();
      rd.onload = () => { img.onload = () => { const c = document.createElement("canvas"), sc = Math.min(1, 1400 / Math.max(img.width, img.height)); c.width = img.width * sc; c.height = img.height * sc; c.getContext("2d").drawImage(img, 0, 0, c.width, c.height); s().img = c.toDataURL("image/jpeg", 0.85); dirty(); drawAll(); }; img.src = rd.result; }; rd.readAsDataURL(f); };
    Q("#ofSIx").onclick = () => { s().img = ""; dirty(); drawAll(); };
    Q("#ofAddSlide").onclick = () => { cur.slides.splice(si + 1, 0, slide("New slide", "")); si++; dirty(); fill(); };
    Q("#ofDup").onclick = () => { cur.slides.splice(si + 1, 0, Object.assign({}, s(), { id: rid() })); si++; dirty(); fill(); };
    Q("#ofUp").onclick = () => { if (si > 0) { [cur.slides[si - 1], cur.slides[si]] = [cur.slides[si], cur.slides[si - 1]]; si--; dirty(); fill(); } };
    Q("#ofDown").onclick = () => { if (si < cur.slides.length - 1) { [cur.slides[si + 1], cur.slides[si]] = [cur.slides[si], cur.slides[si + 1]]; si++; dirty(); fill(); } };
    Q("#ofDelS").onclick = () => { if (cur.slides.length > 1) { cur.slides.splice(si, 1); si = Math.max(0, si - 1); dirty(); fill(); } };
    Q("#ofPlay").onclick = present;
    QA("[data-ex]").forEach(b => b.onclick = () => exportDeck(b.dataset.ex));
    fill();
  }
  function present() {
    let i = si; const ov = document.createElement("div");
    ov.style.cssText = "position:fixed;inset:0;z-index:99;background:#000;display:grid;place-items:center";
    const draw = () => { ov.innerHTML = `<div style="width:min(100vw,177.7vh)">${slideHTML(cur.slides[i], true)}</div><div style="position:fixed;bottom:10px;right:16px;color:#888;font:12px system-ui">${i + 1} / ${cur.slides.length} · tap to go on · Esc to close</div>`; };
    const go = d => { i = Math.max(0, Math.min(cur.slides.length - 1, i + d)); draw(); };
    const end = () => { ov.remove(); document.removeEventListener("keydown", key); if (document.fullscreenElement) document.exitFullscreen().catch(() => { }); };
    const key = e => { if (e.key === "Escape") end(); else if (/Arrow(Right|Down)| |PageDown|Enter/.test(e.key)) go(1); else if (/Arrow(Left|Up)|PageUp|Backspace/.test(e.key)) go(-1); };
    let x0 = null; ov.ontouchstart = e => x0 = e.touches[0].clientX; ov.ontouchend = e => { const dx = e.changedTouches[0].clientX - (x0 ?? 0); if (Math.abs(dx) > 50) go(dx < 0 ? 1 : -1); else go(1); x0 = null; };
    ov.onclick = e => { if (!("ontouchstart" in window)) go(e.clientX < innerWidth / 3 ? -1 : 1); };
    document.addEventListener("keydown", key); document.body.appendChild(ov); draw();
    ov.requestFullscreen?.().catch(() => { });
  }
  async function exportDeck(fmt) {
    const nm = (cur.name || "presentation").replace(/[\\/:*?"<>|]/g, "_");
    if (fmt === "pdf") {
      const { jsPDF } = window.jspdf; const pdf = new jsPDF({ orientation: "landscape", unit: "pt", format: [960, 540] });
      cur.slides.forEach((s, n) => { if (n) pdf.addPage([960, 540], "landscape"); const t = THEMES[s.theme] || THEMES.dark;
        pdf.setFillColor(t.bg); pdf.rect(0, 0, 960, 540, "F"); pdf.setTextColor(t.fg); pdf.setFont("helvetica", "bolditalic"); pdf.setFontSize(40);
        pdf.text(pdf.splitTextToSize((s.title || "").toUpperCase(), s.img ? 440 : 860), 48, 90); pdf.setFillColor(t.acc); pdf.rect(48, 128, 90, 6, "F");
        pdf.setFont("helvetica", "normal"); pdf.setFontSize(22); let y = 190;
        (s.body || "").split("\n").filter(Boolean).forEach(l => pdf.splitTextToSize("•  " + l, s.img ? 440 : 860).forEach(ln => { pdf.text(ln, 48, y); y += 32; }));
        if (s.img) try { pdf.addImage(s.img, "JPEG", 540, 100, 380, 340, undefined, "FAST"); } catch (e) { } });
      return share(pdf.output("blob"), nm + ".pdf", "application/pdf");
    }
    const P = new PptxGenJS(); P.layout = "LAYOUT_WIDE";
    cur.slides.forEach(s => { const t = THEMES[s.theme] || THEMES.dark, sl = P.addSlide(); sl.background = { color: t.bg.slice(1) };
      sl.addText((s.title || "").toUpperCase(), { x: 0.6, y: 0.5, w: s.img ? 6.2 : 12, h: 1.3, fontSize: 36, bold: true, italic: true, color: t.fg.slice(1), fontFace: "Arial" });
      sl.addShape(P.ShapeType.rect, { x: 0.6, y: 1.85, w: 1.1, h: 0.08, fill: { color: t.acc.slice(1) }, line: { color: t.acc.slice(1) } });
      const pts = (s.body || "").split("\n").filter(Boolean);
      if (pts.length) sl.addText(pts.map(p => ({ text: p, options: { bullet: true } })), { x: 0.6, y: 2.2, w: s.img ? 6.2 : 12, h: 4.6, fontSize: 20, color: t.fg.slice(1), fontFace: "Arial", valign: "top", paraSpaceAfter: 8 });
      if (s.img) sl.addImage({ data: s.img, x: 7.2, y: 1.3, w: 5.5, h: 5, sizing: { type: "contain", w: 5.5, h: 5 } }); });
    const blob = await P.write({ outputType: "blob" });
    return fmt === "base" ? toBase(blob, nm + ".pptx") : share(blob, nm + ".pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation");
  }

  // ---------------------------------------------------------------- open files from the device
  async function importFile(f) {
    const ext = f.name.split(".").pop().toLowerCase(), base = f.name.replace(/\.[^.]+$/, "");
    try {
      if (["xlsx", "xls", "csv", "ods"].includes(ext)) {
        const wb = XLSX.read(await f.arrayBuffer(), { cellFormula: true });
        const sheets = wb.SheetNames.map(n => { const ws = wb.Sheets[n]; const rg = ws["!ref"] ? XLSX.utils.decode_range(ws["!ref"]) : { e: { r: 0, c: 0 } };
          const rows = blank(Math.max(rg.e.r + 1, 30), Math.max(rg.e.c + 1, 8));
          for (const a in ws) { if (a[0] === "!") continue; const { r, c } = XLSX.utils.decode_cell(a), cell = ws[a]; rows[r][c] = cell.f ? "=" + cell.f : (cell.w ?? String(cell.v ?? "")); }
          return { name: n, rows }; });
        return create("sheet", { name: base, sheets, at: 0 });
      }
      if (ext === "docx") {
        const z = fflate.unzipSync(new Uint8Array(await f.arrayBuffer())), xml = new TextDecoder().decode(z["word/document.xml"]);
        const doc = new DOMParser().parseFromString(xml, "application/xml"), NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";
        const html = [...doc.getElementsByTagNameNS(NS, "p")].map(p => {
          const st = p.getElementsByTagNameNS(NS, "pStyle")[0]?.getAttribute("w:val") || "", list = p.getElementsByTagNameNS(NS, "numPr").length;
          const txt = [...p.getElementsByTagNameNS(NS, "r")].map(r => { const t = [...r.getElementsByTagNameNS(NS, "t")].map(x => x.textContent).join(""); if (!t) return r.getElementsByTagNameNS(NS, "br").length ? "<br>" : "";
            const b = r.getElementsByTagNameNS(NS, "b").length, i = r.getElementsByTagNameNS(NS, "i").length; return (b ? "<b>" : "") + (i ? "<i>" : "") + H(t) + (i ? "</i>" : "") + (b ? "</b>" : ""); }).join("");
          return /Heading1|Title/i.test(st) ? `<h1>${txt}</h1>` : /Heading[2-9]/i.test(st) ? `<h2>${txt}</h2>` : list ? `<ul><li>${txt}</li></ul>` : `<p>${txt || "<br>"}</p>`;
        }).join("").replace(/<\/ul><ul>/g, "");
        return create("doc", { name: base, html });
      }
      if (["txt", "md"].includes(ext)) return create("doc", { name: base, html: (await f.text()).split(/\n{2,}/).map(p => /^# /.test(p) ? `<h1>${H(p.slice(2))}</h1>` : /^## /.test(p) ? `<h2>${H(p.slice(3))}</h2>` : `<p>${H(p).replace(/\n/g, "<br>")}</p>`).join("") });
      if (["html", "htm"].includes(ext)) { const d = new DOMParser().parseFromString(await f.text(), "text/html"); d.querySelectorAll("script,style,iframe").forEach(x => x.remove()); return create("doc", { name: base, html: d.body.innerHTML }); }
      say("That kind of file can't be opened here yet: Word, Excel, CSV and text files open; PowerPoint files are made and exported.");
    } catch (e) { say("Could not open " + f.name + ": " + (e.message || e)); }
  }

  // ---------------------------------------------------------------- ready-made files
  async function template(t) {
    if (t === "pitch") return create("deck", { name: "PXD2 $500 website pitch", slides: [
      slide("$500 website. Hosted for life.", "Built for the phone in your customer's hand\nNo monthly bill, ever\nBuilt by PXD2, right here in the White Mountains"),
      slide("What you get", "Phone-first site in your shop's own look\nHours, directions, tap-to-call\nQR code kit and print-ready pieces\nYour own .pxd name, free for life"),
      Object.assign(slide("Free ad in our game", "Your ad on the Times Square screens in Global Theaters: Mud for Blood\nOut for reviews at Thanksgiving\nOnly 32 spots: first signed, first placed\nCarried into Rouge Racer: Route 66"), { theme: "red" }),
      slide("Add when you're ready", "Online ordering + full menu: $1,500 (card fees stay with your own provider)\nBookings and QR inventory tags: ask us\nSocial media kit"),
      Object.assign(slide("Sign today, live this week", "$500 one time\nE-sign right here on the tablet\nCall or text 928-457-6404"), { theme: "dark" })] });
    if (t === "price") return create("sheet", { name: "PXD2 price sheet", at: 0, sheets: [{ name: "Quote", rows: [
      ["Item", "Price", "Qty", "Line total"], ["Website (lifetime hosting + .pxd name)", "500", "1", "=B2*C2"], ["Online ordering + full menu", "1500", "0", "=B3*C3"],
      ["Free ad in Mud for Blood", "0", "1", "=B4*C4"], ["", "", "", ""], ["Total", "", "", "=SUM(D2:D4)"], ["Trade value (goods/services)", "", "", "0"], ["Money due", "", "", "=D6-D7"]].concat(blank(20, 4)) }] });
    if (t === "leads") {
      const d = typeof window.ldLoad === "function" ? await window.ldLoad() : null;
      if (!d) return say("Leads haven't loaded yet - open the LEADS tab once with signal.");
      const rows = [["Business", "Town", "Region", "Phone", "Status", "Offer", "Stage", "Notes", "Type", "Address"]].concat(d.leads.map(x => [x.n, x.t || "", x.r || "", x.p || "", x.s || "", x.o || "", x.st || "New", x.no || "", x.ty || "", x.a || ""]));
      return create("sheet", { name: "Leads " + new Date().toLocaleDateString(), at: 0, sheets: [{ name: "Leads", rows }] });
    }
  }

  window.PXD2Office = { home, open: importFile, show: () => { if (!cur || !root().children.length) home(); } };
  if (window.PXD2_STANDALONE) (document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", home) : home());
})();
