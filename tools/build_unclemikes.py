#!/usr/bin/env python3
"""Uncle Mike's Pizza House (Show Low, AZ) - grand-opening site by PXD2.
Facts from their public Facebook page. ADDRESS still to be confirmed by the owners.
Fill PHONE / HOURS / MENU when they post them and re-run.
Run: python3 tools/build_unclemikes.py
"""
import html, io, json, pathlib, sys, importlib.util
import segno

ROOT = pathlib.Path(__file__).resolve().parent.parent
SLUG = "uncle-mikes-pizza-house-48b95c"
OUT = ROOT / "clients" / SLUG / "index.html"
SHORT = ROOT / "unclemikes" / "index.html"
spec = importlib.util.spec_from_file_location("v2", ROOT / "tools" / "clients_v2.py")
v2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(v2)

FB = "https://www.facebook.com/unclemikespizzahouse/"
MSG = "https://m.me/unclemikespizzahouse"
ADDR1, ADDR2 = "1191 E Deuce of Clubs", "Show Low, AZ 85901"   # TO CONFIRM with Mike & Beth
MAPS = "https://www.google.com/maps/search/?api=1&query=1191%20E%20Deuce%20of%20Clubs%2C%20Show%20Low%2C%20AZ%2085901"
EMBED = "https://www.google.com/maps?output=embed&q=1191+E+Deuce+of+Clubs+Show+Low+AZ+85901"
PHONE = ""          # e.g. "928-555-0123" once they have one
URL = f"https://pxd2.github.io/unclemikes"

e = html.escape
def sv(n, cls="ic"): return f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true">{v2.I.get(n) or EXTRA[n]}</svg>'
EXTRA = {
 "slice": '<path d="M12 3L3 20c6 2 12 2 18 0z"/><circle cx="11" cy="12" r="1.3"/><circle cx="14" cy="16" r="1.3"/><circle cx="9" cy="17" r="1.3"/>',
 "fb": '<path d="M15 3h-3a4 4 0 0 0-4 4v3H5v4h3v7h4v-7h3l1-4h-4V7a1 1 0 0 1 1-1h3z"/>',
 "brush": '<path d="M18 3l3 3-9 9-3-3z"/><path d="M9 12c-3 0-5 2-5 5 0 1-1 2-2 2 2 2 7 2 9-1 1-1 1-3 0-4"/>',
 "flame": '<path d="M12 22c4 0 7-3 7-7 0-4-3-6-4-10-2 2-3 4-3 6-1-1-2-2-2-4-2 2-5 5-5 8 0 4 3 7 7 7z"/>',
 "bell": '<path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4z"/><path d="M10 20a2 2 0 0 0 4 0"/>',
}

qr = segno.make(URL, error="m")
buf = io.BytesIO(); qr.save(buf, kind="svg", scale=4, border=2, dark="#1B1410", light="#FFFFFF", xmldecl=False, svgns=True)
QR = buf.getvalue().decode().replace("<svg ", '<svg class="segno" role="img" aria-label="QR code to this page" ', 1)

# Sign recreation: red disc w/ cream outlined lettering + wood plank w/ green "PIZZA HOUSE"
SIGN = '''<svg class="sign" viewBox="0 0 560 240" role="img" aria-label="Uncle Mike's Pizza House sign">
<defs>
 <linearGradient id="plank" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#E7CDA6"/><stop offset="1" stop-color="#CFA676"/></linearGradient>
 <radialGradient id="disc" cx=".4" cy=".35" r=".75"><stop offset="0" stop-color="#E5323F"/><stop offset="1" stop-color="#A3141F"/></radialGradient>
 <pattern id="grain" width="120" height="14" patternUnits="userSpaceOnUse"><path d="M0 7c30-4 60 4 120 0" stroke="#B88B5A" stroke-width="1" fill="none" opacity=".45"/></pattern>
</defs>
<rect x="6" y="40" width="548" height="160" rx="10" fill="#21422C"/>
<rect x="16" y="50" width="528" height="140" rx="6" fill="url(#plank)"/>
<rect x="16" y="50" width="528" height="140" rx="6" fill="url(#grain)"/>
<g stroke="#B88B5A" stroke-width="1.5" opacity=".6"><path d="M16 85h528M16 120h528M16 155h528"/></g>
<text x="398" y="112" text-anchor="middle" font-family="'Zilla Slab',Rockwell,Georgia,serif" font-weight="700" font-size="42" letter-spacing="4" fill="#21422C">PIZZA</text>
<text x="398" y="162" text-anchor="middle" font-family="'Zilla Slab',Rockwell,Georgia,serif" font-weight="700" font-size="42" letter-spacing="4" fill="#21422C">HOUSE</text>
<g class="disc-g">
 <circle cx="150" cy="120" r="112" fill="#F3E6CC"/>
 <circle cx="150" cy="120" r="104" fill="url(#disc)" stroke="#1B1410" stroke-width="4"/>
 <path d="M58 92h184M54 150h192" stroke="#F3E6CC" stroke-width="5" opacity=".9"/>
 <g font-family="'Titan One','Arial Black',sans-serif" font-size="54" text-anchor="middle" stroke="#1B1410" stroke-width="9" stroke-linejoin="round" paint-order="stroke" fill="#F3E6CC" transform="rotate(-8 150 120)">
  <text x="150" y="112">UNCLE</text><text x="150" y="168">MIKE'S</text>
 </g>
</g>
</svg>'''

