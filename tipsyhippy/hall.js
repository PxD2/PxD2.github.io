import * as THREE from "three";
import { VRButton } from "three/addons/webxr/VRButton.js";

const PHONE = "tel:+19283581972";
const ORDER =
  "https://order.spoton.com/so-tipsy-hippy-grill-19076/lakeside-az/66302d9ef52c5a003da949ff/";
const DEST = "2251 W White Mountain Blvd, Pinetop-Lakeside, AZ 85929";
const DIR_GOOGLE = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(DEST)}`;
const DIR_APPLE = `https://maps.apple.com/?daddr=${encodeURIComponent(DEST)}`;
const ios = /iPhone|iPad|iPod/i.test(navigator.userAgent);
const coarse = matchMedia("(pointer: coarse)").matches;

const dirBtn = document.getElementById("btn-dir");
dirBtn.href = ios ? DIR_APPLE : DIR_GOOGLE;
document.getElementById("btn-call").href = PHONE;

const H = 1.65;
const spots = [
  { id: "indoor", name: "Dining room", copy: "Log walls, terracotta, teal booths. Walk the aisle to the patio door.", pos: [0, H, -10], look: [0, 1.5, -16] },
  { id: "door", name: "Patio door", copy: "Same cabin. Through the door you are on the pavers, pines overhead.", pos: [0, H, -3.2], look: [0, 1.5, 6] },
  { id: "patio", name: "Patio", copy: "Stone fire table, string lights, green roof. Best outdoor seating in town.", pos: [2, H, 3], look: [6, 1.4, -1] },
  { id: "pergola", name: "Pergola", copy: "White columns, turf, umbrellas. Lawn runs to the fence and the ponderosas.", pos: [-6.5, H, 8], look: [2, 1.3, 16] },
  { id: "lawn", name: "Forest lawn", copy: "Shack, high-tops, dogs welcome. Ponderosas at the fence — this is the White Mountains.", pos: [0, H, 12], look: [4, 3, 22] },
  { id: "bar", name: "Love Shack", copy: "Off the dining room. Taps, cocktails, the bar people remember.", pos: [8.5, H, -8], look: [12, 1.5, -8] },
];

const keys = {};
const walls = [];
const joy = { x: 0, z: 0 };
let mode = "idle";
let yaw = 0;
let pitch = 0;
let tour = 0;
let walking = false;
let tween = null;
let dragging = false;
let lastX = 0;
let lastY = 0;

const stage = document.getElementById("stage");
const idle = document.getElementById("idle");
const card = document.getElementById("card");
const walkBar = document.getElementById("walk-bar");
const spotLabel = document.getElementById("spot-label");
const stick = document.getElementById("stick");
const knob = document.getElementById("knob");

const renderer = new THREE.WebGLRenderer({ antialias: !coarse, powerPreference: "high-performance", alpha: false });
renderer.setPixelRatio(Math.min(devicePixelRatio, coarse ? 1.4 : 2));
renderer.setSize(innerWidth, innerHeight);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.12;
renderer.shadowMap.enabled = !coarse;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.xr.enabled = true;
stage.appendChild(renderer.domElement);

const vrBtn = VRButton.createButton(renderer);
vrBtn.id = "vr-btn";
document.body.appendChild(vrBtn);

const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2("#8fb4c8", 0.016);

const camera = new THREE.PerspectiveCamera(coarse ? 74 : 68, innerWidth / innerHeight, 0.08, 260);
camera.position.set(0, H, 0);
const rig = new THREE.Group();
rig.position.set(0, 0, -10);
rig.add(camera);
scene.add(rig);

const ctrl0 = renderer.xr.getController(0);
const ctrl1 = renderer.xr.getController(1);
rig.add(ctrl0, ctrl1);

const loader = new THREE.TextureLoader();
const windMats = [];
const swayTrees = [];
function tex(src, rx = 1, ry = 1) {
  const t = loader.load(src);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(rx, ry);
  t.anisotropy = 8;
  return t;
}

function solid(color) {
  return new THREE.MeshStandardMaterial({ color, roughness: 0.86, metalness: 0.02 });
}

