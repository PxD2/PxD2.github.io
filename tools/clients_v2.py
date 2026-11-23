#!/usr/bin/env python3
"""PXD2 client concept sites, v2 renderer.

Reads each templated concept page under clients/<slug>/index.html, pulls out the
business facts already on it (name, category, town, phone, address, services,
menu, hours, QR, art), and re-renders it on the v2 design: full motion hero,
click-to-load map, save-contact, share, and the PXD2 access panel (text size,
contrast, read aloud, voice control, sound cues for blind users).

Custom hand-built pages (antique shops, Stanford, 3D rooms) are not re-rendered;
they only get the access panel injected (--inject).

Usage: python3 tools/clients_v2.py [--only slug,slug] [--dry]
"""
import colorsys, html, json, re, sys, pathlib
from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).resolve().parent.parent
import os
CLIENTS = pathlib.Path(os.environ.get("PXD_CLIENTS", ROOT / "clients"))
MARK = "<!-- pxd2-v2 -->"
A11Y_MARK = "<!-- pxd2-access -->"

# ---------------------------------------------------------------- colour

def hx(c):
    c = c.strip().lstrip("#")
    if len(c) == 3: c = "".join(x * 2 for x in c)
    return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))

def tohex(rgb):
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(v * 255))) for v in rgb)

def de_blue(c):
    """Chad: no blue palettes on PXD2 sites. Blue/slate hues move to warm/green."""
    try: r, g, b = hx(c)
    except Exception: return c
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    deg = h * 360
    if 185 <= deg <= 255 and s > 0.08:
        if l < 0.2:            # dark slate backgrounds -> warm charcoal
            return tohex(colorsys.hls_to_rgb(30 / 360, l, min(s, 0.12)))
        if l > 0.85:           # pale blue tints -> warm cream
            return tohex(colorsys.hls_to_rgb(38 / 360, l, min(s, 0.35)))
        # accents -> deep juniper green, same lightness
        return tohex(colorsys.hls_to_rgb(152 / 360, l, min(s, 0.55)))
    return c

def lum(c):
    try: r, g, b = hx(c)
    except Exception: return 0.5
    f = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

def on(c):
    return "#111111" if lum(c) > 0.42 else "#FFFFFF"

# ---------------------------------------------------------------- icons

I = {
 "phone": '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z"/>',
 "pin": '<path d="M12 22s7-6.2 7-12a7 7 0 0 0-14 0c0 5.8 7 12 7 12z"/><circle cx="12" cy="10" r="2.5"/>',
 "card": '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="11" r="2.2"/><path d="M5.5 16.5a3.6 3.6 0 0 1 7 0M14 10h4M14 13h4"/>',
 "share": '<circle cx="18" cy="5" r="2.5"/><circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="19" r="2.5"/><path d="M8.2 10.8l7.6-4.4M8.2 13.2l7.6 4.4"/>',
 "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
 "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>',
 "home": '<path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
 "star": '<path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>',
 "camera": '<path d="M3 8h4l2-3h6l2 3h4v12H3z"/><circle cx="12" cy="13" r="4"/>',
 "check": '<path d="M4 12.5l5 5L20 6.5"/>',
 "chat": '<path d="M4 5h16v11H9l-5 4z"/>',
 "wrench": '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.8-3.8a6 6 0 0 1-7.9 7.9l-6.9 6.9a2.1 2.1 0 0 1-3-3l6.9-6.9a6 6 0 0 1 7.9-7.9z"/>',
 "bolt": '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
 "car": '<path d="M5 17h14v-5l-2-5H7l-2 5z"/><circle cx="8" cy="17" r="2"/><circle cx="16" cy="17" r="2"/><path d="M5 12h14"/>',
 "bug": '<rect x="8" y="7" width="8" height="12" rx="4"/><path d="M12 7V4M8 11H4M8 15H4M16 11h4M16 15h4M9 4l1.5 2M15 4l-1.5 2"/>',
 "leaf": '<path d="M5 19c0-8 5-14 15-15-1 10-7 15-15 15z"/><path d="M5 19l8-8"/>',
 "bag": '<path d="M5 8h14l-1 12H6z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/>',
 "fork": '<path d="M7 3v8a2 2 0 0 0 2 2v8M11 3v8a2 2 0 0 1-2 2M17 3c-2 2-2 6 0 8v10"/>',
 "heart": '<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/>',
 "shield": '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
 "spark": '<path d="M12 2v6M12 16v6M2 12h6M16 12h6M5 5l4 4M15 15l4 4M19 5l-4 4M9 15l-4 4"/>',
 "access": '<circle cx="12" cy="4.5" r="2"/><path d="M5 8.5l7 1.5 7-1.5M12 10v5l-3 6M12 15l3 6"/>',
 "mic": '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
 "speaker": '<path d="M4 9v6h4l5 4V5L8 9z"/><path d="M16 9a4 4 0 0 1 0 6M18.5 6.5a7.5 7.5 0 0 1 0 11"/>',
 "tone": '<path d="M3 12h2l2-6 3 12 3-9 2 5 2-2h4"/>',
}

def svg(name, cls=""):
    return f'<svg class="ic {cls}" viewBox="0 0 24 24" aria-hidden="true">{I[name]}</svg>'

# ---------------------------------------------------------------- category

def group_of(kind):
    k = kind.lower()
    if re.search(r"cafe|coffee|grill|bar|kitchen|food|bbq|smoked|steak|pizza|deli|treat|sweet|soda|donut|fudge|restaurant|bistro", k): return "food"
    if re.search(r"boutique|gift|antique|thrift|market|store|jewel|furniture|apparel|parts|art|craft|handmade|nursery|garden|feed|music|vehicle|motors|print", k): return "shop"
    if re.search(r"hair|salon|barber|wellness|massage|fitness|gym|groom|spa|hydration", k): return "care"
    if re.search(r"real estate|realty|insurance|account|bookkeep|tax|notary|tutor|cpa", k): return "office"
    return "trade"

STEPS = {
 "food":  [("Call ahead", "Phone your order in or ask what's fresh today."), ("Stop by", "Dine in or grab it on your way through town."), ("Enjoy", "Made fresh by people who live here.")],
 "shop":  [("Stop in", "Come browse. New things show up all the time."), ("Find it", "Ask us. If we have it, we'll help you find it."), ("Take it home", "Call ahead and we can set it aside.")],
 "care":  [("Call to book", "Pick a time that works for you."), ("Come in", "Relax. You're in good hands."), ("Leave happy", "Walk out feeling like yourself again.")],
 "office":[("Give us a call", "Tell us what you need and ask anything."), ("Sit down with us", "Straight answers in plain language."), ("Get it handled", "We take it from there and keep you posted.")],
 "trade": [("Call us", "Tell us what's going on. Real people answer."), ("We take a look", "Clear answers and a fair price before work starts."), ("Done right", "Work you won't have to think about again.")],
}
NAV = {"food": "Menu", "shop": "What we carry", "care": "Services", "office": "Services", "trade": "Services"}
CTA = {"food": "Hungry yet?", "shop": "Come see what's new.", "care": "Ready for your next visit?", "office": "Let's get it handled.", "trade": "Need it done right?"}
MARK_ICON = {"food": "fork", "shop": "bag", "care": "heart", "office": "shield", "trade": "wrench"}

def icon_for(kind, g):
    k = kind.lower()
    for pat, ic in ((r"roof|construct|concrete|drywall|fence|cabinet|floor|door|home|cinder|realty|real estate|rental", "home"),
                    (r"electric|energy|propane|fuel|starlink|security", "bolt"),
                    (r"auto|vehicle|motor|detailing|collision|towing|parts", "car"),
                    (r"pest|wildlife", "bug"), (r"farm|ranch|tree|garden|nursery|feed|clean", "leaf")):
        if re.search(pat, k): return ic
    return MARK_ICON[g]

# ---------------------------------------------------------------- parse

def text(el):
    return el.get_text(" ", strip=True) if el else ""

def inner(el):
    return "".join(str(c) for c in el.contents) if el else ""