# Square pan pie illustration (what their photos show: crisp edges, pepperoni, ricotta, pesto)
PIE = '''<svg class="pie" viewBox="0 0 420 420" role="img" aria-label="A square pan pizza with pepperoni, ricotta and pesto">
<defs>
 <linearGradient id="crust" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#E3A55A"/><stop offset="1" stop-color="#9E5A22"/></linearGradient>
 <radialGradient id="sauce" cx=".5" cy=".5" r=".7"><stop offset="0" stop-color="#E45A3A"/><stop offset="1" stop-color="#B3311F"/></radialGradient>
 <filter id="soft"><feGaussianBlur stdDeviation="1.2"/></filter>
</defs>
<rect x="18" y="26" width="384" height="384" rx="18" fill="#1B1410" opacity=".35" transform="translate(8 10)"/>
<rect x="18" y="18" width="384" height="384" rx="18" fill="#2A2A2A"/>
<rect x="30" y="30" width="360" height="360" rx="14" fill="url(#crust)"/>
<rect x="44" y="44" width="332" height="332" rx="10" fill="url(#sauce)"/>
<path d="M44 80c40 10 80-12 120 0s80 14 120-2 70 6 92 0" stroke="#F6D49A" stroke-width="16" fill="none" opacity=".55" filter="url(#soft)"/>
<path d="M44 220c50-14 90 12 140 0s90-10 120 6 60-6 72-2" stroke="#F6D49A" stroke-width="14" fill="none" opacity=".45" filter="url(#soft)"/>
<g class="pep">''' + "".join(
    f'<g transform="translate({x} {y})"><circle r="21" fill="#8E1E16"/><circle r="15" fill="#B52A1C"/><circle r="6" fill="#6E140E" opacity=".7"/></g>'
    for x, y in [(90, 92), (190, 76), (300, 100), (130, 180), (250, 170), (340, 210), (80, 270), (200, 260), (300, 300), (120, 345), (240, 350), (350, 340)]) + '''</g>
<g fill="#FBF4E6">''' + "".join(
    f'<path transform="translate({x} {y})" d="M-14 2c0-10 8-16 14-16s15 4 14 14c0 8-7 12-14 12s-14-3-14-10z"/>'
    for x, y in [(145, 120), (260, 125), (330, 160), (70, 200), (190, 215), (290, 250), (150, 300), (350, 280), (210, 320), (80, 340)]) + '''</g>
<g stroke="#4E7A2E" stroke-width="5" stroke-linecap="round" fill="none" opacity=".9"><path d="M60 140c20-10 40 8 60 0M220 140c20 8 40-6 50 4M100 240c14-8 30 6 44-2M260 210c14 10 30-4 46 4M180 380c16-8 30 6 50 0M300 360c10 6 24-2 34 4"/></g>
<g fill="#3F6B22"><ellipse cx="170" cy="150" rx="9" ry="5" transform="rotate(-30 170 150)"/><ellipse cx="310" cy="135" rx="9" ry="5" transform="rotate(20 310 135)"/><ellipse cx="240" cy="225" rx="9" ry="5" transform="rotate(-10 240 225)"/><ellipse cx="110" cy="300" rx="9" ry="5" transform="rotate(40 110 300)"/><ellipse cx="270" cy="300" rx="9" ry="5" transform="rotate(-50 270 300)"/></g>
<g stroke="#1B1410" stroke-width="2.5" opacity=".35"><path d="M210 30v360M30 210h360"/></g>
<g class="steam" stroke="#F3E6CC" stroke-width="4" stroke-linecap="round" fill="none" opacity=".55"><path d="M150 14c-10-14 10-22 0-36"/><path d="M210 10c-10-14 10-22 0-36"/><path d="M270 14c-10-14 10-22 0-36"/></g>
</svg>'''

