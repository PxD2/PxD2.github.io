import * as THREE from "three";

const ORDER =
  "https://order.spoton.com/so-tipsy-hippy-grill-19076/lakeside-az/66302d9ef52c5a003da949ff/";

const H = 1.65;
const spots = [
  {
    id: "indoor",
    name: "Dining room",
    copy: "Log walls, terracotta, teal booths. Eat drink & have fun. Walk the aisle to the patio door.",
    pos: [0, H, -10],
    look: [0, 1.5, -16],
  },
  {
    id: "door",
    name: "Patio door",
    copy: "Same cabin. Open the door and you are on the pavers.",
    pos: [0, H, -3.2],
    look: [0, 1.5, 4],
  },
  {
    id: "patio",
    name: "Patio",
    copy: "Stone fire table, string lights, green roof. Reviewers call this the best outdoor seating in town.",
    pos: [2, H, 3],
    look: [6, 1.4, -1],
  },
  {
    id: "pergola",
    name: "Pergola",
    copy: "White columns, lounge chairs, turf, Coca-Cola umbrellas. Lawn runs to the fence and the pines.",
    pos: [-6.5, H, 8],
    look: [2, 1.3, 16],
  },
  {
    id: "lawn",
    name: "Forest lawn",
    copy: "Metal-roof shack, high-tops, dogs welcome, cornhole when it’s out. Ponderosas at the fence.",
    pos: [0, H, 12],
    look: [0, 1.5, 20],
  },
  {
    id: "bar",
    name: "Love Shack",
    copy: "Off the dining room. Taps, cocktails, the bar people remember.",
    pos: [8.5, H, -8],
    look: [12, 1.5, -8],
  },
];

const keys = {};
const walls = [];
let mode = "idle";
let yaw = 0;
let pitch = 0;
let tour = 0;
let walking = false;
let tween = null;

const stage = document.getElementById("stage");
const idle = document.getElementById("idle");
const card = document.getElementById("card");
const walkBar = document.getElementById("walk-bar");
const spotLabel = document.getElementById("spot-label");

const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.08;
renderer.shadowMap.enabled = true;
stage.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color("#7eb7e0");
scene.fog = new THREE.Fog("#cfe4f2", 36, 85);

const camera = new THREE.PerspectiveCamera(68, innerWidth / innerHeight, 0.08, 140);
camera.position.set(0, H, -10);

const loader = new THREE.TextureLoader();
function tex(src, repeatX = 1, repeatY = 1) {
  const t = loader.load(src);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(repeatX, repeatY);
  return t;
}

function solid(color) {
  return new THREE.MeshLambertMaterial({ color });
}

function addBox(w, h, d, x, y, z, mat, collide = true) {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
  mesh.position.set(x, y, z);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  scene.add(mesh);
  if (collide) {
    walls.push({
      minx: x - w / 2,
      maxx: x + w / 2,
      minz: z - d / 2,
      maxz: z + d / 2,
    });
  }
  return mesh;
}

