function card([tag, title, why, id, src]) {
  return `<article class="lesson"><div class="frame"><iframe src="https://www.youtube-nocookie.com/embed/${id}" title="${title.replace(/"/g, "")}" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen loading="lazy"></iframe></div><div class="meta"><div class="tag">${tag}</div><h3>${title}</h3><p>${why}</p><p class="src">${src} · youtube-nocookie embed</p></div></article>`;
}
function grid(list) {
  return `<div class="grid">${list.map(card).join("")}</div>`;
}

const math = [
  ["Hillsdale", "Mathematics and Logic — from Euclid to modern geometry", "Why Euclid is logic, not a formula sheet. Enroll free for the eleven lectures.", "G8uwHZ0Lwxk", "Hillsdale Digital"],
  ["Calculus", "The essence of calculus", "What a derivative is, before the symbol fight.", "WUvTyaaNkzM", "3Blue1Brown"],
  ["Linear algebra", "Vectors — Essence of linear algebra, ch. 1", "Span, basis, the picture the matrix is hiding.", "fNk_zzaMoSs", "3Blue1Brown"],
  ["MIT 18.01", "Single Variable Calculus, lecture 1", "Jerison. Rate of change. Full course on OCW.", "7K1sB05pE0A", "MIT OpenCourseWare"],
  ["MIT 18.06", "Gilbert Strang — Linear Algebra, lecture 1", "The other half of the language physics speaks.", "ZK3OMnyDjA8", "MIT OpenCourseWare"],
];
const physics = [
  ["Yale", "Shankar — Newtonian mechanics (lecture 1)", "Open Yale. Force, mass, the laws as laws.", "KOKnWaLiL8w", "Yale / Open Yale Courses"],
  ["Yale", "Shankar — Newton’s laws of motion (lecture 3)", "The three laws without the high-school cartoon.", "Ns6GB4Dph9U", "Yale / Open Yale Courses"],
  ["Yale", "Shankar — Work and conservation of energy", "Energy as a bookkeeping of Newton, not a mood.", "NlDReZhKEro", "Yale / Open Yale Courses"],
  ["MIT 8.01", "Classical Mechanics — course introduction", "Dourmashkin and Chakrabarty. Cause and effect, not formula lists.", "F3N5EkMX_ks", "MIT OpenCourseWare"],
];
const chem = [
  ["Hillsdale", "The Great Principles of Chemistry — trailer", "Hillsdale’s chemistry course. Enroll free for the lectures.", "nh8Rjq2t-kA", "Hillsdale Digital"],
];
const life = [
  ["MIT 7.01", "Types of organisms, cell composition", "Eric Lander’s door into 7.01SC. Full path on the last tab.", "PzY0MWEEE6U", "MIT OpenCourseWare"],
];

const paths = [
  ["Hillsdale", "Mathematics and Logic: From Euclid to Modern Geometry", "11 lessons · 9.5 h", "https://online.hillsdale.edu/courses/promo/mathematics-and-logic-from-euclid-to-modern-geometry"],
  ["Hillsdale", "The Great Principles of Chemistry", "9 lessons · 6 h", "https://online.hillsdale.edu/courses"],
  ["MIT OCW", "18.01 Single Variable Calculus", "Full lecture set · CC BY-NC-SA", "https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/"],
  ["MIT OCW", "18.06 Linear Algebra (Strang)", "Full lecture set", "https://ocw.mit.edu/courses/18-06-linear-algebra-spring-2010/"],
  ["MIT OCW", "8.01SC Classical Mechanics", "Full course", "https://ocw.mit.edu/courses/8-01sc-classical-mechanics-fall-2016/"],
  ["Yale", "Fundamentals of Physics I (Shankar)", "24 lectures", "https://oyc.yale.edu/physics/phys-200"],
  ["Yale", "Fundamentals of Physics II (Shankar)", "Electricity, magnetism, optics, quantum", "https://oyc.yale.edu/physics/phys-201"],
  ["MIT OCW", "5.111 Principles of Chemical Science", "General chemistry", "https://ocw.mit.edu/courses/5-111-principles-of-chemical-science-fall-2008/"],
  ["MIT OCW", "7.01SC Fundamentals of Biology", "Intro biology", "https://ocw.mit.edu/courses/7-01sc-fundamentals-of-biology-fall-2011/"],
  ["3Blue1Brown", "Essence of calculus (playlist)", "12 films", "https://www.youtube.com/playlist?list=PLZHQObOWTQDMsr9K-rj53DwVRMYO3t5Yr"],
  ["3Blue1Brown", "Essence of linear algebra (playlist)", "16 films", "https://www.youtube.com/playlist?list=PLZHQObOWTQDPD3MizzM2xVFitgF8hE_ab"],
  ["Text", "Euclid, Elements (public domain)", "The book Hillsdale is teaching", "https://archive.org/details/euclid-elements"],
  ["Text", "Newton, Principia (public domain)", "The physics that follows Euclid’s method", "https://archive.org/details/newtonspmathema00newtrich"],
];

document.getElementById("math").innerHTML =
  `<h2>Mathematics</h2><p class="lede">Proof before calculator. Euclid, then the calculus and the linear map.</p>` + grid(math);
document.getElementById("physics").innerHTML =
  `<h2>Physics</h2><p class="lede">Newton’s laws as laws. Yale Shankar, then MIT mechanics. Not a formula sheet.</p>` + grid(physics);
document.getElementById("chem").innerHTML =
  `<h2>Chemistry</h2><p class="lede">Hillsdale’s principles course, then MIT 5.111 on the paths tab.</p>` + grid(chem);
document.getElementById("life").innerHTML =
  `<h2>Life science</h2><p class="lede">One door into MIT’s intro biology. Full path on the last tab. This is not a medical school.</p>` + grid(life);
document.getElementById("paths").innerHTML =
  `<h2>Full paths</h2><p class="lede">Enroll or open the complete lecture set. We host the door, not the stolen course.</p>` +
  paths.map(([k, t, w, h]) => `<div class="row"><div><div class="k">${k}</div><a href="${h}">${t}</a><p class="lede">${w}</p></div><a href="${h}">Open</a></div>`).join("");

document.querySelectorAll(".tabs button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tabs button").forEach((b) => b.classList.remove("on"));
    document.querySelectorAll(".pane").forEach((p) => p.classList.remove("on"));
    btn.classList.add("on");
    document.getElementById(btn.dataset.tab).classList.add("on");
  });
});
