(function () {
  var INFO = "Info,Version=1.0.0,Template=fx_category_template_EBAY_US";
  var HEAD = "Action,Custom label (SKU),Category ID,Title,Start price,Quantity,Item photo URL,Condition ID,Description,Format,Duration,Location,Postal code,Max dispatch time,Shipping service 1 option,Shipping service 1 cost,Shipping service 1 priority,Returns accepted option,Returns within option,Refund option,Return shipping cost paid by,Shipping profile name,Payment profile name,Return profile name,C:Type,C:Publisher,C:Issue Number,C:Grade,C:Universe";
  var KEY = "pxd2.spread.v2";
  var SET = "pxd2.spread.set.v2";
  var rows = [];
  try { rows = JSON.parse(localStorage.getItem(KEY) || "[]"); } catch (e) { rows = []; }

  function $(id) { return document.getElementById(id); }
  function say(t, bad) {
    var el = $("msg");
    el.textContent = t;
    el.className = bad ? "msg bad" : "msg";
  }
  function escCsv(v) {
    var s = String(v == null ? "" : v);
    if (s.indexOf('"') >= 0 || s.indexOf(",") >= 0 || s.indexOf("\n") >= 0) {
      return '"' + s.split('"').join('""') + '"';
    }
    return s;
  }
  function title80(t) {
    t = String(t || "Comic").replace(/[^\x20-\x7E]/g, " ").replace(/\s+/g, " ").trim();
    if (t.length <= 80) return t;
    return t.slice(0, 77).replace(/\s+\S*$/, "").trim() + "...";
  }
  function attr(s) {
    return String(s || "").split('"').join("'");
  }
  function persist() {
    localStorage.setItem(KEY, JSON.stringify(rows));
    localStorage.setItem(SET, JSON.stringify({
      zip: $("zip").value, loc: $("loc").value,
      shipP: $("shipP").value, payP: $("payP").value, retP: $("retP").value
    }));
  }
  function draw() {
    $("stat").textContent = rows.length + " rows";
    var html = "";
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i];
      html += "<tr><td>" + (i + 1) + "</td>";
      html += '<td><input data-i="' + i + '" data-k="sku" value="' + attr(r.sku) + '"></td>';
      html += '<td><input data-i="' + i + '" data-k="title" value="' + attr(r.title) + '"></td>';
      html += '<td><input data-i="' + i + '" data-k="qty" value="' + attr(r.qty || "1") + '"></td>';
      html += '<td><input data-i="' + i + '" data-k="price" value="' + attr(r.price) + '"></td>';
      html += '<td><input data-i="' + i + '" data-k="pic" value="' + attr(r.pic) + '"></td>';
      html += '<td><input data-i="' + i + '" data-k="pub" value="' + attr(r.pub) + '"></td>';
      html += '<td><button type="button" data-del="' + i + '">Del</button></td></tr>';
    }
    $("body").innerHTML = html;
  }
  function fromInventRow(r) {
    if (!r || r.sold) return null;
    var title = r.title || r.name || "";
    if (!title) return null;
    if (Number(r.quantity) === 0 || Number(r.qty) === 0) return null;
    return {
      sku: r.sku || r.customLabel || "",
      title: title,
      qty: String(r.qty || r.quantity || 1),
      price: String(r.price || r.priceUsd || r.price_usd || "").replace(/[^0-9.]/g, ""),
      pic: String(r.pic || r.photoUrls || r.photo_urls || "").split(",")[0].trim(),
      pub: r.pub || r.publisher || ""
    };
  }
  function mergeRows(extra) {
    if (!extra || !extra.length) return 0;
    var have = {};
    var i, j, k, n = 0;
    for (i = 0; i < rows.length; i++) have[(rows[i].sku || "") + "|" + (rows[i].title || "")] = true;
    for (j = 0; j < extra.length; j++) {
      k = (extra[j].sku || "") + "|" + (extra[j].title || "");
      if (have[k]) continue;
      rows.push(extra[j]);
      have[k] = true;
      n++;
    }
    if (n) { persist(); draw(); }
    return n;
  }
  function listFromPayload(data) {
    if (!data) return [];
    if (Array.isArray(data)) return data;
    if (data.state && (data.state.items || data.state.rows)) return data.state.items || data.state.rows;
    return data.items || data.rows || [];
  }
  function readInventLocal() {
    var keys = ["pxd2.invent.v1", "pxd2.invent.v2", "pxd2.invent.v3"];
    var found = [], i, j, raw, data, list, row;
    for (i = 0; i < keys.length; i++) {
      raw = localStorage.getItem(keys[i]);
      if (!raw) continue;
      try { data = JSON.parse(raw); } catch (e) { continue; }
      list = listFromPayload(data);
      for (j = 0; j < list.length; j++) {
        row = fromInventRow(list[j]);
        if (row) found.push(row);
      }
    }
    return found;
  }
  function mapList(list) {
    var out = [], i, row;
    for (i = 0; i < list.length; i++) {
      row = fromInventRow(list[i]);
      if (row) out.push(row);
    }
    return out;
  }
  function autoFromSite() {
    var n = mergeRows(readInventLocal());
    var urls = [
      "https://raw.githubusercontent.com/PxD2/PxD2.github.io/main/invent/catalog.json",
      "https://raw.githubusercontent.com/PxD2/PxD2.github.io/main/spread/catalog.json"
    ];
    var left = urls.length;
    function done() {
      if (rows.length) say("Loaded " + rows.length + " from Invent / this site.");
      else say("Invent has no rows in this browser yet. Open Invent, import there, then click From Invent — or paste a CSV.");
    }
    urls.forEach(function (url) {
      fetch(url, { cache: "no-store" }).then(function (res) {
        if (!res.ok) return null;
        return res.json();
      }).then(function (data) {
        if (data) n += mergeRows(mapList(listFromPayload(data)));
      }).catch(function () {
      }).then(function () {
        left -= 1;
        if (left <= 0) done();
      });
    });
  }
  function splitLine(line) {
    var out = [], cur = "", q = false, i, c;
    for (i = 0; i < line.length; i++) {
      c = line.charAt(i);
      if (c === '"') {
        if (q && line.charAt(i + 1) === '"') { cur += '"'; i++; }
        else q = !q;
      } else if (c === "," && !q) { out.push(cur); cur = ""; }
      else cur += c;
    }
    out.push(cur);
    return out;
  }
  function norm(s) {
    return String(s || "").toLowerCase().replace(/[*#]/g, "").replace(/\s+/g, " ").trim();
  }
  function pick(map, names) {
    var i, v;
    for (i = 0; i < names.length; i++) {
      v = map[names[i]];
      if (v != null && String(v).trim()) return String(v).trim();
    }
    return "";
  }
  function parseCsv(text) {
    var raw = String(text || "").replace(/^\uFEFF/, "").split(/\r?\n/);
    var lines = [], i, l;
    for (i = 0; i < raw.length; i++) {
      l = raw[i];
      if (!l.trim()) continue;
      if (/^\s*#?info\b/i.test(l)) continue;
      lines.push(l);
    }
    if (!lines.length) return [];
    var header = splitLine(lines[0]).map(norm);
    var looksHeader = false;
    for (i = 0; i < header.length; i++) {
      if (/title|name|sku|price|qty|quantity|photo|action|custom label/.test(header[i])) looksHeader = true;
    }
    var start = looksHeader ? 1 : 0;
    var out = [], r, cols, map, c, title, sku;
    for (r = start; r < lines.length; r++) {
      cols = splitLine(lines[r]);
      map = {};
      if (looksHeader) {
        for (c = 0; c < header.length; c++) map[header[c]] = cols[c] || "";
      } else {
        map.title = cols.length === 1 ? cols[0] : (cols[1] || cols[0]);
        map.sku = cols.length > 1 ? cols[0] : "";
        map.price = cols[2] || "";
      }
      title = pick(map, ["title", "item title", "name", "listing title", "product title", "item name"]);
      if (!title && !looksHeader) title = String(cols[0] || "").trim();
      if (!title) continue;
      sku = pick(map, ["sku", "custom label (sku)", "customlabel", "custom label"]);
      out.push({
        sku: sku || ("AW-" + (out.length + 1)),
        title: title,
        qty: pick(map, ["quantity", "qty", "available"]) || "1",
        price: pick(map, ["start price", "price", "startprice", "price usd", "price_usd", "usd"]).replace(/[^0-9.]/g, ""),
        pic: pick(map, ["item photo url", "picurl", "pic url", "photo_urls", "photo", "image", "cover"]).split("|")[0].split(",")[0].trim(),
        pub: pick(map, ["c:publisher", "publisher"])
      });
    }
    return out;
  }
  function loadText(text, source) {
    var extra = parseCsv(text);
    if (!extra.length) {
      say("No listing rows in " + source + ". Need a Title column or one title per line.", true);
      return;
    }
    mergeRows(extra);
    say("Loaded " + extra.length + " from " + source + ". Grid now " + rows.length + ".");
  }

  try {
    var set = JSON.parse(localStorage.getItem(SET) || "{}");
    if (set.zip) $("zip").value = set.zip;
    if (set.loc) $("loc").value = set.loc;
    if (set.shipP) $("shipP").value = set.shipP;
    if (set.payP) $("payP").value = set.payP;
    if (set.retP) $("retP").value = set.retP;
  } catch (e) {}

  $("body").addEventListener("input", function (e) {
    var t = e.target;
    if (!t.getAttribute("data-i")) return;
    rows[+t.getAttribute("data-i")][t.getAttribute("data-k")] = t.value;
    persist();
  });
  $("body").addEventListener("click", function (e) {
    var del = e.target.getAttribute("data-del");
    if (del == null) return;
    rows.splice(+del, 1);
    persist();
    draw();
  });
  $("add").onclick = function () {
    rows.push({ sku: "AW-" + (rows.length + 1), title: "", qty: "1", price: "", pic: "", pub: "" });
    persist();
    draw();
  };
  $("file").onchange = function (ev) {
    var f = ev.target.files && ev.target.files[0];
    if (!f) { say("No file picked.", true); return; }
    var reader = new FileReader();
    reader.onload = function () { loadText(String(reader.result || ""), f.name); };
    reader.onerror = function () { say("Could not read " + f.name, true); };
    reader.readAsText(f);
  };
  $("pastebtn").onclick = function () { loadText($("paste").value, "paste"); };
  $("sitebtn").onclick = function () { autoFromSite(); };
  $("out").onclick = function () {
    var zip = $("zip").value.trim();
    var live = [];
    var i, r;
    for (i = 0; i < rows.length; i++) {
      r = rows[i];
      if (r.title && String(r.title).trim()) live.push(r);
    }
    if (!live.length) { say("No titled rows to download.", true); return; }
    if (!/^\d{5}(-\d{4})?$/.test(zip)) { say("Enter a 5-digit ZIP, then download again.", true); return; }
    persist();
    var loc = $("loc").value.trim() || "United States";
    var sp = $("shipP").value.trim();
    var pp = $("payP").value.trim();
    var rp = $("retP").value.trim();
    var lines = live.map(function (r) {
      return [
        "Add", r.sku || "", "259104", title80(r.title), r.price || "0", r.qty || "1",
        String(r.pic || "").split(",")[0].trim(), "3000", title80(r.title),
        "FixedPrice", "GTC", loc, zip, "1", "USPSMediaMail", "4.99", "1",
        "ReturnsAccepted", "Days_30", "MoneyBack", "Buyer",
        sp, pp, rp, "Comic Book", r.pub || "", "", "Ungraded", r.pub || ""
      ].map(escCsv).join(",");
    });
    var csv = INFO + "\n" + HEAD + "\n" + lines.join("\n") + "\n";
    var a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    a.download = "angelwood-67-ebay-spread.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    say("Downloaded " + live.length + " listings. Upload as Create new listings.");
  };

  draw();
  autoFromSite();
})();
