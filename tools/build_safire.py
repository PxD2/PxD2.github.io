#!/usr/bin/env python3
"""Safire Restaurant & Lounge (Springerville, AZ) - premium PXD2 site.
Menu from Safire's last posted menu; prices to be confirmed with the restaurant.
Run: python3 tools/build_safire.py
"""
import html, json, pathlib, sys, importlib.util

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "clients" / "safire-restaurant-1aac1c" / "index.html"
spec = importlib.util.spec_from_file_location("v2", sys.argv[1] if len(sys.argv) > 1 else ROOT / "tools" / "clients_v2.py")
v2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(v2)
QR = (pathlib.Path(sys.argv[2]).read_text() if len(sys.argv) > 2 else
      __import__("re").search(r'<svg[^>]*class="segno".*?</svg>', OUT.read_text(), __import__("re").S).group(0))

TEL = "+19283334512"; PHONE = "928-333-4512"
ADDR = "411 E Main St, Springerville, AZ 85938"
MAPS = "https://www.google.com/maps/search/?api=1&query=Safire%20Restaurant%20411%20E%20Main%20St%2C%20Springerville%2C%20AZ%2085938"
EMBED = "https://www.google.com/maps?output=embed&q=Safire+Restaurant+411+E+Main+St+Springerville+AZ"
# 0=Sun .. 6=Sat, minutes from midnight (Arizona time, no DST)
HOURS = [(420, 1260), (390, 1260), (390, 1260), (420, 1260), (420, 1260), (420, 1260), (420, 1260)]

# (section, icon, [(name, price, short note, tags)])  tags: pop, spicy, veg
MENU = [
 ("Breakfast", "sun", [
  ("Smothered Breakfast Burrito", "9.99", "Sausage, egg, green chile and hash browns, smothered in green chile and cheese", "pop spicy"),
  ("Farmhouse Breakfast", "9.99", "Bacon, two eggs, hash browns, biscuit and gravy", "pop"),
  ("Huevos Rancheros", "9.99", "Red or green chile, warm flour tortilla", "spicy"),
  ("Chicken Fried Steak & Eggs", "11.99", "Two eggs, hash browns and toast", "pop"),
  ("Pork Chop & Two Eggs", "11.99", "Golden hash browns and toast", ""),
  ("Ham & Eggs", "9.99", "Golden hash browns and toast", ""),
  ("Bacon or Sausage & Eggs", "7.99", "Golden hash browns and toast", ""),
  ("Morning Melt", "7.99", "Ham, egg, cheddar and tomato on grilled sourdough", ""),
  ("Country Scramble", "7.99", "Eggs, onion, green chile and cheddar", "spicy"),
  ("Green Chile Hash Browns", "6.99", "Smothered in green chile and cheddar, with toast", "veg spicy"),
  ("Biscuits & Sausage Gravy", "4.99", "One biscuit 4.99 · two biscuits 5.99", ""),
 ]),
 ("Omelets & Skillets", "egg", [
  ("Range Riders Omelet", "9.99", "Ham, green pepper, onion, tomato, cheese, sour cream", "pop"),
  ("Bunkhouse Omelet", "8.99", "Bacon, mushroom, onion and cheese", ""),
  ("Spanish Omelet", "7.99", "Cheese omelet smothered in green chile", "spicy veg"),
  ("Ham & Cheese Omelet", "7.99", "", ""),
  ("Cheese Omelet", "6.99", "", "veg"),
  ("Rancher Skillet", "8.99", "Eggs, ham, peppers, mushrooms and cheddar over potatoes", ""),
 ]),
 ("Starters", "spark", [
  ("Sampler Platter", "17.99", "Onion rings, zucchini, mushrooms, mozzarella sticks and wings", "pop"),
  ("Half Pound Buffalo Wings", "11.99", "Your choice of sauce", "spicy"),
  ("Green Chile Cheese Fries", "9.99", "", "spicy veg"),
  ("Mozzarella Sticks", "10.99", "With marinara", "veg"),
  ("Fried Zucchini", "8.99", "With ranch", "veg"),
  ("Fried Mushrooms", "8.99", "With ranch", "veg"),
  ("Onion Rings", "7.99", "With ranch", "veg"),
 ]),
 ("Soups & Salads", "leaf", [
  ("Steak Fajita Salad", "14.99", "", ""),
  ("Grilled Shrimp Salad", "14.99", "", ""),
  ("Buffalo Chicken Salad", "13.99", "", "spicy"),
  ("Chicken Fajita Salad", "13.99", "", ""),
  ("Chef Salad", "13.99", "", ""),
  ("Crispy Chicken Salad", "12.99", "", ""),
  ("Soup & Salad", "11.99", "House salad and a bowl of soup", "pop"),
  ("Bowl of Soup", "5.99", "", ""),
  ("Cup of Soup", "3.99", "", ""),
 ]),
 ("Burgers & Sandwiches", "burger", [
  ("The Hangover", "15.99", "", "pop"),
  ("Jack Daniel's Burger", "14.99", "", "pop"),
  ("Ortega Burger", "14.99", "Topped with a green chile", "spicy"),
  ("Black N Bleu", "13.99", "", ""),
  ("Bacon Burger", "13.99", "", ""),
  ("Mushroom Swiss", "13.99", "Mushrooms and melted Swiss", ""),
  ("Sourdough Burger", "13.99", "", ""),
  ("All-American", "12.99", "The classic, with American cheese and the works", "pop"),
  ("Patty Melt", "12.99", "", ""),
  ("Hamburger", "11.99", "Fresh ground chuck", ""),
  ("Steak Sandwich", "18.99", "", ""),
  ("Chicken Fried Steak Sandwich", "15.99", "", ""),
  ("Grilled Chicken Ortega", "14.99", "", "spicy"),
  ("Chicken Cordon Bleu", "14.99", "", ""),
  ("Philly Steak", "14.99", "", ""),
  ("Turkey Club", "14.99", "", ""),
  ("French Dip", "13.99", "Roast beef and Swiss with au jus", ""),
  ("Roast Beef Sandwich", "13.99", "", ""),
  ("Grilled Ham & Cheese", "10.99", "", ""),
  ("B.L.T.", "10.99", "", ""),
 ]),
 ("Mexican Food", "chile", [
  ("Steak & Enchiladas", "19.99", "", "pop"),
  ("Mix Plate", "18.99", "", ""),
  ("Grilled Shrimp Plate", "16.99", "", ""),
  ("Combination Platter", "15.99", "", "pop"),
  ("Fajita Plate", "15.99", "", ""),
  ("Chimichanga Plate", "14.99", "", ""),
  ("Relleno Plate", "13.99", "", "veg spicy"),
  ("Taco Plate", "12.99", "Three tacos, regular or San Juan style, rice and beans", "pop"),
  ("Southwest Chicken Quesadilla", "12.99", "", ""),
  ("Taco Salad", "12.99", "", ""),
  ("Enchilada Plate", "10.99", "", ""),
  ("Bean Burrito", "8.99", "", "veg"),
  ("Cheese Crisp", "8.99", "", "veg"),
  ("A la carte: Taco, Tostada, Cheese Enchilada or Tamale", "3.99", "Each", ""),
  ("A la carte: Relleno", "6.99", "", "veg"),
 ]),
 ("Steaks & Dinners", "steak", [
  ("Ribeye", "27.99", "Hand cut, two sides and a dinner roll", "pop"),
  ("Steak & Shrimp", "25.99", "", "pop"),
  ("Herbed Grilled Salmon", "19.99", "", ""),
  ("Jumbo Shrimp", "19.99", "", ""),
  ("Center Cut Top Sirloin", "18.99", "Hand cut, two sides and a dinner roll", ""),
  ("Roadkill", "17.99", "A house favorite. Ask your server", ""),
  ("Grilled Pork Chops", "16.99", "", ""),
  ("Chicken Fried Steak", "16.99", "", "pop"),
  ("Chicken Fried Chicken", "15.99", "", ""),
  ("Fish & Chips", "14.99", "", ""),
  ("Chicken Tenders", "13.99", "", ""),
 ]),
 ("Dessert & Drinks", "pie", [
  ("White Chocolate Raspberry Cheesecake", "6.99", "", "pop veg"),
  ("Fruit Pie", "4.39", "", "veg"),
  ("Coca-Cola Products", "2.99", "", ""),
  ("Iced Tea", "2.99", "", ""),
  ("Milk", "2.99", "", ""),
  ("Orange Juice", "2.99", "", ""),
 ]),
]

