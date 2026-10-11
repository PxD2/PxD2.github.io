"""PXD Studio: turn Shop Builder submissions into store worlds (the "game"), on base1.

    python build_store.py watch                       # build every submitted store as it arrives
    python build_store.py list                        # every job and its state
    python build_store.py build <job>                 # build one now
    python build_store.py approve <job> --authority keys/ [--stripe-account acct_...] [--days 365]
    python build_store.py reject <job> --reason "Photos are too dark; please retake the back room"

A build:
  - Panoramas: rotated upright, padded to a full 2:1 sphere if the phone made a partial one, at most 4096 px wide, JPEG.
  - Item photos: at most 1400 px, JPEG. 3D scans (.glb) are checked and kept.
  - world.json (spots, item pins, doorways) + catalog.json (items, prices, contact) + the media, packed into one PXDZ
    store bundle. The owner's browser signs it after approval; nothing is published by the studio itself.
Approval issues the owner's PXD merchant certificate for the key their browser sent (their wallet, if given,
pinned in it). The authority key stays on base1.
Next stage (GPU, not built yet): a Gaussian-splat walk-through from the same photos, added as world.splat.
"""
import argparse, datetime, json, os, re, shutil, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(TOOLS, "pxdz"))
import pxdz, pxdsign  # noqa: E402
from PIL import Image, ImageOps  # noqa: E402

INTAKE = os.path.join(os.path.expanduser("~"), "PXD Gateway", "intake")
MARKET = os.path.join(os.path.dirname(TOOLS), "market")


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")[:60] or "shop"


def region_folder(market, type_, name):
    """Reuse an existing region folder whose region.json has the same name; otherwise a new slug."""
    tdir = os.path.join(market, type_)
    if os.path.isdir(tdir):
        for r in sorted(os.listdir(tdir)):
            try:
                if json.load(open(os.path.join(tdir, r, "region.json"))).get("name", "").strip().lower() == name.strip().lower():
                    return r
            except (OSError, ValueError):
                continue
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60]


def state(d):
    return json.load(open(os.path.join(d, "job.json")))


def set_state(d, **kw):
    st = state(d); st.update(kw, updated=time.strftime("%Y-%m-%dT%H:%M:%S"))
    json.dump(st, open(os.path.join(d, "job.json.tmp"), "w"), indent=1); os.replace(os.path.join(d, "job.json.tmp"), os.path.join(d, "job.json"))
    return st


