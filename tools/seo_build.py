"""PXD Names for Google: one indexable page per .pxd name, a sitemap and robots.txt.

Chrome and Firefox turn a typed  mikevanceauto.pxd  into a Google search. For that search to land on the site,
Google needs a page whose address, title and heading are the .pxd name. This builds:

  /n/<name>/      "<name>.pxd · <title>": the site itself opens below the PXD bar (local sites), or a card
                  linking out (names that point at another website)
  /sitemap.xml    every indexable page, for Google Search Console
  /robots.txt     allow all, sitemap link

Concept sites (status "concept": mockups for shops that haven't signed) get noindex, the same rule their own
pages already carry, so a mockup never shows up in Google as if it were the shop's official site. When a shop
signs, change its status (minter: Change) and the next build indexes it.

    python tools/seo_build.py          (the minter runs this after every change)
"""
import datetime, html, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://pxd2.github.io"
MARK = "<!-- pxd2-seo:generated -->"


def page(name, e):
    title = e.get("title") or name
    fq = f"{name}.pxd"
    to = e.get("to") or "/"
    local = to.startswith("/")
    concept = e.get("status") == "concept"
    t, h = html.escape(f"{fq} · {title}"), html.escape(title)
    desc = html.escape(f"{fq} is {title} on the .pxd web. Open it here, or type {fq} in any browser with PXD Web.")
    robots = '<meta name="robots" content="noindex, nofollow">' if concept else '<meta name="robots" content="index, follow">'
    ld = json.dumps({"@context": "https://schema.org", "@type": "WebPage", "name": f"{fq} · {title}", "url": f"{BASE}/n/{name}/",
                     "alternateName": [fq, f"{name}.pxd2", f"pxd://{name}"], "isPartOf": {"@type": "WebSite", "name": "PXD Browser", "url": BASE + "/"}})
    if local:
        body = f'<iframe src="{html.escape(to, quote=True)}" title="{h}" allow="fullscreen; xr-spatial-tracking; clipboard-write; autoplay"></iframe>'
    else:
        host = re.sub(r"^https?://", "", to).split("/")[0]
        body = (f'<div class="card"><p>{html.escape(fq)} points to {html.escape(host)}.</p>'
                f'<a class="go" href="{html.escape(to, quote=True)}" rel="noopener">Open {html.escape(host)}</a></div>')
    return f"""<!doctype html>{MARK}
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t}</title>
<meta name="description" content="{desc}">
{robots}
<link rel="canonical" href="{BASE}/n/{name}/">
<meta property="og:title" content="{t}"><meta property="og:description" content="{desc}"><meta property="og:url" content="{BASE}/n/{name}/">
<meta property="og:image" content="{BASE}/og.jpg">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="search" type="application/opensearchdescription+xml" title="PXD" href="/opensearch.xml">
<script type="application/ld+json">{ld}</script>
<style>
html,body{{margin:0;height:100%;background:#0b0b0a;color:#ece4cf;font:15px/1.4 "Segoe UI",system-ui,sans-serif}}
.bar{{display:flex;align-items:center;gap:12px;padding:8px 14px;background:#121110;border-bottom:1px solid #2e2a24;flex-wrap:wrap}}
.mark{{font:900 19px/1 Impact,"Arial Narrow",sans-serif;color:#ece4cf;text-decoration:none}}.mark b{{color:#d0302f;font-weight:inherit}}
h1{{margin:0;font:600 15px Consolas,monospace;color:#c9a46a}}h1 span{{color:#a39a88;font:400 14px "Segoe UI",system-ui,sans-serif;margin-left:8px}}
.bar a.b{{margin-left:auto;color:#a39a88;font-size:13px;text-decoration:none;border:1px solid #2e2a24;border-radius:999px;padding:4px 12px}}
.wrap{{display:grid;grid-template-rows:auto 1fr;height:100dvh}}iframe{{width:100%;height:100%;border:0;background:#fff}}
.card{{max-width:560px;margin:12vh auto;text-align:center;padding:20px}}.go{{display:inline-block;background:#d0302f;color:#fff;padding:10px 18px;border-radius:8px;text-decoration:none;font-weight:700}}
</style></head><body><div class="wrap">
<div class="bar"><a class="mark" href="/">PX<b>D</b></a><h1>{html.escape(fq)}<span>{h}</span></h1><a class="b" href="/#{html.escape(fq, quote=True)}">Open in PXD Browser</a></div>
{body}
</div></body></html>
"""