function addBox(w, h, d, x, y, z, mat, collide = true) {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
  mesh.position.set(x, y, z);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  scene.add(mesh);
  if (collide) walls.push({ minx: x - w / 2, maxx: x + w / 2, minz: z - d / 2, maxz: z + d / 2 });
  return mesh;
}

function photoWall(src, w, h, x, y, z, rotY) {
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ map: tex(src) }));
  mesh.position.set(x, y, z);
  mesh.rotation.y = rotY;
  scene.add(mesh);
  return mesh;
}

function doorWall({ cx, cz, along, length, y = 1.7, h = 3.4, door = 0, doorW = 1.7, doorH = 2.25, mat }) {
  const thick = 0.28;
  const leftLen = length / 2 + door - doorW / 2;
  const rightLen = length / 2 - door - doorW / 2;
  if (along === "x") {
    const leftC = cx - length / 2 + leftLen / 2;
    const rightC = cx + length / 2 - rightLen / 2;
    if (leftLen > 0.2) addBox(leftLen, h, thick, leftC, y, cz, mat);
    if (rightLen > 0.2) addBox(rightLen, h, thick, rightC, y, cz, mat);
    addBox(doorW + 0.05, h - doorH, thick, cx + door, y + doorH / 2 + (h - doorH) / 2, cz, mat);
  } else {
    const leftC = cz - length / 2 + leftLen / 2;
    const rightC = cz + length / 2 - rightLen / 2;
    if (leftLen > 0.2) addBox(thick, h, leftLen, cx, y, leftC, mat);
    if (rightLen > 0.2) addBox(thick, h, rightLen, cx, y, rightC, mat);
    addBox(thick, h - doorH, doorW + 0.05, cx, y + doorH / 2 + (h - doorH) / 2, cz + door, mat);
  }
}

function alphaTex(src, punchSky = true) {
  return new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      const c = document.createElement("canvas");
      c.width = img.width;
      c.height = img.height;
      const g = c.getContext("2d");
      g.drawImage(img, 0, 0);
      const data = g.getImageData(0, 0, c.width, c.height);
      const p = data.data;
      for (let i = 0; i < p.length; i += 4) {
        const r = p[i], gr = p[i + 1], b = p[i + 2];
        const sky = punchSky && b > 130 && b > r + 18 && b > gr - 8;
        const white = r > 228 && gr > 228 && b > 228;
        if (sky || white) p[i + 3] = 0;
      }
      g.putImageData(data, 0, 0);
      const t = new THREE.CanvasTexture(c);
      t.colorSpace = THREE.SRGBColorSpace;
      t.anisotropy = 8;
      resolve(t);
    };
    img.src = src;
  });
}

const log = solid("#6b4a2e");
const logDark = solid("#4d3420");
const teal = solid("#2d6b5e");
const stone = solid("#8d7a66");
const paver = solid("#9a8b78");
const turf = solid("#4f8a3a");
const roof = solid("#2f6b4a");
const cream = solid("#d8d0c4");
const wood = solid("#5a3c24");
const needle = new THREE.MeshStandardMaterial({ color: "#1c4a28", roughness: 0.92 });
const needle2 = new THREE.MeshStandardMaterial({ color: "#2a5c32", roughness: 0.9 });
const barkMat = new THREE.MeshStandardMaterial({ map: tex("./images/bark.jpg", 1, 3), roughness: 0.95 });

const skyMap = tex("./images/sky.jpg");
const sky = new THREE.Mesh(
  new THREE.SphereGeometry(160, 32, 20),
  new THREE.MeshBasicMaterial({ map: skyMap, side: THREE.BackSide, depthWrite: false }),
);
scene.add(sky);

const hemi = new THREE.HemisphereLight("#cfe6ff", "#3d4a22", 1.05);
scene.add(hemi);
const sun = new THREE.DirectionalLight("#fff3c8", 2.1);
sun.position.set(-18, 28, 10);
sun.castShadow = !coarse;
if (!coarse) {
  sun.shadow.mapSize.set(1024, 1024);
  sun.shadow.camera.near = 2;
  sun.shadow.camera.far = 80;
  sun.shadow.camera.left = sun.shadow.camera.bottom = -30;
  sun.shadow.camera.right = sun.shadow.camera.top = 30;
}
scene.add(sun);
scene.add(new THREE.AmbientLight("#2a2018", 0.22));
const indoorLamp = new THREE.PointLight("#ffd7a0", 34, 18, 2);
indoorLamp.position.set(0, 3.1, -9);
scene.add(indoorLamp);
const patioLamp = new THREE.PointLight("#ffcc77", 26, 16, 2);
patioLamp.position.set(0, 3.8, 4);
scene.add(patioLamp);

