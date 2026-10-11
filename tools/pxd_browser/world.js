/* world.js: a PXD store world. 360° panoramas of the real shop, items pinned where they sit,
 * doorways between spots. The same renderer runs the owner's preview in Shop Builder and the
 * buyer's walk-in in the PXD Browser / Stores view. Needs three.js (classic build) loaded first.
 *
 *   var w = PXDWorld.mount(el, world, { image: path => Promise<url>, onItem: id => {}, onPick: (yaw, pitch) => {} });
 *   w.go(sceneId); w.setWorld(world); w.destroy();
 *
 * world.json: {"format": "pxd-world/1", "title", "start", "scenes": [{"id", "name", "image", "hotspots": [
 *   {"kind": "item", "item": "<item id>", "label", "yaw", "pitch"}, {"kind": "go", "to": "<scene id>", "label", "yaw", "pitch"}]}]}
 * yaw: degrees, 0 = the middle of the photo, positive to the right. pitch: degrees, positive up.
 */
(function (root) {
  "use strict";
  var D2R = Math.PI / 180;

  function mount(el, world, opts) {
    opts = opts || {};
    var THREE = root.THREE;
    if (!THREE) { el.textContent = "3D engine not loaded."; return null; }
    el.classList.add("pxd-world"); el.style.position = el.style.position || "relative"; el.style.overflow = "hidden"; el.style.touchAction = "none";
    var renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(root.devicePixelRatio || 1, 2));
    el.appendChild(renderer.domElement); renderer.domElement.style.display = "block";
    var scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(75, 1, 0.1, 1100);
    var geo = new THREE.SphereGeometry(500, 64, 32); geo.scale(-1, 1, 1);  // look at the inside of the sphere
    var mat = new THREE.MeshBasicMaterial({ color: 0x222222 }), sphere = new THREE.Mesh(geo, mat);
    sphere.rotation.y = -Math.PI / 2;  // the middle of the photo faces yaw 0
    scene.add(sphere);
    var layer = document.createElement("div"); layer.className = "pxd-world-pins";
    layer.style.cssText = "position:absolute;inset:0;pointer-events:none"; el.appendChild(layer);
    var label = document.createElement("div"); label.className = "pxd-world-name";
    label.style.cssText = "position:absolute;left:12px;top:10px;background:rgba(0,0,0,.55);color:#fff;padding:4px 10px;border-radius:999px;font:600 13px system-ui,sans-serif;pointer-events:none";
    el.appendChild(label);
    var yaw = 0, pitch = 0, fov = 75, cur = null, pins = [], dead = false, loader = new THREE.TextureLoader(), cache = {};

    function size() { var w = el.clientWidth || 640, h = el.clientHeight || 360; renderer.setSize(w, h, false); renderer.domElement.style.width = w + "px"; renderer.domElement.style.height = h + "px"; camera.aspect = w / h; camera.updateProjectionMatrix(); }
    function dir(y, p) { return new THREE.Vector3(Math.sin(y * D2R) * Math.cos(p * D2R), Math.sin(p * D2R), -Math.cos(y * D2R) * Math.cos(p * D2R)); }
    function look() { camera.fov = fov; camera.updateProjectionMatrix(); camera.lookAt(dir(yaw, pitch)); }

    function pinEl(h) {
      var b = document.createElement("button"); b.type = "button";
      b.className = "pxd-pin pxd-pin-" + h.kind;
      b.textContent = h.kind === "go" ? "➜ " + (h.label || "Go") : (h.label || "Item");
      b.style.cssText = "position:absolute;transform:translate(-50%,-50%);pointer-events:auto;cursor:pointer;border:0;border-radius:999px;padding:6px 12px;font:700 13px system-ui,sans-serif;white-space:nowrap;box-shadow:0 2px 10px rgba(0,0,0,.5);" +
        (h.kind === "go" ? "background:rgba(255,255,255,.92);color:#111" : "background:#d0302f;color:#fff");
      b.onclick = function (e) { e.stopPropagation(); if (h.kind === "go") go(h.to); else if (opts.onItem) opts.onItem(h.item); };
      layer.appendChild(b); return { h: h, el: b };
    }
    function go(id) {
      var s = (world.scenes || []).find(function (x) { return x.id === id; }) || (world.scenes || [])[0];
      if (!s) { label.textContent = "No photos yet"; return; }
      cur = s; label.textContent = s.name || s.id;
      pins.forEach(function (p) { p.el.remove(); }); pins = (s.hotspots || []).map(pinEl);
      if (s.yaw != null) yaw = s.yaw;
      var apply = function (url) {
        if (cache[url]) { mat.map = cache[url]; mat.color.set(0xffffff); mat.needsUpdate = true; return; }
        loader.load(url, function (t) { if (dead) return; if ("colorSpace" in t) t.colorSpace = THREE.SRGBColorSpace; else t.encoding = THREE.sRGBEncoding;
          cache[url] = t; if (cur === s) { mat.map = t; mat.color.set(0xffffff); mat.needsUpdate = true; } });
      };
      Promise.resolve(opts.image ? opts.image(s.image) : s.image).then(apply);
      if (opts.onScene) opts.onScene(s.id);
    }
    function project() {
      var w = el.clientWidth, h = el.clientHeight;
      pins.forEach(function (p) {
        var v = dir(p.h.yaw || 0, p.h.pitch || 0).multiplyScalar(400), cv = v.clone().project(camera);
        var behind = cv.z > 1 || v.clone().normalize().dot(dir(yaw, pitch)) < 0;
        p.el.style.display = behind ? "none" : "block";
        p.el.style.left = ((cv.x + 1) / 2 * w) + "px"; p.el.style.top = ((1 - cv.y) / 2 * h) + "px";
      });
    }
    function frame() { if (dead) return; look(); renderer.render(scene, camera); project(); requestAnimationFrame(frame); }

    // drag to look, wheel/pinch to zoom, click to place (builder)
    var down = null, moved = 0, pinch = null;
    el.addEventListener("pointerdown", function (e) { if (e.target.closest && e.target.closest(".pxd-pin")) return; down = { x: e.clientX, y: e.clientY, yaw: yaw, pitch: pitch }; moved = 0; el.setPointerCapture(e.pointerId); });
    el.addEventListener("pointermove", function (e) {
      if (!down || pinch) return;
      var k = fov / (el.clientHeight || 400);
      yaw = down.yaw - (e.clientX - down.x) * k; pitch = Math.max(-85, Math.min(85, down.pitch + (e.clientY - down.y) * k));
      moved = Math.max(moved, Math.abs(e.clientX - down.x) + Math.abs(e.clientY - down.y));
    });
    el.addEventListener("pointerup", function (e) {
      if (down && moved < 6 && opts.onPick) {
        var r = el.getBoundingClientRect(), x = (e.clientX - r.left) / r.width * 2 - 1, y = -((e.clientY - r.top) / r.height) * 2 + 1;
        var v = new THREE.Vector3(x, y, 0.5).unproject(camera).normalize();
        opts.onPick(Math.round(((Math.atan2(v.x, -v.z) / D2R) + 540) % 360 - 180), Math.round(Math.asin(v.y) / D2R));
      }
      down = null;
    });
    el.addEventListener("wheel", function (e) { e.preventDefault(); fov = Math.max(30, Math.min(100, fov + e.deltaY * 0.05)); }, { passive: false });
    el.addEventListener("touchmove", function (e) {
      if (e.touches.length !== 2) { pinch = null; return; }
      var d = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
      if (pinch) fov = Math.max(30, Math.min(100, pinch.fov * pinch.d / d)); else pinch = { d: d, fov: fov };
    }, { passive: true });
    el.addEventListener("touchend", function () { pinch = null; });
    var ro = root.ResizeObserver ? new ResizeObserver(size) : null; if (ro) ro.observe(el); else root.addEventListener("resize", size);
    size(); go(world.start); frame();
    return {
      go: go, scene: function () { return cur && cur.id; }, view: function () { return { yaw: yaw, pitch: pitch }; },
      setWorld: function (w) { world = w; go(cur && w.scenes.some(function (s) { return s.id === cur.id; }) ? cur.id : w.start); },
      destroy: function () { dead = true; if (ro) ro.disconnect(); renderer.dispose(); el.textContent = ""; }
    };
  }
  root.PXDWorld = { mount: mount, version: 1 };
})(typeof window !== "undefined" ? window : self);
