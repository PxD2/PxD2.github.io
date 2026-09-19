/* Read every course load aloud. Web Speech. No graph. */
(function () {
  if (!("speechSynthesis" in window)) return;
  var synth = window.speechSynthesis;
  var stopped = true;
  var paused = false;

  function voices() { return synth.getVoices() || []; }
  function pick(lang) {
    var list = voices();
    var p = (lang || "en").slice(0, 2).toLowerCase();
    var best = null, score = -1;
    for (var i = 0; i < list.length; i++) {
      var v = list[i], n = 0;
      if ((v.lang || "").toLowerCase().indexOf(p) === 0) n += 5;
      if (/natural|google|premium|neural|enhanced|microsoft/i.test(v.name || "")) n += 2;
      if (v.localService) n += 1;
      if (n > score) { score = n; best = v; }
    }
    return best;
  }
  function chunk(text) {
    var clean = String(text || "").replace(/\s+/g, " ").trim();
    if (!clean) return [];
    var parts = [], buf = "", bits = clean.split(/(?<=[.!?])\s+/);
    for (var i = 0; i < bits.length; i++) {
      if ((buf + " " + bits[i]).length > 1600 && buf) { parts.push(buf.trim()); buf = bits[i]; }
      else buf = buf ? buf + " " + bits[i] : bits[i];
    }
    if (buf.trim()) parts.push(buf.trim());
    return parts;
  }
  function collect(root) {
    var skip = { SCRIPT:1, STYLE:1, NAV:1, IFRAME:1, NOSCRIPT:1, BUTTON:1, SVG:1 };
    var parts = [];
    function walk(n) {
      if (n.nodeType === 1) {
        var el = n;
        if (skip[el.tagName]) return;
        if (el.hidden || el.getAttribute("aria-hidden") === "true") return;
        if (el.hasAttribute("data-no-read")) return;
        if (/(^| )(bar|rooms|listen-bar)( |$)/.test(el.className || "")) return;
      }
      if (n.nodeType === 3) {
        var t = (n.textContent || "").replace(/\s+/g, " ").trim();
        if (t) parts.push(t);
        return;
      }
      for (var c = n.firstChild; c; c = c.nextSibling) walk(c);
    }
    if (root) walk(root);
    return parts.join(". ");
  }
  function pageLang() {
    var el = document.querySelector("[data-lang]") || document.documentElement;
    return el.getAttribute("data-lang") || el.lang || "en-US";
  }
  function targetText(from) {
    var sel = (window.getSelection && String(window.getSelection())).trim();
    if (sel) return sel;
    if (from) return collect(from);
    var pane = document.querySelector(".pane.on");
    if (pane) return collect(pane);
    var marked = document.querySelector("[data-read]");
    if (marked) return collect(marked);
    return collect(document.querySelector("main, .wrap, article") || document.body);
  }
  function stop() {
    stopped = true;
    paused = false;
    synth.cancel();
    setMode("idle");
  }
  function speakText(text) {
    stop();
    var pieces = chunk(text);
    if (!pieces.length) return;
    stopped = false;
    var lang = pageLang();
    var utterLang = lang.toLowerCase().indexOf("la") === 0 ? "it-IT" : lang;
    var rate = lang.toLowerCase().indexOf("la") === 0 ? 0.85 : 0.95;
    var i = 0;
    function next() {
      if (stopped || i >= pieces.length) { setMode("idle"); return; }
      var u = new SpeechSynthesisUtterance(pieces[i++]);
      u.lang = utterLang;
      u.rate = rate;
      var v = pick(utterLang);
      if (v) u.voice = v;
      u.onend = function () { if (!stopped) next(); };
      synth.speak(u);
    }
    setMode("play");
    if (!voices().length) synth.addEventListener("voiceschanged", next, { once: true });
    next();
  }
  function setMode(mode) {
    var listen = document.getElementById("listen-go");
    var pause = document.getElementById("listen-pause");
    var stopb = document.getElementById("listen-stop");
    if (!listen) return;
    listen.hidden = mode !== "idle";
    pause.hidden = mode === "idle";
    stopb.hidden = mode === "idle";
    pause.textContent = mode === "pause" ? "Resume" : "Pause";
    pause.dataset.mode = mode;
  }
  function bar() {
    if (document.querySelector(".listen-bar")) return;
    var wrap = document.createElement("div");
    wrap.className = "listen-bar";
    wrap.setAttribute("data-no-read", "");
    wrap.innerHTML =
      '<button type="button" id="listen-go">Listen</button>' +
      '<button type="button" id="listen-pause" hidden>Pause</button>' +
      '<button type="button" id="listen-stop" hidden>Stop</button>';
    document.body.appendChild(wrap);
    document.getElementById("listen-go").onclick = function () { speakText(targetText()); };
    document.getElementById("listen-pause").onclick = function () {
      if (this.dataset.mode === "pause") { synth.resume(); setMode("play"); }
      else { synth.pause(); setMode("pause"); }
    };
    document.getElementById("listen-stop").onclick = stop;
  }
  function decorate() {
    var nodes = document.querySelectorAll(".lesson .meta, article.lesson");
    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      if (el.querySelector(".listen-one")) continue;
      var b = document.createElement("button");
      b.type = "button";
      b.className = "listen-one";
      b.setAttribute("data-no-read", "");
      b.textContent = "Listen";
      (el.classList.contains("meta") ? el : el.querySelector(".meta") || el).appendChild(b);
    }
  }
  var css = document.createElement("style");
  css.textContent =
    ".listen-bar{position:fixed;right:12px;bottom:56px;z-index:80;display:flex;gap:8px}" +
    ".listen-bar button,.listen-one{min-height:44px;padding:0 14px;cursor:pointer;border:1px solid var(--line,#2a2a2e);background:var(--panel,var(--bg,#121214));color:var(--fg,var(--ink,#e8e6e3));font:600 12px/1 system-ui,sans-serif;letter-spacing:.08em;text-transform:uppercase;border-radius:6px}" +
    ".listen-one{margin-top:10px;min-height:40px}" +
    "@media print{.listen-bar,.listen-one{display:none!important}}";
  document.head.appendChild(css);
  function boot() {
    bar();
    decorate();
    new MutationObserver(decorate).observe(document.body, { childList: true, subtree: true });
  }
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest(".listen-one");
    if (!b) return;
    e.preventDefault();
    speakText(targetText(b.closest("article") || b.parentElement));
  });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