class _Text(__import__("html.parser").parser.HTMLParser):
    """Title, description, headings and readable text of a page (scripts, styles and nav skipped)."""
    def __init__(self):
        super().__init__(); self.title = ""; self.desc = ""; self.heads = []; self.text = []; self._skip = 0; self._in = None

    def handle_starttag(self, tag, a):
        a = dict(a)
        if tag in ("script", "style", "noscript", "svg", "nav", "template"):
            self._skip += 1
        elif tag == "meta" and (a.get("name") or a.get("property") or "").lower() in ("description", "og:description") and not self.desc:
            self.desc = (a.get("content") or "").strip()
        elif tag in ("title", "h1", "h2", "h3"):
            self._in = tag

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg", "nav", "template") and self._skip:
            self._skip -= 1
        if tag == self._in:
            self._in = None

    def handle_data(self, d):
        if self._skip:
            return
        d = " ".join(d.split())
        if not d:
            return
        if self._in == "title":
            self.title += d
        elif self._in in ("h1", "h2", "h3"):
            self.heads.append(d)
        else:
            self.text.append(d)


def page_text(path):
    f = os.path.join(ROOT, path.lstrip("/"))
    if os.path.isdir(f):
        f = os.path.join(f, "index.html")
    if not os.path.isfile(f) or not f.endswith((".html", ".htm")):
        return None
    p = _Text()
    try:
        p.feed(open(f, encoding="utf-8", errors="replace").read())
    except Exception:  # noqa: BLE001
        return None
    return p


def build_search(names):
    """PXD's own search index: what every .pxd site actually says, rebuilt on every publish (no crawler, no waiting)."""
    docs = []
    for k, e in sorted(names.items()):
        if "." in k:
            continue
        doc = {"n": k, "t": e.get("title") or k, "g": e.get("group") or ""}
        if e.get("status") == "concept":
            doc["c"] = 1
        to = e.get("to") or ""
        p = page_text(to) if to.startswith("/") and not e.get("host") else None
        if p:
            doc["d"] = p.desc[:300]
            doc["h"] = list(dict.fromkeys(p.heads))[:24]
            body = " ".join(p.text)
            doc["x"] = body[:2400]
        elif not to.startswith("/"):
            doc["d"] = "Opens " + re.sub(r"^https?://", "", to).split("/")[0]
        docs.append(doc)
    out = {"v": 1, "built": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "docs": docs}
    open(os.path.join(ROOT, "search-index.json"), "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    return len(docs)


def main():
    reg = json.load(open(os.path.join(ROOT, "names.json"), encoding="utf-8"))
    names = reg["names"]
    nd = os.path.join(ROOT, "n")
    os.makedirs(nd, exist_ok=True)
    keep = set()
    for name, e in sorted(names.items()):
        if "." in name:
            continue
        d = os.path.join(nd, name); os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(page(name, e)); keep.add(name)
    for d in os.listdir(nd):                         # a released name's page goes with it (only pages this script made)
        f = os.path.join(nd, d, "index.html")
        if d not in keep and os.path.isfile(f) and MARK in open(f, encoding="utf-8").read(200):
            os.remove(f); os.rmdir(os.path.join(nd, d))
    today = datetime.date.today().isoformat()
    urls = [(BASE + "/", "1.0"), (BASE + "/names/", "0.8"), (BASE + "/vr/pxdweb/", "0.7"), (BASE + "/display/", "0.6")]
    seen = {u for u, _ in urls}
    for name, e in sorted(names.items()):
        if "." in name or e.get("status") == "concept":
            continue
        for u, pr in ((f"{BASE}/n/{name}/", "0.7"),) + (((BASE + e["to"], "0.5"),) if e.get("to", "").startswith("/") else ()):
            if u not in seen:
                seen.add(u); urls.append((u, pr))
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sm += [f"  <url><loc>{html.escape(u)}</loc><lastmod>{today}</lastmod><priority>{p}</priority></url>" for u, p in urls]
    sm.append("</urlset>")
    open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8").write("\n".join(sm) + "\n")
    open(os.path.join(ROOT, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\nDisallow: /tools/\nDisallow: /names/certs/\n\nSitemap: {BASE}/sitemap.xml\n")
    n_search = build_search(names)
    n_idx = sum(1 for k, e in names.items() if "." not in k and e.get("status") != "concept")
    print(f"seo: {len(keep)} name pages in /n/ ({n_idx} indexable, {len(keep) - n_idx} concept kept out of Google) · sitemap {len(urls)} URLs · PXD search index {n_search} sites")


if __name__ == "__main__":
    main()