def pano(src, dst):
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    w, h = im.size
    if abs(w / h - 2) > 0.02:  # partial panorama or plain photo: center it on a full sphere
        W, H = (w, w // 2) if w / h > 2 else (h * 2, h)
        canvas = Image.new("RGB", (W, H), (18, 18, 16)); canvas.paste(im, ((W - w) // 2, (H - h) // 2)); im = canvas
    if im.width > 4096:
        im = im.resize((4096, 2048), Image.LANCZOS)
    im.save(dst, "JPEG", quality=82, optimize=True, progressive=True)


def photo(src, dst):
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    im.thumbnail((1400, 1400), Image.LANCZOS)
    im.save(dst, "JPEG", quality=84, optimize=True, progressive=True)


def build(d):
    req = json.load(open(os.path.join(d, "request.json")))
    set_state(d, state="building", message="")
    files, src = os.path.join(d, "files"), os.path.join(d, "src")
    shutil.rmtree(src, ignore_errors=True)
    for sub in ("pano", "items", "models"):
        os.makedirs(os.path.join(src, sub))
    world = req["world"]
    for s in world["scenes"]:
        out = f"pano/{s['id']}.jpg"
        pano(os.path.join(files, s["image"]), os.path.join(src, out)); s["image"] = out
    items = []
    for it in req["items"]:
        imgs = []
        for n, f in enumerate(it.get("photos") or []):
            out = f"items/{it['id']}-{n + 1}.jpg"; photo(os.path.join(files, f), os.path.join(src, out)); imgs.append(out)
        model = None
        if it.get("model"):
            model = f"models/{it['id']}.glb"; shutil.copy2(os.path.join(files, it["model"]), os.path.join(src, model))
        items.append({k: v for k, v in {"id": it["id"], "title": it["title"], "price": it.get("price"), "description": it.get("description") or "",
                                        "dims_cm": it.get("dims_cm"), "image": imgs[0] if imgs else None, "images": imgs, "model": model,
                                        "status": "available"}.items() if v is not None or k == "price"})
    shop = req["shop"]
    world["title"] = shop["name"]
    catalog = {"market": shop["name"], "tagline": shop.get("address") or "", "contact": shop.get("contact") or "", "currency": "USD",
               "type": shop["type"], "region": shop["region"], "pay": {}, "items": items,
               "built": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
    json.dump(world, open(os.path.join(src, "world.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(catalog, open(os.path.join(src, "catalog.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    pxdz.pack(src, os.path.join(d, "store.pxdz"), name=shop["name"])
    size = os.path.getsize(os.path.join(d, "store.pxdz"))
    return set_state(d, state="built", slug=state(d).get("slug") or slug(shop["name"]),
                     message=f"{len(world['scenes'])} spot(s), {len(items)} item(s), {size / 1e6:.1f} MB")


def approve(d, auth_dir, days, stripe_account, market=MARKET):
    st = state(d)
    if st["state"] != "built":
        raise SystemExit(f"job is {st['state']}; build it first")
    req = json.load(open(os.path.join(d, "request.json")))
    shop = req["shop"]; mid = slug(shop["name"])
    region_dir = os.path.join(market, shop["type"], region_folder(market, shop["type"], shop["region"]))
    while os.path.exists(os.path.join(region_dir, mid + ".pxdz.sig")) and \
            json.load(open(os.path.join(region_dir, mid + ".pxdz.sig")))["cert"]["cert"]["key"] != {k: req["owner"][k] for k in ("crv", "kty", "x", "y")}:
        mid += "-2"  # that name is taken in this region by another merchant
    pub = os.path.join(d, "owner.pub.json"); json.dump(req["owner"], open(pub, "w"))
    wallets = {"evm": shop["wallet"]} if shop.get("wallet") else None
    pxdsign.issue(auth_dir, pub, mid, shop["name"], pxdsign.DEFAULT_PAY_HOSTS, days, os.path.join(d, "cert.json"), stripe_account, wallets)
    return set_state(d, state="approved", slug=mid, message="Approved by PXD. Sign from your browser to go live.")


def jobs(intake):
    for j in sorted(os.listdir(intake)):
        if os.path.isfile(os.path.join(intake, j, "job.json")):
            yield j, os.path.join(intake, j)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--intake", default=INTAKE)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("list"); w = sp.add_parser("watch"); w.add_argument("--every", type=int, default=20)
    b = sp.add_parser("build"); b.add_argument("job")
    a = sp.add_parser("approve"); a.add_argument("job"); a.add_argument("--authority", required=True); a.add_argument("--market", default=MARKET)
    a.add_argument("--days", type=int, default=365); a.add_argument("--stripe-account")
    r = sp.add_parser("reject"); r.add_argument("job"); r.add_argument("--reason", required=True)
    x = ap.parse_args()
    if x.cmd == "list":
        for j, d in jobs(x.intake):
            st = state(d); print(f"{j}  {st['state']:<10} {(st.get('shop') or {}).get('name', ''):<30} {st.get('message', '')}")
    elif x.cmd == "build":
        print(build(os.path.join(x.intake, x.job))["message"])
    elif x.cmd == "approve":
        st = approve(os.path.join(x.intake, x.job), x.authority, x.days, x.stripe_account, x.market); print(f"approved as {st['slug']}")
    elif x.cmd == "reject":
        set_state(os.path.join(x.intake, x.job), state="rejected", message=x.reason); print("rejected")
    elif x.cmd == "watch":
        print(f"PXD Studio watching {x.intake}")
        while True:
            for j, d in jobs(x.intake):
                if state(d)["state"] == "submitted":
                    try:
                        print(f"{j}: {build(d)['message']}", flush=True)
                    except Exception as e:  # noqa: BLE001
                        set_state(d, state="failed", message=f"Studio error: {e}"); print(f"{j}: FAILED {e}", flush=True)
            time.sleep(x.every)


if __name__ == "__main__":
    main()
