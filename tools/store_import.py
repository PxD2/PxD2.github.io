"""PXD2 Store Import — turn a business's current online store into a PXD2 VR store pitch.

Reads the store's public product catalog the way its own storefront does:
  1. Shopify:      /products.json
  2. WooCommerce:  /wp-json/wc/store/v1/products
  3. Any site:     schema.org Product data (JSON-LD) on the pages you list
It checks robots.txt first, goes slowly, and never logs in or touches checkout.

The result is a PRIVATE pitch preview on your own machine, never published:
    ~/PXD2 Pitches/<slug>/index.html + store.json
Show it to the owner. Publish only after they sign, with their own pay links.

Run on base1:
    python tools/store_import.py https://shop.example.com --name "Example Outfitters"
    python tools/store_import.py https://site.example --pages https://site.example/p/1 https://site.example/p/2
    python tools/store_import.py ... --serve          # opens the preview at http://localhost:8765
"""
import argparse, functools, html, http.server, json, os, re, shutil, sys, threading, time, urllib.request, urllib.robotparser, webbrowser
from urllib.parse import urljoin, urlparse

UA = "PXD2-StoreImport/1.0 (+https://pxd2.github.io/company/)"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.environ.get("PXD2_PITCHES", os.path.join(os.path.expanduser("~"), "PXD2 Pitches"))
MAX = 60
PALETTE = ["#c9a46a", "#6b5a3a", "#4d5a3a", "#9a8a6a", "#a39a88", "#3a3d36", "#8a6a2e"]
SHAPES = ["box", "cylinder", "sphere"]


def allowed(url):
    rp = urllib.robotparser.RobotFileParser(); p = urlparse(url)
    rp.set_url(f"{p.scheme}://{p.netloc}/robots.txt")
    try: rp.read()
    except Exception: return True
    return rp.can_fetch(UA, url)


def get(url, as_json=False):
    if not allowed(url):
        raise PermissionError(f"robots.txt asks us not to read {url}")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json" if as_json else "text/html"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = r.read().decode("utf-8", "replace")
    time.sleep(1.5)  # go easy on their server
    return json.loads(data) if as_json else data


def clean(text, n=280):
    t = re.sub(r"<[^>]+>", " ", html.unescape(text or "")); t = re.sub(r"\s+", " ", t).strip()
    return t[:n] + ("…" if len(t) > n else "")


def shopify(base):
    out, page, seen = [], 1, set()
    while len(out) < MAX and page <= 4:
        d = get(urljoin(base, f"/products.json?limit=50&page={page}"), True)
        items = [p for p in d.get("products", []) if p.get("handle") not in seen]
        if not items: break
        for p in items:
            seen.add(p.get("handle"))
            v = (p.get("variants") or [{}])[0]; img = (p.get("images") or [{}])[0].get("src", "")
            out.append({"name": p.get("title", ""), "price": float(v.get("price") or 0) or None, "description": clean(p.get("body_html")),
                        "image": img, "source": urljoin(base, "/products/" + p.get("handle", ""))})
        page += 1
    return out


def woo(base):
    d = get(urljoin(base, f"/wp-json/wc/store/v1/products?per_page={MAX}"), True)
    out = []
    for p in d:
        pr = p.get("prices", {}); minor = int(pr.get("currency_minor_unit", 2) or 2)
        price = int(pr["price"]) / 10 ** minor if pr.get("price") else None
        out.append({"name": html.unescape(p.get("name", "")), "price": price, "description": clean(p.get("short_description") or p.get("description")),
                    "image": ((p.get("images") or [{}])[0]).get("src", ""), "source": p.get("permalink", "")})
    return out


def jsonld(pages):
    out = []
    for u in pages[:MAX]:
        try: doc = get(u)
        except Exception as e: print("  skip", u, e); continue
        for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', doc, re.S | re.I):
            try: data = json.loads(block.strip())
            except Exception: continue
            stack = data if isinstance(data, list) else [data]
            while stack:
                d = stack.pop()
                if isinstance(d, dict):
                    stack.extend(d.get("@graph", []))
                    if "Product" in (d.get("@type") if isinstance(d.get("@type"), list) else [d.get("@type")]):
                        offer = d.get("offers") or {}; offer = offer[0] if isinstance(offer, list) else offer
                        img = d.get("image"); img = img[0] if isinstance(img, list) else img
                        img = img.get("url") if isinstance(img, dict) else img
                        try: price = float(offer.get("price")) if offer.get("price") not in (None, "") else None
                        except Exception: price = None
                        out.append({"name": d.get("name", ""), "price": price, "description": clean(d.get("description")),
                                    "image": img or "", "source": u, "currency": offer.get("priceCurrency")})
    return out


def build(args):
    base = args.url.rstrip("/") + "/"
    products, how = [], ""
    for label, fn in (("Shopify catalog", lambda: shopify(base)), ("WooCommerce catalog", lambda: woo(base))):
        try:
            products = fn(); how = label
            if products: break
        except Exception:
            products = []
    if not products and args.pages:
        products, how = jsonld(args.pages), "product data on listed pages"
    if not products:
        print("No public catalog found. List product pages with --pages to read their product data."); return 1
    currency = next((p.get("currency") for p in products if p.get("currency")), args.currency)
    slug = re.sub(r"[^a-z0-9]+", "-", (args.name or urlparse(base).netloc).lower()).strip("-")
    folder = os.path.join(OUT, slug); os.makedirs(folder, exist_ok=True)
    store = {
        "name": args.name or urlparse(base).netloc, "tagline": f"VR store preview by PXD2 · rebuilt from their current site",
        "currency": currency or "USD", "contact": "pxd2games@gmail.com", "pitch": True, "source_site": base, "imported_via": how,
        "pay": {}, "wallets": {},
        "products": [dict(name=p["name"], price=p["price"], description=p["description"], image=p["image"], source=p["source"],
                          shape=SHAPES[i % 3], color=PALETTE[i % len(PALETTE)]) for i, p in enumerate(products[:24]) if p["name"]],
    }
    json.dump(store, open(os.path.join(folder, "store.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    page = open(os.path.join(ROOT, "clients", "_template", "index.html"), encoding="utf-8").read()
    eng = os.path.join(folder, "engine"); os.makedirs(eng, exist_ok=True)
    for f in ("vrstore.js", "vrstore.css"):
        shutil.copy(os.path.join(ROOT, "clients", "engine", f), eng)
    page = page.replace("/clients/engine/", "engine/").replace('<script src="/sites.js" defer></script>\n', "").replace('<a class="vs-net" href="/vr/">← PXD VR Net</a>', '<span class="vs-net">PXD2 pitch preview · not published</span>')
    open(os.path.join(folder, "index.html"), "w", encoding="utf-8").write(page)
    print(f"{len(store['products'])} products from {how} → {folder}")
    if args.serve:
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=folder)
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8765), handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        webbrowser.open("http://127.0.0.1:8765/"); print("Preview at http://127.0.0.1:8765/  (Ctrl+C to stop)")
        try:
            while True: time.sleep(1)
        except KeyboardInterrupt: pass
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url"); ap.add_argument("--name"); ap.add_argument("--pages", nargs="*", default=[])
    ap.add_argument("--currency", default="USD"); ap.add_argument("--serve", action="store_true")
    sys.exit(build(ap.parse_args()))
