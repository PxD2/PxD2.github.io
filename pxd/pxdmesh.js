/* PXD Mesh loader: opens PXD2's compact 3D files (.pxdm) in any browser.
 *   <script src="/pxd/pxdmesh.js"></script>
 *   PXDMesh.url("chair.pxdm")            -> Promise<blob: URL of a GLB> (for model-viewer, three.js, anything)
 *   PXDMesh.three(gltfLoader)            -> gives a three.js GLTFLoader the meshopt decoder
 *   <model-viewer src="chair.pxdm">      -> upgraded automatically (also plain .glb files that use meshopt)
 * A .pxdm is a meshopt + WebP GLB, deflated once more; the browser inflates it natively (DecompressionStream).
 * A plain .glb or .pxdm.glb is passed through untouched.
 */
(function () {
  "use strict";
  var here = (document.currentScript && document.currentScript.src) || "/pxd/pxdmesh.js";
  var DECODER = new URL("vendor/meshopt_decoder.js", here).href;
  var cache = {};
  var decoderReady = null;

  function loadDecoder() {
    if (window.MeshoptDecoder) return Promise.resolve(window.MeshoptDecoder);
    if (!decoderReady) decoderReady = new Promise(function (ok, fail) {
      var s = document.createElement("script"); s.src = DECODER; s.async = true;
      s.onload = function () { ok(window.MeshoptDecoder); }; s.onerror = fail;
      document.head.appendChild(s);
    });
    return decoderReady;
  }
  function isPxdm(src) { return /\.pxdm(\?|#|$)/i.test(src); }
  function url(src) {
    if (!isPxdm(src)) return Promise.resolve(src);
    if (cache[src]) return cache[src];
    cache[src] = fetch(src).then(function (r) {
      if (!r.ok) throw new Error("PXD Mesh " + r.status + " " + src);
      var body = r.body.pipeThrough(new DecompressionStream("deflate-raw"));
      return new Response(body).blob();
    }).then(function (b) { return URL.createObjectURL(new Blob([b], { type: "model/gltf-binary" })); });
    return cache[src];
  }
  function three(loader) {
    return loadDecoder().then(function (d) { if (loader && loader.setMeshoptDecoder) loader.setMeshoptDecoder(d); return loader; });
  }
  function upgrade(mv) {
    if (mv.__pxdm) return;
    var src = mv.getAttribute("src") || mv.getAttribute("data-pxdm");
    if (!src || !isPxdm(src)) return;
    mv.__pxdm = true;
    mv.removeAttribute("src");
    url(src).then(function (u) { mv.setAttribute("src", u); }).catch(function (e) { console.warn(e); });
  }
  function setupModelViewer() {
    var MV = customElements.get("model-viewer");
    if (MV && "meshoptDecoderLocation" in MV) MV.meshoptDecoderLocation = DECODER;
  }
  if (window.customElements) customElements.whenDefined("model-viewer").then(setupModelViewer);
  function scan(root) { (root.querySelectorAll ? root.querySelectorAll("model-viewer") : []).forEach(upgrade); }
  new MutationObserver(function (ms) {
    ms.forEach(function (m) {
      if (m.type === "attributes" && m.target.tagName === "MODEL-VIEWER") { m.target.__pxdm = false; upgrade(m.target); }
      m.addedNodes && m.addedNodes.forEach(function (n) { if (n.tagName === "MODEL-VIEWER") upgrade(n); else scan(n); });
    });
  }).observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ["src"] });
  if (document.readyState !== "loading") scan(document); else document.addEventListener("DOMContentLoaded", function () { scan(document); });
  window.PXDMesh = { url: url, three: three, decoder: loadDecoder, isPxdm: isPxdm };
})();