ICONS = {
 "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
 "egg": '<path d="M12 3c-4 0-7 6-7 10a7 7 0 0 0 14 0c0-4-3-10-7-10z"/><circle cx="12" cy="14" r="2.5"/>',
 "spark": '<path d="M12 3l2 5 5 2-5 2-2 5-2-5-5-2 5-2z"/>',
 "leaf": '<path d="M5 19c0-8 5-14 15-15-1 10-7 15-15 15z"/><path d="M5 19l8-8"/>',
 "burger": '<path d="M4 10a8 5 0 0 1 16 0z"/><path d="M3 13h18M4 16h16a0 0 0 0 1 0 0 3 3 0 0 1-3 3H7a3 3 0 0 1-3-3z"/>',
 "chile": '<path d="M7 20c6 0 11-5 11-11 0-1.5-1-2.5-2.5-2.5C13 6.5 14 12 7 17c-1.5 1-1 3 0 3z"/><path d="M15.5 6.5c0-2 1-3 2.5-3.5"/>',
 "steak": '<path d="M5 8c3-4 11-5 14 0s0 11-6 11-10-6-8-11z"/><circle cx="14" cy="10" r="2"/>',
 "pie": '<path d="M3 13h18l-2 6H5z"/><path d="M3 13c2-5 16-5 18 0M8 10l1 3M12 9v4M16 10l-1 3"/>',
}

def sv(name, cls="ic"):
    p = ICONS.get(name) or v2.I[name]
    return f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true">{p}</svg>'

e = html.escape
menu_json = json.dumps([{"s": s, "i": i, "items": [{"n": n, "p": p, "d": d, "t": t.split()} for n, p, d, t in items]} for s, i, items in MENU])
icon_json = json.dumps({k: v for k, v in ICONS.items()})

GEM = '''<svg viewBox="0 0 64 64" aria-hidden="true"><path d="M18 10h28l12 14-26 32L6 24z" fill="url(#gg)" stroke="#F4D58D" stroke-width="2.4" stroke-linejoin="round"/><path d="M6 24h52M18 10l8 14 6 32 6-32 8-14M26 24l6-14 6 14" fill="none" stroke="#F4D58D" stroke-width="1.6" stroke-linejoin="round" opacity=".85"/><defs><linearGradient id="gg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#C0392B"/><stop offset=".55" stop-color="#7A1E1A"/><stop offset="1" stop-color="#3D0F0D"/></linearGradient></defs></svg>'''

HERO = '''<svg class="hero-art" viewBox="0 0 640 470" role="img" aria-label="Safire Restaurant and Lounge on Main Street at dusk">
<defs>
 <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2A1712"/><stop offset=".55" stop-color="#7A3A22"/><stop offset="1" stop-color="#D98A3D"/></linearGradient>
 <linearGradient id="wood" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#6B3F27"/><stop offset="1" stop-color="#3E2416"/></linearGradient>
 <radialGradient id="glow" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#FFD58A" stop-opacity=".95"/><stop offset="1" stop-color="#FFB347" stop-opacity="0"/></radialGradient>
 <linearGradient id="win" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFE3A3"/><stop offset="1" stop-color="#E89A3C"/></linearGradient>
 <linearGradient id="gem2" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#E0553F"/><stop offset=".6" stop-color="#8E2420"/><stop offset="1" stop-color="#4A1210"/></linearGradient>
 <clipPath id="clip"><rect width="640" height="470" rx="30"/></clipPath>
</defs>
<g clip-path="url(#clip)">
<rect width="640" height="470" fill="url(#sky)"/>
<g fill="#FFE9C2" class="stars"><circle cx="60" cy="40" r="1.4"/><circle cx="140" cy="70" r="1"/><circle cx="240" cy="30" r="1.3"/><circle cx="420" cy="50" r="1"/><circle cx="520" cy="28" r="1.5"/><circle cx="590" cy="80" r="1"/><circle cx="330" cy="88" r="1"/></g>
<circle class="sun" cx="500" cy="230" r="60" fill="#F7B65A" opacity=".55"/>
<path d="M0 260 L80 200 L150 236 L230 172 L320 238 L400 190 L470 226 L560 178 L640 220 V470 H0z" fill="#3B1F17" opacity=".75"/>
<path d="M0 300 L120 262 L220 290 L330 250 L440 286 L540 258 L640 280 V470 H0z" fill="#2A1510"/>
<!-- building -->
<rect x="110" y="168" width="420" height="232" fill="url(#wood)"/>
<g stroke="#2A170E" stroke-width="2" opacity=".55"><path d="M110 196h420M110 224h420M110 252h420M110 280h420M110 308h420M110 336h420M110 364h420"/></g>
<path d="M150 120h340v58H150z" fill="#4A2A1A"/><path d="M150 120h340" stroke="#2A170E" stroke-width="4"/>
<!-- marquee sign -->
<g class="sign">
 <rect x="182" y="102" width="276" height="74" rx="10" fill="#1A0E0A" stroke="#F4D58D" stroke-width="3"/>
 <g fill="#FFD58A">
  <circle cx="194" cy="114" r="3"/><circle cx="216" cy="114" r="3"/><circle cx="238" cy="114" r="3"/><circle cx="260" cy="114" r="3"/><circle cx="282" cy="114" r="3"/><circle cx="304" cy="114" r="3"/><circle cx="326" cy="114" r="3"/><circle cx="348" cy="114" r="3"/><circle cx="370" cy="114" r="3"/><circle cx="392" cy="114" r="3"/><circle cx="414" cy="114" r="3"/><circle cx="436" cy="114" r="3"/>
  <circle cx="194" cy="164" r="3"/><circle cx="216" cy="164" r="3"/><circle cx="238" cy="164" r="3"/><circle cx="260" cy="164" r="3"/><circle cx="282" cy="164" r="3"/><circle cx="304" cy="164" r="3"/><circle cx="326" cy="164" r="3"/><circle cx="348" cy="164" r="3"/><circle cx="370" cy="164" r="3"/><circle cx="392" cy="164" r="3"/><circle cx="414" cy="164" r="3"/><circle cx="436" cy="164" r="3"/>
 </g>
 <text x="320" y="150" text-anchor="middle" font-family="Rye,Georgia,serif" font-size="38" fill="#FFE3A3" letter-spacing="4">SAFIRE</text>
</g>
<path d="M300 84 l20 -24 l20 24 l-20 18z" fill="url(#gem2)" stroke="#F4D58D" stroke-width="2"/>
<!-- porch roof -->
<path d="M92 236h456l-16 16H108z" fill="#2E1A10"/>
<g fill="#3E2416"><rect x="122" y="252" width="8" height="148"/><rect x="510" y="252" width="8" height="148"/><rect x="316" y="252" width="8" height="148"/></g>
<!-- windows -->
<ellipse cx="210" cy="320" rx="90" ry="70" fill="url(#glow)" class="flick"/>
<ellipse cx="430" cy="320" rx="90" ry="70" fill="url(#glow)" class="flick d2"/>
<rect x="150" y="276" width="120" height="84" rx="4" fill="url(#win)" stroke="#2A170E" stroke-width="5"/>
<path d="M210 276v84M150 318h120" stroke="#2A170E" stroke-width="4"/>
<rect x="370" y="276" width="120" height="84" rx="4" fill="url(#win)" stroke="#2A170E" stroke-width="5"/>
<path d="M430 276v84M370 318h120" stroke="#2A170E" stroke-width="4"/>
<g fill="#3A1E12" opacity=".75"><circle cx="180" cy="300" r="9"/><rect x="172" y="309" width="16" height="22" rx="6"/><circle cx="242" cy="304" r="8"/><rect x="235" y="312" width="14" height="20" rx="6"/><path d="M392 298h34v4h-34z"/><rect x="396" y="302" width="4" height="16"/><rect x="418" y="302" width="4" height="16"/><path d="M450 290l12 10h-24z"/></g>
<text x="430" y="352" text-anchor="middle" font-family="Georgia,serif" font-style="italic" font-size="13" fill="#7A2E1A">Lounge</text>
<!-- door -->
<rect x="290" y="282" width="60" height="118" fill="#2A170E"/><rect x="296" y="288" width="48" height="56" fill="url(#win)" opacity=".85"/>
<rect x="332" y="346" width="6" height="6" rx="3" fill="#F4D58D"/>
<!-- OPEN sign -->
<g class="open"><rect x="458" y="258" width="58" height="22" rx="5" fill="#1A0E0A" stroke="#E0553F" stroke-width="2"/><text x="487" y="274" text-anchor="middle" font-family="Arial,sans-serif" font-weight="700" font-size="13" fill="#FF7A5C" letter-spacing="2">OPEN</text></g>
<!-- boardwalk + hitching post -->
<rect x="80" y="398" width="480" height="12" fill="#5A3420"/><g stroke="#3A2214" stroke-width="2"><path d="M120 398v12M170 398v12M220 398v12M270 398v12M320 398v12M370 398v12M420 398v12M470 398v12M520 398v12"/></g>
<path d="M40 380h60M48 380v32M92 380v32" stroke="#4A2A1A" stroke-width="6" stroke-linecap="round"/>
<path d="M560 412h60l-4-50h-52z" fill="#3E2416"/><path d="M566 372h48M564 392h52" stroke="#2A170E" stroke-width="3"/>
<rect x="0" y="410" width="640" height="60" fill="#1E110C"/>
<path d="M0 432h640" stroke="#D98A3D" stroke-width="2" stroke-dasharray="26 22" opacity=".5"/>
<text x="320" y="458" text-anchor="middle" font-family="Inter,system-ui,sans-serif" font-size="13" font-weight="700" letter-spacing="5" fill="#F4D58D" opacity=".7">411 E MAIN ST · SPRINGERVILLE</text>
</g>
</svg>'''