CSS = r'''
.dotimg{width:48px;height:47px;border-radius:50%;object-fit:cover;box-shadow:0 0 0 3px #F3E6CC,0 8px 18px -8px rgba(163,20,31,.6)}
.banner{position:relative;max-width:1240px;margin:22px auto 0;padding:0 20px}
.open-stk{position:absolute;left:calc(20px + 33.2%);top:1.5%;width:36.5%;aspect-ratio:3.5/1;display:grid;place-items:center;background:#C8202F;color:#F3E6CC;border:4px solid #F3E6CC;outline:3px solid #1B1410;border-radius:14px;font:400 clamp(1.1rem,4.6vw,3.6rem)/1 var(--disp);letter-spacing:.04em;text-shadow:3px 3px 0 #1B1410;transform:rotate(-4deg);box-shadow:0 18px 30px -12px rgba(0,0,0,.6);animation:slap .7s .6s cubic-bezier(.2,1.6,.4,1) both}
@keyframes slap{from{opacity:0;transform:rotate(-14deg) scale(1.8)}}
.banner img{display:block;width:100%;height:auto;border-radius:26px;box-shadow:0 34px 60px -30px rgba(27,20,16,.55);animation:rise 1.1s cubic-bezier(.2,.8,.2,1) both}
@keyframes rise{from{opacity:0;transform:translateY(20px) scale(.985)}}
.hero .wrap{grid-template-columns:1fr!important;max-width:900px;text-align:center;padding-top:34px!important}
.hero .wrap .acts{justify-content:center}.hero .sub{margin-left:auto;margin-right:auto}
.fc.ph-card{padding:0;overflow:hidden}.ph-card img{display:block;width:100%;aspect-ratio:16/10;object-fit:cover;transition:transform .6s}
.ph-card:hover img{transform:scale(1.06)}.ph-card h3,.ph-card p{padding:0 24px}.ph-card h3{margin-top:20px}.ph-card p{padding-bottom:24px}
.real{margin:0;border-radius:var(--r);overflow:hidden;border:1px solid var(--line)}.real img{width:100%;height:100%;object-fit:cover;display:block;transition:transform .6s}.real:hover img{transform:scale(1.05)}

:root{--bg:#FBF4E6;--panel:#FFFFFF;--panel2:#F3E6CC;--ink:#1B1410;--soft:#5E4E42;--red:#C8202F;--red2:#A3141F;--green:#21422C;--green2:#2F5D3A;--wood:#CFA676;--line:rgba(27,20,16,.12);--disp:"Titan One","Arial Black",sans-serif;--slab:"Zilla Slab",Rockwell,Georgia,serif;--body:"Inter",system-ui,sans-serif;--r:22px;--acc:var(--red);--acc2:var(--green2);--on:#fff}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth;scroll-padding-top:84px}
body{background:var(--bg);color:var(--ink);font:400 1.125rem/1.65 var(--body);-webkit-font-smoothing:antialiased;overflow-x:hidden}
a{color:inherit}:focus-visible{outline:3px solid var(--red);outline-offset:3px;border-radius:6px}
.ic{width:1.15em;height:1.15em;fill:none;stroke:currentColor;stroke-width:2.1;stroke-linecap:round;stroke-linejoin:round;flex:none}
.skip{position:absolute;left:-999px;top:8px;background:var(--red);color:#fff;padding:10px 16px;border-radius:10px;z-index:99}.skip:focus{left:8px}
.prog{position:fixed;top:0;left:0;height:4px;width:0;background:repeating-linear-gradient(90deg,var(--red) 0 18px,#fff 18px 36px,var(--green2) 36px 54px);z-index:30}
.wrap{max-width:1180px;margin:0 auto;padding:0 22px}
.soon{background:var(--green);color:#F3E6CC;text-align:center;font:700 .95rem/1.4 var(--body);padding:10px 16px;letter-spacing:.04em}
.soon b{color:#fff}.soon a{color:#FFD3A8}
header{position:sticky;top:0;z-index:20;background:rgba(251,244,230,.88);backdrop-filter:saturate(1.4) blur(14px);-webkit-backdrop-filter:saturate(1.4) blur(14px);border-bottom:1px solid var(--line);transition:box-shadow .3s}
header.up{box-shadow:0 10px 28px -18px rgba(27,20,16,.45)}
header .wrap{display:flex;align-items:center;gap:14px;padding-top:10px;padding-bottom:10px}
.logo{display:flex;align-items:center;gap:12px;text-decoration:none}
.logo .dot{width:48px;height:48px;border-radius:50%;background:radial-gradient(circle at 40% 35%,#E5323F,#A3141F);border:3px solid #1B1410;box-shadow:0 0 0 3px #F3E6CC,0 8px 18px -8px rgba(163,20,31,.6);display:grid;place-items:center;font:400 .62rem/1 var(--disp);color:#F3E6CC;text-align:center;letter-spacing:.02em;transform:rotate(-8deg)}
.logo b{font:400 1.35rem/1 var(--disp);color:var(--red);letter-spacing:.01em}.logo small{display:block;font:700 .74rem/1.2 var(--slab);letter-spacing:.26em;color:var(--green);margin-top:3px}
nav.main{margin-left:auto;display:flex;gap:2px;font-weight:600;font-size:.95rem}
nav.main a{text-decoration:none;color:var(--soft);padding:8px 14px;border-radius:999px;transition:.2s}nav.main a:hover,nav.main a.on{color:var(--ink);background:var(--panel2)}
.pill{display:inline-flex;align-items:center;gap:8px;text-decoration:none;font-weight:700;background:var(--red);color:#fff;padding:11px 18px;border-radius:999px;white-space:nowrap}
.abtn{width:46px;height:46px;border-radius:50%;border:1px solid var(--line);background:var(--panel);color:var(--ink);display:grid;place-items:center;cursor:pointer;flex:none}.abtn .ic{width:24px;height:24px}
@media(max-width:960px){nav.main{display:none}.hdr-cta{margin-left:auto}}
@media(max-width:560px){.hdr-cta{display:none}.abtn{margin-left:auto}}
.hero{position:relative;overflow:hidden;background:radial-gradient(70vw 40vw at 85% 0%,rgba(200,32,47,.12),transparent 70%),radial-gradient(60vw 40vw at 0% 100%,rgba(47,93,58,.12),transparent 70%)}
.hero::after{content:"";position:absolute;left:0;right:0;bottom:0;height:28px;background:repeating-linear-gradient(90deg,var(--red) 0 28px,#fff 28px 56px);opacity:.9;-webkit-mask:repeating-linear-gradient(0deg,#000 0 14px,transparent 14px 28px);mask:repeating-linear-gradient(0deg,#000 0 14px,transparent 14px 28px)}
.hero .wrap{display:grid;grid-template-columns:1.05fr .95fr;gap:46px;align-items:center;padding-top:54px;padding-bottom:86px}
@media(max-width:900px){.hero .wrap{grid-template-columns:1fr;padding-top:30px;gap:28px}}
.hero .wrap>*{min-width:0}
.badge{display:inline-flex;align-items:center;gap:10px;font:700 .82rem/1 var(--body);letter-spacing:.14em;text-transform:uppercase;color:var(--green);background:rgba(47,93,58,.1);border:1px solid rgba(47,93,58,.25);padding:9px 16px 9px 12px;border-radius:999px}
.badge i{width:9px;height:9px;border-radius:50%;background:var(--red);animation:ping 2s infinite}@keyframes ping{0%{box-shadow:0 0 0 0 rgba(200,32,47,.55)}80%,100%{box-shadow:0 0 0 10px transparent}}
.sign{width:100%;height:auto;display:block;margin:22px 0 6px;filter:drop-shadow(0 22px 30px rgba(27,20,16,.25))}
.sign .disc-g{transform-origin:150px 120px;animation:wob 6s ease-in-out infinite}@keyframes wob{50%{transform:rotate(-3deg) scale(1.02)}}
h1{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
.tag{font:600 clamp(1.3rem,2.6vw,1.75rem)/1.3 var(--slab);color:var(--ink);margin-top:8px;text-wrap:balance}
.tag em{font-style:normal;color:var(--red)}
.sub{color:var(--soft);margin-top:12px;max-width:34em;font-size:1.12rem}
.acts{display:flex;flex-wrap:wrap;gap:12px;margin-top:26px}
.btn{display:inline-flex;align-items:center;gap:10px;text-decoration:none;font-weight:700;font-size:1.05rem;padding:15px 24px;border-radius:999px;border:0;cursor:pointer;font-family:inherit;color:var(--ink);transition:transform .2s,box-shadow .2s}
.btn .ic{width:20px;height:20px}
.b1{background:var(--red);color:#fff;box-shadow:0 14px 30px -14px rgba(200,32,47,.7)}.b1:hover{transform:translateY(-2px);background:var(--red2)}
.b2{background:var(--panel);box-shadow:inset 0 0 0 2px var(--line)}.b2:hover{box-shadow:inset 0 0 0 2px var(--green2);transform:translateY(-2px)}
.b3{background:transparent;color:var(--soft);padding-left:8px;padding-right:8px}.b3:hover{color:var(--ink)}
.bg{background:var(--green);color:#F3E6CC}.bg:hover{background:var(--green2);transform:translateY(-2px)}
.piebox{position:relative;display:grid;place-items:center}
.piebox::before{content:"";position:absolute;inset:8%;border-radius:50%;background:radial-gradient(closest-side,rgba(200,32,47,.22),transparent);filter:blur(30px)}
.pie{position:relative;width:min(100%,460px);height:auto;filter:drop-shadow(0 30px 40px rgba(27,20,16,.3));animation:spinIn 1.4s cubic-bezier(.2,.8,.2,1) both,float 7s 1.4s ease-in-out infinite}
.pie .steam path{animation:steam 3s ease-in-out infinite}.pie .steam path:nth-child(2){animation-delay:.6s}.pie .steam path:nth-child(3){animation-delay:1.2s}
@keyframes spinIn{from{transform:rotate(-25deg) scale(.7);opacity:0}}@keyframes float{50%{transform:translateY(-10px) rotate(1.5deg)}}@keyframes steam{0%{opacity:0;transform:translateY(10px)}50%{opacity:.6}100%{opacity:0;transform:translateY(-14px)}}
.stamp{position:absolute;right:2%;top:4%;width:118px;height:118px;border-radius:50%;background:var(--green);color:#F3E6CC;display:grid;place-items:center;text-align:center;font:700 .78rem/1.2 var(--slab);letter-spacing:.12em;text-transform:uppercase;box-shadow:0 0 0 5px var(--bg),0 0 0 7px var(--green);transform:rotate(12deg);animation:sway 5s ease-in-out infinite}
.stamp b{display:block;font:400 1.35rem/1 var(--disp);letter-spacing:.02em;margin:3px 0}
@keyframes sway{50%{transform:rotate(4deg)}}
.ticker{background:var(--ink);color:#F3E6CC;overflow:hidden;white-space:nowrap;padding:15px 0;font:400 clamp(1.05rem,2vw,1.35rem)/1 var(--disp);letter-spacing:.03em}
.ticker div{display:inline-flex;gap:28px;padding-right:28px;animation:tick 34s linear infinite}.ticker i{color:var(--red);font-style:normal}
@keyframes tick{to{transform:translateX(-50%)}}
section{padding:92px 0}
.kick{font:700 .82rem/1 var(--slab);letter-spacing:.26em;text-transform:uppercase;color:var(--red);margin-bottom:12px;display:flex;align-items:center;gap:12px}.kick::after{content:"";height:2px;width:56px;background:var(--green2)}
h2{font:400 clamp(2.2rem,5vw,3.7rem)/1.02 var(--disp);letter-spacing:.005em;margin-bottom:14px;text-wrap:balance}
h2 em{font-style:normal;color:var(--red)}
.lede{color:var(--soft);max-width:38em;font-size:1.15rem;margin-bottom:34px}
.feat3{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}@media(max-width:860px){.feat3{grid-template-columns:1fr}}
.fc{position:relative;background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:30px 26px;transition:transform .3s cubic-bezier(.2,.8,.2,1),box-shadow .3s}
.fc:hover{transform:translateY(-6px);box-shadow:0 30px 50px -30px rgba(27,20,16,.4)}
.fc .i{width:56px;height:56px;border-radius:16px;display:grid;place-items:center;background:var(--panel2);margin-bottom:16px}.fc .i svg{width:30px;height:30px;stroke:var(--red);fill:none;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round}
.fc h3{font:700 1.4rem/1.2 var(--slab);margin-bottom:6px}.fc p{color:var(--soft)}
.menu-soon{position:relative;overflow:hidden;border-radius:30px;background:var(--green);color:#F3E6CC;padding:54px 40px;display:grid;grid-template-columns:1.2fr .8fr;gap:30px;align-items:center}
@media(max-width:820px){.menu-soon{grid-template-columns:1fr;padding:40px 26px}}
.menu-soon::before{content:"";position:absolute;inset:0;background:repeating-linear-gradient(45deg,transparent 0 22px,rgba(243,230,204,.05) 22px 23px)}
.menu-soon>*{position:relative}
.menu-soon h2{color:#fff}.menu-soon p{color:#DCCFB4;font-size:1.12rem}
.board{background:#1B1410;border:6px solid #8B5E34;border-radius:14px;padding:24px;font:400 1.05rem/1.9 var(--slab);color:#F3E6CC;box-shadow:inset 0 0 40px rgba(0,0,0,.6)}
.board b{display:block;font:400 1.5rem/1 var(--disp);color:#FFD3A8;margin-bottom:10px}
.board .ln{display:flex;gap:10px}.board .ln span{flex:1;border-bottom:2px dotted rgba(243,230,204,.3);transform:translateY(-8px)}
.story{display:grid;grid-template-columns:1fr 1fr;gap:40px;align-items:center}@media(max-width:860px){.story{grid-template-columns:1fr}}
.quote{position:relative;background:var(--panel);border-radius:30px;padding:40px 36px;border:1px solid var(--line);box-shadow:0 30px 60px -40px rgba(27,20,16,.5)}
.quote::before{content:"\201C";position:absolute;top:-28px;left:26px;font:400 7rem/1 var(--disp);color:var(--red)}
.quote p{font:600 1.45rem/1.4 var(--slab)}.quote small{display:block;margin-top:14px;color:var(--soft);font-size:.95rem}
.mural{margin-top:18px;display:flex;gap:16px;align-items:flex-start;background:var(--panel2);border-radius:18px;padding:20px}
.mural svg{width:34px;height:34px;stroke:var(--green2);fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;flex:none}
.gal{display:grid;grid-template-columns:2fr 1fr 1fr;grid-template-rows:1fr 1fr;gap:14px;height:clamp(320px,40vw,460px)}
.gal .ph:first-child{grid-row:span 2}.gal .ph:nth-child(4){grid-column:span 2}
@media(max-width:700px){.gal{grid-template-columns:1fr 1fr;grid-template-rows:repeat(3,150px);height:auto}.gal .ph:first-child{grid-column:span 2;grid-row:auto}}
.ph{position:relative;border-radius:var(--r);overflow:hidden;display:grid;place-items:center;align-content:center;gap:10px;color:var(--soft);font-weight:600;font-size:.92rem;background:linear-gradient(135deg,var(--panel2),#fff);border:1px solid var(--line)}
.ph::before{content:"";position:absolute;inset:0;background:repeating-linear-gradient(45deg,transparent 0 14px,rgba(200,32,47,.05) 14px 15px)}
.ph svg{position:relative;width:44px;height:44px;stroke:var(--red);fill:none;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round;opacity:.8}.ph span{position:relative}
.visit{display:grid;grid-template-columns:1fr 1fr;gap:18px}@media(max-width:900px){.visit{grid-template-columns:1fr}}
.vbox{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:30px}
.lbl{display:flex;align-items:center;gap:8px;font-size:.76rem;font-weight:700;letter-spacing:.18em;text-transform:uppercase;color:var(--soft);margin-bottom:6px}.lbl .ic{color:var(--red);width:16px;height:16px}
.bigt{font:700 1.4rem/1.3 var(--body);margin-bottom:20px}.bigt a{text-decoration:none}.bigt.s{font-size:1.1rem;font-weight:600;color:var(--soft)}
.map{position:relative;min-height:380px;border-radius:var(--r);overflow:hidden;border:1px solid var(--line);background:var(--panel2)}
.map iframe{position:absolute;inset:0;width:100%;height:100%;border:0}
.mapc{position:absolute;inset:0;display:grid;place-items:center;align-content:center;gap:14px;text-align:center;padding:20px;background:radial-gradient(circle at 50% 45%,rgba(200,32,47,.14),transparent 60%),repeating-linear-gradient(0deg,transparent 0 38px,var(--line) 38px 39px),repeating-linear-gradient(90deg,transparent 0 38px,var(--line) 38px 39px)}
.mapc .pin{width:56px;height:56px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);background:var(--red);display:grid;place-items:center;box-shadow:0 14px 30px -10px rgba(200,32,47,.6);animation:bob 2.6s ease-in-out infinite}.mapc .pin i{width:18px;height:18px;border-radius:50%;background:#fff}@keyframes bob{50%{transform:rotate(-45deg) translate(4px,-4px)}}
.mapc small{color:var(--soft);font-size:.82rem}
.tools{display:grid;grid-template-columns:auto 1fr;gap:22px;align-items:center}@media(max-width:560px){.tools{grid-template-columns:1fr;justify-items:center;text-align:center}}
.qr svg{width:136px;height:136px;border-radius:14px;display:block;background:#fff;border:1px solid var(--line)}
.band{position:relative;overflow:hidden;text-align:center;border-radius:34px;padding:70px 22px;background:var(--red);color:#fff}
.band::before{content:"";position:absolute;inset:0;background:repeating-conic-gradient(from 0deg at 50% 120%,rgba(255,255,255,.07) 0 6deg,transparent 6deg 12deg);animation:rays 40s linear infinite}
.band>*{position:relative}@keyframes rays{to{transform:rotate(360deg)}}
.band h2{color:#fff}.band p{opacity:.9;margin-top:8px;font-size:1.15rem}
.band .acts{justify-content:center}
.band .b2{background:#fff;color:var(--red)}
footer{padding:44px 0 120px;color:var(--soft);font-size:.95rem;border-top:1px solid var(--line);margin-top:60px}footer .wrap{display:flex;flex-wrap:wrap;gap:10px 24px;justify-content:space-between}
.dock{position:fixed;left:10px;right:10px;bottom:calc(10px + env(safe-area-inset-bottom));display:none;gap:8px;z-index:18}
.dock a{flex:1;display:flex;align-items:center;justify-content:center;gap:8px;text-decoration:none;font-weight:700;font-size:1.05rem;padding:15px;border-radius:16px;background:var(--red);color:#fff;box-shadow:0 12px 30px -10px rgba(27,20,16,.5)}
.dock a+a{background:var(--panel);color:var(--ink);border:1px solid var(--line)}
@media(max-width:760px){.dock{display:flex}section{padding:66px 0}.stamp{width:96px;height:96px;font-size:.66rem}.stamp b{font-size:1.1rem}}
.rv{opacity:0;transform:translateY(26px);transition:opacity .8s cubic-bezier(.2,.8,.2,1) var(--d,0ms),transform .8s cubic-bezier(.2,.8,.2,1) var(--d,0ms)}.rv.in{opacity:1;transform:none}
.toast{position:fixed;left:50%;bottom:96px;transform:translateX(-50%) translateY(20px);background:var(--ink);color:var(--bg);padding:12px 20px;border-radius:999px;font-weight:600;opacity:0;transition:.3s;z-index:40;pointer-events:none}.toast.on{opacity:1;transform:translateX(-50%)}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}.rv{opacity:1;transform:none}}
html.rm *,html.rm *::before,html.rm *::after{animation:none!important;transition:none!important}html.rm .rv{opacity:1;transform:none}
html.hc{--bg:#000;--panel:#0a0a0a;--panel2:#161616;--ink:#fff;--soft:#f0f0f0;--line:#fff;--red:#FFD400;--red2:#FFD400;--green:#000;--green2:#FFD400;--acc:#FFD400;--on:#000}html.hc a{text-decoration:underline}html.hc .b1,html.hc .dock a,html.hc .band{color:#000}
html.dys body{letter-spacing:.04em;word-spacing:.14em;line-height:1.9}html.dys h2,html.dys h3{font-family:Verdana,Arial,sans-serif;letter-spacing:0}
'''

