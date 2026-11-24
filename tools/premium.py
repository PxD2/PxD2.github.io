#!/usr/bin/env python3
"""PXD2 premium client-site engine.

One config per client in tools/premium_clients.py -> clients/<slug>/index.html.
Built from each business's own real photos, menus and words (Facebook, old sites,
Google listing). Includes: photo hero, live open/closed (Arizona time) when hours are
known, searchable menu or service cards, real reviews, gallery with lightbox,
tap-to-load map, QR, save-contact, share, mobile dock, and the PXD2 access panel.

Run: python3 tools/premium.py [key ...]
"""
import html, io, json, pathlib, re, sys, importlib.util
import segno

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("v2", ROOT / "tools" / "clients_v2.py")
v2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(v2)
spec2 = importlib.util.spec_from_file_location("pc", ROOT / "tools" / "premium_clients.py")
pc = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(pc)

e = html.escape
DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

def ic(n, cls="ic"):
    return f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true">{v2.I.get(n) or EXTRA.get(n, v2.I["star"])}</svg>'

EXTRA = {
 "flame": '<path d="M12 22c4 0 7-3 7-7 0-4-3-6-4-10-2 2-3 4-3 6-1-1-2-2-2-4-2 2-5 5-5 8 0 4 3 7 7 7z"/>',
 "fb": '<path d="M15 3h-3a4 4 0 0 0-4 4v3H5v4h3v7h4v-7h3l1-4h-4V7a1 1 0 0 1 1-1h3z"/>',
 "car": '<path d="M5 17h14v-5l-2-5H7l-2 5z"/><circle cx="8" cy="17" r="2"/><circle cx="16" cy="17" r="2"/><path d="M5 12h14"/>',
 "flag": '<path d="M5 21V4"/><path d="M5 4h12l-2 4 2 4H5"/>',
 "truck": '<path d="M3 7h11v9H3zM14 10h4l3 3v3h-7z"/><circle cx="7" cy="17" r="2"/><circle cx="17" cy="17" r="2"/>',
 "gift": '<rect x="3" y="9" width="18" height="12" rx="1"/><path d="M3 13h18M12 9v12M12 9c-2-4-6-4-6-1s6 1 6 1 6 2 6-1-4-3-6 1"/>',
 "cake": '<path d="M4 12h16v8H4z"/><path d="M4 15c2 1 4-1 6 0s4 1 6 0 3-1 4 0M12 12V8M12 5v1"/>',
 "pie": '<path d="M3 13h18l-2 6H5z"/><path d="M3 13c2-5 16-5 18 0M8 10l1 3M12 9v4M16 10l-1 3"/>',
 "users": '<circle cx="9" cy="8" r="3"/><path d="M3 20c0-3 3-5 6-5s6 2 6 5"/><circle cx="17" cy="9" r="2.5"/><path d="M15 15c3 0 6 1.5 6 4"/>',
 "drop": '<path d="M12 3c4 5 6 8 6 11a6 6 0 0 1-12 0c0-3 2-6 6-11z"/>',
 "build": '<path d="M3 21h18M5 21V10l7-5 7 5v11M9 21v-6h6v6"/>',
 "dig": '<path d="M3 20h18M6 20l3-8 4 2 3-6M13 14l4 2"/><circle cx="17" cy="6" r="2"/>',
 "layers": '<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5"/>',
 "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
 "map": '<path d="M9 4L3 6v14l6-2 6 2 6-2V4l-6 2z"/><path d="M9 4v14M15 6v14"/>',
}

def fmt(m):
    h, mi = divmod(m, 60); ap = "am" if h < 12 else "pm"; h = h % 12 or 12
    return f"{h}:{mi:02d} {ap}" if mi else f"{h} {ap}"

def qr_svg(url, dark):
    q = segno.make(url, error="m"); b = io.BytesIO()
    q.save(b, kind="svg", scale=4, border=2, dark=dark, light="#FFFFFF", xmldecl=False, svgns=True)
    return b.getvalue().decode().replace("<svg ", '<svg class="segno" role="img" aria-label="QR code to this page" ', 1)