function photoWall(src, w, h, x, y, z, rotY) {
  const mesh = new THREE.Mesh(
    new THREE.PlaneGeometry(w, h),
    new THREE.MeshBasicMaterial({ map: tex(src) }),
  );
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

const log = solid("#6b4a2e");
const logDark = solid("#4d3420");
const teal = solid("#2d6b5e");
const stone = solid("#8d7a66");
const paver = solid("#9a8b78");
const turf = solid("#4f8a3a");
const roof = solid("#2f6b4a");
const cream = solid("#d8d0c4");
const wood = solid("#5a3c24");

scene.add(new THREE.HemisphereLight("#fff6dc", "#3d4a2a", 0.95));
const sun = new THREE.DirectionalLight("#fff1c2", 1.35);
sun.position.set(-12, 22, 8);
sun.castShadow = true;
scene.add(sun);
scene.add(new THREE.AmbientLight("#2a2018", 0.28));
const indoorLamp = new THREE.PointLight("#ffd7a0", 28, 16, 2);
indoorLamp.position.set(0, 3.1, -9);
scene.add(indoorLamp);
const patioLamp = new THREE.PointLight("#ffcc77", 18, 14, 2);
patioLamp.position.set(0, 3.6, 4);
scene.add(patioLamp);

addBox(80, 0.08, 80, 0, -0.04, 8, turf, false);
addBox(11.6, 0.06, 12.2, 0, 0.03, -8.1, solid("#b56a3a"), false);
addBox(16, 0.05, 11, 1, 0.025, 3.2, paver, false);
addBox(18, 0.04, 16, 1, 0.02, 14, turf, false);

doorWall({ cx: 0, cz: -14.1, along: "x", length: 12, mat: logDark });
doorWall({ cx: -6.05, cz: -8, along: "z", length: 12.4, mat: log });
doorWall({ cx: 0, cz: -2.05, along: "x", length: 12, door: 0, mat: log, doorW: 1.8, doorH: 2.3 });
doorWall({ cx: 6.05, cz: -10.2, along: "z", length: 8, door: 1.6, mat: log, doorW: 1.6, doorH: 2.2 });

addBox(8.2, 3.4, 0.28, 10, 1.7, -3.95, logDark);
addBox(0.28, 3.4, 8.4, 14.05, 1.7, -8);
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

addBox(13, 0.12, 7.2, 0, 3.55, -0.6, roof, false);
addBox(0.7, 2.4, 0.7, 4.6, 4.5, -1.4, stone, false);

[[-4.6, -6.4], [-4.6, -10.2], [4.6, -6.4], [4.6, -10.8]].forEach(([x, z]) => {
  addBox(1.5, 0.9, 3.2, x, 0.55, z, teal);
});
[[-1.2, -8.4], [1.3, -7.2], [0, -11]].forEach(([x, z]) => {
  addBox(1.3, 0.72, 0.8, x, 0.42, z, wood, false);
});
addBox(0.22, 2.6, 0.22, 0.1, 1.4, -8.6, wood, false);

addBox(2.3, 1.05, 1.15, -5.2, 0.55, 1.4, stone);
addBox(2.3, 0.08, 1.15, -5.2, 1.1, 1.4, solid("#5f8a7a"), false);
[[-4.2, 2.1], [-6.1, 2.1], [-4.2, 0.6], [-6.1, 0.6]].forEach(([x, z]) => {
  addBox(0.32, 0.55, 0.32, x, 0.35, z, solid("#1a1a1a"), false);
});
[[2.4, 2.8], [4.6, 4.2], [1.2, 5.1]].forEach(([x, z], i) => {
  addBox(1.2, 0.7, 0.7, x, 0.4, z, solid("#4a4a4a"), false);
  const umb = new THREE.Mesh(new THREE.ConeGeometry(1.15, 0.28, 12), solid(["#c43b2b", "#2457a8", "#d24c7a"][i]));
  umb.position.set(x, 2.35, z);
  scene.add(umb);
  addBox(0.06, 2.1, 0.06, x, 1.15, z, solid("#333"), false);
});

[-8.6, -5.4].forEach((x) => {
  [7.2, 10.4].forEach((z) => {
    addBox(0.38, 2.8, 0.38, x, 1.5, z, cream);
  });
});
addBox(3.6, 0.16, 0.28, -7, 2.95, 7.2, wood, false);
addBox(3.6, 0.16, 0.28, -7, 2.95, 10.4, wood, false);
addBox(0.28, 0.16, 3.5, -8.6, 2.95, 8.8, wood, false);
addBox(0.28, 0.16, 3.5, -5.4, 2.95, 8.8, wood, false);
addBox(1.4, 0.7, 0.7, -7, 0.4, 8.6, solid("#6b675e"), false);
addBox(0.7, 0.55, 0.7, -8.1, 0.35, 8.2, cream, false);
addBox(0.7, 0.55, 0.7, -5.9, 0.35, 8.2, cream, false);

function pine(x, z, s = 1) {
  const trunk = new THREE.Mesh(
    new THREE.CylinderGeometry(0.16 * s, 0.26 * s, 2.6 * s, 6),
    solid("#4a321c"),
  );
  trunk.position.set(x, 1.3 * s, z);
  const needles = new THREE.Mesh(
    new THREE.ConeGeometry(1.45 * s, 4.4 * s, 7),
    solid("#1f4a26"),
  );
  needles.position.set(x, 3.8 * s, z);
  scene.add(trunk, needles);
}
[
  [-12, 16],
  [-10, 20],
  [10, 18],
  [13, 14],
  [8, 22],
  [-6, 22],
  [16, 10],
  [-16, 8],
  [14, 22],
  [-14, 18],
].forEach(([x, z], i) => pine(x, z, 0.95 + (i % 3) * 0.22));

addBox(0.12, 1.1, 16, 10.4, 0.55, 14, wood);
addBox(18, 1.1, 0.12, 1, 0.55, 22.2, wood);

function collide(next) {
  const r = 0.32;
  for (const w of walls) {
    if (next.x + r > w.minx && next.x - r < w.maxx && next.z + r > w.minz && next.z - r < w.maxz) {
      return true;
    }
  }
  return next.x < -16 || next.x > 16 || next.z < -15.2 || next.z > 22.4;
}

function nearestSpot(p) {
  let best = spots[0];
  let d = 1e9;
  for (const s of spots) {
    const dx = p.x - s.pos[0];
    const dz = p.z - s.pos[2];
    const n = dx * dx + dz * dz;
    if (n < d) {
      d = n;
      best = s;
    }
  }
  return best;
}

function setCard(spot) {
  card.classList.remove("hidden");
  card.innerHTML = `<p class="kicker">Room</p><h3>${spot.name}</h3><p>${spot.copy}</p>`;
  spotLabel.textContent = spot.name;
}

function lookFrom(pos, look) {
  const dx = look.x - pos.x;
  const dz = look.z - pos.z;
  yaw = Math.atan2(dx, -dz);
  pitch = 0;
}

function goTo(id, instant = false) {
  const spot = spots.find((s) => s.id === id) || spots[0];
  tour = spots.indexOf(spot);
  setCard(spot);
  const target = new THREE.Vector3(...spot.pos);
  const look = new THREE.Vector3(...spot.look);
  if (instant) {
    camera.position.copy(target);
    camera.lookAt(look);
    lookFrom(target, look);
    return;
  }
  const start = camera.position.clone();
  const startLook = new THREE.Vector3();
  camera.getWorldDirection(startLook);
  startLook.add(camera.position);
  const t0 = performance.now();
  tween = (now) => {
    const u = Math.min(1, (now - t0) / 1100);
    const e = 1 - (1 - u) ** 3;
    camera.position.lerpVectors(start, target, e);
    const cur = startLook.clone().lerp(look, e);
    camera.lookAt(cur);
    if (u < 1) requestAnimationFrame(tween);
    else {
      tween = null;
      lookFrom(target, look);
    }
  };
  requestAnimationFrame(tween);
}

function enter(next = "tour") {
  mode = next;
  idle.classList.add("hidden");
  walkBar.classList.remove("hidden");
  if (next === "walk") {
    walking = true;
    renderer.domElement.requestPointerLock?.();
    setCard(nearestSpot(camera.position));
  } else {
    walking = false;
    document.exitPointerLock?.();
    goTo(spots[tour].id);
  }
}

function exitWalk() {
  mode = "idle";
  walking = false;
  document.exitPointerLock?.();
  idle.classList.remove("hidden");
  walkBar.classList.add("hidden");
  card.classList.add("hidden");
}

document.getElementById("btn-enter").onclick = () => {
  tour = 0;
  enter("tour");
};
document.getElementById("btn-walk").onclick = () => enter("walk");
document.getElementById("btn-tour").onclick = () => enter("tour");
document.getElementById("btn-exit").onclick = exitWalk;
document.getElementById("btn-next").onclick = () => {
  tour = (tour + 1) % spots.length;
  walking = false;
  enter("tour");
};
document.getElementById("btn-prev").onclick = () => {
  tour = (tour - 1 + spots.length) % spots.length;
  walking = false;
  enter("tour");
};
document.querySelectorAll("[data-go]").forEach((btn) => {
  btn.onclick = () => {
    walking = false;
    enter("tour");
    goTo(btn.dataset.go);
  };
});

addEventListener("keydown", (e) => {
  keys[e.code] = true;
  if (e.code === "Escape") exitWalk();
  if (e.code === "Enter" && mode === "idle") enter("walk");
});
addEventListener("keyup", (e) => {
  keys[e.code] = false;
});
addEventListener("mousemove", (e) => {
  if (!walking || document.pointerLockElement !== renderer.domElement) return;
  yaw -= e.movementX * 0.0021;
  pitch -= e.movementY * 0.0021;
  pitch = Math.max(-1.15, Math.min(1.15, pitch));
});
renderer.domElement.addEventListener("click", () => {
  if (mode === "walk") renderer.domElement.requestPointerLock?.();
});
addEventListener("resize", () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

const clock = new THREE.Clock();
function tick() {
  const dt = Math.min(clock.getDelta(), 0.05);
  if (walking && !tween) {
    const dir = new THREE.Vector3(Math.sin(yaw), 0, -Math.cos(yaw));
    const right = new THREE.Vector3().crossVectors(dir, new THREE.Vector3(0, 1, 0)).negate();
    const speed = (keys.ShiftLeft ? 6.4 : 3.6) * dt;
    const next = camera.position.clone();
    if (keys.KeyW) next.addScaledVector(dir, speed);
    if (keys.KeyS) next.addScaledVector(dir, -speed);
    if (keys.KeyA) next.addScaledVector(right, -speed);
    if (keys.KeyD) next.addScaledVector(right, speed);
    const tryX = next.clone();
    tryX.z = camera.position.z;
    if (!collide(tryX)) camera.position.x = tryX.x;
    const tryZ = next.clone();
    tryZ.x = camera.position.x;
    if (!collide(tryZ)) camera.position.z = tryZ.z;
    camera.position.y = H;
    camera.rotation.set(pitch, yaw, 0, "YXZ");
    const here = nearestSpot(camera.position);
    if (spotLabel.textContent !== here.name) setCard(here);
  }
  renderer.render(scene, camera);
  requestAnimationFrame(tick);
}
goTo("indoor", true);
tick();
window.__tipsy = { ORDER, goTo, enter, spots };