def parse(path):
    raw = path.read_text(encoding="utf-8")
    soup = BeautifulSoup(raw, "html.parser")
    d = {"slug": path.parent.name}
    style = soup.find("style").string or ""
    root = re.search(r":root\{([^}]*)\}", style).group(1)
    var = dict(re.findall(r"--([a-z0-9]+):\s*([^;]+)", root))
    d["vars"] = {k: v.strip() for k, v in var.items()}
    fl = soup.find("link", href=re.compile("fonts.googleapis.com/css2"))
    d["fonts"] = fl["href"] if fl else ""
    d["title"] = text(soup.title)
    md = soup.find("meta", attrs={"name": "description"})
    d["desc"] = md["content"] if md else ""
    d["concept"] = inner(soup.select_one(".concept"))
    hdr = soup.header
    mark = hdr.select_one(".mark")
    d["mark_svg"] = str(mark.find("svg")) if mark and mark.find("svg") else ""
    d["mark_txt"] = text(mark) if mark and not mark.find("svg") else ""
    brand = hdr.select_one(".brand")
    sm = brand.find("small")
    d["brand_small"] = text(sm)
    if sm: sm.extract()
    d["name"] = text(brand)
    kind = soup.select_one(".kind")
    d["kind"] = text(kind)
    d["h1"] = inner(soup.find("h1")).strip()
    d["tag"] = inner(soup.select_one(".tag")).strip()
    d["stars"] = inner(soup.select_one(".stars")).strip()
    acts = soup.select(".acts a")
    d["call_label"] = text(acts[0]) if acts else ""
    tel = soup.find("a", href=re.compile(r"^tel:\+1(?!9284576404)"))
    d["tel"] = tel["href"] if tel else ""
    d["phone"] = re.sub(r"^tel:\+1(\d{3})(\d{3})(\d{4})$", r"\1-\2-\3", d["tel"])
    mp = soup.find("a", href=re.compile("google.com/maps"))
    d["maps"] = mp["href"] if mp else ""
    art = soup.select_one(".art svg") or soup.select_one(".gauge svg")
    d["art"] = str(art) if art else ""
    gp = soup.select_one(".gauge p")
    d["art_note"] = text(gp)
    qr = soup.select_one("svg.segno")
    d["qr"] = str(qr) if qr else ""
    d["email"] = ""
    em = soup.find("a", href=re.compile("^mailto:"))
    if em: d["email"] = em["href"][7:]
    # sections
    d["cards"], d["menu"], d["why"], d["notes"] = [], [], [], {}
    d["cards_title"] = d["menu_title"] = d["why_title"] = ""
    d["address"] = ""; d["hours"] = ""; d["band"] = ""; d["quote"] = ""
    for sec in soup.find_all("section"):
        h2 = sec.find("h2"); t = text(h2)
        if sec.select_one(".cards"):
            d["cards_title"] = t
            for c in sec.select(".card"):
                ic = c.find("svg")
                d["cards"].append({"svg": inner(ic) if ic else "", "b": inner(c.find("b")), "s": inner(c.find("span"))})
            n = sec.select_one(".note");  d["notes"]["cards"] = inner(n) if n else ""
        elif sec.select_one(".menu"):
            d["menu_title"] = t
            for c in sec.select(".mt"):
                d["menu"].append({"b": inner(c.find("b")), "s": inner(c.find("span"))})
            n = sec.select_one(".note"); d["notes"]["menu"] = inner(n) if n else ""
        elif sec.select_one(".why"):
            d["why_title"] = t
            for c in sec.select(".why > div"):
                sp = c.find("span")
                d["why"].append(inner(sp))
            q = sec.select_one(".quote"); d["quote"] = inner(q) if q else ""
        elif sec.select_one(".visit"):
            for box in sec.select(".vbox"):
                lbls = box.select(".lbl")
                for l in lbls:
                    nxt = l.find_next_sibling()
                    lt = text(l).lower()
                    if lt == "address" and nxt is not None: d["address"] = inner(nxt)
                    if lt == "hours":
                        tb = box.find("table")
                        if tb: d["hours"] = str(tb)
                        elif nxt is not None: d["hours"] = text(nxt)
        elif sec.select_one(".band"):
            d["band"] = text(sec.select_one(".band h2"))
    if not d["address"]:
        d["address"] = html.escape(d["kind"].split("·")[-1].strip())
    return d

# ---------------------------------------------------------------- render

def town_of(d):
    t = d["brand_small"].split("·")[-1].strip() if d["brand_small"] else d["kind"].split("·")[-1].strip()
    t = re.sub(r",\s*(AZ|Arizona)$", "", t).strip()
    return t or "the White Mountains"

def initials(name):
    w = [x for x in re.findall(r"[A-Za-z0-9]+", name) if x.lower() not in ("the", "and", "of", "at", "s")]
    return (w[0][0] + (w[1][0] if len(w) > 1 else "")).upper() if w else "★"

def scene(acc, acc2, panel, icon_paths, town):
    """Layered high-country scene with the trade icon in a medallion (for pages that had no art)."""
    return f'''<svg viewBox="0 0 420 320" role="img" aria-label="{html.escape(town)} illustration">
<defs><linearGradient id="v2sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{acc}" stop-opacity=".28"/><stop offset="1" stop-color="{acc2}" stop-opacity=".08"/></linearGradient></defs>
<rect width="420" height="320" rx="28" fill="url(#v2sky)"/>
<circle class="sun" cx="318" cy="80" r="34" fill="{acc2}" opacity=".6"/>
<path d="M0 250 L70 168 L120 214 L190 128 L262 220 L318 168 L420 250 V320 H0z" fill="{acc}" opacity=".3"/>
<path d="M0 270 L90 214 L160 250 L240 196 L320 248 L420 222 V320 H0z" fill="{acc}" opacity=".55"/>
<g fill="{acc}" opacity=".9"><path d="M44 190 l16 26 h-9 l13 23 h-40 l13 -23 h-9 z"/><path d="M80 206 l12 20 h-7 l10 18 h-30 l10 -18 h-7 z"/><path d="M312 186 l18 28 h-10 l14 25 h-45 l14 -25 h-10 z"/><path d="M286 204 l12 20 h-7 l10 18 h-30 l10 -18 h-7 z"/><path d="M350 210 l10 17 h-6 l8 15 h-25 l8 -15 h-6 z"/></g>
<circle cx="210" cy="150" r="74" fill="{panel}" stroke="{acc}" stroke-width="6"/>
<circle class="spin" cx="210" cy="150" r="62" fill="none" stroke="{acc2}" stroke-width="2" stroke-dasharray="4 6"/>
<g transform="translate(176 116) scale(2.85)" fill="none" stroke="{acc}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{icon_paths}</g>
<text x="210" y="300" text-anchor="middle" font-family="system-ui,sans-serif" font-size="15" letter-spacing="4" font-weight="700" fill="{acc}" opacity=".8">{html.escape(town.upper())} · ARIZONA</text>
</svg>'''