CSS = r'''
.shop{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}@media(max-width:1000px){.shop{grid-template-columns:repeat(3,1fr)}}@media(max-width:720px){.shop{grid-template-columns:1fr 1fr;gap:12px}}
.prod{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);overflow:hidden;display:flex;flex-direction:column;transition:transform .3s,box-shadow .3s,border-color .3s;position:relative}
.prod:hover{transform:translateY(-4px);box-shadow:0 24px 40px -28px rgba(0,0,0,.5);border-color:color-mix(in srgb,var(--acc) 45%,var(--line))}
.prod .pi{aspect-ratio:1;background:#fff;display:grid;place-items:center;overflow:hidden}.prod .pi img{width:100%;height:100%;object-fit:contain;padding:8px;transition:transform .6s}.prod:hover .pi img{transform:scale(1.05)}
.prod .pb{padding:14px 16px 16px;display:flex;flex-direction:column;gap:6px;flex:1}.prod h3{font:700 1.02rem/1.25 var(--body);margin:0}.prod .pp{font:700 1.2rem/1 var(--head);color:var(--acc)}.prod .pp small{font:500 .8rem var(--body);color:var(--soft);margin-right:4px}
.prod .pd{color:var(--soft);font-size:.88rem;margin:0}.prod .pa{margin-top:auto;display:flex;gap:8px;padding-top:8px}.prod .pa a{flex:1;text-align:center;padding:10px 8px;border-radius:10px;font:700 .88rem/1 var(--body);text-decoration:none}
.prod .pa .buy{background:var(--acc);color:var(--on)}.prod .pa .ask{border:1px solid var(--line);color:var(--ink)}.prod .rib{position:absolute;top:10px;left:10px;background:var(--acc2);color:#1E1B18;font:800 .72rem/1 var(--body);letter-spacing:.04em;text-transform:uppercase;padding:6px 9px;border-radius:999px;z-index:2}
.prod[hidden]{display:none}.trust{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 18px}.trust span{display:inline-flex;align-items:center;gap:8px;background:var(--panel2);border-radius:999px;padding:8px 14px;font-weight:600;font-size:.92rem}.trust .ic{color:var(--acc)}
.howto{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:26px;counter-reset:h}@media(max-width:800px){.howto{grid-template-columns:1fr 1fr}}.howto div{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px 18px;counter-increment:h}.howto div::before{content:counter(h);display:inline-grid;place-items:center;width:28px;height:28px;border-radius:50%;background:var(--acc);color:var(--on);font-weight:800;margin-bottom:8px}.howto b{display:block}.howto span{color:var(--soft);font-size:.92rem}
@media(max-width:720px){.prod .pa{flex-direction:column}.prod .pb{padding:12px}}
:root{--bg:%BG%;--panel:%PANEL%;--panel2:%PANEL2%;--ink:%INK%;--soft:%SOFT%;--acc:%ACC%;--acc2:%ACC2%;--on:%ON%;--line:%LINE%;--head:%HEAD%;--body:%BODY%;--r:22px;--glow:%GLOW%}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth;scroll-padding-top:84px;overflow-x:clip}
body{background:var(--bg);color:var(--ink);font:400 1.125rem/1.65 var(--body);-webkit-font-smoothing:antialiased;overflow-x:clip}
body::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:-1;background:radial-gradient(70vw 50vw at 92% -10%,color-mix(in srgb,var(--acc) 15%,transparent),transparent 70%),radial-gradient(50vw 40vw at -10% 40%,color-mix(in srgb,var(--acc2) 12%,transparent),transparent 70%)}
a{color:inherit}:focus-visible{outline:3px solid var(--acc);outline-offset:3px;border-radius:6px}
img{max-width:100%}
.ic{width:1.15em;height:1.15em;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;flex:none}
.skip{position:absolute;left:-999px;top:8px;background:var(--acc);color:var(--on);padding:10px 16px;border-radius:10px;z-index:99}.skip:focus{left:8px}
.concept{background:#0d0b09;color:#d8cbb8;font:13px/1.45 system-ui,sans-serif;text-align:center;padding:8px 16px}.concept b{color:#fff}
.prog{position:fixed;top:0;left:0;height:3px;width:0;background:linear-gradient(90deg,var(--acc2),var(--acc));z-index:30}
.wrap{max-width:1200px;margin:0 auto;padding:0 22px}
header{position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--bg) 85%,transparent);backdrop-filter:saturate(1.4) blur(14px);-webkit-backdrop-filter:saturate(1.4) blur(14px);border-bottom:1px solid var(--line);transition:box-shadow .3s}
header.up{box-shadow:0 12px 30px -18px rgba(0,0,0,.55)}
header .wrap{display:flex;align-items:center;gap:14px;padding-top:10px;padding-bottom:10px}
.logo{display:flex;align-items:center;gap:12px;text-decoration:none;min-width:0}
.logo img{height:48px;width:auto;max-width:150px;object-fit:contain;border-radius:10px;flex:none}
.logo b{font:700 1.3rem/1.05 var(--head);display:block}.logo small{display:block;font:600 .68rem/1.3 var(--body);letter-spacing:.18em;color:var(--soft);text-transform:uppercase;margin-top:3px}
nav.main{margin-left:auto;display:flex;gap:2px;font-weight:600;font-size:.95rem}
nav.main a{text-decoration:none;color:var(--soft);padding:8px 13px;border-radius:999px;transition:.2s}nav.main a:hover,nav.main a.on{color:var(--ink);background:var(--panel2)}
.pill{display:inline-flex;align-items:center;gap:8px;text-decoration:none;font-weight:700;background:var(--acc);color:var(--on);padding:11px 18px;border-radius:999px;white-space:nowrap}
.abtn{width:46px;height:46px;border-radius:50%;border:1px solid var(--line);background:var(--panel);color:var(--ink);display:grid;place-items:center;cursor:pointer;flex:none}.abtn .ic{width:24px;height:24px}
@media(max-width:1020px){nav.main{display:none}.hdr-call{margin-left:auto}}
@media(max-width:560px){.hdr-call{display:none}.abtn{margin-left:auto}.logo small{letter-spacing:.08em}}
.hero .wrap{display:grid;grid-template-columns:1fr 1.05fr;gap:48px;align-items:center;padding-top:52px;padding-bottom:68px}
.hero .wrap>*{min-width:0}
@media(max-width:900px){.hero .wrap{grid-template-columns:1fr;padding-top:28px;gap:30px}}
.status{display:inline-flex;align-items:center;gap:10px;font-weight:600;font-size:.95rem;padding:8px 16px 8px 12px;border-radius:999px;background:var(--panel);border:1px solid var(--line)}
.status i{width:10px;height:10px;border-radius:50%;background:#5BAE5B;box-shadow:0 0 0 0 rgba(91,174,91,.6);animation:ping 2.2s infinite}.status.closed i{background:#C8452F;animation:none}.status.plain i{background:var(--acc);animation:ping 2.2s infinite}
@keyframes ping{80%,100%{box-shadow:0 0 0 10px transparent}}
.eyb{font:700 .8rem/1.4 var(--body);letter-spacing:.22em;text-transform:uppercase;color:var(--acc);display:block;margin:22px 0 12px}
h1{font:700 clamp(2.7rem,6.8vw,5.3rem)/.98 var(--head);letter-spacing:-.01em;text-wrap:balance;overflow-wrap:break-word}
h1 em{font-style:normal;color:var(--acc)}
.tag{font-size:clamp(1.12rem,2.1vw,1.35rem);color:var(--soft);max-width:32em;margin-top:18px;text-wrap:pretty}
.acts{display:flex;flex-wrap:wrap;gap:12px;margin-top:28px}
.btn{display:inline-flex;align-items:center;gap:10px;text-decoration:none;font-weight:700;font-size:1.05rem;padding:15px 24px;border-radius:999px;border:0;cursor:pointer;font-family:inherit;color:var(--ink);transition:transform .2s,box-shadow .2s,background .2s}
.btn .ic{width:20px;height:20px}
.b1{background:var(--acc);color:var(--on);box-shadow:0 16px 34px -14px var(--glow)}.b1:hover{transform:translateY(-2px);box-shadow:0 22px 44px -16px var(--glow)}
.b2{background:var(--panel);box-shadow:inset 0 0 0 2px var(--line)}.b2:hover{box-shadow:inset 0 0 0 2px var(--acc);transform:translateY(-2px)}
.b3{background:transparent;color:var(--soft);padding-left:8px;padding-right:8px}.b3:hover{color:var(--ink)}
.facts{display:flex;flex-wrap:wrap;gap:10px;margin-top:26px}
.facts span{display:inline-flex;align-items:center;gap:8px;font-weight:600;font-size:.92rem;padding:8px 14px;border-radius:12px;background:var(--panel);border:1px solid var(--line);color:var(--soft)}.facts .ic{color:var(--acc);width:18px;height:18px}
.rating{display:flex;align-items:center;gap:12px;margin-top:22px;color:var(--soft);font-weight:600}.rating b{font:700 2rem/1 var(--head);color:var(--ink)}.rating .st{color:#E8B33A;letter-spacing:2px;font-size:1.15rem}
.collage{position:relative;display:grid;grid-template-columns:1.35fr 1fr;grid-template-rows:1fr 1fr;gap:14px;height:clamp(360px,44vw,560px)}
.collage figure{margin:0;border-radius:24px;overflow:hidden;position:relative;box-shadow:0 30px 60px -36px rgba(0,0,0,.7);border:1px solid var(--line);background:var(--panel2)}
.collage figure:first-child{grid-row:span 2}
.collage img{width:100%;height:100%;object-fit:cover;display:block;transition:transform 1.2s cubic-bezier(.2,.8,.2,1)}
.collage figure:hover img{transform:scale(1.06)}
.collage .badge{position:absolute;left:-14px;bottom:28px;background:var(--acc);color:var(--on);border-radius:18px;padding:14px 18px;font:700 1rem/1.2 var(--body);box-shadow:0 20px 40px -18px rgba(0,0,0,.6);max-width:220px;animation:bob 5s ease-in-out infinite}
.collage .badge b{display:block;font:700 1.7rem/1 var(--head)}
@keyframes bob{50%{transform:translateY(-8px)}}
.collage.one{grid-template-columns:1fr;grid-template-rows:1fr}.collage.one figure:first-child{grid-row:auto}
.collage.logo figure:first-child img{object-fit:contain;background:var(--logo-bg,#fff);padding:6%}
@media(max-width:600px){.collage{height:auto;grid-template-columns:1fr 1fr;grid-template-rows:240px 150px}.collage figure:first-child{grid-column:span 2;grid-row:auto}.collage .badge{left:10px;bottom:10px}}
.ribbon{border-block:1px solid var(--line);background:var(--panel);overflow:hidden;white-space:nowrap;padding:15px 0;font:700 clamp(1rem,1.9vw,1.25rem)/1 var(--head);color:var(--soft)}
.ribbon div{display:inline-flex;gap:28px;padding-right:28px;animation:tick 40s linear infinite}.ribbon i{color:var(--acc);font-style:normal}
@keyframes tick{to{transform:translateX(-50%)}}
section{padding:90px 0}
.kick{font:700 .8rem/1 var(--body);letter-spacing:.24em;text-transform:uppercase;color:var(--acc);display:flex;align-items:center;gap:12px;margin-bottom:14px}.kick::after{content:"";height:2px;width:56px;background:var(--acc);opacity:.5}
h2{font:700 clamp(2.1rem,4.6vw,3.4rem)/1.04 var(--head);letter-spacing:-.01em;text-wrap:balance;margin-bottom:14px}h2 em{font-style:normal;color:var(--acc)}
.lede{color:var(--soft);max-width:40em;font-size:1.15rem;margin-bottom:34px}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}@media(max-width:900px){.cards{grid-template-columns:1fr 1fr}}@media(max-width:600px){.cards{grid-template-columns:1fr}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);overflow:hidden;transition:transform .35s cubic-bezier(.2,.8,.2,1),box-shadow .35s,border-color .3s;display:flex;flex-direction:column}
.card:hover{transform:translateY(-6px);box-shadow:0 30px 50px -30px rgba(0,0,0,.55);border-color:color-mix(in srgb,var(--acc) 45%,var(--line))}
.card .ph{aspect-ratio:16/10;overflow:hidden;background:var(--panel2)}.card .ph img{width:100%;height:100%;object-fit:cover;display:block;transition:transform .8s}.card:hover .ph img{transform:scale(1.06)}
.card .bd{padding:22px 24px 26px}.card h3{font:700 1.3rem/1.2 var(--head);margin-bottom:6px;display:flex;align-items:center;gap:10px}.card h3 .ic{color:var(--acc)}.card p{color:var(--soft);font-size:1.02rem}
.card .pr{display:inline-block;margin-top:10px;font:700 1.15rem var(--head);color:var(--acc)}
.mbar{position:sticky;top:69px;z-index:9;background:color-mix(in srgb,var(--bg) 94%,transparent);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);padding:12px 0;border-bottom:1px solid var(--line);margin-bottom:24px}
.tabs{display:flex;gap:8px;overflow-x:auto;scrollbar-width:none}.tabs::-webkit-scrollbar{display:none}
.tab{flex:none;padding:10px 16px;border-radius:999px;border:1px solid var(--line);background:var(--panel);color:var(--soft);font:600 .95rem/1 var(--body);cursor:pointer}
.tab:hover{color:var(--ink)}.tab[aria-selected=true]{background:var(--acc);color:var(--on);border-color:transparent}
.search{display:flex;align-items:center;gap:10px;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:0 14px;margin-top:10px}
.search input{flex:1;background:transparent;border:0;color:var(--ink);font:500 1rem var(--body);padding:12px 0;outline:none;min-width:0}
.msec{margin-bottom:44px}.msec h3{font:700 1.8rem/1.1 var(--head);margin-bottom:4px}.msec .sn{color:var(--soft);margin-bottom:14px;font-size:.98rem}
.items{display:grid;grid-template-columns:1fr 1fr;gap:4px 40px}@media(max-width:780px){.items{grid-template-columns:1fr}}
.it{padding:13px 0;border-bottom:1px dashed var(--line)}
.it .row{display:flex;align-items:baseline;gap:10px}.it b{font:700 1.06rem/1.3 var(--body)}
.it .dots{flex:1;border-bottom:2px dotted color-mix(in srgb,var(--ink) 20%,transparent);transform:translateY(-4px);min-width:16px}
.it .pr{font:700 1.06rem/1 var(--head);color:var(--acc);white-space:nowrap}
.it p{color:var(--soft);font-size:.95rem;margin-top:3px}
.mnote{color:var(--soft);font-size:.93rem;border-left:3px solid var(--acc);padding-left:14px}
.split{display:grid;grid-template-columns:1fr 1fr;gap:44px;align-items:center}@media(max-width:860px){.split{grid-template-columns:1fr}}
.split figure{margin:0;border-radius:26px;overflow:hidden;border:1px solid var(--line);box-shadow:0 40px 70px -40px rgba(0,0,0,.8);transform:rotate(-1deg);transition:transform .4s}.split figure:hover{transform:none}
.split figure img{display:block;width:100%;height:auto}
.points{display:grid;gap:12px;margin-top:8px}.points div{display:flex;gap:14px;align-items:flex-start;background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:16px 18px}
.points .ic{width:28px;height:28px;padding:5px;border-radius:50%;background:var(--acc);color:var(--on);stroke-width:2.6;margin-top:2px}
.points b{display:block}.points span{color:var(--soft);font-size:.98rem}
.revs{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}@media(max-width:860px){.revs{grid-template-columns:1fr}}
.rev{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:26px}.rev .st{color:#E8B33A;letter-spacing:3px}.rev p{font:italic 600 1.15rem/1.45 var(--head);margin:10px 0 12px}.rev small{color:var(--soft)}
.gal{columns:3 260px;column-gap:14px}.gal button{display:block;width:100%;margin:0 0 14px;padding:0;border:0;background:none;cursor:zoom-in;border-radius:18px;overflow:hidden;break-inside:avoid;box-shadow:0 20px 40px -30px rgba(0,0,0,.7)}
.gal img{display:block;width:100%;height:auto;transition:transform .7s}.gal button:hover img{transform:scale(1.04)}
.lb{position:fixed;inset:0;background:rgba(0,0,0,.9);z-index:70;display:grid;place-items:center;padding:20px}.lb[hidden]{display:none}.lb img{max-width:94vw;max-height:86vh;border-radius:14px}
.lb button{position:absolute;top:14px;right:16px;width:48px;height:48px;border-radius:50%;border:0;background:#fff;font-size:26px;cursor:pointer}
.lb .nx,.lb .pv{top:50%;transform:translateY(-50%);right:auto}.lb .pv{left:14px}.lb .nx{right:14px}
.visit{display:grid;grid-template-columns:1fr 1fr;gap:18px}@media(max-width:900px){.visit{grid-template-columns:1fr}}
.vbox{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:30px}
.lbl{display:flex;align-items:center;gap:8px;font-size:.76rem;font-weight:700;letter-spacing:.18em;text-transform:uppercase;color:var(--soft);margin-bottom:6px}.lbl .ic{color:var(--acc);width:16px;height:16px}
.bigt{font:700 1.35rem/1.3 var(--body);margin-bottom:20px;overflow-wrap:anywhere}.bigt a{text-decoration:none}.bigt.s{font-size:1.08rem;font-weight:600;color:var(--soft)}
table.hrs{border-collapse:collapse;width:100%;margin-bottom:18px}table.hrs td{padding:8px 0;border-bottom:1px solid var(--line)}table.hrs td+td{text-align:right;font-weight:600}table.hrs tr.today td{color:var(--acc);font-weight:700}
.map{position:relative;min-height:380px;border-radius:var(--r);overflow:hidden;border:1px solid var(--line);background:var(--panel2)}
.map iframe{position:absolute;inset:0;width:100%;height:100%;border:0}
.mapc{position:absolute;inset:0;display:grid;place-items:center;align-content:center;gap:14px;text-align:center;padding:20px;background:radial-gradient(circle at 50% 45%,color-mix(in srgb,var(--acc) 16%,transparent),transparent 60%),repeating-linear-gradient(0deg,transparent 0 38px,var(--line) 38px 39px),repeating-linear-gradient(90deg,transparent 0 38px,var(--line) 38px 39px)}
.mapc small{color:var(--soft);font-size:.82rem}
.tools{display:grid;grid-template-columns:auto 1fr;gap:22px;align-items:center}@media(max-width:560px){.tools{grid-template-columns:1fr;justify-items:center;text-align:center}}
.qr svg{width:136px;height:136px;border-radius:14px;display:block;background:#fff}
.band{position:relative;overflow:hidden;text-align:center;border-radius:34px;padding:70px 22px;background:linear-gradient(120deg,var(--acc),color-mix(in srgb,var(--acc) 60%,#000));color:var(--on)}
.band::before{content:"";position:absolute;width:560px;height:560px;left:-140px;top:-300px;border-radius:50%;background:radial-gradient(closest-side,rgba(255,255,255,.22),transparent);animation:drift 12s ease-in-out infinite alternate}
.band>*{position:relative}@keyframes drift{to{transform:translate(180px,90px)}}
.band h2{color:inherit}.band a.num{font:700 clamp(2.1rem,6vw,3.6rem)/1 var(--body);text-decoration:none;display:inline-block;margin-top:8px}.band p{opacity:.88;margin-top:12px}
footer{padding:44px 0 120px;color:var(--soft);font-size:.95rem;border-top:1px solid var(--line);margin-top:60px}footer .wrap{display:flex;flex-wrap:wrap;gap:10px 24px;justify-content:space-between}
.dock{position:fixed;left:10px;right:10px;bottom:calc(10px + env(safe-area-inset-bottom));display:none;gap:8px;z-index:18}
.dock a{flex:1;display:flex;align-items:center;justify-content:center;gap:8px;text-decoration:none;font-weight:700;font-size:1.05rem;padding:15px;border-radius:16px;background:var(--acc);color:var(--on);box-shadow:0 12px 30px -10px rgba(0,0,0,.6)}
.dock a+a{background:var(--panel);color:var(--ink);border:1px solid var(--line)}
@media(max-width:760px){.dock{display:flex}section{padding:64px 0}.mbar{top:65px}}
.rv{opacity:0;transform:translateY(26px);transition:opacity .8s cubic-bezier(.2,.8,.2,1) var(--d,0ms),transform .8s cubic-bezier(.2,.8,.2,1) var(--d,0ms)}.rv.in{opacity:1;transform:none}
.toast{position:fixed;left:50%;bottom:96px;transform:translateX(-50%) translateY(20px);background:var(--ink);color:var(--bg);padding:12px 20px;border-radius:999px;font-weight:600;opacity:0;transition:.3s;z-index:40;pointer-events:none}.toast.on{opacity:1;transform:translateX(-50%)}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}.rv{opacity:1;transform:none}}
html.rm *,html.rm *::before,html.rm *::after{animation:none!important;transition:none!important}html.rm .rv{opacity:1;transform:none}
html.hc{--bg:#000;--panel:#0a0a0a;--panel2:#161616;--ink:#fff;--soft:#f0f0f0;--line:#fff;--acc:#FFD400;--acc2:#FFD400;--on:#000}html.hc body::before{display:none}html.hc a{text-decoration:underline}
html.dys body{letter-spacing:.04em;word-spacing:.14em;line-height:1.9}html.dys h1,html.dys h2,html.dys h3{font-family:Verdana,Arial,sans-serif;letter-spacing:0}
'''

