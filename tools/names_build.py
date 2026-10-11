"""PXD2 Names: build one redirect folder per registered name.

Edit names.json, then run:  python tools/names_build.py
Each name becomes https://pxd2.github.io/<name>/ . Names that collide with an
existing site folder are refused so no real page is ever overwritten.
"""
import json, os, re, html, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARK = "<!-- pxd2-names:generated -->"
reg = json.load(open(os.path.join(ROOT, "names.json"), encoding="utf-8"))

def page(name, entry):
    to = entry["to"]
    title = html.escape(entry.get("title") or name)
    t = html.escape(to, quote=True)
    js = json.dumps(to)
    return f"""<!doctype html>{MARK}
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta http-equiv="refresh" content="0; url={t}">
<link rel="canonical" href="{t}">
<meta property="og:title" content="{title}">
<meta property="og:image" content="https://pxd2.github.io/games/og.jpg">
<script>location.replace({js} + location.hash);</script>
</head><body style="background:#0b0b0a;color:#e8dfc8;font:16px system-ui;padding:24px">
<p>pxd2.github.io/{html.escape(name)} → <a style="color:#c9a46a" href="{t}">{title}</a></p>
</body></html>
"""

ok, refused = [], []
for name, entry in sorted(reg["names"].items()):
    if entry.get("native"):
        continue  # a real site folder: the name is the page itself
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", name):
        refused.append((name, "letters, digits and dashes only")); continue
    d = os.path.join(ROOT, name); f = os.path.join(d, "index.html")
    if os.path.isdir(d) and not (os.path.isfile(f) and MARK in open(f, encoding="utf-8").read(400)):
        refused.append((name, "a real site folder already uses this name")); continue
    os.makedirs(d, exist_ok=True)
    open(f, "w", encoding="utf-8").write(page(name, entry)); ok.append(name)

print("built:", ", ".join(ok) or "none")
for n, why in refused: print(f"refused {n}: {why}", file=sys.stderr)
