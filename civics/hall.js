const intro = [
  ["Lesson 1", "The Connection Between the Constitution and the Declaration", "The Constitution is the form; the Declaration is the end.", "vGGx7sTDnMY"],
  ["Lesson 2", "The Laws of Nature and of Nature’s God", "Rights are found, not granted.", "waGj1WUCPz0"],
  ["Lesson 3", "Freedom and Equality", "No person may rule another without consent.", "iP97Xi-srnc"],
  ["Lesson 4", "Consent of the Governed", "The compact.", "squSO3A24dg"],
  ["Lesson 5", "Representation", "The people rule through officers.", "lb--PjsgmA4"],
  ["Lesson 6", "The People Rule, But They Do Not Govern", "Energy in the executive; reason in the forms.", "XzCwSzZ-cEw"],
  ["Lesson 7", "A Constitution that Encourages Reason to Rule the Passions", "Forms exist so passion does not become law.", "oXUFzLd9VtQ"],
  ["Lesson 8", "The People are the Most Powerful and the Most Dangerous", "Majority faction. Federalist 10.", "a4IyRndlUhk"],
  ["Lesson 9", "A Virtuous People is Necessary for Good Government", "Free government is not self-executing.", "1hrCFUoAVDs"],
  ["Lesson 10", "Ballots Rather Than Bullets", "The constitutional substitute for the sword.", "Owp9j84NtCk"],
  ["Lesson 11", "The Importance of Limited Government", "National things only.", "bn_5eiWH2z4"],
  ["Lesson 12", "The Problem with Progressivism", "The later doctrine that unmoors the forms.", "4vutqN-v0lQ"],
];
const con101 = [
  ["Trailer", "Constitution 101 — official trailer", "Enroll free for the remaining ten lectures.", "UrNWiTLYr9E"],
  ["Lecture 1", "Constitution 101 | Lecture 1", "Declaration and Constitution as final and formal cause.", "oU5gasRxYdU"],
  ["Lecture 2", "Constitution 101 | Lecture 2", "Natural rights, social compact, consent, equality.", "wvCWORnRy1A"],
];
const extra = [
  ["Jackson", "Bradley J. Birzer — The Character of General Jackson", "Hillsdale’s Jacksonian America teacher.", "vrTuWkuOfTk"],
  ["Rights", "Where Do Rights Come From?", "Prior to the state.", "HAZppxL52Z8"],
  ["Founding", "Were our Founders Really Christian?", "Public religion and the compact.", "w5J4S5LPeWM"],
  ["Purpose", "The Founding Purpose of Government", "To secure rights, not to invent them.", "XsWBR3ivlbs"],
  ["Bill of Rights", "Why wasn’t the Bill of Rights in the original Constitution?", "Enumeration and the Ninth.", "37V2S2RFTbQ"],
  ["Admin", "The Administrative State Breeds Oligarchy", "Extra-constitutional power in the palace.", "RQ9aouun2O0"],
  ["Rule of law", "William P. Barr — The Constitution and the Rule of Law", "The magistrate under law.", "I0Ho5_DiRdc"],
];
const jackson = [
  extra[0],
  ["Crash Course", "Age of Jackson — Crash Course #14", "Mass politics, veto, spoils, Bank, Removal.", "beN4qE-e5O8"],
  ["Khan", "Jacksonian Democracy", "How expanded white-male suffrage remade parties.", "mSzaJXR6MhA"],
  ["TED-Ed", "History vs. Andrew Jackson", "Union-saver versus Worcester ignored.", "gx5IyumKmDI"],
  ["Lecture", "The Jacksonian Era", "Suffrage, Removal, Nullification, Panic of 1837.", "IomAC6-sJUg"],
  ["Party", "Democracy and the Mob", "Second Party System.", "niWD4WSJr_I"],
  ["Market", "The Market Revolution — Crash Course #12", "The world the Bank War was fought in.", "RNftCCwAol0"],
];
const courses = [
  ["Politics", "Introduction to the Constitution", "The twelve films on the Hillsdale tab.", "https://online.hillsdale.edu/"],
  ["Politics", "Constitution 101", "Founding, Civil War, Progressivism.", "https://online.hillsdale.edu/landing/constitution-101"],
  ["Politics", "Constitution 201", "Progressive rejection; administrative state.", "https://online.hillsdale.edu/courses/promo/constitution-201"],
  ["Politics", "The Federalist", "Pestritto. Publius, Anti-Federalists, faction.", "https://online.hillsdale.edu/courses/register/the-federalist"],
  ["Politics", "The Federalist Papers", "Earlier Hillsdale pass through Madison, Hamilton, Jay.", "https://online.hillsdale.edu/courses"],
  ["Politics", "The Presidency and the Constitution", "Executive energy — Jackson’s tool.", "https://online.hillsdale.edu/courses"],
  ["Politics", "Congress: How It Worked and Why It Doesn’t", "The law-making body that forgot how.", "https://online.hillsdale.edu/courses"],
  ["Politics", "The U.S. Supreme Court", "Marbury through Heller and Brown.", "https://online.hillsdale.edu/courses/promo/the-us-supreme-court"],
  ["Politics", "Public Policy from a Constitutional Viewpoint", "Policy under the forms.", "https://online.hillsdale.edu/courses"],
  ["Politics", "The Real American Founding: A Conversation", "Founding as argument, not myth.", "https://online.hillsdale.edu/courses"],
  ["Politics", "Civil Rights in American History", "Equality as named, and the later struggle.", "https://online.hillsdale.edu/courses"],
  ["History", "American Citizenship and Its Decline", "Victor Davis Hanson.", "https://online.hillsdale.edu/courses"],
  ["History", "American Heritage", "Includes Jacksonian Democracy.", "https://online.hillsdale.edu/courses"],
  ["History", "The Great American Story: A Land of Hope", "Wilfred McClay.", "https://online.hillsdale.edu/courses"],
  ["History", "Revolutionary America: From Subjects to Citizens", "The consent later withheld, then given.", "https://online.hillsdale.edu/courses"],
  ["Politics", "The American Left: From Liberalism to Despotism", "Later vocabulary seated in the chair.", "https://online.hillsdale.edu/courses"],
  ["Economics", "Economics 101", "Producers, prices, the Bank War’s longer argument.", "https://online.hillsdale.edu/courses"],
  ["K–12", "Teaching American History & Civics, K–2", "For the teachers who host this hall.", "https://online.hillsdale.edu/courses"],
  ["K–12", "Teaching American History & Civics, 3–5", "Elementary.", "https://online.hillsdale.edu/courses"],
  ["K–12", "Teaching American History, 6–8", "Middle school.", "https://online.hillsdale.edu/courses"],
  ["K–12", "Teaching American History & Civics, 9–12", "High school.", "https://online.hillsdale.edu/courses"],
];