JS = r'''
(function(){
var C=window.PXC;
var pr=document.querySelector('.prog'),hd=document.querySelector('header');
function sc(){var h=document.documentElement,m=h.scrollHeight-h.clientHeight;pr.style.width=(m>0?h.scrollTop/m*100:0)+'%';hd.classList.toggle('up',h.scrollTop>10)}
addEventListener('scroll',sc,{passive:true});sc();
var io='IntersectionObserver' in window?new IntersectionObserver(function(es){es.forEach(function(x){if(x.isIntersecting){x.target.classList.add('in');io.unobserve(x.target)}})},{rootMargin:'0px 0px -8% 0px'}):null;
document.querySelectorAll('.rv').forEach(function(el){io?io.observe(el):el.classList.add('in')});
var links=[].slice.call(document.querySelectorAll('nav.main a'));
if(io)links.forEach(function(a){var s=document.querySelector(a.getAttribute('href'));if(!s)return;new IntersectionObserver(function(es){es.forEach(function(x){if(x.isIntersecting)links.forEach(function(l){l.classList.toggle('on',l===a)})})},{rootMargin:'-45% 0px -50% 0px'}).observe(s)});
var t=document.querySelector('.toast');window.pxToast=function(m){t.textContent=m;t.classList.add('on');clearTimeout(t._h);t._h=setTimeout(function(){t.classList.remove('on')},2600)};
// open now (Arizona = UTC-7 all year)
var st=document.getElementById('status');
function fmt(m){var h=Math.floor(m/60),mi=m%60,ap=h<12?'am':'pm';h=h%12||12;return h+(mi?':'+('0'+mi).slice(-2):'')+' '+ap}
if(C.hours&&st){var tick=function(){var n=new Date(Date.now()+(new Date().getTimezoneOffset()-420)*60000),d=n.getDay(),m=n.getHours()*60+n.getMinutes(),h=C.hours[d],txt;
 if(h&&m>=h[0]&&m<h[1]){st.className='status';txt='<b>Open now</b> · until '+fmt(h[1])}
 else{st.className='status closed';var k=0,nd=d;if(h&&m<h[0]){k=0}else{for(k=1;k<8;k++){nd=(d+k)%7;if(C.hours[nd])break}}var o=C.hours[k?nd:d];
  txt='<b>Closed</b> · opens '+(k===0?'today':k===1?'tomorrow':['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'][nd])+' at '+fmt(o[0])}
 st.querySelector('span').innerHTML=txt;document.querySelectorAll('#hrs tr').forEach(function(r){r.classList.toggle('today',+r.getAttribute('data-d')===d)})};tick();setInterval(tick,60000)}
// menu
if(C.menu){var tabs=document.getElementById('tabs'),list=document.getElementById('mlist'),q=document.getElementById('q'),cur='all';
 function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
 tabs.innerHTML='<button class="tab" role="tab" type="button" aria-selected="true" data-k="all">Everything</button>'+C.menu.map(function(m){return '<button class="tab" role="tab" type="button" aria-selected="false" data-k="'+esc(m.s)+'">'+esc(m.s)+'</button>'}).join('');
 function draw(){var term=q.value.trim().toLowerCase(),out='';
  C.menu.forEach(function(s){if(cur!=='all'&&s.s!==cur)return;var its=s.items.filter(function(it){return !term||(it.n+' '+(it.d||'')+' '+s.s).toLowerCase().indexOf(term)>-1});if(!its.length)return;
   out+='<div class="msec"><h3>'+esc(s.s)+'</h3>'+(s.note?'<p class="sn">'+esc(s.note)+'</p>':'')+'<div class="items">'+its.map(function(it){return '<div class="it"><div class="row"><b>'+esc(it.n)+'</b>'+(it.p?'<span class="dots"></span><span class="pr">'+esc(it.p)+'</span>':'')+'</div>'+(it.d?'<p>'+esc(it.d)+'</p>':'')+'</div>'}).join('')+'</div></div>'});
  list.innerHTML=out||'<p class="mnote">Nothing matches that. Call us, we probably have it.</p>'}
 tabs.addEventListener('click',function(e){var b=e.target.closest('.tab');if(!b)return;cur=b.getAttribute('data-k');tabs.querySelectorAll('.tab').forEach(function(x){x.setAttribute('aria-selected',x===b)});draw();var top=document.getElementById('menu').getBoundingClientRect().top+scrollY-70;if(scrollY>top+200)scrollTo({top:top,behavior:'smooth'})});
 q.addEventListener('input',draw);draw()}
// lightbox
var lb=document.getElementById('lb'),li=lb&&lb.querySelector('img'),gs=[].slice.call(document.querySelectorAll('.gal button')),gi=0;
function show(i){gi=(i+gs.length)%gs.length;var im=gs[gi].querySelector('img');li.src=im.src;li.alt=im.alt;lb.hidden=false;lb.querySelector('.x').focus()}
gs.forEach(function(b,i){b.addEventListener('click',function(){show(i)})});
if(lb){lb.querySelector('.x').addEventListener('click',function(){lb.hidden=true});lb.querySelector('.nx').addEventListener('click',function(){show(gi+1)});lb.querySelector('.pv').addEventListener('click',function(){show(gi-1)});
 lb.addEventListener('click',function(e){if(e.target===lb)lb.hidden=true});document.addEventListener('keydown',function(e){if(lb.hidden)return;if(e.key==='Escape')lb.hidden=true;if(e.key==='ArrowRight')show(gi+1);if(e.key==='ArrowLeft')show(gi-1)})}
document.querySelectorAll('[data-map]').forEach(function(b){b.addEventListener('click',function(){var m=b.closest('.map'),f=document.createElement('iframe');f.src=m.getAttribute('data-src');f.title='Map to '+C.name;f.loading='lazy';f.referrerPolicy='no-referrer-when-downgrade';m.innerHTML='';m.appendChild(f)})});
document.querySelectorAll('[data-share]').forEach(function(b){b.addEventListener('click',function(){var u=location.href;if(navigator.share){navigator.share({title:C.name,url:u}).catch(function(){})}else if(navigator.clipboard){navigator.clipboard.writeText(u).then(function(){pxToast('Link copied')})}})});
document.querySelectorAll('[data-vcard]').forEach(function(b){b.addEventListener('click',function(){var c=['BEGIN:VCARD','VERSION:3.0','FN:'+C.name,'ORG:'+C.name,C.tel?'TEL;TYPE=WORK,VOICE:'+C.tel:'',C.email?'EMAIL:'+C.email:'','ADR;TYPE=WORK:;;'+C.adr.replace(/,/g,'\\,')+';;;;','URL:'+location.href,'END:VCARD'].filter(Boolean).join('\r\n');var a=document.createElement('a');a.href=URL.createObjectURL(new Blob([c],{type:'text/vcard'}));a.download=C.name.replace(/[^a-z0-9]+/gi,'-')+'.vcf';document.body.appendChild(a);a.click();a.remove();pxToast('Contact saved')})});
})();
'''