addBox(120, 0.08, 120, 0, -0.04, 10, turf, false);
addBox(11.6, 0.06, 12.2, 0, 0.03, -8.1, solid("#b56a3a"), false);
addBox(16, 0.05, 11, 1, 0.025, 3.2, paver, false);
addBox(18, 0.04, 16, 1, 0.02, 14, turf, false);
addBox(90, 0.05, 90, 0, 0.01, 20, new THREE.MeshStandardMaterial({ color: "#3a4a28", roughness: 1 }), false);

doorWall({ cx: 0, cz: -14.1, along: "x", length: 12, mat: logDark });
doorWall({ cx: -6.05, cz: -8, along: "z", length: 12.4, mat: log });
doorWall({ cx: 0, cz: -2.05, along: "x", length: 12, door: 0, mat: log, doorW: 1.8, doorH: 2.3 });
doorWall({ cx: 6.05, cz: -10.2, along: "z", length: 8, door: 1.6, mat: log, doorW: 1.6, doorH: 2.2 });
addBox(8.2, 3.4, 0.28, 10, 1.7, -3.95, logDark);
addBox(0.28, 3.4, 8.4, 14.05, 1.7, -8, log);
addBox(8.2, 3.4, 0.28, 10, 1.7, -12.05, log);
addBox(12.2, 0.2, 12.4, 0, 3.45, -8, logDark, false);
addBox(8.4, 0.2, 8.4, 10, 3.45, -8, logDark, false);

photoWall("./images/indoor.jpg", 10.6, 3.15, 0, 1.7, -13.92, 0);
photoWall("./images/booths.jpg", 11.6, 3.15, -5.9, 1.7, -8, Math.PI / 2);
photoWall("./images/doorway.jpg", 5.4, 3.0, 0, 1.65, -2.22, Math.PI);
photoWall("./images/cabin-wall.jpg", 11.2, 3.2, 0, 1.7, -1.88, 0);
photoWall("./images/loveshack.jpg", 7.6, 3.05, 13.88, 1.7, -8, -Math.PI / 2);
photoWall("./images/bar.jpg", 7.6, 3.05, 10, 1.7, -12.18, 0);
photoWall("./images/patio.jpg", 9.4, 4.4, 7.4, 2.2, 3.4, -Math.PI / 2);
photoWall("./images/pergola.jpg", 10.5, 5.2, -8.6, 2.5, 11, Math.PI / 2);
photoWall("./images/shack.jpg", 12, 5.4, 1, 2.6, 21.4, Math.PI);
photoWall("./images/wings.jpg", 1.6, 0.95, -2.1, 1.55, -12.4, 0.15);
photoWall("./images/forest.jpg", 48, 16, 0, 7.5, 38, Math.PI);
photoWall("./images/forest.jpg", 36, 14, -28, 6.8, 18, Math.PI / 2);
photoWall("./images/forest.jpg", 36, 14, 28, 6.8, 18, -Math.PI / 2);

addBox(13, 0.12, 7.2, 0, 3.55, -0.6, roof, false);
addBox(0.7, 2.4, 0.7, 4.6, 4.5, -1.4, stone, false);