CSS = r'''
:root{--bg:#17100D;--panel:#221813;--panel2:#2D201A;--ink:#F6EAD6;--soft:#CDB89C;--acc:#E0A64A;--acc2:#C8452F;--on:#1A0F0A;--line:rgba(246,234,214,.12);--head:"Playfair Display",Georgia,serif;--west:"Rye",Georgia,serif;--body:"Inter",system-ui,sans-serif;--r:22px;--glow:rgba(224,166,74,.35)}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth;scroll-padding-top:86px}
body{background:var(--bg);color:var(--ink);font:400 1.125rem/1.65 var(--body);-webkit-font-smoothing:antialiased;overflow-x:hidden}
body::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:-1;background:radial-gradient(70vw 50vw at 90% -10%,rgba(224,166,74,.14),transparent 70%),radial-gradient(50vw 40vw at -10% 40%,rgba(200,69,47,.12),transparent 70%)}
body::after{content:"";position:fixed;inset:0;pointer-events:none;z-index:-1;opacity:.05;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence baseFrequency='.8' numOctaves='3'/%3E%3C/filter%3E%3Crect width='160' height='160' filter='url(%23n)'/%3E%3C/svg%3E")}
a{color:inherit}:focus-visible{outline:3px solid var(--acc);outline-offset:3px;border-radius:6px}
.ic{width:1.15em;height:1.15em;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;flex:none}
.skip{position:absolute;left:-999px;top:8px;background:var(--acc);color:var(--on);padding:10px 16px;border-radius:10px;z-index:99}.skip:focus{left:8px}
.concept{background:#0b0705;color:#d8cbb8;font:13px/1.45 system-ui,sans-serif;text-align:center;padding:8px 16px}.concept b{color:#fff}
.prog{position:fixed;top:0;left:0;height:3px;width:0;background:linear-gradient(90deg,var(--acc2),var(--acc));z-index:30}
.wrap{max-width:1200px;margin:0 auto;padding:0 22px}
header{position:sticky;top:0;z-index:20;background:rgba(23,16,13,.82);backdrop-filter:saturate(1.4) blur(14px);-webkit-backdrop-filter:saturate(1.4) blur(14px);border-bottom:1px solid var(--line);transition:box-shadow .3s}
header.up{box-shadow:0 12px 30px -16px rgba(0,0,0,.7)}
header .wrap{display:flex;align-items:center;gap:14px;padding-top:11px;padding-bottom:11px}
.logo{display:flex;align-items:center;gap:12px;text-decoration:none}.logo svg{width:42px;height:42px;filter:drop-shadow(0 6px 14px rgba(200,69,47,.45))}
.logo b{font:400 1.55rem/1 var(--west);letter-spacing:.08em;color:var(--acc)}.logo small{display:block;font:600 .68rem/1.3 var(--body);letter-spacing:.22em;color:var(--soft);text-transform:uppercase;margin-top:4px}
nav.main{margin-left:auto;display:flex;gap:2px;font-weight:600;font-size:.95rem}
nav.main a{text-decoration:none;color:var(--soft);padding:8px 14px;border-radius:999px;transition:.2s}nav.main a:hover,nav.main a.on{color:var(--ink);background:var(--panel2)}
.pill{display:inline-flex;align-items:center;gap:8px;text-decoration:none;font-weight:700;background:var(--acc);color:var(--on);padding:11px 18px;border-radius:999px;white-space:nowrap}
.abtn{width:46px;height:46px;border-radius:50%;border:1px solid var(--line);background:var(--panel);color:var(--ink);display:grid;place-items:center;cursor:pointer;flex:none}.abtn .ic{width:24px;height:24px}
@media(max-width:980px){nav.main{display:none}.hdr-call{margin-left:auto}}
@media(max-width:560px){.hdr-call{display:none}.abtn{margin-left:auto}}
.status{display:inline-flex;align-items:center;gap:10px;font-weight:600;font-size:.95rem;padding:8px 16px 8px 12px;border-radius:999px;background:rgba(246,234,214,.06);border:1px solid var(--line)}
.status i{width:10px;height:10px;border-radius:50%;background:#7CC36E;box-shadow:0 0 0 0 rgba(124,195,110,.6);animation:ping 2.2s infinite}.status.closed i{background:#C8452F;animation:none}
@keyframes ping{80%,100%{box-shadow:0 0 0 10px transparent}}
.hero .wrap{display:grid;grid-template-columns:1.02fr 1.08fr;gap:50px;align-items:center;padding-top:58px;padding-bottom:70px}
@media(max-width:900px){.hero .wrap{grid-template-columns:1fr;padding-top:32px;gap:30px}}
.hero .wrap>*{min-width:0}
.eyb{font:700 .8rem/1 var(--body);letter-spacing:.24em;text-transform:uppercase;color:var(--acc);display:block;margin:22px 0 14px}
h1{font:400 clamp(3.3rem,8.5vw,6.4rem)/.92 var(--west);letter-spacing:.02em;color:var(--ink);text-wrap:balance}
h1 span{display:block;font:italic 700 .5em/1.1 var(--head);color:var(--acc);letter-spacing:0;margin-top:14px}
.tag{font-size:clamp(1.12rem,2.1vw,1.35rem);color:var(--soft);max-width:32em;margin-top:20px;text-wrap:pretty}
.acts{display:flex;flex-wrap:wrap;gap:12px;margin-top:30px}
.btn{display:inline-flex;align-items:center;gap:10px;text-decoration:none;font-weight:700;font-size:1.05rem;padding:15px 24px;border-radius:999px;border:0;cursor:pointer;font-family:inherit;color:var(--ink);transition:transform .2s,box-shadow .2s,background .2s}
.btn .ic{width:20px;height:20px}
.b1{background:linear-gradient(135deg,#F0BC62,#D08F2E);color:var(--on);box-shadow:0 16px 34px -14px var(--glow)}.b1:hover{transform:translateY(-2px);box-shadow:0 22px 44px -16px var(--glow)}
.b2{background:var(--panel);box-shadow:inset 0 0 0 2px var(--line)}.b2:hover{box-shadow:inset 0 0 0 2px var(--acc);transform:translateY(-2px)}
.b3{background:transparent;color:var(--soft);padding-left:8px;padding-right:8px}.b3:hover{color:var(--ink)}
.facts{display:flex;flex-wrap:wrap;gap:10px;margin-top:28px}
.facts span{display:inline-flex;align-items:center;gap:8px;font-weight:600;font-size:.92rem;padding:8px 14px;border-radius:12px;background:var(--panel);border:1px solid var(--line);color:var(--soft)}.facts .ic{color:var(--acc);width:18px;height:18px}
.artbox{position:relative}.artbox::before{content:"";position:absolute;inset:10% 4%;background:radial-gradient(closest-side,rgba(224,166,74,.4),transparent);filter:blur(40px);z-index:-1}
.hero-art{width:100%;height:auto;display:block;border-radius:30px;box-shadow:0 40px 80px -30px rgba(0,0,0,.8),0 0 0 1px var(--line)}
.hero-art .flick{animation:flick 4s ease-in-out infinite}.hero-art .d2{animation-delay:1.3s}
.hero-art .sign circle{animation:bulb 1.6s steps(2) infinite}.hero-art .sign circle:nth-child(2n){animation-delay:.8s}
.hero-art .open{animation:neon 3s infinite}.hero-art .stars{animation:tw 4s ease-in-out infinite}.hero-art .sun{animation:pulse 6s ease-in-out infinite}
@keyframes flick{50%{opacity:.7}}@keyframes bulb{50%{opacity:.35}}@keyframes neon{0%,92%,100%{opacity:1}94%{opacity:.3}96%{opacity:1}97%{opacity:.4}}@keyframes tw{50%{opacity:.4}}@keyframes pulse{50%{opacity:.75}}
.ribbon{border-block:1px solid var(--line);background:var(--panel);overflow:hidden;white-space:nowrap;padding:16px 0;font:400 clamp(1.05rem,2vw,1.35rem)/1 var(--west);letter-spacing:.06em;color:var(--soft)}
.ribbon div{display:inline-flex;gap:30px;padding-right:30px;animation:tick 40s linear infinite}.ribbon i{color:var(--acc2);font-style:normal}
@keyframes tick{to{transform:translateX(-50%)}}
section{padding:92px 0}
.kick{font:700 .8rem/1 var(--body);letter-spacing:.24em;text-transform:uppercase;color:var(--acc);display:flex;align-items:center;gap:12px;margin-bottom:14px}.kick::after{content:"";height:1px;width:60px;background:var(--acc);opacity:.5}
h2{font:700 clamp(2.2rem,4.8vw,3.6rem)/1.04 var(--head);letter-spacing:-.01em;text-wrap:balance;margin-bottom:14px}
h2 em{font-style:italic;color:var(--acc)}
.lede{color:var(--soft);max-width:38em;font-size:1.15rem;margin-bottom:36px}
.trio{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}@media(max-width:860px){.trio{grid-template-columns:1fr}}
.meal{position:relative;overflow:hidden;border-radius:var(--r);padding:34px 30px;background:linear-gradient(160deg,var(--panel2),var(--panel));border:1px solid var(--line);transition:transform .35s cubic-bezier(.2,.8,.2,1),border-color .3s}
.meal:hover{transform:translateY(-6px);border-color:rgba(224,166,74,.5)}
.meal .big-ic{width:58px;height:58px;border-radius:18px;display:grid;place-items:center;background:rgba(224,166,74,.12);margin-bottom:20px}.meal .big-ic svg{width:30px;height:30px;stroke:var(--acc);fill:none;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round}
.meal h3{font:700 1.7rem/1.1 var(--head);margin-bottom:8px}.meal p{color:var(--soft)}
.meal ul{list-style:none;margin-top:18px;display:grid;gap:8px}.meal li{display:flex;justify-content:space-between;gap:12px;border-top:1px dashed var(--line);padding-top:8px;font-weight:600;font-size:1rem}.meal li span{color:var(--acc)}
.meal::after{content:"";position:absolute;right:-60px;top:-60px;width:180px;height:180px;border-radius:50%;background:radial-gradient(closest-side,rgba(224,166,74,.18),transparent)}
/* menu */
.mbar{position:sticky;top:73px;z-index:10;background:rgba(23,16,13,.92);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);padding:14px 0;border-bottom:1px solid var(--line);margin-bottom:26px}
.tabs{display:flex;gap:8px;overflow-x:auto;scrollbar-width:none;padding-bottom:2px}.tabs::-webkit-scrollbar{display:none}
.tab{flex:none;display:inline-flex;align-items:center;gap:8px;padding:10px 16px;border-radius:999px;border:1px solid var(--line);background:var(--panel);color:var(--soft);font:600 .95rem/1 var(--body);cursor:pointer;transition:.2s}
.tab svg{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.tab:hover{color:var(--ink)}.tab[aria-selected=true]{background:var(--acc);color:var(--on);border-color:transparent}
.mtools{display:flex;gap:10px;margin-top:12px;flex-wrap:wrap}
.search{flex:1;min-width:220px;display:flex;align-items:center;gap:10px;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:0 14px}
.search input{flex:1;background:transparent;border:0;color:var(--ink);font:500 1rem var(--body);padding:12px 0;outline:none;min-width:0}.search input::placeholder{color:var(--soft);opacity:.75}
.chip{display:inline-flex;align-items:center;gap:6px;padding:10px 14px;border-radius:14px;border:1px solid var(--line);background:var(--panel);color:var(--soft);font:600 .9rem var(--body);cursor:pointer}.chip[aria-pressed=true]{border-color:var(--acc);color:var(--acc);background:rgba(224,166,74,.08)}
.msec{margin-bottom:46px}.msec h3{display:flex;align-items:center;gap:14px;font:700 1.9rem/1.1 var(--head);margin-bottom:18px}
.msec h3 svg{width:34px;height:34px;padding:7px;border-radius:12px;background:rgba(224,166,74,.12);stroke:var(--acc);fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.items{display:grid;grid-template-columns:1fr 1fr;gap:6px 40px}@media(max-width:780px){.items{grid-template-columns:1fr}}
.it{padding:14px 0;border-bottom:1px dashed var(--line)}
.it .row{display:flex;align-items:baseline;gap:10px}.it b{font:700 1.08rem/1.3 var(--body)}
.it .dots{flex:1;border-bottom:2px dotted rgba(246,234,214,.18);transform:translateY(-4px);min-width:16px}
.it .pr{font:700 1.08rem/1 var(--head);color:var(--acc);white-space:nowrap}
.it p{color:var(--soft);font-size:.95rem;margin-top:3px}
.tg{display:inline-block;font:700 .66rem/1 var(--body);letter-spacing:.1em;text-transform:uppercase;padding:4px 7px;border-radius:6px;margin-left:6px;vertical-align:2px}
.tg.pop{background:rgba(224,166,74,.16);color:var(--acc)}.tg.spicy{background:rgba(200,69,47,.18);color:#FF8A70}.tg.veg{background:rgba(124,195,110,.14);color:#9AD58E}
.empty{color:var(--soft);padding:30px 0;text-align:center}
.mnote{color:var(--soft);font-size:.92rem;border-left:3px solid var(--acc);padding-left:14px}
/* story */
.story{display:grid;grid-template-columns:1fr 1fr;gap:40px;align-items:center}@media(max-width:860px){.story{grid-template-columns:1fr}}
.duke{position:relative;border-radius:30px;padding:46px 40px;background:radial-gradient(circle at 20% 0%,rgba(224,166,74,.2),transparent 60%),linear-gradient(160deg,#3A2416,#1F130D);border:1px solid rgba(224,166,74,.25);overflow:hidden}
.duke q{display:block;font:italic 700 clamp(1.6rem,3vw,2.3rem)/1.25 var(--head);quotes:"\201C" "\201D"}
.duke small{display:block;margin-top:16px;color:var(--soft);font-size:.95rem}
.duke svg.hat{position:absolute;right:-20px;bottom:-26px;width:220px;opacity:.12;fill:var(--acc)}
.feats{display:grid;grid-template-columns:1fr 1fr;gap:14px}@media(max-width:520px){.feats{grid-template-columns:1fr}}
.feat{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:22px}
.feat svg{width:28px;height:28px;stroke:var(--acc);fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;margin-bottom:10px}.feat b{display:block;font-size:1.1rem;margin-bottom:4px}.feat span{color:var(--soft);font-size:.97rem}
/* gallery */
.gal{display:grid;grid-template-columns:2fr 1fr 1fr;grid-template-rows:1fr 1fr;gap:14px;height:clamp(320px,40vw,480px)}
.gal .ph:first-child{grid-row:span 2}.gal .ph:nth-child(4){grid-column:span 2}
@media(max-width:700px){.gal{grid-template-columns:1fr 1fr;grid-template-rows:repeat(3,150px);height:auto}.gal .ph:first-child{grid-column:span 2;grid-row:auto}}
.ph{position:relative;border-radius:var(--r);overflow:hidden;display:grid;place-items:center;align-content:center;gap:10px;color:var(--soft);font-weight:600;font-size:.92rem;background:linear-gradient(135deg,var(--panel2),var(--panel));border:1px solid var(--line)}
.ph::before{content:"";position:absolute;inset:0;background:repeating-linear-gradient(45deg,transparent 0 14px,rgba(224,166,74,.05) 14px 15px)}
.ph svg{position:relative;width:44px;height:44px;stroke:var(--acc);fill:none;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round;opacity:.8}.ph span{position:relative}
/* visit */
.visit{display:grid;grid-template-columns:1fr 1fr;gap:18px}@media(max-width:900px){.visit{grid-template-columns:1fr}}
.vbox{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:30px}
.lbl{display:flex;align-items:center;gap:8px;font-size:.76rem;font-weight:700;letter-spacing:.18em;text-transform:uppercase;color:var(--soft);margin-bottom:6px}.lbl .ic{color:var(--acc);width:16px;height:16px}
.bigt{font:700 1.4rem/1.3 var(--body);margin-bottom:20px}.bigt a{text-decoration:none}
table.hrs{border-collapse:collapse;width:100%;margin-bottom:18px}table.hrs td{padding:8px 0;border-bottom:1px solid var(--line)}table.hrs td+td{text-align:right;font-weight:600}
table.hrs tr.today td{color:var(--acc);font-weight:700}
.map{position:relative;min-height:380px;border-radius:var(--r);overflow:hidden;border:1px solid var(--line);background:var(--panel2)}
.map iframe{position:absolute;inset:0;width:100%;height:100%;border:0;filter:sepia(.25) saturate(.9)}
.mapc{position:absolute;inset:0;display:grid;place-items:center;align-content:center;gap:14px;text-align:center;padding:20px;background:radial-gradient(circle at 50% 45%,rgba(224,166,74,.18),transparent 60%),repeating-linear-gradient(0deg,transparent 0 38px,var(--line) 38px 39px),repeating-linear-gradient(90deg,transparent 0 38px,var(--line) 38px 39px)}
.mapc small{color:var(--soft);font-size:.82rem}
.tools{display:grid;grid-template-columns:auto 1fr;gap:22px;align-items:center}@media(max-width:560px){.tools{grid-template-columns:1fr;justify-items:center;text-align:center}}
.qr svg{width:136px;height:136px;border-radius:14px;display:block;background:#fff;padding:6px}
.band{position:relative;overflow:hidden;text-align:center;border-radius:34px;padding:70px 22px;background:linear-gradient(120deg,#7A1E1A,#3D0F0D);border:1px solid rgba(224,166,74,.3)}
.band::before{content:"";position:absolute;width:560px;height:560px;left:-140px;top:-300px;border-radius:50%;background:radial-gradient(closest-side,rgba(224,166,74,.4),transparent);animation:drift 12s ease-in-out infinite alternate}
.band>*{position:relative}@keyframes drift{to{transform:translate(180px,90px)}}
.band h2{font-family:var(--west);font-weight:400;letter-spacing:.04em}
.band a.num{font:700 clamp(2.2rem,6vw,3.8rem)/1 var(--body);text-decoration:none;color:var(--acc);display:inline-block;margin-top:8px}
.band p{color:var(--soft);margin-top:12px}
footer{padding:44px 0 120px;color:var(--soft);font-size:.95rem;border-top:1px solid var(--line);margin-top:60px}footer .wrap{display:flex;flex-wrap:wrap;gap:10px 24px;justify-content:space-between}
.dock{position:fixed;left:10px;right:10px;bottom:calc(10px + env(safe-area-inset-bottom));display:none;gap:8px;z-index:18}
.dock a{flex:1;display:flex;align-items:center;justify-content:center;gap:8px;text-decoration:none;font-weight:700;font-size:1.05rem;padding:15px;border-radius:16px;background:var(--acc);color:var(--on);box-shadow:0 12px 30px -10px rgba(0,0,0,.7)}
.dock a+a{background:var(--panel);color:var(--ink);border:1px solid var(--line)}
@media(max-width:760px){.dock{display:flex}section{padding:66px 0}.mbar{top:69px}}
.rv{opacity:0;transform:translateY(26px);transition:opacity .8s cubic-bezier(.2,.8,.2,1) var(--d,0ms),transform .8s cubic-bezier(.2,.8,.2,1) var(--d,0ms)}.rv.in{opacity:1;transform:none}
.toast{position:fixed;left:50%;bottom:96px;transform:translateX(-50%) translateY(20px);background:var(--ink);color:var(--bg);padding:12px 20px;border-radius:999px;font-weight:600;opacity:0;transition:.3s;z-index:40;pointer-events:none}.toast.on{opacity:1;transform:translateX(-50%)}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}.rv{opacity:1;transform:none}}
html.rm *,html.rm *::before,html.rm *::after{animation:none!important;transition:none!important}html.rm .rv{opacity:1;transform:none}
html.hc{--bg:#000;--panel:#0a0a0a;--panel2:#161616;--ink:#fff;--soft:#f0f0f0;--line:#fff;--acc:#FFD400;--acc2:#FFD400;--on:#000}html.hc body::before,html.hc body::after{display:none}html.hc a{text-decoration:underline}
html.dys body{letter-spacing:.04em;word-spacing:.14em;line-height:1.9}html.dys h1,html.dys h2,html.dys h3{font-family:Verdana,Arial,sans-serif;letter-spacing:0}
'''