ld = {"@context": "https://schema.org", "@type": "Restaurant", "name": "Uncle Mike's Pizza House", "servesCuisine": "Pizza",
      "address": {"@type": "PostalAddress", "streetAddress": ADDR1, "addressLocality": "Show Low", "addressRegion": "AZ", "postalCode": "85901", "addressCountry": "US"},
      "sameAs": [FB]}
if PHONE: ld["telephone"] = "+1-" + PHONE

tick_items = ["Now open in Show Low", "Square pies", "Crispy edges", "Cup &amp; char pepperoni", "Fresh ricotta", "Basil pesto", "Made by Mike &amp; Beth", "Hometown pizza"]
ticker = "".join(f"<span>{x}</span><i>●</i>" for x in tick_items)

call_or_msg = (f'<a class="btn b1" href="tel:+1{PHONE.replace("-", "")}">{sv("phone")}Call {PHONE}</a>' if PHONE
               else f'<a class="btn b1" href="{e(MAPS)}" target="_blank" rel="noopener">{sv("pin")}Come get a pie</a>')
dock_first = (f'<a href="tel:+1{PHONE.replace("-", "")}">{sv("phone")}Call</a>' if PHONE else f'<a href="{FB}" target="_blank" rel="noopener">{sv("fb")}Follow</a>')