[[-4.6, -6.4], [-4.6, -10.2], [4.6, -6.4], [4.6, -10.8]].forEach(([x, z]) => addBox(1.5, 0.9, 3.2, x, 0.55, z, teal));
[[-1.2, -8.4], [1.3, -7.2], [0, -11]].forEach(([x, z]) => addBox(1.3, 0.72, 0.8, x, 0.42, z, wood, false));
addBox(0.22, 2.6, 0.22, 0.1, 1.4, -8.6, wood, false);
addBox(2.3, 1.05, 1.15, -5.2, 0.55, 1.4, stone);
addBox(2.3, 0.08, 1.15, -5.2, 1.1, 1.4, solid("#5f8a7a"), false);
[[-4.2, 2.1], [-6.1, 2.1], [-4.2, 0.6], [-6.1, 0.6]].forEach(([x, z]) => addBox(0.32, 0.55, 0.32, x, 0.35, z, solid("#1a1a1a"), false));
[[2.4, 2.8], [4.6, 4.2], [1.2, 5.1]].forEach(([x, z], i) => {
  addBox(1.2, 0.7, 0.7, x, 0.4, z, solid("#4a4a4a"), false);
  const umb = new THREE.Mesh(new THREE.ConeGeometry(1.15, 0.28, 12), solid(["#c43b2b", "#2457a8", "#d24c7a"][i]));
  umb.position.set(x, 2.35, z);
  scene.add(umb);
  addBox(0.06, 2.1, 0.06, x, 1.15, z, solid("#333"), false);
});
[-8.6, -5.4].forEach((x) => {
  [7.2, 10.4].forEach((z) => addBox(0.38, 2.8, 0.38, x, 1.5, z, cream));
});
addBox(3.6, 0.16, 0.28, -7, 2.95, 7.2, wood, false);
addBox(3.6, 0.16, 0.28, -7, 2.95, 10.4, wood, false);
addBox(0.28, 0.16, 3.5, -8.6, 2.95, 8.8, wood, false);
addBox(0.28, 0.16, 3.5, -5.4, 2.95, 8.8, wood, false);
addBox(1.4, 0.7, 0.7, -7, 0.4, 8.6, solid("#6b675e"), false);
addBox(0.7, 0.55, 0.7, -8.1, 0.35, 8.2, cream, false);
addBox(0.7, 0.55, 0.7, -5.9, 0.35, 8.2, cream, false);

function stringLights(from, to, n = 10) {
  for (let i = 0; i < n; i++) {
    const u = i / (n - 1);
    const bulb = new THREE.Mesh(new THREE.SphereGeometry(0.05, 8, 8), new THREE.MeshBasicMaterial({ color: "#ffd58a" }));
    bulb.position.lerpVectors(from, to, u);
    bulb.position.y += Math.sin(u * Math.PI) * 0.15;
    scene.add(bulb);
    if (i % 3 === 0) {
      const l = new THREE.PointLight("#ffcc88", 2.4, 5, 2);
      l.position.copy(bulb.position);
      scene.add(l);
    }
  }
}
stringLights(new THREE.Vector3(-8.5, 3.05, 7.3), new THREE.Vector3(-5.5, 3.05, 10.3), 8);
stringLights(new THREE.Vector3(-4, 3.4, 1), new THREE.Vector3(5, 3.4, 5), 12);

function ponderosa3d(x, z, s = 1) {
  const g = new THREE.Group();
  const trunkH = 11 * s;
  const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.16 * s, 0.42 * s, trunkH, 10), barkMat);
  trunk.position.y = trunkH / 2;
  trunk.castShadow = true;
  g.add(trunk);
  const crown = new THREE.Group();
  const clusters = [
    [0, 0, 0, 2.6],
    [0.85, -1.3, 0.2, 1.9],
    [-0.7, -0.8, -0.45, 1.85],
    [0.15, 1.2, 0.2, 1.55],
    [-0.35, -2.4, 0.55, 1.7],
    [0.55, -2.0, -0.5, 1.4],
  ];
  clusters.forEach(([cx, cy, cz, r], i) => {
    const c = new THREE.Mesh(
      new THREE.SphereGeometry(r * s, 11, 8),
      i % 2 ? needle : needle2,
    );
    c.position.set(cx * s, trunkH + cy * s, cz * s);
    c.scale.set(1.05, 0.62, 1.1);
    c.castShadow = true;
    crown.add(c);
  });
  g.add(crown);
  g.position.set(x, 0, z);
  g.rotation.y = Math.random() * Math.PI;
  g.userData = { phase: Math.random() * 6, crown };
  scene.add(g);
  swayTrees.push(g);
}

