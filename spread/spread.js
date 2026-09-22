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
    rows = rows.concat(extra);
    persist();
    draw();
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
  say(rows.length ? rows.length + " rows in this browser." : "Ready. Import a CSV or paste titles.");
})();