def render(d):
    v = {k: de_blue(x) if x.startswith("#") else x for k, x in d["vars"].items()}
    bg = v.get("bg", "#F6EFE6"); ink = v.get("ink", "#222"); acc = v.get("acc", "#B5562D"); acc2 = v.get("acc2", acc)
    dark = lum(bg) < 0.2
    panel = v.get("panel", bg)
    panel2 = v.get("panel2", f"color-mix(in srgb,{panel} 80%,{acc} 20%)")
    line = v.get("line", f"color-mix(in srgb,{ink} 14%,transparent)")
    soft = v.get("soft", f"color-mix(in srgb,{ink} 65%,{bg})")
    head = v.get("head", "Georgia,serif"); body = v.get("body", "system-ui,sans-serif")
    acc_on = on(acc)
    g = group_of(d["kind"] or d["brand_small"])
    town = town_of(d)
    name = d["name"]; e = html.escape
    nm = e(name)
    phone = d["phone"]; tel = d["tel"]; maps = d["maps"]
    h1 = d["h1"] or nm
    if "<em>" not in h1 and "<br" not in h1:
        h1 = f'{h1}<br><em>{e(town)}, AZ</em>' if len(name) < 26 else f'<span class="long">{h1}</span>'
    kind = d["kind"] or f"{d['brand_small']}"
    tag = d["tag"] or f"Locally owned in {e(town)}."
    cards = d["cards"]
    for c in cards:
        if not c["svg"]: c["svg"] = I[icon_for(d["kind"] + " " + d["brand_small"], g)]
    mark_html = d["mark_svg"] or f'<span>{e(d["mark_txt"] or initials(name))}</span>'
    art = d["art"] or scene(acc, acc2, panel, I[icon_for(d["kind"] + " " + d["brand_small"], g)], town)
    art = re.sub(r"#[0-9A-Fa-f]{6}\b", lambda m: de_blue(m.group(0)), art)
    art = art.replace("<svg ", '<svg class="hero-art" ', 1)
    steps = STEPS[g]
    has_menu = bool(d["menu"])
    nav = [("services", NAV[g] if not has_menu else "What we serve")]
    if has_menu: nav.append(("menu", "Menu"))
    nav += [("photos", "Photos"), ("visit", "Visit")]
    addr_txt = BeautifulSoup(d["address"], "html.parser").get_text(", ", strip=True)
    q = f"{name} {addr_txt}"
    embed = "https://www.google.com/maps?output=embed&q=" + re.sub(r"\s+", "+", html.escape(q, quote=True))
    hours = d["hours"] or "Call for today's hours"
    hours_html = hours if hours.startswith("<table") else f'<p class="big">{e(hours)}</p>'
    marquee = " ".join(f'<span>{BeautifulSoup(c["b"], "html.parser").get_text()}</span><i>✦</i>' for c in cards) or f"<span>{nm}</span><i>✦</i>"
    ld = {"@context": "https://schema.org", "@type": "LocalBusiness", "name": name,
          "telephone": "+1-" + phone if phone else None,
          "address": {"@type": "PostalAddress", "streetAddress": addr_txt.split(",")[0] if "," in addr_txt else "", "addressLocality": town, "addressRegion": "AZ", "addressCountry": "US"}}
    if d["email"]: ld["email"] = d["email"]
    ld = {k: x for k, x in ld.items() if x}
    vcard = {"n": name, "tel": "+1" + phone.replace("-", "") if phone else "", "adr": addr_txt, "town": town, "email": d["email"]}

    def card_html(i, c):
        return f'<article class="card rv" style="--d:{i*60}ms"><div class="ci"><svg viewBox="0 0 24 24" aria-hidden="true">{c["svg"]}</svg></div><span class="num">{i+1:02d}</span><h3>{c["b"]}</h3><p>{c["s"]}</p></article>'

    out = []
    w = out.append
    w(f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
{MARK}
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex, nofollow">
<title>{e(d["title"])}</title>
<meta name="description" content="{e(d["desc"])}">
<meta name="theme-color" content="{bg}">
<meta name="color-scheme" content="{'dark' if dark else 'light'}">
<meta property="og:title" content="{nm}"><meta property="og:description" content="{e(d['desc'])}"><meta property="og:type" content="website">
<link rel="icon" href="data:image/svg+xml,{html.escape("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><rect width='64' height='64' rx='16' fill='"+acc.replace('#','%23')+"'/><text x='32' y='42' font-size='28' font-family='Arial' font-weight='700' text-anchor='middle' fill='"+acc_on.replace('#','%23')+"'>"+e(initials(name))+"</text></svg>")}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{e(d["fonts"])}" rel="stylesheet">
<script type="application/ld+json">{json.dumps(ld)}</script>
<style>
:root{{--bg:{bg};--panel:{panel};--panel2:{panel2};--ink:{ink};--soft:{soft};--acc:{acc};--acc2:{acc2};--on:{acc_on};--line:{line};--head:{head};--body:{body};--fs:1;--r:22px;--glow:color-mix(in srgb,var(--acc) 35%,transparent)}}
*{{box-sizing:border-box;margin:0;padding:0}}
html{{scroll-behavior:smooth;scroll-padding-top:90px;font-size:calc(100% * var(--fs))}}
body{{background:var(--bg);color:var(--ink);font:400 1.125rem/1.65 var(--body);-webkit-font-smoothing:antialiased;overflow-x:hidden}}
body::before{{content:"";position:fixed;inset:0;pointer-events:none;z-index:-1;background:radial-gradient(60vw 50vw at 85% -10%,color-mix(in srgb,var(--acc) 16%,transparent),transparent 70%),radial-gradient(50vw 40vw at -10% 30%,color-mix(in srgb,var(--acc2) 12%,transparent),transparent 70%)}}
a{{color:inherit}}:focus-visible{{outline:3px solid var(--acc2);outline-offset:3px;border-radius:6px}}
.ic{{width:1.15em;height:1.15em;fill:none;stroke:currentColor;stroke-width:2.1;stroke-linecap:round;stroke-linejoin:round;flex:none}}
.skip{{position:absolute;left:-999px;top:8px;background:var(--acc);color:var(--on);padding:10px 16px;border-radius:10px;z-index:99}}.skip:focus{{left:8px}}
.concept{{background:#0d0d0d;color:#d8d8d8;font:13px/1.45 system-ui,sans-serif;text-align:center;padding:8px 16px}}.concept b{{color:#fff}}
.prog{{position:fixed;top:0;left:0;height:3px;width:0;background:linear-gradient(90deg,var(--acc),var(--acc2));z-index:20}}
.wrap{{max-width:1180px;margin:0 auto;padding:0 22px}}
header{{position:sticky;top:0;z-index:12;background:color-mix(in srgb,var(--bg) 82%,transparent);backdrop-filter:saturate(1.4) blur(14px);-webkit-backdrop-filter:saturate(1.4) blur(14px);border-bottom:1px solid var(--line);transition:box-shadow .3s}}
header.up{{box-shadow:0 10px 30px -18px rgba(0,0,0,.45)}}
header .wrap{{display:flex;align-items:center;gap:14px;padding-top:12px;padding-bottom:12px}}
.mark{{width:48px;height:48px;border-radius:14px;background:linear-gradient(140deg,var(--acc),color-mix(in srgb,var(--acc) 60%,#000));color:var(--on);display:grid;place-items:center;flex:none;font:700 18px/1 var(--body);box-shadow:0 8px 20px -10px var(--glow)}}
.mark svg{{width:28px;height:28px;fill:none;stroke:currentColor;stroke-width:3;stroke-linecap:round;stroke-linejoin:round}}
.brand{{font:700 1.3rem/1.05 var(--head);text-decoration:none}}.brand small{{display:block;font:600 .72rem/1.3 var(--body);letter-spacing:.16em;color:var(--soft);text-transform:uppercase;margin-top:4px}}
nav.main{{margin-left:auto;display:flex;gap:4px;font-weight:600;font-size:.95rem}}
nav.main a{{text-decoration:none;color:var(--soft);padding:8px 14px;border-radius:999px;transition:.2s}}nav.main a:hover,nav.main a.on{{color:var(--ink);background:var(--panel2)}}
.pill{{display:inline-flex;align-items:center;gap:8px;text-decoration:none;font-weight:700;background:var(--acc);color:var(--on);padding:11px 18px;border-radius:999px;white-space:nowrap;border:0;font-size:1rem;cursor:pointer;font-family:inherit}}
.abtn{{width:46px;height:46px;border-radius:50%;border:1px solid var(--line);background:var(--panel);color:var(--ink);display:grid;place-items:center;cursor:pointer;flex:none}}.abtn .ic{{width:24px;height:24px}}
@media(max-width:940px){{nav.main{{display:none}}.hdr-call{{margin-left:auto}}}}
@media(max-width:560px){{.hdr-call{{display:none}}.abtn{{margin-left:auto}}.brand small{{letter-spacing:.08em}}}}
.hero{{position:relative}}.hero .wrap{{padding-top:64px;padding-bottom:72px;display:grid;grid-template-columns:1.12fr .98fr;gap:48px;align-items:center}}
@media(max-width:880px){{.hero .wrap{{grid-template-columns:1fr;padding-top:38px;gap:34px}}}}
.kind{{display:inline-flex;align-items:center;gap:10px;font-weight:700;font-size:.8rem;letter-spacing:.16em;text-transform:uppercase;color:var(--acc);background:color-mix(in srgb,var(--acc) 10%,transparent);padding:7px 14px 7px 10px;border-radius:999px;border:1px solid color-mix(in srgb,var(--acc) 25%,transparent)}}
.kind i{{width:8px;height:8px;border-radius:50%;background:var(--acc2);box-shadow:0 0 0 0 var(--acc2);animation:ping 2.4s infinite}}
@keyframes ping{{0%{{box-shadow:0 0 0 0 color-mix(in srgb,var(--acc2) 60%,transparent)}}80%,100%{{box-shadow:0 0 0 10px transparent}}}}
h1{{font:700 clamp(2.9rem,7.2vw,5.6rem)/.98 var(--head);margin:20px 0 20px;letter-spacing:-.015em;text-wrap:balance}}
h1 .long{{font-size:.72em;display:block}}
.hero .wrap>*{{min-width:0}}@media(max-width:640px){{h1 em{{white-space:normal!important}}h1{{overflow-wrap:break-word}}}}
h1 em{{font-style:normal;color:var(--acc);position:relative;white-space:nowrap}}
h1 em::after{{content:"";position:absolute;left:0;right:0;bottom:.04em;height:.12em;background:var(--acc2);opacity:.45;border-radius:4px;transform-origin:left;transform:scaleX(0);animation:draw 1s .5s cubic-bezier(.2,.8,.2,1) forwards;z-index:-1}}
@keyframes draw{{to{{transform:scaleX(1)}}}}
.tag{{font-size:clamp(1.15rem,2.2vw,1.4rem);color:var(--soft);max-width:31em;text-wrap:pretty}}
.stars{{margin-top:16px;color:var(--soft)}}.stars b{{color:var(--acc2);letter-spacing:2px}}
.acts{{display:flex;flex-wrap:wrap;gap:12px;margin-top:30px}}
.btn{{display:inline-flex;align-items:center;gap:10px;text-decoration:none;font-weight:700;font-size:1.05rem;padding:15px 24px;border-radius:999px;transition:transform .2s,box-shadow .2s,background .2s;border:0;cursor:pointer;font-family:inherit;color:var(--ink)}}
.btn .ic{{width:20px;height:20px}}
.b1{{background:var(--acc);color:var(--on);box-shadow:0 14px 30px -14px var(--glow)}}.b1:hover{{transform:translateY(-2px);box-shadow:0 20px 40px -16px var(--glow)}}
.b2{{box-shadow:inset 0 0 0 2px var(--line);background:var(--panel)}}.b2:hover{{box-shadow:inset 0 0 0 2px var(--acc);transform:translateY(-2px)}}
.b3{{background:transparent;color:var(--soft);padding-left:10px;padding-right:10px}}.b3:hover{{color:var(--ink)}}
.chips{{display:flex;flex-wrap:wrap;gap:10px 20px;margin-top:28px;color:var(--soft);font-size:.95rem;font-weight:600}}
.chips span{{display:inline-flex;align-items:center;gap:8px}}.chips .ic{{color:var(--acc);width:18px;height:18px}}
.artbox{{position:relative}}
.artbox::before{{content:"";position:absolute;inset:8% 6%;background:radial-gradient(closest-side,var(--glow),transparent);filter:blur(30px);z-index:-1}}
.hero-art{{width:100%;height:auto;display:block;filter:drop-shadow(0 34px 44px rgba(0,0,0,.18));animation:float 7s ease-in-out infinite}}
.hero-art .spin{{transform-origin:210px 150px;animation:spin 30s linear infinite}}.hero-art .sun{{animation:pulse 5s ease-in-out infinite}}
@keyframes float{{50%{{transform:translateY(-10px)}}}}@keyframes spin{{to{{transform:rotate(360deg)}}}}@keyframes pulse{{50%{{opacity:.85}}}}
.artnote{{text-align:center;color:var(--soft);font-weight:600;margin-top:10px}}
.ticker{{border-block:1px solid var(--line);background:var(--panel);overflow:hidden;white-space:nowrap;padding:16px 0;font:700 clamp(1.05rem,2vw,1.35rem)/1 var(--head)}}
.ticker div{{display:inline-flex;gap:28px;padding-right:28px;animation:tick 38s linear infinite}}.ticker i{{color:var(--acc);font-style:normal}}
@keyframes tick{{to{{transform:translateX(-50%)}}}}
section{{padding:88px 0}}
.eyebrow{{font-weight:700;font-size:.8rem;letter-spacing:.18em;text-transform:uppercase;color:var(--acc);margin-bottom:10px;display:block}}
h2{{font:700 clamp(2.1rem,4.6vw,3.4rem)/1.04 var(--head);margin-bottom:14px;letter-spacing:-.01em;text-wrap:balance}}
.lede{{color:var(--soft);max-width:36em;margin-bottom:38px;font-size:1.15rem}}
.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}}@media(max-width:900px){{.cards{{grid-template-columns:1fr 1fr}}}}@media(max-width:600px){{.cards{{grid-template-columns:1fr}}}}
.card{{position:relative;background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:28px 26px 26px;transition:transform .3s cubic-bezier(.2,.8,.2,1),box-shadow .3s,border-color .3s;overflow:hidden}}
.card::after{{content:"";position:absolute;inset:auto -40% -60% auto;width:220px;height:220px;border-radius:50%;background:radial-gradient(closest-side,var(--glow),transparent);opacity:0;transition:.4s}}
.card:hover{{transform:translateY(-6px);box-shadow:0 30px 50px -30px rgba(0,0,0,.45);border-color:color-mix(in srgb,var(--acc) 45%,var(--line))}}.card:hover::after{{opacity:1}}
.ci{{width:54px;height:54px;border-radius:16px;background:var(--panel2);display:grid;place-items:center;margin-bottom:18px}}
.ci svg{{width:28px;height:28px;stroke:var(--acc);fill:none;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round}}
.num{{position:absolute;top:22px;right:24px;font:700 .85rem/1 var(--body);color:var(--soft);opacity:.6;letter-spacing:.1em}}
.card h3{{font:700 1.3rem/1.25 var(--body);margin-bottom:6px}}.card p{{color:var(--soft);font-size:1.02rem}}
.note{{color:var(--soft);font-size:.95rem;margin-top:18px}}
.menu{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}@media(max-width:700px){{.menu{{grid-template-columns:1fr 1fr}}}}
@media(max-width:430px){{.menu{{grid-template-columns:1fr}}}}
.mt{{min-width:0;background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:20px 22px;display:flex;justify-content:space-between;align-items:center;gap:12px;transition:.25s}}
.mt:hover{{border-color:var(--acc)}}.mt b{{display:block;font:700 1.25rem/1.2 var(--head)}}.mt span{{color:var(--soft);font-size:.88rem}}
.mt em{{font-style:normal;width:34px;height:34px;border-radius:50%;background:var(--panel2);color:var(--acc);display:grid;place-items:center;flex:none;font-weight:700}}
.steps{{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;counter-reset:s}}@media(max-width:820px){{.steps{{grid-template-columns:1fr}}}}
.step{{position:relative;padding:30px 26px;border-radius:var(--r);background:linear-gradient(160deg,var(--panel2),var(--panel));border:1px solid var(--line)}}
.step::before{{counter-increment:s;content:counter(s);display:grid;place-items:center;width:46px;height:46px;border-radius:50%;background:var(--acc);color:var(--on);font:700 1.2rem/1 var(--head);margin-bottom:16px;box-shadow:0 10px 24px -12px var(--glow)}}
.step h3{{font:700 1.3rem/1.2 var(--body);margin-bottom:6px}}.step p{{color:var(--soft)}}
.why{{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}}@media(max-width:820px){{.why{{grid-template-columns:1fr}}}}
.why div{{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:22px 24px;display:flex;gap:16px;align-items:flex-start}}
.why .ic{{width:30px;height:30px;padding:6px;border-radius:50%;background:var(--acc);color:var(--on);stroke-width:2.6}}
.quote{{margin-top:24px;font:italic 1.25rem/1.5 var(--head);color:var(--soft);border-left:4px solid var(--acc);padding-left:18px}}
.gal{{display:grid;grid-template-columns:2fr 1fr 1fr;grid-template-rows:1fr 1fr;gap:14px;height:clamp(320px,40vw,460px)}}
.gal .ph:first-child{{grid-row:span 2}}.gal .ph:nth-child(4){{grid-column:span 2}}
@media(max-width:700px){{.gal{{grid-template-columns:1fr 1fr;grid-template-rows:repeat(3,150px);height:auto}}.gal .ph:first-child{{grid-column:span 2;grid-row:auto}}.gal .ph:nth-child(4){{grid-column:span 2}}}}
.ph{{position:relative;border-radius:var(--r);overflow:hidden;display:grid;place-items:center;align-content:center;gap:10px;color:var(--soft);font-size:.92rem;font-weight:600;background:linear-gradient(135deg,var(--panel2),var(--panel));border:1px solid var(--line)}}
.ph::before{{content:"";position:absolute;inset:0;background:repeating-linear-gradient(45deg,transparent 0 14px,color-mix(in srgb,var(--acc) 6%,transparent) 14px 15px)}}
.ph svg{{position:relative;width:46px;height:46px;stroke:var(--acc);fill:none;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round;opacity:.8}}.ph span{{position:relative}}
.revs{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}@media(max-width:820px){{.revs{{grid-template-columns:1fr}}}}
.rev{{border:2px dashed var(--line);border-radius:var(--r);padding:24px;color:var(--soft)}}.rev .st{{color:var(--acc2);letter-spacing:3px;font-size:1.1rem;opacity:.55}}.rev p{{margin:10px 0 14px}}.rev b{{color:var(--ink);font-size:.95rem}}
.visit{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}@media(max-width:900px){{.visit{{grid-template-columns:1fr}}}}
.vbox{{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:28px}}
.lbl{{display:flex;align-items:center;gap:8px;font-size:.78rem;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:var(--soft);margin-bottom:6px}}.lbl .ic{{color:var(--acc);width:16px;height:16px}}
.big{{font:700 1.4rem/1.3 var(--body);margin-bottom:20px}}.big a{{text-decoration:none}}
.vbox table{{border-collapse:collapse;width:100%;margin-bottom:12px}}.vbox td{{padding:7px 0;border-bottom:1px solid var(--line)}}.vbox td+td{{text-align:right;font-weight:600}}
.map{{position:relative;min-height:340px;border-radius:var(--r);overflow:hidden;border:1px solid var(--line);background:var(--panel2)}}
.map iframe{{position:absolute;inset:0;width:100%;height:100%;border:0}}
.map .mapc{{position:absolute;inset:0;display:grid;place-items:center;align-content:center;gap:14px;text-align:center;padding:20px;background:radial-gradient(circle at 50% 45%,color-mix(in srgb,var(--acc) 18%,transparent),transparent 60%),repeating-linear-gradient(0deg,transparent 0 38px,var(--line) 38px 39px),repeating-linear-gradient(90deg,transparent 0 38px,var(--line) 38px 39px)}}
.map .mapc .pin{{width:56px;height:56px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);background:var(--acc);display:grid;place-items:center;box-shadow:0 14px 30px -10px var(--glow);animation:bob 2.6s ease-in-out infinite}}
.map .mapc .pin i{{width:18px;height:18px;border-radius:50%;background:var(--on)}}@keyframes bob{{50%{{transform:rotate(-45deg) translate(4px,-4px)}}}}
.map small{{color:var(--soft);font-size:.82rem}}
.tools{{display:grid;grid-template-columns:auto 1fr;gap:22px;align-items:center;margin-top:18px}}@media(max-width:560px){{.tools{{grid-template-columns:1fr;text-align:center;justify-items:center}}}}
.qr svg{{width:140px;height:140px;border-radius:14px;display:block;background:#fff;padding:6px}}
.tools .acts{{margin-top:0}}
.band{{position:relative;overflow:hidden;background:linear-gradient(120deg,var(--acc),color-mix(in srgb,var(--acc) 62%,#000));color:var(--on);text-align:center;border-radius:32px;padding:66px 22px}}
.band::before{{content:"";position:absolute;width:520px;height:520px;left:-120px;top:-260px;border-radius:50%;background:radial-gradient(closest-side,color-mix(in srgb,var(--acc2) 45%,transparent),transparent);animation:drift 12s ease-in-out infinite alternate}}
.band::after{{content:"";position:absolute;width:420px;height:420px;right:-120px;bottom:-240px;border-radius:50%;background:radial-gradient(closest-side,rgba(255,255,255,.18),transparent);animation:drift 15s ease-in-out infinite alternate-reverse}}
@keyframes drift{{to{{transform:translate(160px,80px)}}}}
.band>*{{position:relative}}.band h2{{margin-bottom:12px}}.band a.num-big{{font:700 clamp(2.1rem,6vw,3.6rem)/1 var(--body);text-decoration:none;display:inline-block;margin-top:6px}}
.band p{{opacity:.85;margin-top:12px}}
footer{{padding:40px 0 120px;color:var(--soft);font-size:.95rem;border-top:1px solid var(--line);margin-top:60px}}footer .wrap{{display:flex;flex-wrap:wrap;gap:10px 24px;justify-content:space-between}}
.dock{{position:fixed;left:10px;right:10px;bottom:calc(10px + env(safe-area-inset-bottom));display:none;gap:8px;z-index:14}}
.dock a{{flex:1;display:flex;align-items:center;justify-content:center;gap:8px;text-decoration:none;font-weight:700;font-size:1.05rem;padding:15px;border-radius:16px;background:var(--acc);color:var(--on);box-shadow:0 12px 30px -10px rgba(0,0,0,.55)}}
.dock a+a{{background:var(--panel);color:var(--ink);border:1px solid var(--line)}}
@media(max-width:760px){{.dock{{display:flex}}section{{padding:64px 0}}}}
.rv{{opacity:0;transform:translateY(26px);transition:opacity .8s cubic-bezier(.2,.8,.2,1) var(--d,0ms),transform .8s cubic-bezier(.2,.8,.2,1) var(--d,0ms)}}.rv.in{{opacity:1;transform:none}}
.toast{{position:fixed;left:50%;bottom:96px;transform:translateX(-50%) translateY(20px);background:var(--ink);color:var(--bg);padding:12px 20px;border-radius:999px;font-weight:600;opacity:0;transition:.3s;z-index:40;pointer-events:none}}.toast.on{{opacity:1;transform:translateX(-50%)}}
@media (prefers-reduced-motion:reduce){{*,*::before,*::after{{animation:none!important;transition:none!important;scroll-behavior:auto!important}}.rv{{opacity:1;transform:none}}}}
html.rm *,html.rm *::before,html.rm *::after{{animation:none!important;transition:none!important}}html.rm .rv{{opacity:1;transform:none}}
html.hc{{--bg:#000;--panel:#0a0a0a;--panel2:#161616;--ink:#fff;--soft:#f0f0f0;--line:#fff;--acc:#FFD400;--acc2:#FFD400;--on:#000}}html.hc body::before{{display:none}}html.hc a{{text-decoration:underline}}
html.dys body{{letter-spacing:.04em;word-spacing:.14em;line-height:1.9}}html.dys h1,html.dys h2,html.dys h3{{font-family:Verdana,Arial,sans-serif;letter-spacing:0}}
</style></head>
<body>
<a class="skip" href="#main">Skip to content</a>
<div class="prog" aria-hidden="true"></div>
<div class="concept">{d["concept"]}</div>
<header id="top"><div class="wrap"><div class="mark" aria-hidden="true">{mark_html}</div><a class="brand" href="#main">{nm}<small>{e(d["brand_small"] or kind)}</small></a>
<nav class="main" aria-label="Sections">{"".join(f'<a href="#{i}">{t}</a>' for i, t in nav)}</nav>
<a class="pill hdr-call" href="{tel}">{svg("phone")}Call {phone}</a>
<button class="abtn" type="button" id="pxa-open" aria-haspopup="dialog" aria-controls="pxa" aria-label="Accessibility and voice options">{svg("access")}</button></div></header>
<main id="main" tabindex="-1">
<div class="hero"><div class="wrap">
 <div class="rv in">
  <span class="kind"><i></i>{e(kind)}</span>
  <h1>{h1}</h1>
  <p class="tag">{tag}</p>
  {f'<div class="stars">{d["stars"]}</div>' if d["stars"] else ""}
  <div class="acts">
   <a class="btn b1" href="{tel}">{svg("phone")}{e(d["call_label"] or "Call " + phone)}</a>
   <a class="btn b2" href="{e(maps)}" target="_blank" rel="noopener">{svg("pin")}Directions</a>
   <button class="btn b3" type="button" data-vcard>{svg("card")}Save contact</button>
  </div>
  <div class="chips"><span>{svg("home")}Locally owned</span><span>{svg("pin")}{e(town)}, Arizona</span><span>{svg("chat")}Real people answer</span></div>
 </div>
 <div class="artbox rv in" style="--d:120ms">{art}{f'<p class="artnote">{e(d["art_note"])}</p>' if d["art_note"] else ""}</div>
</div></div>
<div class="ticker" aria-hidden="true"><div>{marquee}{marquee}</div><div>{marquee}{marquee}</div></div>
<section id="services"><div class="wrap">
 <span class="eyebrow rv">{e(NAV[g] if not has_menu else "What we serve")}</span>
 <h2 class="rv">{e(d["cards_title"] or "What we do")}</h2>
 <p class="lede rv">Everything {nm} does for {e(town)} and the White Mountains, all in one place.</p>
 <div class="cards">{"".join(card_html(i, c) for i, c in enumerate(cards))}</div>
 {f'<p class="note">{d["notes"].get("cards")}</p>' if d["notes"].get("cards") else ""}
</div></section>''')
    if has_menu:
        w(f'''<section id="menu" style="padding-top:0"><div class="wrap">
 <span class="eyebrow rv">Menu</span><h2 class="rv">{e(d["menu_title"] or "Menu")}</h2>
 <div class="menu">{"".join(f'<div class="mt rv" style="--d:{i*50}ms"><div><b>{m["b"]}</b><span>{m["s"]}</span></div><em aria-hidden="true">→</em></div>' for i, m in enumerate(d["menu"]))}</div>
 {f'<p class="note">{d["notes"].get("menu")}</p>' if d["notes"].get("menu") else ""}
</div></section>''')
    w(f'''<section id="how" style="padding-top:0"><div class="wrap">
 <span class="eyebrow rv">How it works</span><h2 class="rv">Easy as one, two, three.</h2>
 <div class="steps">{"".join(f'<div class="step rv" style="--d:{i*90}ms"><h3>{e(a)}</h3><p>{e(b)}</p></div>' for i, (a, b) in enumerate(steps))}</div>
</div></section>''')
    if d["why"]:
        w(f'''<section style="padding-top:0"><div class="wrap">
 <span class="eyebrow rv">Why us</span><h2 class="rv">{e(d["why_title"])}</h2>
 <div class="why">{"".join(f'<div class="rv" style="--d:{i*60}ms">{svg("check")}<span>{x}</span></div>' for i, x in enumerate(d["why"]))}</div>
 {f'<p class="quote rv">{d["quote"]}</p>' if d["quote"] else ""}
</div></section>''')
    gal_ic = [I[icon_for(d["kind"] + " " + d["brand_small"], g)], I["camera"], I["star"], I["home"]]
    w(f'''<section id="photos" style="padding-top:0"><div class="wrap">
 <span class="eyebrow rv">Photos</span><h2 class="rv">See it for yourself.</h2>
 <div class="gal rv">{"".join(f'<div class="ph"><svg viewBox="0 0 24 24" aria-hidden="true">{x}</svg><span>Your photo here</span></div>' for x in gal_ic)}</div>
 <p class="note">Your own photos go here. Send them over and PXD2 puts them in.</p>
</div></section>
<section id="reviews" style="padding-top:0"><div class="wrap">
 <span class="eyebrow rv">Reviews</span><h2 class="rv">What {e(town)} says.</h2>
 <div class="revs">{"".join(f'<div class="rev rv" style="--d:{i*70}ms"><div class="st" aria-hidden="true">★★★★★</div><p>Your best customer reviews show here, pulled from Google and Facebook.</p><b>Review spot {i+1}</b></div>' for i in range(3))}</div>
</div></section>
<section id="visit" style="padding-top:0"><div class="wrap">
 <span class="eyebrow rv">Visit</span><h2 class="rv">Come see us.</h2>
 <div class="visit">
  <div class="vbox rv">
   <p class="lbl">{svg("pin")}Address</p><p class="big">{d["address"]}</p>
   <p class="lbl">{svg("phone")}Phone</p><p class="big"><a href="{tel}">{phone}</a></p>
   {f'<p class="lbl">{svg("mail")}Email</p><p class="big" style="font-size:1.1rem"><a href="mailto:{e(d["email"])}">{e(d["email"])}</a></p>' if d["email"] else ""}
   <p class="lbl">{svg("clock")}Hours</p>{hours_html}
   <div class="tools">{f'<div class="qr" title="Scan with a phone camera">{d["qr"]}</div>' if d["qr"] else ""}<div><div class="acts"><a class="btn b1" href="{e(maps)}" target="_blank" rel="noopener">{svg("pin")}Open in maps</a><button class="btn b2" type="button" data-share>{svg("share")}Share</button></div><p class="note" style="margin-top:10px">Scan the code with a phone camera to open this page.</p></div></div>
  </div>
  <div class="map rv" style="--d:100ms" data-src="{embed}"><div class="mapc"><div class="pin" aria-hidden="true"><i></i></div><button class="btn b1" type="button" data-map>{svg("pin")}Show the map</button><small>Map loads from Google only when you tap.</small></div></div>
 </div>
</div></section>
<section style="padding-top:0"><div class="wrap"><div class="band rv"><h2>{e(d["band"] or CTA[g])}</h2><a class="num-big" href="{tel}">{phone}</a><p>{nm} · {e(town)}, Arizona</p></div></div></section>
</main>
<footer><div class="wrap"><span>{nm} · {BeautifulSoup(d["address"], "html.parser").get_text(", ", strip=True)} · {phone}</span><span>Built for everyone: voice control, read aloud and sound cues. Tap {svg("access")} up top.</span></div></footer>
<div class="dock"><a href="{tel}">{svg("phone")}Call</a><a href="{e(maps)}" target="_blank" rel="noopener">{svg("pin")}Directions</a></div>
<div class="toast" role="status" aria-live="polite"></div>
<script>window.PXD_V={json.dumps(vcard)};</script>
<script>
(function(){{
var pr=document.querySelector('.prog'),hd=document.querySelector('header');
function sc(){{var h=document.documentElement,m=h.scrollHeight-h.clientHeight;pr.style.width=(m>0?h.scrollTop/m*100:0)+'%';hd.classList.toggle('up',h.scrollTop>10)}}
addEventListener('scroll',sc,{{passive:true}});sc();
var io='IntersectionObserver' in window?new IntersectionObserver(function(es){{es.forEach(function(x){{if(x.isIntersecting){{x.target.classList.add('in');io.unobserve(x.target)}}}})}},{{rootMargin:'0px 0px -8% 0px'}}):null;
document.querySelectorAll('.rv').forEach(function(el){{io?io.observe(el):el.classList.add('in')}});
var links=[].slice.call(document.querySelectorAll('nav.main a'));
if(io)links.forEach(function(a){{var s=document.querySelector(a.getAttribute('href'));if(!s)return;new IntersectionObserver(function(es){{es.forEach(function(x){{if(x.isIntersecting){{links.forEach(function(l){{l.classList.toggle('on',l===a)}})}}}})}},{{rootMargin:'-45% 0px -50% 0px'}}).observe(s)}});
var t=document.querySelector('.toast');window.pxToast=function(m){{t.textContent=m;t.classList.add('on');clearTimeout(t._h);t._h=setTimeout(function(){{t.classList.remove('on')}},2600)}};
document.querySelectorAll('[data-map]').forEach(function(b){{b.addEventListener('click',function(){{var m=b.closest('.map'),f=document.createElement('iframe');f.src=m.getAttribute('data-src');f.title='Map to '+PXD_V.n;f.loading='lazy';f.referrerPolicy='no-referrer-when-downgrade';m.innerHTML='';m.appendChild(f)}})}});
document.querySelectorAll('[data-share]').forEach(function(b){{b.addEventListener('click',function(){{var u=location.href;if(navigator.share){{navigator.share({{title:PXD_V.n,url:u}}).catch(function(){{}})}}else if(navigator.clipboard){{navigator.clipboard.writeText(u).then(function(){{pxToast('Link copied')}})}}}})}});
document.querySelectorAll('[data-vcard]').forEach(function(b){{b.addEventListener('click',function(){{var v=PXD_V,c=['BEGIN:VCARD','VERSION:3.0','FN:'+v.n,'ORG:'+v.n,v.tel?'TEL;TYPE=WORK,VOICE:'+v.tel:'',v.email?'EMAIL:'+v.email:'','ADR;TYPE=WORK:;;'+v.adr.replace(/,/g,'\\\\,')+';;;;','URL:'+location.href,'END:VCARD'].filter(Boolean).join('\\r\\n');var a=document.createElement('a');a.href=URL.createObjectURL(new Blob([c],{{type:'text/vcard'}}));a.download=v.n.replace(/[^a-z0-9]+/gi,'-')+'.vcf';document.body.appendChild(a);a.click();a.remove();pxToast('Contact saved')}})}});
}})();
</script>
''')
    w(ACCESS)
    w("</body></html>\n")
    return "".join(out)

# ---------------------------------------------------------------- access layer (shared)

ACCESS = A11Y_MARK + r'''
<div id="pxa" role="dialog" aria-modal="false" aria-labelledby="pxa-t" hidden>
 <div class="pxa-h"><b id="pxa-t">Make this page work for you</b><button type="button" class="pxa-x" aria-label="Close">×</button></div>
 <div class="pxa-g">
  <button type="button" data-a="bigger" aria-label="Bigger text"><span aria-hidden="true">A+</span>Bigger text</button>
  <button type="button" data-a="smaller" aria-label="Smaller text"><span aria-hidden="true">A−</span>Smaller text</button>
  <button type="button" data-a="hc" aria-pressed="false"><span aria-hidden="true"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 3v18" /><path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor"/></svg></span>High contrast</button>
  <button type="button" data-a="dys" aria-pressed="false"><span aria-hidden="true">Aa</span>Easy reading</button>
  <button type="button" data-a="rm" aria-pressed="false"><span aria-hidden="true"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M9 5v14M15 5v14"/></svg></span>Stop motion</button>
  <button type="button" data-a="read" aria-pressed="false"><span aria-hidden="true"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9v6h4l5 4V5L8 9z"/><path d="M16 9a4 4 0 0 1 0 6M18.5 6.5a7.5 7.5 0 0 1 0 11"/></svg></span>Read page aloud</button>
  <button type="button" data-a="voice" aria-pressed="false"><span aria-hidden="true"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg></span>Voice control</button>
  <button type="button" data-a="tones" aria-pressed="false"><span aria-hidden="true"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12h2l2-6 3 12 3-9 2 5 2-2h4"/></svg></span>Sound cues</button>
 </div>
 <p class="pxa-n" id="pxa-n">Voice: say “call”, “directions”, “menu”, “photos”, “visit”, “read”, “stop”, “bigger” or “top”. Sound cues play a tone as you move: high for links, middle for buttons, low for headings.</p>
</div>
<style>
#pxa{position:fixed;right:14px;top:84px;width:min(380px,calc(100vw - 28px));background:var(--panel,#fff);color:var(--ink,#111);border:1px solid var(--line,#ccc);border-radius:22px;box-shadow:0 30px 80px -20px rgba(0,0,0,.5);z-index:60;padding:18px;font:16px/1.45 system-ui,sans-serif}
#pxa[hidden]{display:none}html.hc #pxa{background:#000!important;color:#fff!important;border-color:#fff!important}html.hc #pxa-fab{background:#FFD400!important;color:#000!important}.pxa-h{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}.pxa-h b{font-size:17px}
.pxa-x{width:36px;height:36px;border-radius:50%;border:1px solid var(--line,#ccc);background:transparent;color:inherit;font-size:22px;cursor:pointer}
.pxa-g{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.pxa-g button{display:flex;align-items:center;gap:10px;text-align:left;padding:12px;border-radius:14px;border:1px solid var(--line,#ccc);background:transparent;color:inherit;font:600 14px/1.2 system-ui,sans-serif;cursor:pointer;min-height:52px}
.pxa-g button span{width:28px;height:28px;border-radius:8px;display:grid;place-items:center;background:color-mix(in srgb,currentColor 16%,transparent);font-weight:800;flex:none}
.pxa-g button[aria-pressed=true]{background:var(--acc,#333);color:var(--on,#fff);border-color:transparent}.pxa-g button[aria-pressed=true] span{background:rgba(255,255,255,.22)}
.pxa-n{font-size:13px;color:var(--soft,#555);margin-top:12px}
.pxa-live{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
.pxa-reading{outline:3px solid var(--acc2,#f90)!important;outline-offset:4px;border-radius:6px;background:color-mix(in srgb,var(--acc2,#f90) 14%,transparent)}
#pxa-fab{position:fixed;right:14px;bottom:calc(84px + env(safe-area-inset-bottom));width:52px;height:52px;border-radius:50%;border:0;background:var(--acc,#333);color:var(--on,#fff);box-shadow:0 12px 30px -10px rgba(0,0,0,.5);cursor:pointer;z-index:15;display:grid;place-items:center}
#pxa-fab svg{width:26px;height:26px;fill:none;stroke:currentColor;stroke-width:2.1;stroke-linecap:round;stroke-linejoin:round}
@media(min-width:761px){#pxa-fab{bottom:20px}}
</style>
<div class="pxa-live" aria-live="assertive" id="pxa-live"></div>
<script>
(function(){
var H=document.documentElement,P=document.getElementById('pxa'),L=document.getElementById('pxa-live');
var S={};try{S=JSON.parse(localStorage.getItem('pxa')||'{}')}catch(e){}
function save(){try{localStorage.setItem('pxa',JSON.stringify(S))}catch(e){}}
function say(m){L.textContent='';setTimeout(function(){L.textContent=m},30);if(window.pxToast)pxToast(m)}
function btn(a){return P.querySelector('[data-a="'+a+'"]')}
function setFs(){H.style.setProperty('--fs',S.fs||1);H.style.fontSize=(S.fs&&S.fs!=1)?(100*S.fs)+'%':''}
function flag(k){H.classList.toggle(k,!!S[k]);var b=btn(k);if(b)b.setAttribute('aria-pressed',!!S[k])}
['hc','dys','rm'].forEach(flag);setFs();
var opener=document.getElementById('pxa-open');
if(!opener){opener=document.createElement('button');opener.id='pxa-fab';opener.type='button';opener.setAttribute('aria-label','Accessibility and voice options');opener.setAttribute('aria-controls','pxa');opener.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="4.5" r="2"/><path d="M5 8.5l7 1.5 7-1.5M12 10v5l-3 6M12 15l3 6"/></svg>';document.body.appendChild(opener)}
function open(v){P.hidden=!v;opener.setAttribute('aria-expanded',v);if(v)P.querySelector('button').focus()}
opener.addEventListener('click',function(){open(P.hidden)});
P.querySelector('.pxa-x').addEventListener('click',function(){open(false);opener.focus()});
document.addEventListener('keydown',function(e){if(e.key==='Escape'&&!P.hidden){open(false);opener.focus()}if(e.altKey&&(e.key==='a'||e.key==='A')){open(P.hidden)}});
/* ---- read aloud ---- */
var synth=window.speechSynthesis,reading=false,q=[],cur=null;
function blocks(){var root=document.querySelector('main')||document.body;return [].slice.call(root.querySelectorAll('h1,h2,h3,p,li,td,.btn,.chips span,.mt b,.big')).filter(function(el){return el.offsetParent!==null&&!el.closest('#pxa,[aria-hidden=true],.ticker')&&el.innerText.trim()})}
function stopRead(){reading=false;if(synth)synth.cancel();if(cur)cur.classList.remove('pxa-reading');cur=null;var b=btn('read');b&&b.setAttribute('aria-pressed','false')}
function next(){if(!reading||!q.length){stopRead();return}if(cur)cur.classList.remove('pxa-reading');cur=q.shift();cur.classList.add('pxa-reading');cur.scrollIntoView({block:'center',behavior:H.classList.contains('rm')?'auto':'smooth'});var u=new SpeechSynthesisUtterance(cur.innerText.replace(/\s+/g,' '));u.rate=S.rate||1;u.lang='en-US';u.onend=next;u.onerror=next;synth.speak(u)}
function read(){if(!synth){say('Read aloud is not supported in this browser');return}stopRead();q=blocks();reading=true;btn('read').setAttribute('aria-pressed','true');next()}
/* ---- sound cues (tone system) ---- */
var ac=null;function tone(f,d){try{ac=ac||new (window.AudioContext||window.webkitAudioContext)();var o=ac.createOscillator(),g=ac.createGain();o.type='sine';o.frequency.value=f;g.gain.setValueAtTime(.0001,ac.currentTime);g.gain.exponentialRampToValueAtTime(.18,ac.currentTime+.02);g.gain.exponentialRampToValueAtTime(.0001,ac.currentTime+(d||.14));o.connect(g).connect(ac.destination);o.start();o.stop(ac.currentTime+(d||.14)+.02)}catch(e){}}
function cue(el){if(!S.tones||!el||!el.tagName)return;var t=el.tagName;if(t==='A'){tone(/^tel:/.test(el.getAttribute('href')||'')?988:880)}else if(t==='BUTTON'){tone(660)}else if(/^H[1-3]$/.test(t)){tone(440,.2)}else if(t==='INPUT'||t==='SELECT'||t==='TEXTAREA'){tone(587)}}
document.addEventListener('focusin',function(e){cue(e.target)});
var lastSec=null;if('IntersectionObserver' in window){var so=new IntersectionObserver(function(es){es.forEach(function(x){if(x.isIntersecting&&S.tones&&x.target!==lastSec){lastSec=x.target;tone(330,.09);setTimeout(function(){tone(494,.12)},110)}})},{rootMargin:'-45% 0px -50% 0px'});document.querySelectorAll('main section,.hero').forEach(function(s){so.observe(s)})}
/* ---- voice control ---- */
var SR=window.SpeechRecognition||window.webkitSpeechRecognition,rec=null,listening=false;
function go(sel){var el=document.querySelector(sel);if(el){el.scrollIntoView({behavior:'smooth'});var h=el.querySelector('h2');if(h){h.setAttribute('tabindex','-1');h.focus({preventScroll:true})}return true}return false}
function cmd(t){t=t.toLowerCase();
 if(/\b(call|phone|ring)\b/.test(t)){var a=document.querySelector('a[href^="tel:"]:not(.concept a)')||document.querySelectorAll('a[href^="tel:"]')[1];if(a){say('Calling');location.href=a.href}return}
 if(/direction|map|navigate|where/.test(t)){var m=document.querySelector('a[href*="google.com/maps"]');if(m){say('Opening directions');window.open(m.href,'_blank')}return}
 if(/\bread\b/.test(t)){read();return}
 if(/\b(stop|quiet|pause|cancel)\b/.test(t)){stopRead();say('Stopped');return}
 if(/bigger|larger|zoom in/.test(t)){act('bigger');return}if(/smaller|zoom out/.test(t)){act('smaller');return}
 if(/contrast/.test(t)){act('hc');return}
 if(/\btop|home|start\b/.test(t)){scrollTo({top:0,behavior:'smooth'});say('Top of page');return}
 if(/bottom|end/.test(t)){scrollTo({top:document.body.scrollHeight,behavior:'smooth'});return}
 if(/down|scroll/.test(t)){scrollBy({top:innerHeight*.8,behavior:'smooth'});return}if(/\bup\b/.test(t)){scrollBy({top:-innerHeight*.8,behavior:'smooth'});return}
 var map={menu:'#menu,#services,#finds',food:'#menu,#services',service:'#services,#finds',carry:'#finds,#services',photo:'#photos,#gallery',picture:'#photos,#gallery',review:'#reviews',visit:'#visit',hour:'#visit',address:'#visit',contact:'#visit',how:'#how'};
 for(var k in map){if(t.indexOf(k)>-1){var ok=map[k].split(',').some(go);say(ok?'Going to '+k:'No '+k+' section on this page');return}}
 say('Heard: '+t+'. Try call, directions, menu, read or stop.')}
function voice(on){if(!SR){say('Voice control needs Chrome, Edge or Safari');return}
 if(!on){listening=false;try{rec&&rec.stop()}catch(e){}btn('voice').setAttribute('aria-pressed','false');return}
 rec=new SR();rec.lang='en-US';rec.continuous=true;rec.interimResults=false;
 rec.onresult=function(e){var r=e.results[e.results.length-1];if(r.isFinal)cmd(r[0].transcript)};
 rec.onend=function(){if(listening)try{rec.start()}catch(e){}};
 rec.onerror=function(e){if(e.error==='not-allowed'){listening=false;btn('voice').setAttribute('aria-pressed','false');say('Microphone was blocked')}};
 listening=true;btn('voice').setAttribute('aria-pressed','true');try{rec.start();say('Listening. Say call, directions, menu, or read.')}catch(e){}}
function act(a){
 if(a==='bigger'){S.fs=Math.min(1.6,Math.round(((S.fs||1)+.1)*10)/10);setFs();say('Text '+Math.round(S.fs*100)+' percent')}
 else if(a==='smaller'){S.fs=Math.max(.9,Math.round(((S.fs||1)-.1)*10)/10);setFs();say('Text '+Math.round(S.fs*100)+' percent')}
 else if(a==='hc'||a==='dys'||a==='rm'){S[a]=!S[a];flag(a);say((btn(a).innerText.replace(/^\S+\s*/,''))+(S[a]?' on':' off'))}
 else if(a==='read'){reading?stopRead():read()}
 else if(a==='voice'){voice(!listening)}
 else if(a==='tones'){S.tones=!S.tones;btn('tones').setAttribute('aria-pressed',!!S.tones);if(S.tones){tone(440,.1);setTimeout(function(){tone(660,.1)},120);setTimeout(function(){tone(880,.14)},240)}say('Sound cues '+(S.tones?'on':'off'))}
 save()}
btn('tones').setAttribute('aria-pressed',!!S.tones);
P.querySelectorAll('[data-a]').forEach(function(b){b.addEventListener('click',function(){act(b.getAttribute('data-a'))})});
})();
</script>
'''

# ---------------------------------------------------------------- inject (custom pages)

def inject(path):
    s = path.read_text(encoding="utf-8")
    if A11Y_MARK in s: s = re.sub(re.escape(A11Y_MARK) + r".*?</script>\n", "", s, flags=re.S)
    extra = ("<style>.skip-pxa{position:absolute;left:-999px;top:8px;z-index:99;background:#111;color:#fff;padding:10px 16px;border-radius:10px}.skip-pxa:focus{left:8px}"
             "html.rm *,html.rm *::before,html.rm *::after{animation:none!important;transition:none!important}"
             "html.hc,html.hc body{background:#000!important;color:#fff!important}html.hc *:not(#pxa):not(#pxa *):not(#pxa-fab){background-color:transparent!important;color:#fff!important;border-color:#fff!important}html.hc a{color:#FFD400!important;text-decoration:underline!important}html.hc img{filter:contrast(1.1)}"
             "html.dys body{letter-spacing:.04em;word-spacing:.14em;line-height:1.9}</style>\n")
    s = s.replace("</body>", extra + ACCESS + "</body>", 1)
    return s

# ---------------------------------------------------------------- main

def templated(s):
    return 'class="mark"' in s and 'class="dock"' in s and 'class="kind"' in s and 'id="finds"' not in s

def main():
    args = sys.argv[1:]
    only = None
    if "--only" in args: only = set(args[args.index("--only") + 1].split(","))
    dry = "--dry" in args
    done, inj, skipped = [], [], []
    for d in sorted(CLIENTS.iterdir()):
        f = d / "index.html"
        if not f.is_file() or d.name.startswith("_") or d.name == "engine": continue
        if only and d.name not in only: continue
        s = f.read_text(encoding="utf-8")
        if MARK in s:
            skipped.append(d.name); continue
        if templated(s):
            try:
                data = parse(f)
                out = render(data)
            except Exception as ex:
                print("FAIL", d.name, ex); continue
            if not dry: f.write_text(out, encoding="utf-8")
            done.append(d.name)
        else:
            if not dry: f.write_text(inject(f), encoding="utf-8")
            inj.append(d.name)
    print(f"rebuilt {len(done)}  access-layer {len(inj)}  already-v2 {len(skipped)}")
    if inj: print("access layer:", ", ".join(inj))

if __name__ == "__main__":
    main()