def build(key, c):
    slug = c["slug"]; out = ROOT / "clients" / slug / "index.html"
    P = c["palette"]
    css = CSS
    for k, v in P.items(): css = css.replace("%" + k.upper() + "%", v)
    tel = "+1" + re.sub(r"\D", "", c["phone"]) if c.get("phone") else ""
    phone = c.get("phone", "")
    url = "https://pxd2.github.io/" + c["short"]
    qr = qr_svg(url, P.get("qrdark", "#1A1410"))
    maps_q = c.get("maps_q", c["name"] + " " + c["address"])
    maps = "https://www.google.com/maps/search/?api=1&query=" + re.sub(r"\s+", "%20", e(maps_q, quote=True))
    embed = "https://www.google.com/maps?output=embed&q=" + re.sub(r"\s+", "+", e(maps_q, quote=True))
    img = lambda f: f"img/{f}.jpg"
    nav = [("top3", c.get("nav_first", "Highlights"))]
    if c.get("menu"): nav.append(("menu", c.get("menu_nav", "Menu")))
    if c.get("services"): nav.append(("services", "Services"))
    if c.get("shop"): nav.insert(1, ("shop", "Shop"))
    nav += [("story", c.get("story_nav", "Our story")), ("photos", "Photos"), ("visit", "Visit")]
    # hero collage
    hp = c["hero_photos"]
    coll_cls = "collage" + (" one" if len(hp) == 1 else "") + (" logo" if c.get("hero_logo_first") else "")
    coll = "".join(f'<figure><img src="{img(f)}" alt="{e(a)}" {"fetchpriority=high" if i==0 else "loading=lazy"}></figure>' for i, (f, a) in enumerate(hp))
    badge = f'<div class="badge"><b>{e(c["badge"][0])}</b>{e(c["badge"][1])}</div>' if c.get("badge") else ""
    rating = ""
    if c.get("rating"):
        r, n, src = c["rating"]
        rating = f'<div class="rating"><b>{r}</b><span class="st" aria-hidden="true">★★★★★</span><span>{e(n)} {e(src)}</span></div>'
    facts = "".join(f'<span>{ic(i)}{e(t)}</span>' for i, t in c.get("facts", []))
    status = ('<span class="status" id="status" role="status"><i></i><span>Checking hours…</span></span>' if c.get("hours")
              else f'<span class="status plain"><i></i><span>{e(c.get("status_text", "Locally owned"))}</span></span>')
    ribbon = "".join(f"<span>{e(x)}</span><i>✦</i>" for x in c["ribbon"])
    cta2 = c.get("cta2", ("#menu" if c.get("menu") else "#services", "fork" if c.get("menu") else "check", "See the menu" if c.get("menu") else "See services"))
    # highlight cards
    cards = "".join(
        f'<article class="card rv" style="--d:{i*80}ms"><div class="ph"><img src="{img(f)}" alt="{e(t)}" loading="lazy"></div><div class="bd"><h3>{e(t)}</h3><p>{e(d)}</p>{f"<span class=pr>{e(p)}</span>" if p else ""}</div></article>'
        for i, (f, t, d, p) in enumerate(c["top3"]))
    # services
    serv = ""
    if c.get("services"):
        sv_cards = "".join(
            f'<article class="card rv" style="--d:{(i%3)*80}ms">{f"<div class=ph><img src={img(f)} alt=\"{e(t)}\" loading=lazy></div>" if f else ""}<div class="bd"><h3>{ic(icn)}{e(t)}</h3><p>{e(d)}</p></div></article>'
            for i, (f, icn, t, d) in enumerate(c["services"]))
        serv = f'''<section id="services" style="padding-top:0"><div class="wrap">
 <p class="kick rv">{e(c.get("services_kick","Services"))}</p><h2 class="rv">{c["services_h2"]}</h2>{f'<p class="lede rv">{e(c["services_lede"])}</p>' if c.get("services_lede") else ""}
 <div class="cards">{sv_cards}</div>{f'<p class="mnote" style="margin-top:22px">{e(c["services_note"])}</p>' if c.get("services_note") else ""}
</div></section>'''
    shop = ""
    if c.get("shop"):
        S = c["shop"]
        cats = ["All"] + list(dict.fromkeys(it["cat"] for it in S["items"]))
        chips = "".join(f'<button class="tab" type="button" role="tab" aria-selected="{"true" if i==0 else "false"}" data-cat="{e(k)}">{e(k)}</button>' for i, k in enumerate(cats))
        def pcard(it):
            rib = f'<span class="rib">{e(it["rib"])}</span>' if it.get("rib") else ""
            pre = '<small>from</small>' if it.get("from") else ""
            d = f'<p class="pd">{e(it["d"])}</p>' if it.get("d") else ""
            return (f'<article class="prod rv" data-cat="{e(it["cat"])}" data-n="{e(it["n"].lower())}">{rib}<div class="pi"><img src="img/shop/{it["img"]}.jpg" alt="{e(it["n"])}" loading="lazy"></div>'
                    f'<div class="pb"><h3>{e(it["n"])}</h3><span class="pp">{pre}{e(it["p"])}</span>{d}<div class="pa"><a class="buy" href="{e(S["store"])}/product-page/{it["h"]}" target="_blank" rel="noopener">Buy online</a>'
                    f'<a class="ask" href="tel:{tel}">Call</a></div></div></article>')
        trust = "".join(f'<span>{ic(i)}{e(t)}</span>' for i, t in S.get("trust", []))
        how = "".join(f'<div><b>{e(a)}</b><span>{e(b)}</span></div>' for a, b in S.get("howto", []))
        shop = f'''<section id="shop" style="padding-top:0"><div class="wrap">
 <p class="kick rv">{e(S.get("kick","Shop"))}</p><h2 class="rv">{S["h2"]}</h2><p class="lede rv">{e(S["lede"])}</p>
 <div class="trust rv">{trust}</div>
 <div class="mbar"><div class="tabs" role="tablist" aria-label="Shop categories" id="stabs">{chips}</div>
  <label class="search">{ic("spark")}<input id="sq" type="search" placeholder="{e(S.get("search","Search products"))}" aria-label="Search products"></label></div>
 <div class="shop" id="shopg">{"".join(pcard(it) for it in S["items"])}</div>
 <div style="text-align:center;margin-top:20px"><button class="btn b2" type="button" id="smore">{ic("flag")}Show all {len(S["items"])} products</button></div>
 <p class="mnote" style="margin-top:22px">{S["note"]}</p>
 {f'<h3 class="rv" style="font:700 1.5rem var(--head);margin-top:40px">{e(S["howto_h"])}</h3><div class="howto">{how}</div>' if how else ""}
</div></section>
<script>(()=>{{const g=document.getElementById('shopg'),t=document.getElementById('stabs'),q=document.getElementById('sq');let cat='All';
const mb=document.getElementById('smore');let all=false;const run=()=>{{const v=(q.value||'').toLowerCase().trim();const lim=!all&&cat==='All'&&!v;let k=0;g.querySelectorAll('.prod').forEach(p=>{{const ok=(cat==='All'||p.dataset.cat===cat)&&(!v||p.dataset.n.includes(v)||p.dataset.cat.toLowerCase().includes(v));p.hidden=!ok||(lim&&k>=12);if(ok)k++}});mb.parentNode.hidden=!lim}};mb.addEventListener('click',()=>{{all=true;run()}});run();
t.addEventListener('click',ev=>{{const b=ev.target.closest('.tab');if(!b)return;cat=b.dataset.cat;t.querySelectorAll('.tab').forEach(x=>x.setAttribute('aria-selected',x===b));run()}});q.addEventListener('input',run)}})();</script>'''
    menu = ""
    if c.get("menu"):
        menu = f'''<section id="menu" style="padding-top:0"><div class="wrap">
 <p class="kick rv">{e(c.get("menu_kick","The menu"))}</p><h2 class="rv">{c["menu_h2"]}</h2>{f'<p class="lede rv">{e(c["menu_lede"])}</p>' if c.get("menu_lede") else ""}
 <div class="mbar"><div class="tabs" role="tablist" aria-label="Menu sections" id="tabs"></div>
  <label class="search">{ic("spark")}<input id="q" type="search" placeholder="{e(c.get("menu_search","Search the menu"))}" aria-label="Search the menu"></label></div>
 <div id="mlist" aria-live="polite"></div>
 <p class="mnote">{e(c.get("menu_note","Prices can change. Call to confirm."))}</p>
</div></section>'''
    pts = "".join(f'<div class="rv" style="--d:{i*70}ms">{ic("check")}<span><b>{e(a)}</b>{e(b)}</span></div>' for i, (a, b) in enumerate(c["points"]))
    revs = ""
    if c.get("reviews"):
        revs = '<div class="revs" style="margin-top:46px">' + "".join(
            f'<figure class="rev rv" style="--d:{i*80}ms;margin:0"><div class="st" aria-hidden="true">★★★★★</div><p>“{e(q)}”</p><small>{e(w)}</small></figure>' for i, (q, w) in enumerate(c["reviews"])) + "</div>"
    gal = "".join(f'<button type="button" aria-label="Open photo: {e(a)}"><img src="{img(f)}" alt="{e(a)}" loading="lazy"></button>' for f, a in c["gallery"])
    if c.get("hours"):
        hrs = "".join(f'<tr data-d="{i}"><td>{DAYS[i]}</td><td>{(fmt(h[0])+" – "+fmt(h[1])) if h else "Closed"}</td></tr>' for i, h in enumerate(c["hours"]))
        hours_html = f'<table class="hrs" id="hrs">{hrs}</table>'
    else:
        hours_html = f'<p class="bigt s">{e(c.get("hours_text","Call for today’s hours"))}</p>'
    email = c.get("email", "")
    ld = {"@context": "https://schema.org", "@type": c.get("ld_type", "LocalBusiness"), "name": c["name"], "telephone": "+1-" + phone if phone else None,
          "address": {"@type": "PostalAddress", "streetAddress": c.get("street", ""), "addressLocality": c["town"], "addressRegion": "AZ", "addressCountry": "US"},
          "sameAs": [c["fb"]] if c.get("fb") else None}
    if c.get("hours"):
        ld["openingHoursSpecification"] = [{"@type": "OpeningHoursSpecification", "dayOfWeek": DAYS[i], "opens": f"{h[0]//60:02d}:{h[0]%60:02d}", "closes": f"{h[1]//60:02d}:{h[1]%60:02d}"} for i, h in enumerate(c["hours"]) if h]
    ld = {k: v for k, v in ld.items() if v}
    pxc = {"name": c["name"], "tel": tel, "email": email, "adr": c["address"], "hours": c.get("hours"), "menu": c.get("menu")}
    logo = (f'<img src="{img(c["logo"])}" alt="" width="48" height="48">' if c.get("logo") else "")
    concept = (f'Concept design by PXD2 for {e(c["name"])}. Not the business&#x27;s official website. <b>Black Friday sale: $250 one time, lifetime hosting, live the same day. First 100 customers only.</b> '
               '<a href="tel:+19284576404" style="color:inherit;font-weight:700;margin-left:6px;white-space:nowrap">Want this site? Call PXD2 at 928-457-6404</a>')
    contact_rows = (f'<p class="lbl">{ic("pin")}{e(c.get("addr_label","Address"))}</p><p class="bigt">{c["address_html"]}</p>'
                    + (f'<p class="lbl">{ic("phone")}Phone</p><p class="bigt"><a href="tel:{tel}">{phone}</a></p>' if phone else "")
                    + (f'<p class="lbl">{ic("mail")}Email</p><p class="bigt" style="font-size:1.05rem"><a href="mailto:{e(email)}">{e(email)}</a></p>' if email else "")
                    + (f'<p class="lbl">{ic("cart" if "cart" in v2.I else "flag")}Online store</p><p class="bigt" style="font-size:1.05rem"><a href="{e(c["web"])}" target="_blank" rel="noopener">{e(c["web"].split("//")[1].replace("www.",""))}</a></p>' if c.get("web") else "")
                    + (f'<p class="lbl">{ic("fb")}Facebook</p><p class="bigt" style="font-size:1.05rem"><a href="{e(c["fb"])}" target="_blank" rel="noopener">Follow for specials &amp; news</a></p>' if c.get("fb") else "")
                    + f'<p class="lbl">{ic("clock")}Hours</p>{hours_html}')
    story_fig = f'<figure class="rv"><img src="{img(c["story_photo"][0])}" alt="{e(c["story_photo"][1])}" loading="lazy"></figure>'
    page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<!-- pxd2-v2 --><!-- pxd2-premium -->
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex, nofollow">
<title>{e(c["name"])} · {e(c["town"])}, Arizona</title>
<meta name="description" content="{e(c["desc"])}">
<meta name="theme-color" content="{P["bg"]}"><meta name="color-scheme" content="{P.get("scheme","light")}">
<meta property="og:title" content="{e(c["name"])}"><meta property="og:description" content="{e(c["desc"])}"><meta property="og:type" content="website"><meta property="og:image" content="{img(hp[0][0])}">
<link rel="icon" href="{img(c["logo"]) if c.get("logo") else img(hp[0][0])}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{c["fonts"]}" rel="stylesheet">
<script type="application/ld+json">{json.dumps(ld)}</script>
<style>{css}{c.get("css","")}</style></head>
<body>
<a class="skip" href="#main">Skip to content</a>
<div class="prog" aria-hidden="true"></div>
<div class="concept">{concept}</div>
<header><div class="wrap">
 <a class="logo" href="#main">{logo}<span><b>{e(c["short_name"])}</b><small>{e(c["sub"])}</small></span></a>
 <nav class="main" aria-label="Sections">{"".join(f'<a href="#{a}">{e(b)}</a>' for a, b in nav)}</nav>
 {f'<a class="pill hdr-call" href="tel:{tel}">{ic("phone")}{phone}</a>' if phone else ""}
 <button class="abtn" type="button" id="pxa-open" aria-haspopup="dialog" aria-controls="pxa" aria-label="Accessibility and voice options">{ic("access")}</button>