page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<!-- pxd2-v2 -->
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex, nofollow">
<title>Uncle Mike's Pizza House · Show Low, Arizona</title>
<meta name="description" content="Uncle Mike's Pizza House is now open in Show Low, Arizona. Square pan pies with crispy edges, pepperoni, ricotta and pesto from Mike and Beth.">
<meta name="theme-color" content="#C8202F">
<meta property="og:title" content="Uncle Mike's Pizza House · Now open in Show Low"><meta property="og:description" content="Square pies, crispy edges, hometown pizza from Mike and Beth."><meta property="og:image" content="banner-1100.jpg"><meta property="og:type" content="restaurant">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Ccircle cx='32' cy='32' r='29' fill='%23C8202F' stroke='%231B1410' stroke-width='4'/%3E%3Ctext x='32' y='41' font-family='Arial Black' font-size='22' text-anchor='middle' fill='%23F3E6CC'%3EUM%3C/text%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Titan+One&family=Zilla+Slab:wght@600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<script type="application/ld+json">{json.dumps(ld)}</script>
<style>{CSS}</style></head>
<body>
<a class="skip" href="#main">Skip to content</a>
<div class="prog" aria-hidden="true"></div>
<div class="soon"><b>Now open in Show Low!</b> Come get a square pie. <a href="{FB}" target="_blank" rel="noopener">Follow on Facebook</a> for specials.</div>
<header><div class="wrap">
 <a class="logo" href="#main"><img class="dotimg" src="logo-sm.jpg" alt="" width="48" height="47"><span><b>Uncle Mike's</b><small>PIZZA HOUSE</small></span></a>
 <nav class="main" aria-label="Sections"><a href="#pie">The pie</a><a href="#menu">Menu</a><a href="#story">Mike &amp; Beth</a><a href="#photos">Photos</a><a href="#visit">Visit</a></nav>
 <a class="pill hdr-cta" href="{FB}" target="_blank" rel="noopener">{sv("fb")}Follow us</a>
 <button class="abtn" type="button" id="pxa-open" aria-haspopup="dialog" aria-controls="pxa" aria-label="Accessibility and voice options">{sv("access")}</button>