ld = {"@context": "https://schema.org", "@type": "Restaurant", "name": "Safire Restaurant & Lounge", "telephone": "+1-928-333-4512",
      "servesCuisine": ["American", "Mexican", "Steakhouse"], "priceRange": "$$",
      "address": {"@type": "PostalAddress", "streetAddress": "411 E Main St", "addressLocality": "Springerville", "addressRegion": "AZ", "postalCode": "85938", "addressCountry": "US"},
      "openingHoursSpecification": [{"@type": "OpeningHoursSpecification", "dayOfWeek": d, "opens": f"{o//60:02d}:{o%60:02d}", "closes": f"{c//60:02d}:{c%60:02d}"}
                                    for d, (o, c) in zip(["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"], HOURS)]}

def fmt(m):
    h, mi = divmod(m, 60); ap = "am" if h < 12 else "pm"; h = h % 12 or 12
    return f"{h}:{mi:02d} {ap}" if mi else f"{h} {ap}"

days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
hours_rows = "".join(f'<tr data-d="{i}"><td>{d}</td><td>{fmt(o)} – {fmt(c)}</td></tr>' for i, (d, (o, c)) in enumerate(zip(days, HOURS)))

HAT = '<svg class="hat" viewBox="0 0 200 100" aria-hidden="true"><path d="M10 78c30 14 150 14 180 0-8-8-30-10-40-10-4-30-14-50-30-50-8 0-12 8-20 8s-12-8-20-8c-16 0-26 20-30 50-10 0-32 2-40 10z"/></svg>'

