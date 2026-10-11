/* PXD2 VR Store engine — a 3D / WebXR storefront any PXD2 client site can run.
 * A client folder holds index.html (loads three.js + this file) and store.json.
 * Payments go straight to the store owner's own accounts (links and wallet
 * addresses in store.json). PXD2 never holds the money.
 */
(function () {
  "use strict";
  var PAY_LABELS = {
    stripe: "Card (Stripe)", paypal: "PayPal", square: "Square", cashapp: "Cash App", venmo: "Venmo",
    coinbase: "Crypto (Coinbase Commerce)", btcpay: "Crypto (BTCPay)"
  };
  var WALLET_LABELS = { btc: "Bitcoin", eth: "Ethereum", sol: "Solana", usdc: "USDC", ltc: "Litecoin", doge: "Dogecoin" };

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function money(p, cur) { if (p == null || p === "") return ""; try { return new Intl.NumberFormat(undefined, { style: "currency", currency: cur || "USD" }).format(p); } catch (e) { return "$" + p; } }
  function safeUrl(u) { return /^(https:|mailto:)/i.test(u || "") ? u : ""; }

  function labelTexture(lines, opts) {
    opts = opts || {};
    var c = document.createElement("canvas"); c.width = 512; c.height = 160;
    var g = c.getContext("2d");
    g.fillStyle = opts.bg || "rgba(11,11,10,.86)"; g.fillRect(0, 0, 512, 160);
    g.strokeStyle = opts.edge || "#c9a46a"; g.lineWidth = 4; g.strokeRect(2, 2, 508, 156);
    g.fillStyle = "#e8dfc8"; g.font = "600 40px system-ui, sans-serif"; g.textBaseline = "top";
    g.fillText(String(lines[0] || "").slice(0, 22), 22, 22);
    g.fillStyle = opts.sub || "#c9a46a"; g.font = "500 34px system-ui, sans-serif";
    g.fillText(String(lines[1] || "").slice(0, 26), 22, 92);
    var t = new THREE.CanvasTexture(c); t.anisotropy = 4; return t;
  }

  function buildPanel(store) {
    var root = el("aside", "vs-panel"); root.hidden = true; root.setAttribute("aria-live", "polite");
    var close = el("button", "vs-close", "Close"); close.type = "button";
    close.addEventListener("click", function () { root.hidden = true; });
    root.appendChild(close);
    var body = el("div", "vs-body"); root.appendChild(body);
    document.body.appendChild(root);
    return {
      show: function (p) {
        body.textContent = "";
        if (p.example) body.appendChild(el("span", "vs-tag", "Example item"));
        if (store.pitch) body.appendChild(el("span", "vs-tag", "Preview"));
        if (safeUrl(p.image)) { var im = el("img", "vs-img"); im.src = p.image; im.alt = p.name || ""; im.loading = "lazy"; body.appendChild(im); }
        body.appendChild(el("h2", "vs-name", p.name));
        var price = money(p.price, store.currency); if (price) body.appendChild(el("div", "vs-price", price));
        if (p.description) body.appendChild(el("p", "vs-desc", p.description));
        var links = Object.assign({}, store.pay || {}, p.pay || {});
        var row = el("div", "vs-pay"), any = false;
        Object.keys(PAY_LABELS).forEach(function (k) {
          var u = safeUrl(links[k]); if (!u) return;
          var a = el("a", "vs-btn", PAY_LABELS[k]); a.href = u; a.target = "_blank"; a.rel = "noopener"; row.appendChild(a); any = true;
        });
        if (any) { body.appendChild(el("h3", "vs-h", "Pay")); body.appendChild(row); }
        var wallets = Object.assign({}, store.wallets || {}, p.wallets || {}), wb = el("div", "vs-wallets"), anyW = false;
        Object.keys(WALLET_LABELS).forEach(function (k) {
          var addr = (wallets[k] || "").trim(); if (!addr) return; anyW = true;
          var w = el("div", "vs-wallet");
          w.appendChild(el("b", null, WALLET_LABELS[k]));
          var code = el("code", null, addr); w.appendChild(code);
          var cp = el("button", "vs-copy", "Copy address"); cp.type = "button";
          cp.addEventListener("click", function () {
            (navigator.clipboard ? navigator.clipboard.writeText(addr) : Promise.reject()).then(function () { cp.textContent = "Copied"; }, function () {
              var r = document.createRange(); r.selectNodeContents(code); var s = getSelection(); s.removeAllRanges(); s.addRange(r); cp.textContent = "Selected";
            });
            setTimeout(function () { cp.textContent = "Copy address"; }, 1500);
          });
          w.appendChild(cp);
          if (window.QRCode) { var q = el("div", "vs-qr"); w.appendChild(q); try { new QRCode(q, { text: addr, width: 112, height: 112 }); } catch (e) {} }
          wb.appendChild(w);
        });
        if (anyW) { body.appendChild(el("h3", "vs-h", "Pay with crypto")); body.appendChild(wb);
          body.appendChild(el("p", "vs-note", "Send the amount shown, then email your transaction ID to " + (store.contact || "the store") + ".")); }
        if (!any && !anyW) body.appendChild(el("p", "vs-note", "Payment options for this store aren't set up yet."));
        if (safeUrl(p.source)) { var src = el("a", "vs-btn", "See it on the current site"); src.href = p.source; src.target = "_blank"; src.rel = "noopener"; body.appendChild(src); }
        if (store.contact) body.appendChild(el("p", "vs-note", "Questions: " + store.contact));
        root.hidden = false; close.focus();
      }
    };
  }

  function start(store) {
    document.title = store.name || document.title;
    var head = document.querySelector(".vs-head");
    if (head) { head.querySelector(".vs-title").textContent = store.name || ""; head.querySelector(".vs-sub").textContent = store.tagline || ""; }

    var mount = document.getElementById("vs-stage");
    var renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    renderer.outputEncoding = THREE.sRGBEncoding;
    renderer.xr.enabled = true;
    mount.appendChild(renderer.domElement);

    var scene = new THREE.Scene();
    scene.background = new THREE.Color(store.theme && store.theme.bg || "#0b0b0a");
    scene.fog = new THREE.Fog(scene.background, 12, 28);
    var camera = new THREE.PerspectiveCamera(60, mount.clientWidth / mount.clientHeight, 0.05, 100);
    camera.position.set(0, 2.2, 7.5);

    scene.add(new THREE.HemisphereLight(0xfff2dd, 0x1a1814, 0.75));
    var key = new THREE.DirectionalLight(0xffffff, 0.9); key.position.set(4, 8, 5); scene.add(key);

    var floor = new THREE.Mesh(new THREE.CircleGeometry(14, 64), new THREE.MeshStandardMaterial({ color: 0x1b1916, roughness: 0.9 }));
    floor.rotation.x = -Math.PI / 2; scene.add(floor);
    var ring = new THREE.Mesh(new THREE.RingGeometry(4.6, 4.66, 96), new THREE.MeshBasicMaterial({ color: 0xc9a46a }));
    ring.rotation.x = -Math.PI / 2; ring.position.y = 0.01; scene.add(ring);

    var controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 1, 0); controls.enableDamping = true; controls.maxPolarAngle = Math.PI * 0.49;
    controls.minDistance = 2; controls.maxDistance = 14;
    controls.autoRotate = !(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);
    controls.autoRotateSpeed = 0.4;
    controls.addEventListener("start", function () { controls.autoRotate = false; });

    var panel = buildPanel(store);
    var pickables = [];
    var products = store.products || [];
    var loader = THREE.GLTFLoader ? new THREE.GLTFLoader() : null;
    products.forEach(function (p, i) {
      var a = (i / Math.max(products.length, 1)) * Math.PI * 2;
      var group = new THREE.Group(); group.position.set(Math.sin(a) * 4.6, 0, Math.cos(a) * 4.6); group.lookAt(0, 0, 0);
      var ped = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.62, 0.9, 32), new THREE.MeshStandardMaterial({ color: 0x2e2a24, roughness: 0.6 }));
      ped.position.y = 0.45; group.add(ped);
      var color = new THREE.Color(p.color || "#c9a46a");
      var stand = new THREE.Mesh(p.shape === "cylinder" ? new THREE.CylinderGeometry(0.28, 0.28, 0.7, 32) : p.shape === "sphere" ? new THREE.SphereGeometry(0.36, 32, 16) : new THREE.BoxGeometry(0.55, 0.55, 0.55),
        new THREE.MeshStandardMaterial({ color: color, roughness: 0.35, metalness: 0.2 }));
      stand.position.y = 1.3; group.add(stand);
      if (p.model && loader) {
        loader.load(p.model, function (g) {
          var m = g.scene, box = new THREE.Box3().setFromObject(m), size = box.getSize(new THREE.Vector3()), s = 0.9 / Math.max(size.x, size.y, size.z || 1);
          m.scale.setScalar(s); box.setFromObject(m); m.position.y = 0.9 - box.min.y; m.userData.product = p;
          group.remove(stand); group.add(m); m.traverse(function (o) { o.userData.product = p; }); pickables.push(m);
        }, undefined, function () { /* keep the stand-in shape */ });
      }
      stand.userData.product = p; pickables.push(stand);
      var sign = new THREE.Sprite(new THREE.SpriteMaterial({ map: labelTexture([p.name, money(p.price, store.currency)]) }));
      sign.scale.set(1.6, 0.5, 1); sign.position.y = 2.15; group.add(sign);
      group.userData.spin = stand; scene.add(group);
    });

    var ray = new THREE.Raycaster(), ptr = new THREE.Vector2(), down = null;
    function pick(x, y) {
      var r = renderer.domElement.getBoundingClientRect();
      ptr.set(((x - r.left) / r.width) * 2 - 1, -((y - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(ptr, camera);
      var hit = ray.intersectObjects(pickables, true)[0];
      if (hit) { var o = hit.object; while (o && !o.userData.product) o = o.parent; if (o) panel.show(o.userData.product); }
    }
    renderer.domElement.addEventListener("pointerdown", function (e) { down = [e.clientX, e.clientY]; });
    renderer.domElement.addEventListener("pointerup", function (e) { if (down && Math.hypot(e.clientX - down[0], e.clientY - down[1]) < 6) pick(e.clientX, e.clientY); down = null; });

    // VR: point a controller at a product and squeeze the trigger; the price sign lights up. Pay outside the headset.
    var vrNote = null;
    [0, 1].forEach(function (i) {
      var c = renderer.xr.getController(i); scene.add(c);
      var line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 0, -1)]), new THREE.LineBasicMaterial({ color: 0xc9a46a }));
      line.scale.z = 8; c.add(line);
      c.addEventListener("select", function () {
        var m = new THREE.Matrix4().extractRotation(c.matrixWorld);
        ray.ray.origin.setFromMatrixPosition(c.matrixWorld); ray.ray.direction.set(0, 0, -1).applyMatrix4(m);
        var hit = ray.intersectObjects(pickables, true)[0]; if (!hit) return;
        var o = hit.object; while (o && !o.userData.product) o = o.parent; if (!o) return;
        var p = o.userData.product;
        if (vrNote) scene.remove(vrNote);
        vrNote = new THREE.Sprite(new THREE.SpriteMaterial({ map: labelTexture([p.name + " " + money(p.price, store.currency), "Take off headset to pay"], { edge: "#c8282c" }) }));
        vrNote.scale.set(2.4, 0.75, 1); vrNote.position.set(0, 2.9, 0); scene.add(vrNote);
        panel.show(p);
      });
    });
    if (navigator.xr && navigator.xr.isSessionSupported) {
      navigator.xr.isSessionSupported("immersive-vr").then(function (ok) {
        if (!ok) return;
        var b = el("button", "vs-vr", "Enter VR"); b.type = "button"; var session = null;
        b.addEventListener("click", function () {
          if (session) { session.end(); return; }
          navigator.xr.requestSession("immersive-vr", { optionalFeatures: ["local-floor", "bounded-floor"] }).then(function (s) {
            session = s; b.textContent = "Exit VR"; renderer.xr.setSession(s);
            s.addEventListener("end", function () { session = null; b.textContent = "Enter VR"; });
          }).catch(function () { b.textContent = "VR unavailable"; });
        });
        document.body.appendChild(b);
      }).catch(function () {});
    }

    function size() { var w = mount.clientWidth, h = mount.clientHeight; renderer.setSize(w, h); camera.aspect = w / h; camera.updateProjectionMatrix(); }
    window.addEventListener("resize", size);
    var clock = new THREE.Clock();
    renderer.setAnimationLoop(function () {
      var t = clock.getElapsedTime();
      scene.children.forEach(function (g) { if (g.userData.spin) g.userData.spin.rotation.y = t * 0.5; });
      controls.update(); renderer.render(scene, camera);
    });
  }

  window.PXD2VRStore = {
    boot: function (url) {
      fetch(url || "store.json", { cache: "no-store" }).then(function (r) { return r.json(); }).then(start).catch(function (e) {
        var s = document.getElementById("vs-stage"); if (s) s.textContent = "This store's catalog could not load.";
        console.error(e);
      });
    }
  };
})();