</div></header>
<main id="main" tabindex="-1">
<div class="hero"><figure class="banner rv in"><img src="banner.jpg" srcset="banner-1100.jpg 1100w, banner.jpg 1942w" sizes="(max-width:1240px) 100vw, 1200px" alt="Uncle Mike's Pizza House sign with three of their pizzas: tomato pesto ricotta, BBQ chicken, and cup pepperoni" width="1942" height="809" fetchpriority="high"><span class="open-stk" aria-hidden="true">NOW OPEN!</span></figure><div class="wrap">
 <div class="rv in">
  <span class="badge"><i></i>Now open · Show Low, AZ</span>
  <h1>Uncle Mike's Pizza House</h1>
  <p class="tag">Square pies. Crispy edges. <em>Hometown pizza</em> in Show Low.</p>
  <p class="sub">Mike and Beth's pizza house is open in the White Mountains: cup-and-char pepperoni, fresh ricotta and basil pesto on a golden, crunchy crust.</p>
  <div class="acts">{call_or_msg}<a class="btn b2" href="{MSG}" target="_blank" rel="noopener">{sv("chat")}Message us</a><a class="btn b3" href="#pie">{sv("slice")}See the pies</a></div>
 </div>
 <div class="rv in" style="--d:150ms"></div>
</div></div>
<div class="ticker" aria-hidden="true"><div>{ticker}{ticker}</div><div>{ticker}{ticker}</div></div>