const nearPines = [
  [-11, 15], [-9.5, 19], [10.5, 17], [13, 13], [8.5, 22], [-6, 23],
  [16, 9], [-16, 8], [14.5, 21], [-14, 17], [18, 16], [-13, 12],
  [12, 8], [-10, 10], [7, 24], [-3, 25], [3, 24.5], [20, 12],
];
nearPines.forEach(([x, z], i) => ponderosa3d(x, z, 0.85 + (i % 5) * 0.12));

addBox(0.12, 1.1, 16, 10.4, 0.55, 14, wood);
addBox(18, 1.1, 0.12, 1, 0.55, 22.2, wood);

alphaTex("./images/ponderosa.jpg").then((t) => {
  const mat = new THREE.MeshBasicMaterial({
    map: t,
    transparent: true,
    alphaTest: 0.22,
    side: THREE.DoubleSide,
    depthWrite: false,
  });
  mat.onBeforeCompile = (shader) => {
    shader.uniforms.uTime = { value: 0 };
    shader.vertexShader = `uniform float uTime;\n${shader.vertexShader.replace(
      "#include <begin_vertex>",
      `#include <begin_vertex>
       float lift = clamp(transformed.y / 6.0 + 0.5, 0.0, 1.0);
       transformed.x += sin(uTime * 0.85 + transformed.y * 0.35) * lift * 0.22;
       transformed.z += cos(uTime * 0.62 + transformed.x * 0.2) * lift * 0.14;`,
    )}`;
    mat.userData.shader = shader;
  };
  windMats.push(mat);
  const geo = new THREE.PlaneGeometry(6.8, 14.4, 6, 10);
  for (let i = 0; i < 52; i++) {
    const a = (i / 52) * Math.PI * 1.2 + 0.15;
    const r = 22 + (i % 6) * 4.2 + (i % 4);
    const x = Math.sin(a) * r;
    const z = 6 + Math.cos(a) * r * 0.7 + 12;
    const s = 0.9 + (i % 7) * 0.11;
    const g = new THREE.Group();
    for (let k = 0; k < 3; k++) {
      const p = new THREE.Mesh(geo, mat);
      p.rotation.y = (k * Math.PI) / 3;
      g.add(p);
    }
    g.position.set(x, 7.1 * s, z);
    g.scale.setScalar(s);
    g.userData = { phase: Math.random() * 8, crown: g };
    scene.add(g);
    swayTrees.push(g);
  }
});

function collide(next) {
  const r = 0.32;
  for (const w of walls) {
    if (next.x + r > w.minx && next.x - r < w.maxx && next.z + r > w.minz && next.z - r < w.maxz) return true;
  }
  return next.x < -16 || next.x > 16 || next.z < -15.2 || next.z > 23;
}

function playerPos() {
  const p = new THREE.Vector3();
  if (renderer.xr.isPresenting) camera.getWorldPosition(p);
  else p.set(rig.position.x, H, rig.position.z);
  return p;
}

function nearestSpot(p) {
  let best = spots[0];
  let d = 1e9;
  for (const s of spots) {
    const dx = p.x - s.pos[0];
    const dz = p.z - s.pos[2];
    const n = dx * dx + dz * dz;
    if (n < d) { d = n; best = s; }
  }
  return best;
}

function setCard(spot) {
  card.classList.remove("hidden");
  card.innerHTML = `<p class="kicker">Room</p><h3>${spot.name}</h3><p>${spot.copy}</p>`;
  spotLabel.textContent = spot.name;
}

function lookFrom(pos, look) {
  yaw = Math.atan2(look.x - pos.x, -(look.z - pos.z));
  pitch = 0;
}

function goTo(id, instant = false) {
  const spot = spots.find((s) => s.id === id) || spots[0];
  tour = spots.indexOf(spot);
  setCard(spot);
  const target = new THREE.Vector3(spot.pos[0], 0, spot.pos[2]);
  const look = new THREE.Vector3(...spot.look);
  lookFrom(new THREE.Vector3(spot.pos[0], H, spot.pos[2]), look);
  if (instant) {
    rig.position.copy(target);
    if (!renderer.xr.isPresenting) {
      rig.rotation.y = yaw;
      camera.rotation.x = pitch;
    }
    return;
  }
  const start = rig.position.clone();
  const startYaw = rig.rotation.y;
  const t0 = performance.now();
  tween = (now) => {
    const u = Math.min(1, (now - t0) / 1100);
    const e = 1 - (1 - u) ** 3;
    rig.position.lerpVectors(start, target, e);
    if (!renderer.xr.isPresenting) {
      rig.rotation.y = startYaw + (yaw - startYaw) * e;
      camera.rotation.x = pitch;
    }
    if (u < 1) requestAnimationFrame(tween);
    else tween = null;
  };
  requestAnimationFrame(tween);
}

