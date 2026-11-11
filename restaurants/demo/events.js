/* Demo Diner - events calendar (shared by the home page and the manage page). PXD2.
   Events live on the PXD2 relay (menu.json "relay") so the store can change them from a phone; before the relay is on,
   events.json is used, and the manage page saves to this device only (preview). */
window.DemoEvents = (() => {
  const KINDS = { music: ["Live music", "#B23A1E"], karaoke: ["Karaoke", "#7A3FA0"], special: ["Special", "#1F8A8A"], food: ["Kitchen special", "#C77A12"],
                  community: ["Community", "#3E7B4E"], hours: ["Hours change", "#22160E"], other: ["Event", "#6B3A1F"] };
  const PREVIEW = "demo_events_preview";
  let cfg = null;
  async function config() {
    if (!cfg) { try { cfg = await (await fetch("menu.json", { cache: "no-cache" })).json(); } catch (e) { cfg = {}; } }
    return cfg;
  }
  async function load() {
    const c = await config();
    if (c.relay) {
      try { const r = await fetch(c.relay.replace(/\/$/, "") + "/events", { cache: "no-cache" }); if (r.ok) return (await r.json()).events || []; } catch (e) { }
    }
    try { const p = JSON.parse(localStorage.getItem(PREVIEW)); if (Array.isArray(p)) return p; } catch (e) { }
    try { return (await (await fetch("events.json", { cache: "no-cache" })).json()).events || []; } catch (e) { return []; }
  }
  async function save(events, key) {
    const c = await config();
    if (!c.relay) { localStorage.setItem(PREVIEW, JSON.stringify(events)); return { preview: true }; }
    const r = await fetch(c.relay.replace(/\/$/, "") + "/events", { method: "PUT", headers: { "Content-Type": "application/json", Authorization: "Bearer " + key }, body: JSON.stringify({ events }) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || "Could not save");
    return j;
  }
  async function check(key) {           // is this the owner key? (relay only)
    const c = await config();
    if (!c.relay) return true;
    const r = await fetch(c.relay.replace(/\/$/, "") + "/events/check", { headers: { Authorization: "Bearer " + key } });
    return r.ok;
  }
  const pad = n => String(n).padStart(2, "0");
  const ymd = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const parse = s => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };
  const today = () => { const n = new Date(new Date().toLocaleString("en-US", { timeZone: "America/Phoenix" })); n.setHours(0, 0, 0, 0); return n; };
  // every date an event happens on between a and b (weekly repeats expanded)
  function occurrences(events, a, b) {
    const out = [];
    for (const e of events) {
      if (!e.date) continue;
      let d = parse(e.date);
      const stop = e.repeat === "weekly" ? (e.until ? parse(e.until) : new Date(d.getTime() + 26 * 7 * 864e5)) : d;
      while (d <= stop && d <= b) {
        if (d >= a && !(e.skip || []).includes(ymd(d))) out.push(Object.assign({}, e, { on: ymd(d) }));
        if (e.repeat !== "weekly") break;
        d = new Date(d.getFullYear(), d.getMonth(), d.getDate() + 7);
      }
    }
    return out.sort((x, y) => (x.on + (x.start || "")).localeCompare(y.on + (y.start || "")));
  }
  const t12 = s => { if (!s) return ""; const [h, m] = s.split(":").map(Number); return `${h % 12 || 12}${m ? ":" + pad(m) : ""} ${h < 12 ? "AM" : "PM"}`; };
  const when = e => [t12(e.start), t12(e.end)].filter(Boolean).join(" to ");
  function ics(e) {           // "Add to my calendar" file for one date of an event
    const dt = (d, t) => d.replace(/-/g, "") + "T" + (t || "00:00").replace(":", "") + "00";
    const esc = s => String(s || "").replace(/([,;\\])/g, "\\$1").replace(/\n/g, "\\n");
    const body = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//PXD2//Demo Diner//EN", "BEGIN:VEVENT",
      `UID:${e.id}-${e.on}@demo.pxd`, `DTSTAMP:${new Date().toISOString().replace(/[-:]/g, "").slice(0, 15)}Z`,
      e.start ? `DTSTART;TZID=America/Phoenix:${dt(e.on, e.start)}` : `DTSTART;VALUE=DATE:${e.on.replace(/-/g, "")}`,
      e.start ? `DTEND;TZID=America/Phoenix:${dt(e.on, e.end || e.start)}` : null,
      `SUMMARY:${esc(e.title)}`, `LOCATION:${esc((e.where || "Demo Diner") + ", PXD2 demo, Concho, AZ")}`,
      `DESCRIPTION:${esc(e.details)}`, "END:VEVENT", "END:VCALENDAR"].filter(Boolean).join("\r\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([body], { type: "text/calendar" }));
    a.download = (e.title || "event").replace(/[^\w ]+/g, "").trim().replace(/ +/g, "-") + "-" + e.on + ".ics";
    document.body.appendChild(a); a.click(); a.remove();
  }
  return { KINDS, load, save, check, occurrences, ymd, parse, today, when, t12, ics, config };
})();