<section id="pie"><div class="wrap">
 <p class="kick rv">The pie</p>
 <h2 class="rv">Straight out <em>of the oven.</em></h2>
 <p class="lede rv">Real pies from Uncle Mike's kitchen. No floppy chain slices here.</p>
 <div class="feat3">
  <article class="fc ph-card rv"><img src="pizza3.jpg" alt="Square pepperoni pizza with crispy cupped pepperoni" loading="lazy"><h3>Cup &amp; char pepperoni</h3><p>Pepperoni cups that crisp at the rim over a golden, crunchy pan crust.</p></article>
  <article class="fc ph-card rv" style="--d:90ms"><img src="pizza1.jpg" alt="Pizza with cherry tomatoes, basil pesto drizzle and ricotta" loading="lazy"><h3>Tomato, pesto &amp; ricotta</h3><p>Roasted cherry tomatoes, a basil pesto drizzle and cool dollops of ricotta.</p></article>
  <article class="fc ph-card rv" style="--d:180ms"><img src="pizza2.jpg" alt="BBQ chicken pizza with cilantro" loading="lazy"><h3>BBQ chicken</h3><p>Chicken, a BBQ drizzle, fresh cilantro and a cool, creamy finish.</p></article>
 </div>
</div></section>

<section id="menu" style="padding-top:0"><div class="wrap">
 <div class="menu-soon rv">
  <div><p class="kick" style="color:#FFD3A8">The menu</p><h2>Today's pies are on the board.</h2><p>Stop in to see what's coming out of the oven, or message Mike &amp; Beth to ask what's on today. The full menu with prices posts here soon.</p>
   <div class="acts"><a class="btn b1" href="{MSG}" target="_blank" rel="noopener">{sv("chat")}Ask what's on today</a></div></div>
  <div class="board" aria-hidden="true"><b>Today at Uncle Mike's</b><div class="ln">Cup &amp; char pepperoni<span></span>★</div><div class="ln">Tomato, pesto &amp; ricotta<span></span>★</div><div class="ln">BBQ chicken<span></span>★</div><div class="ln">Today's special<span></span>ask</div></div>
 </div>
</div></section>

<section id="story" style="padding-top:0"><div class="wrap story">
 <div class="rv">
  <p class="kick">Mike &amp; Beth</p>
  <h2>A pizza house <em>with an uncle in it.</em></h2>
  <p class="lede">Uncle Mike's is a family pizza shop in Show Low run by Mike and Beth, who are already part of the community.</p>
  <div class="mural">{sv("brush","x")}<div><b>A mural is coming.</b><br><span style="color:var(--soft)">A local White Mountains artist sketched a piece for the shop, and it's going up on a wall inside. Come see it once it's painted.</span></div></div>
 </div>
 <div class="quote rv" style="--d:120ms"><p>We feel grateful to have Uncle Mike and Beth in our community!</p><small>A neighbor, on the Uncle Mike's Facebook page</small></div>
</div></section>

<section id="photos" style="padding-top:0"><div class="wrap">
 <p class="kick rv">Photos</p><h2 class="rv">From the shop.</h2>
 <div class="gal rv">
  <figure class="real"><img src="pizza3.jpg" alt="Cup pepperoni square pizza" loading="lazy"></figure>
  <figure class="real"><img src="pizza1.jpg" alt="Tomato pesto ricotta pizza" loading="lazy"></figure>
  <figure class="real"><img src="logo.jpg" alt="Uncle Mike's Pizza House logo" loading="lazy" style="object-fit:contain;background:#2B4A2A"></figure>
  <figure class="real"><img src="pizza2.jpg" alt="BBQ chicken pizza" loading="lazy"></figure>
 </div>
 
</div></section>