function enter(next = "tour") {
  mode = next;
  idle.classList.add("hidden");
  walkBar.classList.remove("hidden");
  document.body.classList.add("walking");
  if (next === "walk") {
    walking = true;
    stick.classList.remove("hidden");
    if (!coarse) renderer.domElement.requestPointerLock?.();
    setCard(nearestSpot(playerPos()));
  } else {
    walking = false;
    stick.classList.add("hidden");
    document.exitPointerLock?.();
    goTo(spots[tour].id);
  }
}

function exitWalk() {
  mode = "idle";
  walking = false;
  document.exitPointerLock?.();
  document.body.classList.remove("walking");
  idle.classList.remove("hidden");
  walkBar.classList.add("hidden");
  stick.classList.add("hidden");
  card.classList.add("hidden");
  joy.x = joy.z = 0;
}

document.getElementById("btn-enter").onclick = () => { tour = 0; enter("tour"); };
document.getElementById("btn-walk").onclick = () => enter("walk");
document.getElementById("btn-dock-walk").onclick = () => enter("walk");
document.getElementById("btn-tour").onclick = () => enter("tour");
document.getElementById("btn-exit").onclick = exitWalk;
document.getElementById("btn-next").onclick = () => { tour = (tour + 1) % spots.length; walking = false; enter("tour"); };
document.getElementById("btn-prev").onclick = () => { tour = (tour - 1 + spots.length) % spots.length; walking = false; enter("tour"); };
document.querySelectorAll("[data-go]").forEach((btn) => {
  btn.onclick = () => { walking = false; enter("tour"); goTo(btn.dataset.go); };
});

addEventListener("keydown", (e) => {
  keys[e.code] = true;
  if (e.code === "Escape") exitWalk();
  if (e.code === "Enter" && mode === "idle") enter("walk");
});
addEventListener("keyup", (e) => { keys[e.code] = false; });

function lookDelta(dx, dy) {
  yaw -= dx * 0.0024;
  pitch -= dy * 0.0024;
  pitch = Math.max(-1.15, Math.min(1.15, pitch));
}

addEventListener("mousemove", (e) => {
  if (walking && document.pointerLockElement === renderer.domElement) lookDelta(e.movementX, e.movementY);
});

renderer.domElement.addEventListener("pointerdown", (e) => {
  if (!walking) return;
  if (e.target === stick || stick.contains(e.target)) return;
  dragging = true;
  lastX = e.clientX;
  lastY = e.clientY;
  renderer.domElement.setPointerCapture(e.pointerId);
  if (!coarse) renderer.domElement.requestPointerLock?.();
});
renderer.domElement.addEventListener("pointermove", (e) => {
  if (!dragging || !walking) return;
  if (document.pointerLockElement === renderer.domElement) return;
  lookDelta(e.clientX - lastX, e.clientY - lastY);
  lastX = e.clientX;
  lastY = e.clientY;
});
renderer.domElement.addEventListener("pointerup", () => { dragging = false; });

function stickAt(e) {
  const r = stick.getBoundingClientRect();
  const cx = r.left + r.width / 2;
  const cy = r.top + r.height / 2;
  let dx = e.clientX - cx;
  let dy = e.clientY - cy;
  const max = r.width * 0.34;
  const m = Math.hypot(dx, dy) || 1;
  if (m > max) { dx *= max / m; dy *= max / m; }
  knob.style.transform = `translate(${dx}px, ${dy}px)`;
  joy.x = dx / max;
  joy.z = dy / max;
}
stick.addEventListener("pointerdown", (e) => {
  e.preventDefault();
  stick.setPointerCapture(e.pointerId);
  stickAt(e);
});
stick.addEventListener("pointermove", (e) => {
  if (stick.hasPointerCapture(e.pointerId)) stickAt(e);
});
const zeroStick = () => { joy.x = joy.z = 0; knob.style.transform = ""; };
stick.addEventListener("pointerup", zeroStick);
stick.addEventListener("pointercancel", zeroStick);

