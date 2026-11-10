/* PXD2 — AMD ROCm Certified Associate chip.
   Include: <script src="/assets/rocm-cert.js" data-pos="inline" defer></script>
   data-pos / data-mpos (phones <=700px):
     inline        static strip at the end of the page (scrolling pages)
     br|bl|tr|tl   fixed corner chip
     edge          small tab on the right edge, mid-height; full text on hover/tap (full-screen apps) */
(function () {
  var s = document.currentScript;
  var pos = (s && s.getAttribute("data-pos")) || "inline";
  var mpos = s && s.getAttribute("data-mpos");
  var phone = window.matchMedia && matchMedia("(max-width: 700px)").matches;
  if (mpos && phone) pos = mpos;

  var ICON =
    '<svg viewBox="0 0 100 100" width="14" height="14" aria-hidden="true" fill="none" stroke="#ed1c24" stroke-width="9" style="flex:none">' +
    '<rect x="14" y="14" width="72" height="72" rx="8"/><rect x="36" y="36" width="28" height="28" fill="#ed1c24" stroke="none"/></svg>';
  var TEXT = '<span class="t">AMD ROCm™ <b style="color:#ed1c24;font-weight:700">Certified Associate</b></span>';
  var BASE =
    "display:inline-flex;align-items:center;gap:7px;padding:6px 10px;border:1px solid #ed1c24;" +
    "background:rgba(10,11,14,.9);color:#e9eaee;text-decoration:none;font:600 11px/1 Barlow,system-ui,sans-serif;" +
    "letter-spacing:.12em;text-transform:uppercase;box-shadow:0 2px 10px rgba(0,0,0,.35);white-space:nowrap;";

  function mount() {
    if (document.getElementById("pxd2-rocm")) return;
    var a = document.createElement("a");
    a.id = "pxd2-rocm";
    a.href = "/sites/#cert";
    a.title = "PXD2 has passed the AMD ROCm Certified Associate certification. Continuing to Professional and Expert.";
    a.setAttribute("aria-label", "AMD ROCm Certified Associate");
    a.innerHTML = ICON + TEXT;

    if (pos === "inline") {
      var wrap = document.createElement("div");
      wrap.style.cssText = "display:flex;justify-content:center;padding:22px 16px " + (phone ? "150px" : "72px") + ";";
      a.style.cssText = BASE + "border-radius:999px;";
      wrap.appendChild(a);
      document.body.appendChild(wrap);
    } else if (pos === "edge") {
      a.style.cssText = BASE + "position:fixed;z-index:60;right:0;top:50%;transform:translateY(-50%);" +
        "border-right:0;border-radius:999px 0 0 999px;padding:7px 8px 7px 9px;transition:padding .2s;";
      var t = a.querySelector(".t");
      t.style.cssText = "display:none";
      var open = false;
      function set(o) { open = o; t.style.display = o ? "inline" : "none"; a.style.padding = o ? "7px 12px 7px 10px" : "7px 8px 7px 9px"; }
      a.addEventListener("mouseenter", function () { set(true); });
      a.addEventListener("mouseleave", function () { set(false); });
      a.addEventListener("focus", function () { set(true); });
      a.addEventListener("blur", function () { set(false); });
      a.addEventListener("click", function (e) { if (!open) { e.preventDefault(); set(true); } });
      document.body.appendChild(a);
    } else {
      var v = pos.charAt(0) === "t" ? "top:12px;" : "bottom:12px;";
      var h = pos.charAt(1) === "l" ? "left:12px;" : "right:12px;";
      a.style.cssText = BASE + "border-radius:999px;position:fixed;z-index:60;" + v + h;
      document.body.appendChild(a);
    }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount);
  else mount();
})();
