import * as THREE from "three";

const ORDER =
  "https://order.spoton.com/so-tipsy-hippy-grill-19076/lakeside-az/66302d9ef52c5a003da949ff/";

const spots = [
  {
    id: "patio",
    name: "Patio",
    copy: "Stone fire table, string lights, green roof, pines. This is why people drive from Show Low.",
    pos: [0, 1.7, 6],
    look: [0, 1.5, -4],
  },
  {
    id: "indoor",
    name: "Dining room",
    copy: "Log walls, terracotta, teal booths. Eat drink & have fun. No pissy attitudes.",
    pos: [-8, 1.7, -2],
    look: [-14, 1.6, -2],
  },
  {
    id: "bar",
    name: "Love Shack",
    copy: "Taps, cocktails, the weird little bar people remember. Twenty drafts.",
    pos: [8, 1.7, -1],
    look: [14, 1.5, -1],
  },
  {
    id: "lawn",
    name: "Forest lawn",
    copy: "Cornhole, picnic tables, dogs welcome. Live music when the backyard is posted.",
    pos: [2, 1.7, 8],
    look: [2, 1.4, 16],
  },
  {
    id: "dusk",
    name: "Dusk",
    copy: "Lights up. Patio stays the move after the sun drops behind the Rim.",
    pos: [-3, 1.7, 5],
    look: [-3, 1.5, -6],
  },
];

const keys = {};
let mode = "idle";
let yaw = 0;
let pitch = 0;
let tour = 0;
let walking = false;

const stage = document.getElementById("stage");
const idle = document.getElementById("idle");
const card = document.getElementById("card");
const walkBar = document.getElementById("walk-bar");
const spotLabel = document.getElementById("spot-label");

const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
stage.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color("#7ec4e8");
scene.fog = new THREE.Fog("#cfe6f2", 28, 70);

const camera = new THREE.PerspectiveCamera(70, innerWidth / innerHeight, 0.1, 120);
camera.position.set(0, 1.7, 8);

const loader = new THREE.TextureLoader();
const tex = (src) => {
  const t = loader.load(src);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
};

function panel(src, w, h, x, y, z, rotY = 0) {
  const geo = new THREE.PlaneGeometry(w, h);
  const mat = new THREE.MeshBasicMaterial({ map: tex(src) });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.position.set(x, y, z);
  mesh.rotation.y = rotY;
  scene.add(mesh);
  return mesh;
}

const ground = new THREE.Mesh(
  new THREE.CircleGeometry(40, 48),
  new THREE.MeshLambertMaterial({ color: "#5a7a3a" }),
);
ground.rotation.x = -Math.PI / 2;
scene.add(ground);

const stone = new THREE.Mesh(
  new THREE.CircleGeometry(11, 40),
  new THREE.MeshLambertMaterial({ color: "#8a7a68" }),
);
stone.rotation.x = -Math.PI / 2;
stone.position.y = 0.02;
scene.add(stone);

scene.add(new THREE.HemisphereLight("#fff4d6", "#3a4a28", 1.15));
const sun = new THREE.DirectionalLight("#fff3c4", 1.4);
sun.position.set(-8, 18, 10);
scene.add(sun);

panel("./images/patio.jpg", 16, 9, 0, 4.4, -8);
panel("./images/lawn.jpg", 16, 9, 0, 4.4, 16, Math.PI);
panel("./images/indoor.jpg", 14, 8, -16, 4, -1, Math.PI / 2);
panel("./images/bar.jpg", 14, 8, 16, 4, -1, -Math.PI / 2);
panel("./images/loveshack.jpg", 10, 5.6, 10, 3.2, -10, Math.PI / 6);
panel("./images/patio-dusk.jpg", 10, 5.6, -10, 3.2, -10, -Math.PI / 6);
panel("./images/wings.jpg", 4.4, 2.5, 5.5, 1.8, 3.2, -0.5);