function card([tag, title, why, id]) {
  return `<article class="lesson"><div class="frame"><iframe src="https://www.youtube-nocookie.com/embed/${id}" title="${title.replace(/"/g, "")}" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen loading="lazy"></iframe></div><div class="meta"><div class="tag">${tag}</div><h3>${title}</h3><p>${why}</p><p class="src">Hillsdale College · youtube-nocookie embed</p></div></article>`;
}
function grid(list) {
  return `<div class="grid">${list.map(card).join("")}</div>`;
}
document.getElementById("founding").innerHTML =
  `<h2>Two complete accounts</h2>
  <p class="lede">Do not score 1788 by the government that later won. Federalists wanted energy and union. Anti-Federalists wanted a confederated republic and rights as the price of consent. Lincoln is where they met: acts while Congress was out, legalized after the fact, by a Congress without the dissenting section.</p>
  <p><a href="founding.html">Open the full record — quotes, dates, cases →</a></p>
  <div class="grid" style="margin-top:1.5rem">
    <article class="lesson"><div class="meta"><div class="tag">Federalist</div><h3>Energy, union, extended republic</h3><p>Hamilton said energy in the executive out loud (Fed. 70). Bill of rights unnecessary (Fed. 84). They lost that argument and wrote the amendments. They did not lose Article II.</p></div></article>
    <article class="lesson"><div class="meta"><div class="tag">Anti-Federalist</div><h3>Consolidation, scale, written rights</h3><p>Brutus: officers above control. Mason: no press, jury, or standing-army clause. North Carolina withheld consent until the amendments moved.</p></div></article>
  </div>
  <h2>Lincoln, in one paragraph</h2>
  <p class="lede">15 April 1861: troops called, Congress set for 4 July. Blockade 19 April. Habeas 27 April. Taney in Merryman: only Congress suspends. Lincoln does not produce the body. 6 August 1861: Congress declares the past “legalized… as if” it had already authorized it. Prize Cases 5–4 after the captures. Milligan after the war. The 37th Congress sat without eleven states. Retroactive legality is the statute’s own words.</p>`;
document.getElementById("resistance").innerHTML =
  `<h2>PxD2 resistance theory</h2>
  <p class="lede">Four classes: Knox, Rutherford’s Lex Rex, Craighead in the Piedmont, Witherspoon. Then Heller, McDonald, Bruen, Reese v. ATF, Lara v. Evanchick, and Cockerham as applications — not the source of the right. Lesser magistrates first. Not a private war.</p>
  <p><a href="resistance.html">Open the four classes and the cases →</a></p>
  <div class="grid" style="margin-top:1.5rem">
    <article class="lesson"><div class="meta"><div class="tag">I–IV</div><h3>Knox · Rutherford · Craighead · Witherspoon</h3><p>Office under law. Covenant withheld. Resistance last, through estates, not a mob.</p></div></article>
    <article class="lesson"><div class="meta"><div class="tag">Cases</div><h3>Heller to Cockerham</h3><p>Individual right; incorporation; text-and-history; 18–20 among the people; as-applied lifetime disarmament for a paid debt fails in the Fifth.</p></div></article>
  </div>`;
document.getElementById("hillsdale").innerHTML =
  `<h2>Introduction to the Constitution</h2>` +
  grid(intro) +
  `<h2>Constitution 101</h2><p class="lede">Lectures 1–2 are public. Enroll free for the other ten.</p>` +
  grid(con101) +
  `<p><a href="https://online.hillsdale.edu/landing/constitution-101">Enroll in Constitution 101 →</a></p>` +
  `<h2>Hillsdale civics films</h2>` +
  grid(extra);
document.getElementById("courses").innerHTML =
  `<h2>Free course catalog</h2><p class="lede">Click through to Hillsdale. Courses are free; they ask for an account.</p>` +
  courses
    .map(
      ([k, t, w, h]) =>
        `<div class="row"><div><div class="k">${k}</div><a href="${h}">${t}</a><p class="lede">${w}</p></div><a href="${h}">Enroll</a></div>`,
    )
    .join("") +
  `<p class="lede" style="margin-top:1.5rem">Full catalog: <a href="https://online.hillsdale.edu/courses">online.hillsdale.edu/courses</a></p>`;
document.getElementById("jackson").innerHTML =
  `<h2>Jacksonian political ideals</h2>` + grid(jackson);

document.querySelectorAll(".tabs button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tabs button").forEach((b) => b.classList.remove("on"));
    document.querySelectorAll(".pane").forEach((p) => p.classList.remove("on"));
    btn.classList.add("on");
    document.getElementById(btn.dataset.tab).classList.add("on");
  });
});