ribbon_items = ["Breakfast all morning", "Hand cut steaks", "Green chile everything", "Salad bar", "Live music", "The Lounge", "Since the Duke rode through", "Seven days a week"]
ribbon = "".join(f"<span>{x}</span><i>✦</i>" for x in ribbon_items)

page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<!-- pxd2-v2 -->
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex, nofollow">
<title>Safire Restaurant & Lounge · Springerville, Arizona</title>
<meta name="description" content="Safire Restaurant & Lounge on Main Street in Springerville, AZ. Breakfast, lunch and dinner seven days a week: hand cut steaks, burgers, Mexican plates, salad bar, live music and the Lounge.">
<meta name="theme-color" content="#17100D"><meta name="color-scheme" content="dark">
<meta property="og:title" content="Safire Restaurant & Lounge"><meta property="og:description" content="Breakfast, lunch and dinner on Main Street, Springerville. Steaks, green chile, salad bar and the Lounge."><meta property="og:type" content="restaurant">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Cpath d='M18 10h28l12 14-26 32L6 24z' fill='%23A12B24' stroke='%23F4D58D' stroke-width='3'/%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Rye&family=Playfair+Display:ital,wght@0,700;1,700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<script type="application/ld+json">{json.dumps(ld)}</script>
<style>{CSS}</style></head>
<body>
<a class="skip" href="#main">Skip to content</a>
<div class="prog" aria-hidden="true"></div>
<div class="concept">Concept design by PXD2 for Safire Restaurant. Not the business's official website. <b>Black Friday sale: $250 one time, lifetime hosting, live the same day. First 100 customers only. Add online ordering for $1,500.</b> <a href="tel:+19284576404" style="color:inherit;font-weight:700;margin-left:6px">Want this site? Call PXD2 at 928-457-6404</a></div>
<header><div class="wrap">
 <a class="logo" href="#main">{GEM}<span><b>SAFIRE</b><small>Restaurant & Lounge · Springerville</small></span></a>
 <nav class="main" aria-label="Sections"><a href="#meals">Today</a><a href="#menu">Menu</a><a href="#story">Our story</a><a href="#photos">Photos</a><a href="#visit">Visit</a></nav>
 <a class="pill hdr-call" href="tel:{TEL}">{sv("phone")}{PHONE}</a>
 <button class="abtn" type="button" id="pxa-open" aria-haspopup="dialog" aria-controls="pxa" aria-label="Accessibility and voice options">{sv("access")}</button>
