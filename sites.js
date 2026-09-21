/* Every PXD2 hall links to the list of sites. */
(function () {
  var SITES = [
    { name: "Sites", href: "/sites/" },
    { name: "HOLD", href: "/" },
    { name: "Edu", href: "/edu/" },
    { name: "Civics", href: "/civics/" },
    { name: "STEM", href: "/stem/" },
    { name: "College", href: "/college/" },
    { name: "Davidson", href: "/davidson/" },
    { name: "Hornet", href: "/hornet/" },
    { name: "House", href: "/hornet/house.html" },
    { name: "Lens", href: "/hornet/lens.html" },
    { name: "Alexandria", href: "/alexandria/" },
    { name: "Studio A", href: "/studioa/" },
    { name: "GitHub", href: "https://github.com/PxD2" }
  ];
  function paint(nav) {
    nav.innerHTML = SITES.map(function (s) {
      return '<a href="' + s.href + '">' + s.name + "</a>";
    }).join("");
  }
  function boot() {
    var nav = document.querySelector("nav.rooms");
    if (!nav) {
      nav = document.createElement("nav");
      nav.className = "rooms";
      document.body.appendChild(nav);
    }
    paint(nav);
    if (!document.getElementById("sites-rooms-css")) {
      var css = document.createElement("style");
      css.id = "sites-rooms-css";
      css.textContent =
        "nav.rooms{position:fixed;left:12px;bottom:12px;z-index:50;display:flex;gap:10px 14px;flex-wrap:wrap;align-items:center;max-width:min(72vw,38rem);font:600 11px/1 system-ui,sans-serif;letter-spacing:.18em;text-transform:uppercase}" +
        "nav.rooms a{color:var(--muted,var(--dim,#9aa4ae));text-decoration:none}" +
        "nav.rooms a:first-child{color:var(--fg,var(--ink,#e8e6e3))}" +
        "@media print{nav.rooms{display:none!important}}";
      document.head.appendChild(css);
    }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