addEventListener("resize", () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

const clock = new THREE.Clock();
function xrMove(dt) {
  const session = renderer.xr.getSession();
  if (!session) return;
  let ax = 0, az = 0;
  for (const src of session.inputSources) {
    const gp = src.gamepad;
    if (!gp) continue;
    const x = gp.axes[2] ?? gp.axes[0] ?? 0;
    const y = gp.axes[3] ?? gp.axes[1] ?? 0;
    if (Math.abs(x) > Math.abs(ax)) ax = x;
    if (Math.abs(y) > Math.abs(az)) az = y;
  }
  if (Math.abs(ax) < 0.15) ax = 0;
  if (Math.abs(az) < 0.15) az = 0;
  if (!ax && !az) return;
  const dir = new THREE.Vector3();
  camera.getWorldDirection(dir);
  dir.y = 0;
  dir.normalize();
  const right = new THREE.Vector3().crossVectors(dir, new THREE.Vector3(0, 1, 0)).normalize();
  const next = rig.position.clone();
  next.addScaledVector(dir, -az * 3.6 * dt);
  next.addScaledVector(right, ax * 3.6 * dt);
  const tryX = next.clone(); tryX.z = rig.position.z;
  if (!collide({ x: tryX.x, z: tryX.z })) rig.position.x = tryX.x;
  const tryZ = next.clone(); tryZ.x = rig.position.x;
  if (!collide({ x: tryZ.x, z: tryZ.z })) rig.position.z = tryZ.z;
}

function tick() {
  const dt = Math.min(clock.getDelta(), 0.05);
  const t = clock.elapsedTime;
  sky.position.copy(rig.position);
  windMats.forEach((m) => {
    if (m.userData.shader) m.userData.shader.uniforms.uTime.value = t;
  });
  swayTrees.forEach((g) => {
    const ph = g.userData.phase || 0;
    g.rotation.z = Math.sin(t * 0.55 + ph) * 0.028;
    g.rotation.x = Math.cos(t * 0.42 + ph) * 0.016;
    if (g.userData.crown && g.userData.crown !== g) {
      g.userData.crown.rotation.y = Math.sin(t * 0.35 + ph) * 0.08;
    }
  });
  if (renderer.xr.isPresenting) {
    xrMove(dt);
  } else if (walking && !tween) {
    const dir = new THREE.Vector3(Math.sin(yaw), 0, -Math.cos(yaw));
    const right = new THREE.Vector3().crossVectors(dir, new THREE.Vector3(0, 1, 0)).negate();
    const speed = (keys.ShiftLeft ? 6.4 : 3.5) * dt;
    const next = rig.position.clone();
    if (keys.KeyW) next.addScaledVector(dir, speed);
    if (keys.KeyS) next.addScaledVector(dir, -speed);
    if (keys.KeyA) next.addScaledVector(right, -speed);
    if (keys.KeyD) next.addScaledVector(right, speed);
    next.addScaledVector(dir, -joy.z * 3.8 * dt);
    next.addScaledVector(right, joy.x * 3.8 * dt);
    const tryX = next.clone(); tryX.z = rig.position.z;
    if (!collide({ x: tryX.x, z: tryX.z })) rig.position.x = tryX.x;
    const tryZ = next.clone(); tryZ.x = rig.position.x;
    if (!collide({ x: tryZ.x, z: tryZ.z })) rig.position.z = tryZ.z;
    rig.rotation.y = yaw;
    camera.rotation.x = pitch;
    camera.rotation.y = 0;
    camera.rotation.z = 0;
    const here = nearestSpot(playerPos());
    if (spotLabel.textContent !== here.name) setCard(here);
  }
  renderer.render(scene, camera);
}

renderer.xr.addEventListener("sessionstart", () => enter("walk"));
renderer.setAnimationLoop(tick);
goTo("indoor", true);
window.__tipsy = { ORDER, PHONE, DIR_GOOGLE, goTo, enter, spots };