<section id="visit" style="padding-top:0"><div class="wrap">
 <p class="kick rv">Visit</p><h2 class="rv">Find us in Show Low.</h2>
 <div class="visit">
  <div class="vbox rv">
   <p class="lbl">{sv("pin")}Address</p><p class="bigt">{ADDR1}<br>{ADDR2}</p>
   <p class="lbl">{sv("phone")}Phone</p><p class="bigt{'' if PHONE else ' s'}">{f'<a href="tel:+1{PHONE.replace("-", "")}">{PHONE}</a>' if PHONE else f'<a href="{MSG}" target="_blank" rel="noopener">Message on Facebook</a>'}</p>
   <p class="lbl">{sv("clock")}Hours</p><p class="bigt s">Open now · message us for today's hours</p>
   <div class="tools"><div class="qr" title="Scan with a phone camera">{QR}</div>
    <div><div class="acts" style="margin-top:0"><a class="btn b1" href="{e(MAPS)}" target="_blank" rel="noopener">{sv("pin")}Directions</a><button class="btn b2" type="button" data-share>{sv("share")}Share</button></div>
    <p style="margin-top:10px;color:var(--soft);font-size:.92rem">Scan the code with a phone camera to open this page.</p></div></div>
  </div>
  <div class="map rv" style="--d:100ms" data-src="{EMBED}"><div class="mapc"><div class="pin" aria-hidden="true"><i></i></div><button class="btn b1" type="button" data-map>{sv("pin")}Show the map</button><small>The map loads from Google only when you tap.</small></div></div>
 </div>
</div></section>

<section style="padding-top:0"><div class="wrap"><div class="band rv"><h2>Hungry? Uncle Mike's is open.</h2><p>Square pies in Show Low, Arizona.</p>
 <div class="acts"><a class="btn b2" href="{FB}" target="_blank" rel="noopener">{sv("fb")}Follow on Facebook</a></div></div></div></section>
</main>
<footer><div class="wrap"><span>Uncle Mike's Pizza House · {ADDR1}, {ADDR2}</span><span>Built for everyone: voice control, read aloud and sound cues. Tap {sv("access")} at the top.</span></div></footer>
<div class="dock">{dock_first}<a href="{e(MAPS)}" target="_blank" rel="noopener">{sv("pin")}Directions</a></div>
<div class="toast" role="status" aria-live="polite"></div>
<script>
(function(){{
var pr=document.querySelector('.prog'),hd=document.querySelector('header');
function sc(){{var h=document.documentElement,m=h.scrollHeight-h.clientHeight;pr.style.width=(m>0?h.scrollTop/m*100:0)+'%';hd.classList.toggle('up',h.scrollTop>10)}}
addEventListener('scroll',sc,{{passive:true}});sc();
var io='IntersectionObserver' in window?new IntersectionObserver(function(es){{es.forEach(function(x){{if(x.isIntersecting){{x.target.classList.add('in');io.unobserve(x.target)}}}})}},{{rootMargin:'0px 0px -8% 0px'}}):null;
document.querySelectorAll('.rv').forEach(function(el){{io?io.observe(el):el.classList.add('in')}});
var links=[].slice.call(document.querySelectorAll('nav.main a'));
if(io)links.forEach(function(a){{var s=document.querySelector(a.getAttribute('href'));if(!s)return;new IntersectionObserver(function(es){{es.forEach(function(x){{if(x.isIntersecting)links.forEach(function(l){{l.classList.toggle('on',l===a)}})}})}},{{rootMargin:'-45% 0px -50% 0px'}}).observe(s)}});
var t=document.querySelector('.toast');window.pxToast=function(m){{t.textContent=m;t.classList.add('on');clearTimeout(t._h);t._h=setTimeout(function(){{t.classList.remove('on')}},2600)}};
document.querySelectorAll('[data-map]').forEach(function(b){{b.addEventListener('click',function(){{var m=b.closest('.map'),f=document.createElement('iframe');f.src=m.getAttribute('data-src');f.title="Map to Uncle Mike's Pizza House";f.loading='lazy';f.referrerPolicy='no-referrer-when-downgrade';m.innerHTML='';m.appendChild(f)}})}});
document.querySelectorAll('[data-share]').forEach(function(b){{b.addEventListener('click',function(){{var u=location.href;if(navigator.share){{navigator.share({{title:"Uncle Mike's Pizza House",url:u}}).catch(function(){{}})}}else if(navigator.clipboard){{navigator.clipboard.writeText(u).then(function(){{pxToast('Link copied')}})}}}})}});
}})();
</script>
{v2.ACCESS}
</body></html>
'''
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(page, encoding="utf-8")
SHORT.parent.mkdir(parents=True, exist_ok=True)
SHORT.write_text(f'''<!doctype html><!-- pxd2-names:generated -->
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Uncle Mike's Pizza House</title>
<meta http-equiv="refresh" content="0; url=/clients/{SLUG}/">
<link rel="canonical" href="/clients/{SLUG}/">
<meta name="robots" content="noindex">
<script>location.replace("/clients/{SLUG}/" + location.hash);</script>
</head><body style="background:#FBF4E6;color:#1B1410;font:16px system-ui;padding:24px">
<p>pxd2.github.io/unclemikes → <a style="color:#C8202F" href="/clients/{SLUG}/">Uncle Mike's Pizza House</a></p>
</body></html>
''', encoding="utf-8")
(ROOT / "clients" / SLUG / "qr.svg").write_text(QR.replace(' class="segno" role="img" aria-label="QR code to this page"', ''), encoding="utf-8")
print("wrote", OUT, len(page))