</div></header>
<main id="main" tabindex="-1">
<div class="hero"><div class="wrap">
 <div class="rv in">
  <span class="status" id="status" role="status"><i></i><span>Checking hours…</span></span>
  <span class="eyb">Main Street · Springerville, Arizona</span>
  <h1>SAFIRE<span>Restaurant &amp; Lounge</span></h1>
  <p class="tag">Breakfast, lunch and dinner seven days a week. Hand cut steaks, green chile plates and burgers off the grill, a salad bar, live music, and the Lounge when the day is done.</p>
  <div class="acts">
   <a class="btn b1" href="tel:{TEL}">{sv("phone")}Call {PHONE}</a>
   <a class="btn b2" href="#menu">{sv("fork")}See the menu</a>
   <a class="btn b3" href="{e(MAPS)}" target="_blank" rel="noopener">{sv("pin")}Directions</a>
  </div>
  <div class="facts"><span>{sv("clock")}Open 7 days</span><span>{sv("leaf")}Salad bar</span><span>{sv("tone")}Live music</span><span>{sv("bag")}Takeout</span><span>{sv("access")}Wheelchair accessible</span></div>
 </div>
 <div class="artbox rv in" style="--d:120ms">{HERO}</div>
</div></div>
<div class="ribbon" aria-hidden="true"><div>{ribbon}{ribbon}</div><div>{ribbon}{ribbon}</div></div>