</div></header>
<main id="main" tabindex="-1">
<div class="hero"><div class="wrap">
 <div class="rv in">
  {status}
  <span class="eyb">{e(c["eyebrow"])}</span>
  <h1>{c["h1"]}</h1>
  <p class="tag">{e(c["tagline"])}</p>
  <div class="acts">
   {f'<a class="btn b1" href="tel:{tel}">{ic("phone")}Call {phone}</a>' if phone else ""}
   <a class="btn b2" href="{cta2[0]}">{ic(cta2[1])}{e(cta2[2])}</a>
   <a class="btn b3" href="{e(maps)}" target="_blank" rel="noopener">{ic("pin")}Directions</a>
  </div>
  {rating}
  <div class="facts">{facts}</div>
 </div>
 <div class="rv in" style="--d:120ms"><div class="{coll_cls}">{coll}{badge}</div></div>
</div></div>
<div class="ribbon" aria-hidden="true"><div>{ribbon}{ribbon}</div><div>{ribbon}{ribbon}</div></div>
<section id="top3"><div class="wrap">
 <p class="kick rv">{e(c["top3_kick"])}</p><h2 class="rv">{c["top3_h2"]}</h2>{f'<p class="lede rv">{e(c["top3_lede"])}</p>' if c.get("top3_lede") else ""}
 <div class="cards">{cards}</div>