function pine(x, z, s = 1) {
  const trunk = new THREE.Mesh(
    new THREE.CylinderGeometry(0.18 * s, 0.28 * s, 2.4 * s, 6),
    new THREE.MeshLambertMaterial({ color: "#4a321c" }),
  );
  trunk.position.set(x, 1.2 * s, z);
  const needles = new THREE.Mesh(
    new THREE.ConeGeometry(1.5 * s, 4.2 * s, 7),
    new THREE.MeshLambertMaterial({ color: "#234a28" }),
  );
  needles.position.set(x, 3.6 * s, z);
  scene.add(trunk, needles);
}
[
  [-14, 12],
  [12, 14],
  [18, 8],
  [-18, 6],
  [8, 18],
  [-8, 18],
  [22, -6],
  [-22, -8],
].forEach(([x, z], i) => pine(x, z, 0.9 + (i % 3) * 0.2));

function setCard(spot) {
  card.classList.remove("hidden");
  card.innerHTML = `<p class="kicker">Room</p><h3>${spot.name}</h3><p>${spot.copy}</p>`;
  spotLabel.textContent = spot.name;
}

function goTo(id, instant = false) {
  const spot = spots.find((s) => s.id === id) || spots[0];
  tour = spots.indexOf(spot);
  setCard(spot);
  const [x, y, z] = spot.pos;
  const [lx, ly, lz] = spot.look;
  const target = new THREE.Vector3(x, y, z);
  const look = new THREE.Vector3(lx, ly, lz);
  if (instant) {
    camera.position.copy(target);
    camera.lookAt(look);
    yaw = Math.atan2(x - lx, z - lz);
    pitch = 0;
    return;
  }
  const start = camera.position.clone();
  const t0 = performance.now();
  const step = (now) => {
    const u = Math.min(1, (now - t0) / 900);
    const e = 1 - (1 - u) ** 3;
    camera.position.lerpVectors(start, target, e);
    camera.lookAt(look);
    if (u < 1) requestAnimationFrame(step);
    else {
      yaw = Math.atan2(look.x - target.x, look.z - target.z) * -1;
      pitch = 0;
    }
  };
  requestAnimationFrame(step);
}

function enter(next = "tour") {
  mode = next;
  idle.classList.add("hidden");
  walkBar.classList.remove("hidden");
  if (next === "walk") {
    walking = true;
    renderer.domElement.requestPointerLock?.();
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
  camera.position.set(0, 1.7, 8);
  camera.lookAt(0, 1.5, -4);
}

document.getElementById("btn-enter").onclick = () => enter("tour");
document.getElementById("btn-walk").onclick = () => enter("walk");
document.getElementById("btn-tour").onclick = () => enter("tour");
document.getElementById("btn-exit").onclick = exitWalk;
document.getElementById("btn-next").onclick = () => {
  tour = (tour + 1) % spots.length;
  enter("tour");
  goTo(spots[tour].id);
};
document.getElementById("btn-prev").onclick = () => {
  tour = (tour - 1 + spots.length) % spots.length;
  enter("tour");
  goTo(spots[tour].id);
};
document.querySelectorAll("[data-go]").forEach((btn) => {
  btn.onclick = () => {
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
  yaw -= e.movementX * 0.0022;
  pitch -= e.movementY * 0.0022;
  pitch = Math.max(-1.1, Math.min(1.1, pitch));
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
  if (walking) {
    const dir = new THREE.Vector3(Math.sin(yaw), 0, -Math.cos(yaw));
    const right = new THREE.Vector3().crossVectors(dir, new THREE.Vector3(0, 1, 0)).negate();
    const speed = (keys.ShiftLeft ? 8 : 4.2) * dt;
    if (keys.KeyW) camera.position.addScaledVector(dir, speed);
    if (keys.KeyS) camera.position.addScaledVector(dir, -speed);
    if (keys.KeyA) camera.position.addScaledVector(right, -speed);
    if (keys.KeyD) camera.position.addScaledVector(right, speed);
    camera.position.y = 1.7;
    camera.position.x = THREE.MathUtils.clamp(camera.position.x, -18, 18);
    camera.position.z = THREE.MathUtils.clamp(camera.position.z, -12, 18);
    camera.rotation.set(pitch, yaw, 0, "YXZ");
  }
  renderer.render(scene, camera);
  requestAnimationFrame(tick);
}
goTo("patio", true);
tick();

window.__tipsy = { ORDER, goTo, enter };