<section id="meals"><div class="wrap">
 <p class="kick rv">Morning to night</p>
 <h2 class="rv">Three square meals, <em>one Main Street table.</em></h2>
 <p class="lede rv">Locals start the day here and travelers on the 60 end it here. Here is what people order most.</p>
 <div class="trio">
  <article class="meal rv"><div class="big-ic">{sv("sun","x")}</div><h3>Breakfast</h3><p>Ranch-hand portions, green chile on everything, coffee that keeps coming.</p>
   <ul><li>Smothered Breakfast Burrito<span>$9.99</span></li><li>Farmhouse Breakfast<span>$9.99</span></li><li>Chicken Fried Steak &amp; Eggs<span>$11.99</span></li></ul></article>
  <article class="meal rv" style="--d:90ms"><div class="big-ic">{sv("burger","x")}</div><h3>Lunch</h3><p>Burgers off the flat-top, Mexican plates, sandwiches and the salad bar.</p>
   <ul><li>Jack Daniel's Burger<span>$14.99</span></li><li>Taco Plate<span>$12.99</span></li><li>Soup &amp; Salad<span>$11.99</span></li></ul></article>
  <article class="meal rv" style="--d:180ms"><div class="big-ic">{sv("steak","x")}</div><h3>Dinner</h3><p>Hand cut steaks, shrimp and salmon, country dinners, then a nightcap in the Lounge.</p>
   <ul><li>14 oz Ribeye<span>$27.99</span></li><li>Steak &amp; Shrimp<span>$25.99</span></li><li>Steak &amp; Enchiladas<span>$19.99</span></li></ul></article>
 </div>
</div></section>

<section id="menu" style="padding-top:0"><div class="wrap">
 <p class="kick rv">The full menu</p>
 <h2 class="rv">Pull up a chair.</h2>
 <div class="mbar">
  <div class="tabs" role="tablist" aria-label="Menu sections" id="tabs"></div>
  <div class="mtools">
   <label class="search">{sv("spark")}<span class="pxa-live" style="position:absolute;left:-9999px">Search the menu</span><input id="q" type="search" placeholder="Search: green chile, ribeye, omelet…" aria-label="Search the menu"></label>
   <button class="chip" type="button" data-f="pop" aria-pressed="false">★ Favorites</button>
   <button class="chip" type="button" data-f="spicy" aria-pressed="false">🌶 Green chile & spicy</button>
   <button class="chip" type="button" data-f="veg" aria-pressed="false">Meatless</button>
  </div>
 </div>
 <div id="mlist" aria-live="polite"></div>
 <p class="mnote">Prices are from Safire's last posted menu and can change. Call {PHONE} to confirm, ask about today's specials, or place a takeout order.</p>
</div></section>

<section id="story" style="padding-top:0"><div class="wrap story">
 <div class="duke rv"><q>Folks around here will tell you the Duke himself ate here, back when he came through for the 26 Bar Ranch.</q><small>A Springerville legend, as told by our regulars.</small>{HAT}</div>
 <div>
  <p class="kick rv">Our story</p>
  <h2 class="rv">Rustic, western, <em>and always on.</em></h2>
  <p class="lede rv">Safire has served Round Valley for years from 411 E Main Street. Come for the food, stay for the music, and finish the night in the Lounge.</p>
  <div class="feats">
   <div class="feat rv">{sv("leaf","x")}<b>Salad bar</b><span>Fresh and stocked, alongside any meal.</span></div>
   <div class="feat rv" style="--d:70ms">{sv("tone","x")}<b>Live music</b><span>Local players on the Safire stage.</span></div>
   <div class="feat rv" style="--d:140ms">{sv("star","x")}<b>The Lounge</b><span>A full bar inside for a drink after dinner.</span></div>
   <div class="feat rv" style="--d:210ms">{sv("bag","x")}<b>Takeout</b><span>Call it in and we'll have it ready.</span></div>
  </div>
 </div>
</div></section>

<section id="photos" style="padding-top:0"><div class="wrap">
 <p class="kick rv">Photos</p><h2 class="rv">See it for yourself.</h2>
 <div class="gal rv">
  <div class="ph">{sv("steak","x")}<span>Ribeye on the plate</span></div>
  <div class="ph">{sv("home","x")}<span>The dining room</span></div>
  <div class="ph">{sv("star","x")}<span>The Lounge</span></div>
  <div class="ph">{sv("sun","x")}<span>Breakfast spread</span></div>
 </div>
 <p class="mnote" style="margin-top:18px">Safire's own photos go here. Send them to PXD2 and we'll put them in.</p>
</div></section>

<section id="visit" style="padding-top:0"><div class="wrap">
 <p class="kick rv">Visit</p><h2 class="rv">Find us on Main Street.</h2>
 <div class="visit">
  <div class="vbox rv">
   <p class="lbl">{sv("pin")}Address</p><p class="bigt">411 E Main St<br>Springerville, AZ 85938</p>
   <p class="lbl">{sv("phone")}Phone</p><p class="bigt"><a href="tel:{TEL}">{PHONE}</a></p>
   <p class="lbl">{sv("clock")}Hours</p><table class="hrs" id="hrs">{hours_rows}</table>
   <div class="tools"><div class="qr" title="Scan with a phone camera">{QR}</div>
    <div><div class="acts" style="margin-top:0"><a class="btn b1" href="{e(MAPS)}" target="_blank" rel="noopener">{sv("pin")}Directions</a><button class="btn b2" type="button" data-share>{sv("share")}Share</button><button class="btn b3" type="button" data-vcard>{sv("card")}Save contact</button></div>
    <p class="mnote" style="margin-top:12px;border:0;padding:0">Scan the code with a phone camera to open this page.</p></div></div>
  </div>
  <div class="map rv" style="--d:100ms" data-src="{EMBED}"><div class="mapc"><svg viewBox="0 0 64 64" width="64" height="64" aria-hidden="true">{GEM[GEM.index('>')+1:GEM.rindex('</svg>')]}</svg><button class="btn b1" type="button" data-map>{sv("pin")}Show the map</button><small>The map loads from Google only when you tap.</small></div></div>
 </div>
</div></section>