</div></section>
{shop}{menu}{serv}
<section id="story" style="padding-top:0"><div class="wrap">
 <div class="split">{story_fig}<div><p class="kick rv">{e(c.get("story_kick","Our story"))}</p><h2 class="rv">{c["story_h2"]}</h2><p class="lede rv">{e(c["story"])}</p><div class="points">{pts}</div></div></div>
 {revs}
</div></section>
<section id="photos" style="padding-top:0"><div class="wrap">
 <p class="kick rv">Photos</p><h2 class="rv">{c.get("gallery_h2","See it for yourself.")}</h2>
 <div class="gal rv">{gal}</div>
</div></section>
<section id="visit" style="padding-top:0"><div class="wrap">
 <p class="kick rv">{e(c.get("visit_kick","Visit"))}</p><h2 class="rv">{c.get("visit_h2","Come see us.")}</h2>
 <div class="visit">
  <div class="vbox rv">{contact_rows}
   <div class="tools"><div class="qr" title="Scan with a phone camera">{qr}</div>
    <div><div class="acts" style="margin-top:0"><a class="btn b1" href="{e(maps)}" target="_blank" rel="noopener">{ic("pin")}Directions</a><button class="btn b2" type="button" data-share>{ic("share")}Share</button><button class="btn b3" type="button" data-vcard>{ic("card")}Save contact</button></div>
    <p class="mnote" style="margin-top:12px;border:0;padding:0">Scan the code with a phone camera to open this page.</p></div></div>
  </div>
  <div class="map rv" style="--d:100ms" data-src="{embed}"><div class="mapc">{ic("pin","ic big")}<button class="btn b1" type="button" data-map>{ic("pin")}Show the map</button><small>The map loads from Google only when you tap.</small></div></div>
 </div>
