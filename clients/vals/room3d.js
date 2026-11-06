/* PXD2 3D Room: a sample walk-through room for a client concept.
 * Call PXD2Room.boot(config). Needs three.js r147 + OrbitControls loaded first.
 * After the client signs, the real 3D scan replaces this sample room.
 */
(function () {
  "use strict";
  function signTexture(text, sub, bg, fg) {
    var c = document.createElement("canvas"); c.width = 1024; c.height = 256;
    var g = c.getContext("2d");
    g.fillStyle = bg; g.fillRect(0, 0, 1024, 256);
    g.strokeStyle = fg; g.lineWidth = 10; g.strokeRect(14, 14, 996, 228);
    g.fillStyle = fg; g.textAlign = "center"; g.textBaseline = "middle";
    var fs = 92; do { g.font = "bold " + fs + "px Georgia, serif"; fs -= 4; } while (g.measureText(text).width > 940 && fs > 30);
    g.fillText(text, 512, sub ? 105 : 128);
    if (sub) { g.font = "44px Arial, sans-serif"; g.fillText(sub, 512, 190); }
    var t = new THREE.CanvasTexture(c); t.anisotropy = 8; return t;
  }
  function mat(color, rough) { return new THREE.MeshStandardMaterial({ color: color, roughness: rough == null ? 0.8 : rough }); }
  function box(w, h, d, color, x, y, z, parent) {
    var m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat(color));
    m.position.set(x, y, z); m.castShadow = true; m.receiveShadow = true; parent.add(m); return m;
  }
  function cyl(r, h, color, x, y, z, parent) {
    var m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, h, 24), mat(color));
    m.position.set(x, y, z); m.castShadow = true; parent.add(m); return m;
  }

  var PROPS = {
    table: function (s, x, z, c) {
      cyl(0.6, 0.06, c.wood, x, 0.76, z, s); cyl(0.06, 0.74, c.metal, x, 0.38, z, s);
      [[0.85, 0], [-0.85, 0], [0, 0.85], [0, -0.85]].forEach(function (o) {
        box(0.4, 0.06, 0.4, c.accent, x + o[0], 0.46, z + o[1], s);
        box(0.4, 0.45, 0.06, c.accent, x + o[0] * 1.25, 0.7, z + o[1] * 1.25, s).lookAt(x, 0.7, z);
      });
    },
    counter: function (s, x, z, c) {
      box(4, 1.05, 0.8, c.wood, x, 0.525, z, s); box(4.2, 0.08, 0.95, c.top, x, 1.09, z, s);
    },
    vase: function (s, x, z, c) {
      cyl(0.12, 0.3, c.metal, x, 1.28, z, s);
      for (var i = 0; i < 7; i++) {
        var f = new THREE.Mesh(new THREE.SphereGeometry(0.09, 12, 12), mat(c.flowers[i % c.flowers.length], 0.6));
        f.position.set(x + Math.cos(i) * 0.12, 1.55 + (i % 3) * 0.06, z + Math.sin(i) * 0.12); s.add(f);
      }
    },
    shelf: function (s, x, z, c) {
      box(2.4, 2.2, 0.4, c.wood, x, 1.1, z, s);
      for (var i = 0; i < 3; i++) for (var j = 0; j < 4; j++)
        box(0.38, 0.35, 0.3, c.flowers[(i + j) % c.flowers.length], x - 0.85 + j * 0.57, 0.45 + i * 0.7, z + 0.08, s);
    },
    sample: function (s, x, z, c, i) {
      var panel = box(0.9, 1.6, 0.06, c.flowers[i % c.flowers.length], x, 1.2, z, s);
      for (var k = 0; k < 5; k++) box(0.04, 1.6, 0.1, 0x222222, x - 0.36 + k * 0.18, 1.2, z + 0.02, s);
      panel.material.metalness = 0.6; panel.material.roughness = 0.35;
    },
    smoker: function (s, x, z, c) {
      var b = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.55, 2.2, 24), mat(0x1c1c1c, 0.5));
      b.rotation.z = Math.PI / 2; b.position.set(x, 1.0, z); b.castShadow = true; s.add(b);
      cyl(0.12, 1.4, 0x1c1c1c, x + 0.8, 1.9, z, s);
      box(0.08, 0.9, 0.08, 0x333333, x - 0.9, 0.45, z, s); box(0.08, 0.9, 0.08, 0x333333, x + 0.9, 0.45, z, s);
    },
    booth: function (s, x, z, c) {
      box(2.2, 0.5, 0.8, c.accent, x, 0.25, z - 0.9, s); box(2.2, 1.1, 0.2, c.accent, x, 0.75, z - 1.3, s);
      box(2.2, 0.5, 0.8, c.accent, x, 0.25, z + 0.9, s); box(2.2, 1.1, 0.2, c.accent, x, 0.75, z + 1.3, s);
      box(1.8, 0.06, 1.0, c.top, x, 0.78, z, s); box(0.1, 0.74, 0.1, c.metal, x, 0.39, z, s);
    }
  };

  window.PXD2Room = {
    boot: function (cfg) {
      var stage = document.getElementById("room");
      var c = cfg.colors;
      var renderer = new THREE.WebGLRenderer({ antialias: true });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.shadowMap.enabled = true;
      renderer.outputEncoding = THREE.sRGBEncoding;
      stage.appendChild(renderer.domElement);
      var scene = new THREE.Scene(); scene.background = new THREE.Color(c.sky);
      var cam = new THREE.PerspectiveCamera(60, 1, 0.1, 100); cam.position.set(0, 3.2, 8.5);
      var controls = new THREE.OrbitControls(cam, renderer.domElement);
      controls.target.set(0, 1.3, 0); controls.enableDamping = true;
      controls.maxPolarAngle = Math.PI * 0.49; controls.minDistance = 2.5; controls.maxDistance = 11;
      controls.autoRotate = !matchMedia("(prefers-reduced-motion: reduce)").matches; controls.autoRotateSpeed = 0.6;
      renderer.domElement.addEventListener("pointerdown", function () { controls.autoRotate = false; });

      scene.add(new THREE.HemisphereLight(0xffffff, c.floor, 0.65));
      var sun = new THREE.DirectionalLight(0xfff2dd, 0.9); sun.position.set(5, 9, 6); sun.castShadow = true;
      sun.shadow.mapSize.set(1024, 1024); ["left", "bottom"].forEach(function (k) { sun.shadow.camera[k] = -10; });
      ["right", "top"].forEach(function (k) { sun.shadow.camera[k] = 10; }); scene.add(sun);
      var warm = new THREE.PointLight(c.glow || 0xffc98a, 0.6, 14); warm.position.set(0, 3.4, 0); scene.add(warm);

      var W = 14, D = 10, H = 4;
      var floor = new THREE.Mesh(new THREE.PlaneGeometry(W, D), mat(c.floor, 0.9));
      floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; scene.add(floor);
      box(W, H, 0.2, c.wall, 0, H / 2, -D / 2, scene);
      box(0.2, H, D, c.wall2 || c.wall, -W / 2, H / 2, 0, scene);
      box(0.2, H, D, c.wall2 || c.wall, W / 2, H / 2, 0, scene);
      box(W, 0.3, 0.25, c.trim, 0, 0.15, -D / 2 + 0.15, scene);

      var sign = new THREE.Mesh(new THREE.PlaneGeometry(6, 1.5),
        new THREE.MeshBasicMaterial({ map: signTexture(cfg.sign, cfg.signSub, cfg.signBg, cfg.signFg) }));
      sign.position.set(0, 3.0, -D / 2 + 0.12); scene.add(sign);

      (cfg.props || []).forEach(function (p, i) { PROPS[p[0]](scene, p[1], p[2], c, i); });

      function size() {
        var w = stage.clientWidth, h = stage.clientHeight;
        renderer.setSize(w, h); cam.aspect = w / h; cam.updateProjectionMatrix();
      }
      window.addEventListener("resize", size); size();
      (function loop() { requestAnimationFrame(loop); controls.update(); renderer.render(scene, cam); })();
    }
  };
})();