<section style="padding-top:0"><div class="wrap"><div class="band rv"><h2>Hungry yet?</h2><a class="num" href="tel:{TEL}">{PHONE}</a><p>Safire Restaurant &amp; Lounge · 411 E Main St · Springerville, Arizona</p></div></div></section>
</main>
<footer><div class="wrap"><span>Safire Restaurant &amp; Lounge · 411 E Main St, Springerville, AZ 85938 · {PHONE}</span><span>Built for everyone: voice control, read aloud and sound cues. Tap {sv("access")} at the top.</span></div></footer>
<div class="dock"><a href="tel:{TEL}">{sv("phone")}Call</a><a href="{e(MAPS)}" target="_blank" rel="noopener">{sv("pin")}Directions</a></div>
<div class="toast" role="status" aria-live="polite"></div>
<script>
window.PXD_V={{"n":"Safire Restaurant & Lounge","tel":"+19283334512","adr":"411 E Main St, Springerville, AZ 85938","email":""}};
var MENU={menu_json},ICO={icon_json},HOURS={json.dumps(HOURS)};
(function(){{
var pr=document.querySelector('.prog'),hd=document.querySelector('header');
function sc(){{var h=document.documentElement,m=h.scrollHeight-h.clientHeight;pr.style.width=(m>0?h.scrollTop/m*100:0)+'%';hd.classList.toggle('up',h.scrollTop>10)}}
addEventListener('scroll',sc,{{passive:true}});sc();
var io='IntersectionObserver' in window?new IntersectionObserver(function(es){{es.forEach(function(x){{if(x.isIntersecting){{x.target.classList.add('in');io.unobserve(x.target)}}}})}},{{rootMargin:'0px 0px -8% 0px'}}):null;
function watch(r){{(r||document).querySelectorAll('.rv:not(.in)').forEach(function(el){{io?io.observe(el):el.classList.add('in')}})}}watch();
var links=[].slice.call(document.querySelectorAll('nav.main a'));
if(io)links.forEach(function(a){{var s=document.querySelector(a.getAttribute('href'));if(!s)return;new IntersectionObserver(function(es){{es.forEach(function(x){{if(x.isIntersecting)links.forEach(function(l){{l.classList.toggle('on',l===a)}})}})}},{{rootMargin:'-45% 0px -50% 0px'}}).observe(s)}});
var t=document.querySelector('.toast');window.pxToast=function(m){{t.textContent=m;t.classList.add('on');clearTimeout(t._h);t._h=setTimeout(function(){{t.classList.remove('on')}},2600)}};
/* open now - Arizona time (UTC-7, no DST) */
function azNow(){{var d=new Date(Date.now()+d0());return d}}function d0(){{return (new Date().getTimezoneOffset()-420)*60000}}
function fmt(m){{var h=Math.floor(m/60),mi=m%60,ap=h<12?'am':'pm';h=h%12||12;return h+(mi?':'+('0'+mi).slice(-2):'')+' '+ap}}
function status(){{var n=azNow(),day=n.getDay(),mins=n.getHours()*60+n.getMinutes(),h=HOURS[day],el=document.getElementById('status'),txt;
 if(mins>=h[0]&&mins<h[1]){{el.classList.remove('closed');txt='<b>Open now</b> · until '+fmt(h[1])}}
 else{{el.classList.add('closed');var nd=mins<h[0]?day:(day+1)%7;txt='<b>Closed</b> · opens '+(nd===day?'today':'tomorrow')+' at '+fmt(HOURS[nd][0])}}
 el.querySelector('span').innerHTML=txt;var r=document.querySelector('#hrs tr[data-d="'+day+'"]');document.querySelectorAll('#hrs tr').forEach(function(x){{x.classList.toggle('today',x===r)}})}}
status();setInterval(status,60000);
/* menu */
var tabs=document.getElementById('tabs'),list=document.getElementById('mlist'),q=document.getElementById('q'),cur='all',filt=null;
function svg(i){{return '<svg viewBox="0 0 24 24" aria-hidden="true">'+ICO[i]+'</svg>'}}
function esc(s){{return s.replace(/[&<>"]/g,function(c){{return {{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]}})}}
var all=[{{s:'Everything',i:'spark'}}].concat(MENU);
tabs.innerHTML=all.map(function(m,k){{return '<button class="tab" role="tab" type="button" aria-selected="'+(k===0)+'" data-k="'+(k?m.s:'all')+'">'+svg(m.i)+esc(m.s)+'</button>'}}).join('');
var LBL={{pop:'Favorite',spicy:'Green chile',veg:'Meatless'}};
function draw(){{var term=q.value.trim().toLowerCase(),out='',n=0;
 MENU.forEach(function(sec){{if(cur!=='all'&&sec.s!==cur)return;
  var its=sec.items.filter(function(it){{return (!filt||it.t.indexOf(filt)>-1)&&(!term||(it.n+' '+it.d+' '+sec.s).toLowerCase().indexOf(term)>-1)}});
  if(!its.length)return;n+=its.length;
  out+='<div class="msec"><h3>'+svg(sec.i)+esc(sec.s)+'</h3><div class="items">'+its.map(function(it){{
   return '<div class="it"><div class="row"><b>'+esc(it.n)+it.t.map(function(x){{return x?'<span class="tg '+x+'">'+LBL[x]+'</span>':''}}).join('')+'</b><span class="dots"></span><span class="pr">$'+it.p+'</span></div>'+(it.d?'<p>'+esc(it.d)+'</p>':'')+'</div>'}}).join('')+'</div></div>'}});
 list.innerHTML=out||'<p class="empty">Nothing matches that. Try “steak”, “burrito” or “green chile”, or call us. We probably make it.</p>'}}
tabs.addEventListener('click',function(e){{var b=e.target.closest('.tab');if(!b)return;cur=b.getAttribute('data-k');tabs.querySelectorAll('.tab').forEach(function(x){{x.setAttribute('aria-selected',x===b)}});b.scrollIntoView({{inline:'center',block:'nearest',behavior:'smooth'}});draw();var top=document.getElementById('menu').getBoundingClientRect().top+scrollY-70;if(scrollY>top+200)scrollTo({{top:top,behavior:'smooth'}})}});
q.addEventListener('input',draw);
document.querySelectorAll('.chip[data-f]').forEach(function(c){{c.addEventListener('click',function(){{var f=c.getAttribute('data-f');filt=filt===f?null:f;document.querySelectorAll('.chip[data-f]').forEach(function(x){{x.setAttribute('aria-pressed',x.getAttribute('data-f')===filt)}});draw()}})}});
draw();
document.querySelectorAll('[data-map]').forEach(function(b){{b.addEventListener('click',function(){{var m=b.closest('.map'),f=document.createElement('iframe');f.src=m.getAttribute('data-src');f.title='Map to Safire Restaurant';f.loading='lazy';f.referrerPolicy='no-referrer-when-downgrade';m.innerHTML='';m.appendChild(f)}})}});
document.querySelectorAll('[data-share]').forEach(function(b){{b.addEventListener('click',function(){{var u=location.href;if(navigator.share){{navigator.share({{title:'Safire Restaurant & Lounge',url:u}}).catch(function(){{}})}}else if(navigator.clipboard){{navigator.clipboard.writeText(u).then(function(){{pxToast('Link copied')}})}}}})}});
document.querySelectorAll('[data-vcard]').forEach(function(b){{b.addEventListener('click',function(){{var v=PXD_V,c=['BEGIN:VCARD','VERSION:3.0','FN:'+v.n,'ORG:'+v.n,'TEL;TYPE=WORK,VOICE:'+v.tel,'ADR;TYPE=WORK:;;411 E Main St;Springerville;AZ;85938;US','URL:'+location.href,'END:VCARD'].join('\\r\\n');var a=document.createElement('a');a.href=URL.createObjectURL(new Blob([c],{{type:'text/vcard'}}));a.download='Safire-Restaurant.vcf';document.body.appendChild(a);a.click();a.remove();pxToast('Contact saved')}})}});
}})();
</script>
{v2.ACCESS}
</body></html>
'''
page = page.replace('<svg class="x"', '<svg class="x"')
OUT.write_text(page, encoding="utf-8")
print("wrote", OUT, len(page))