</div></section>
<section style="padding-top:0"><div class="wrap"><div class="band rv"><h2>{e(c["band"])}</h2>{f'<a class="num" href="tel:{tel}">{phone}</a>' if phone else ""}<p>{e(c["name"])} · {e(c["town"])}, Arizona</p></div></div></section>
</main>
<footer><div class="wrap"><span>{e(c["name"])} · {e(c["address"])}{" · " + phone if phone else ""}</span><span>Built for everyone: voice control, read aloud and sound cues. Tap {ic("access")} at the top.</span></div></footer>
<div class="dock">{f'<a href="tel:{tel}">{ic("phone")}Call</a>' if phone else ""}<a href="{e(maps)}" target="_blank" rel="noopener">{ic("pin")}Directions</a></div>
<div class="lb" id="lb" hidden role="dialog" aria-label="Photo viewer"><img alt=""><button type="button" class="x" aria-label="Close">×</button><button type="button" class="pv" aria-label="Previous photo">‹</button><button type="button" class="nx" aria-label="Next photo">›</button></div>
<div class="toast" role="status" aria-live="polite"></div>
<script>window.PXC={json.dumps(pxc)};</script>
<script>{JS}</script>
{v2.ACCESS}
</body></html>
'''
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out

if __name__ == "__main__":
    keys = sys.argv[1:] or list(pc.CLIENTS)
    for k in keys:
        print("wrote", build(k, pc.CLIENTS[k]))
