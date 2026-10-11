"""PXD Market index: every approved store, by type of store, then region.

Layout, in this repository or in any sub-hub repository (one GitHub org per type scales the same way):
    market/<type>/type.json                      {"name": "Food & drink"}            (optional)
    market/<type>/<region>/region.json           {"name": "Apache County, AZ"}       (optional)
    market/<type>/<region>/<store>.pxdz          the store's signed data
    market/<type>/<region>/<store>.pxdz.sig

    python tools/market/pxd_market.py --authority pxd/authority-demo.json

Writes market/index.json (types), market/<type>/index.json (regions) and
market/<type>/<region>/index.json (stores and items). A store is listed only when its bundle
verifies against a merchant certificate from the PXD authority: that is what "approved" means.
Sealed (private) stores are never listed. The PXD home page searches these indexes on the
buyer's own device; the gateway prices every checkout from the signed bundle, never from them.
"""
import argparse, datetime, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "pxdz"))
import pxdsign, pxdz  # noqa: E402

BASE = "https://raw.githubusercontent.com/PxD2/PxD2.github.io/main/"
TYPE_NAMES = {"eats": "Food & drink", "retail": "Retail", "antiques": "Antiques & vintage", "services": "Services",
              "auto": "Auto", "home": "Home & garden", "games": "Games & hobby"}
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


def meta(path, key, default):
    try:
        return json.load(open(path, encoding="utf-8")).get(key, default)
    except (OSError, ValueError):
        return default


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")[:60] or "item"


def store_entry(path, rel, tid, rid, authority, base):
    ok, rep = pxdsign.verify_bundle(path, authority)
    if not ok:
        bad = next((c for c in rep["checks"] if not c["ok"]), {"check": "unknown"})
        return None, f"{bad['check']} {bad.get('detail', '')}".strip()
    try:
        _, files = pxdz.read(path)
    except SystemExit as e:
        return None, f"not listed: {e}"
    cats = [p for p in files if p.endswith("catalog.json")] or [p for p in files if p.endswith(".json")]
    if not cats:
        return None, "no catalog in bundle"
    cat = json.loads(files[cats[0]])
    cert = json.load(open(path + ".sig"))["cert"]["cert"]
    items = []
    for it in cat.get("items") or cat.get("products") or []:
        if it.get("status") in ("sold", "hidden"):
            continue
        title = it.get("title") or it.get("name") or ""
        items.append({k: v for k, v in {
            "id": it.get("id") or slug(title), "title": title, "price": it.get("price"),
            "category": it.get("category") or "", "description": (it.get("description") or "")[:240],
            "model": bool(it.get("model")), "example": bool(it.get("example"))}.items() if v not in ("", None) or k == "price"})
    stem = os.path.basename(path)[:-5]
    return {"name": stem, "title": cat.get("market") or cat.get("name") or stem, "type": tid, "region": rid,
            "merchant": {"id": cert["merchant"], "name": cert["name"], "expires": cert["expires"]},
            "pxd_pay": bool((cert.get("pay_account") or {}).get("stripe")),
            "crypto": sorted((cert.get("wallets") or {}).keys()),
            "currency": cat.get("currency", "USD"), "tagline": cat.get("tagline", ""),
            "bundle": base + rel, "sig": base + rel + ".sig", "items": items,
            "example": bool(items) and all(i.get("example") for i in items)}, None


def build(market, authority, base):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    top, report = {"format": "pxd-market/1", "built": now, "types": []}, []
    for tid in sorted(os.listdir(market)):
        tdir = os.path.join(market, tid)
        if not (os.path.isdir(tdir) and SLUG.match(tid)):
            continue
        tname = meta(os.path.join(tdir, "type.json"), "name", TYPE_NAMES.get(tid, tid.title()))
        regions = []
        for rid in sorted(os.listdir(tdir)):
            rdir = os.path.join(tdir, rid)
            if not (os.path.isdir(rdir) and SLUG.match(rid)):
                continue
            rname = meta(os.path.join(rdir, "region.json"), "name", rid)
            stores = []
            for f in sorted(os.listdir(rdir)):
                if not f.endswith(".pxdz"):
                    continue
                rel = os.path.relpath(os.path.join(rdir, f), os.path.dirname(market)).replace("\\", "/")
                entry, why = store_entry(os.path.join(rdir, f), rel, tid, rid, authority, base)
                if entry:
                    entry["region_name"], entry["type_name"] = rname, tname
                    stores.append(entry); report.append(f"  listed  {tid}/{rid}/{f}: {entry['merchant']['name']}, {len(entry['items'])} item(s)")
                else:
                    report.append(f"  REFUSED {tid}/{rid}/{f}: {why}")
            if not stores:
                continue
            json.dump({"format": "pxd-market-region/1", "built": now, "type": tid, "region": rid, "name": rname, "stores": stores},
                      open(os.path.join(rdir, "index.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            rel = os.path.relpath(os.path.join(rdir, "index.json"), os.path.dirname(market)).replace("\\", "/")
            regions.append({"id": rid, "name": rname, "stores": len(stores), "items": sum(len(s["items"]) for s in stores), "index": base + rel})
        if not regions:
            continue
        json.dump({"format": "pxd-market-type/1", "built": now, "type": tid, "name": tname, "regions": regions},
                  open(os.path.join(tdir, "index.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        rel = os.path.relpath(os.path.join(tdir, "index.json"), os.path.dirname(market)).replace("\\", "/")
        top["types"].append({"id": tid, "name": tname, "regions": len(regions), "stores": sum(r["stores"] for r in regions),
                             "items": sum(r["items"] for r in regions), "index": base + rel})
    json.dump(top, open(os.path.join(market, "index.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return top, report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--market", default=os.path.join(ROOT, "market"))
    ap.add_argument("--authority", required=True, help="PXD authority PUBLIC record")
    ap.add_argument("--base", default=BASE, help="public address the market folder's parent is served from")
    a = ap.parse_args()
    top, report = build(a.market, a.authority, a.base if a.base.endswith("/") else a.base + "/")
    print("\n".join(report))
    print(f"market/index.json: {len(top['types'])} type(s), {sum(t['stores'] for t in top['types'])} store(s), "
          f"{sum(t['items'] for t in top['types'])} item(s)")
    return 1 if any("REFUSED" in r for r in report) else 0


if __name__ == "__main__":
    sys.exit(main())
