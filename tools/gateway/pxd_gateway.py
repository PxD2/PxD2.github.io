"""PXD Gateway — the second stream, run on base1.

Serves the .pxd store data stream alongside GitHub, authenticates merchants, and uses the
RTX GPU (CUDA, through the local Ollama embedding model) for COG meaning grouping.

    python tools/gateway/pxd_gateway.py --authority pxd/authority.json --store "C:\\PXD Gateway\\bundles"

Endpoints
  GET  /                        PXD Stores: the buyer-facing page for every sub-store (data from all main repositories)
  GET  /api/status              GPU, Ollama and store status
  GET  /api/stores              every bundle with its merchant verification result
  GET  /b/<name>.pxdz[.sig]     bundle stream, with HTTP Range (a reader fetches one part at a time)
  POST /api/publish             {"name", "bundle_b64", "sig"}: accepted only from a certified merchant
  POST /api/cog/group           {"sentences": [...], "threshold": 0.9}: GPU embeddings -> meaning groups
  GET  /market/...              the market indexes and store bundles (type / region / store)
  POST /api/checkout            PXD Pay: {"lines": [{"type","region","store","item","qty"}]} -> one checkout per merchant.
                                Prices come from the signed store data, never from the cart. Money goes straight
                                into each merchant's own Stripe account (direct charge on the account named in its
                                certificate); PXD never holds it. Without Stripe, the merchant's certified pay links.
"""
import argparse, base64, json, math, os, re, secrets, shutil, subprocess, sys, tempfile, threading, time, urllib.error, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "pxdz"))
import pxdsign, pxdz  # noqa: E402
sys.path.insert(0, HERE)
import pxd_crypto  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "ledger"))
import pxdledger  # noqa: E402
import hashlib, hmac  # noqa: E402
CRYPTO = None
LEDGER_LOCK = threading.Lock()
MID = re.compile(r"^[0-9a-f]{24}$")


def ledger_path(mid):
    if not MID.match(str(mid)):
        raise ValueError("bad model id")
    return os.path.join(CFG["ledger"], mid + ".jsonl")


def holder_jwk(h):
    if not (isinstance(h, dict) and h.get("crv") == "P-256" and h.get("kty") == "EC" and all(isinstance(h.get(k), str) for k in ("x", "y"))):
        raise ValueError("holder must be a P-256 public key (JWK)")
    pxdsign.load_pub(h)  # raises if the point is not on the curve
    return {k: h[k] for k in ("crv", "kty", "x", "y")}


def claim(body):
    """After a paid order, write each license bought to that model's ledger, held by the buyer's key."""
    if not CFG.get("delegate"):
        raise ValueError("this gateway issues no licenses (start it with --delegate-key)")
    rid = str(body.get("request", "")); holder = holder_jwk(body.get("holder"))
    r = CRYPTO.status(rid)
    if not r:
        raise ValueError("no such payment")
    if r["state"] != "paid":
        raise ValueError("not paid yet")
    if r.get("claimed"):
        if r["claimed"]["holder"] != pxdledger.kid(holder):
            raise ValueError("these licenses were already issued to another key")
        return r["claimed"]
    tokens = []
    with LEDGER_LOCK:
        for it in r.get("items", []):
            led = it.get("ledger")
            if not led:
                continue
            path = ledger_path(led["model"])
            for _ in range(it["qty"]):
                n = len(pxdledger.read_log(path))
                tok = pxdledger.new_token(led["model"], led["tier"], holder, n)
                pxdledger.append(path, CFG["delegate"], "issue", {"token": tok, "tier": led["tier"], "holder": holder, "payment": r["order"]},
                                 authority=json.load(open(CFG["authority"])))
                tokens.append({"model": led["model"], "tier": led["tier"], "token": tok, "title": it.get("title", "")})
    out = {"holder": pxdledger.kid(holder), "licenses": tokens}
    CRYPTO.update(rid, claimed=out)
    return out


# ------------------------------------------------------------------ Shop Builder intake: owner -> studio -> approval -> owner signs -> market
JOB = re.compile(r"^[0-9a-f]{24}$")
UPLOAD = re.compile(r"^(pano|items)/[a-z0-9][a-z0-9-]{0,80}\.(jpg|png|webp|glb)$")
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "market"))
import pxd_market  # noqa: E402


def job_dir(job):
    if not JOB.match(str(job)):
        raise ValueError("bad job id")
    d = os.path.join(CFG["intake"], job)
    if not os.path.isdir(d):
        raise ValueError("no such job")
    return d


def job_state(d):
    return json.load(open(os.path.join(d, "job.json")))


def set_state(d, **kw):
    st = job_state(d); st.update(kw, updated=time.strftime("%Y-%m-%dT%H:%M:%S"))
    json.dump(st, open(os.path.join(d, "job.json.tmp"), "w"), indent=1); os.replace(os.path.join(d, "job.json.tmp"), os.path.join(d, "job.json"))
    return st


def intake_new():
    job = secrets.token_hex(12); d = os.path.join(CFG["intake"], job); os.makedirs(os.path.join(d, "files"))
    json.dump({"state": "open", "created": time.strftime("%Y-%m-%dT%H:%M:%S")}, open(os.path.join(d, "job.json"), "w"))
    return {"job": job}


def intake_submit(job, body):
    d = job_dir(job)
    if job_state(d)["state"] != "open":
        raise ValueError("already sent")
    owner = holder_jwk(body.get("owner"))
    shop = body.get("shop") or {}
    for k in ("name", "type", "region"):
        if not str(shop.get(k, "")).strip():
            raise ValueError(f"shop {k} is required")
    if not re.fullmatch(r"[a-z][a-z0-9-]{1,30}", shop["type"]):
        raise ValueError("bad store type")
    if shop.get("wallet") and not re.fullmatch(r"0x[0-9a-fA-F]{40}", shop["wallet"]):
        raise ValueError("bad wallet address")
    world, items = body.get("world") or {}, body.get("items") or []
    have = set()
    for root_, _, files in os.walk(os.path.join(d, "files")):
        have |= {os.path.relpath(os.path.join(root_, f), os.path.join(d, "files")).replace("\\", "/") for f in files}
    scenes = world.get("scenes") or []
    if not scenes or len(scenes) > 60 or len(items) > 500:
        raise ValueError("1 to 60 shop photos and up to 500 items")
    ids = {s.get("id") for s in scenes}; item_ids = {i.get("id") for i in items}
    for s in scenes:
        if s.get("image") not in have:
            raise ValueError(f"photo for {s.get('name')} was not uploaded")
        for h in s.get("hotspots") or []:
            if h.get("kind") == "go" and h.get("to") not in ids or h.get("kind") == "item" and h.get("item") not in item_ids:
                raise ValueError("a pin points at something that isn't there")
    for it in items:
        for f in (it.get("photos") or []) + ([it["model"]] if it.get("model") else []):
            if f not in have:
                raise ValueError(f"file {f} was not uploaded")
    json.dump({"owner": owner, "shop": shop, "world": world, "items": items}, open(os.path.join(d, "request.json"), "w"), indent=1)
    return set_state(d, state="submitted", shop={k: shop.get(k, "") for k in ("name", "type", "region")}, owner=owner)


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


def intake_publish(job, body):
    """The owner's own signature over the studio-built store, with PXD's certificate for the owner's key."""
    d = job_dir(job); st = job_state(d)
    if st["state"] != "approved":
        raise ValueError("not approved yet")
    cert = json.load(open(os.path.join(d, "cert.json")))
    sig = {"sig": body.get("sig"), "signature": str(body.get("signature", "")), "cert": cert}
    bundle = os.path.join(d, "store.pxdz")
    tmp = bundle + ".sig"; json.dump(sig, open(tmp, "w"), indent=2)
    ok, rep = pxdsign.verify_bundle(bundle, CFG["authority"])
    if not ok:
        os.remove(tmp)
        bad = next((c for c in rep["checks"] if not c["ok"]), {})
        raise ValueError(f"signature refused: {bad.get('check')} {bad.get('detail', '')}".strip())
    shop = st["shop"]; region = region_folder(CFG["market"], shop["type"], shop["region"])
    rdir = os.path.join(CFG["market"], shop["type"], region); os.makedirs(rdir, exist_ok=True)
    if not os.path.exists(os.path.join(rdir, "region.json")):
        json.dump({"name": shop["region"]}, open(os.path.join(rdir, "region.json"), "w"))
    dst = os.path.join(rdir, st["slug"] + ".pxdz")
    if os.path.exists(dst + ".sig") and json.load(open(dst + ".sig"))["cert"]["cert"]["merchant"] != cert["cert"]["merchant"]:
        raise ValueError("that store name belongs to another merchant in this region")
    shutil.copy2(bundle, dst); shutil.copy2(tmp, dst + ".sig")
    pxd_market.build(CFG["market"], CFG["authority"], CFG["market_base"])
    return set_state(d, state="published", market=f"{shop['type']}/{region}/{st['slug']}")


def challenge():
    raw = f"{int(time.time())}.{secrets.token_hex(12)}"
    return raw + "." + hmac.new(CFG["secret"], raw.encode(), hashlib.sha256).hexdigest()[:32]


def model_key(body):
    """Give the model's file key to the current holder of a license, proven by signing a fresh challenge."""
    ch = str(body.get("challenge", "")); parts = ch.split(".")
    if len(parts) != 3 or not hmac.compare_digest(parts[2], hmac.new(CFG["secret"], f"{parts[0]}.{parts[1]}".encode(), hashlib.sha256).hexdigest()[:32]):
        raise ValueError("bad challenge")
    if time.time() - int(parts[0]) > 300:
        raise ValueError("challenge expired; ask for a new one")
    st = pxdledger.replay(pxdledger.read_log(ledger_path(body.get("model"))), json.load(open(CFG["authority"])))
    lic = st["licenses"].get(str(body.get("token")))
    if not lic or not lic["current"]:
        raise ValueError("no current license with that token")
    if not pxdsign.verify(pxdsign.load_pub(lic["holder"]), ch.encode(), str(body.get("sig", ""))):
        raise ValueError("signature is not from the license holder")
    key = CFG["model_keys"].get(st["model"])
    if not key:
        raise ValueError("the artist has not deposited a file key for this model")
    return {"model": st["model"], "title": st["title"], "tier": lic["tier"], "rights": st["tiers"][lic["tier"]].get("rights", ""), "key": key}

CFG = {}
NAME_OK = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
VERIFY_CACHE, LOCK = {}, threading.Lock()


def gpu_status():
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "--query-gpu=name,utilization.gpu,memory.used,memory.total,driver_version",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5).stdout.strip().splitlines()
        return [dict(zip(["name", "util_pct", "mem_used_mb", "mem_total_mb", "driver"], [x.strip() for x in l.split(",")])) for l in out]
    except Exception:
        return None


def ollama(path, payload=None, timeout=60):
    req = urllib.request.Request(CFG["ollama"] + path, data=json.dumps(payload).encode() if payload else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def embed(texts):
    """Embeddings from Ollama, which runs the model on the GPU (CUDA) when one is present."""
    try:
        return ollama("/api/embed", {"model": CFG["embed_model"], "input": texts})["embeddings"]
    except Exception:
        return None


def group(sentences, threshold):
    vecs = embed(sentences)
    if not vecs:
        groups, seen = [], {}
        for s in sentences:
            k = " ".join(sorted(set(re.findall(r"[a-z0-9']+", s.lower()))))
            if k not in seen:
                seen[k] = len(groups); groups.append([])
            groups[seen[k]].append(s)
        return {"engine": "cpu: exact word-set match (Ollama not reachable)", "groups": groups}
    norm = [math.sqrt(sum(x * x for x in v)) or 1.0 for v in vecs]
    centroids, groups = [], []
    for i, v in enumerate(vecs):
        best, score = None, -1.0
        for g, c in enumerate(centroids):
            s = sum(a * b for a, b in zip(v, c[0])) / (norm[i] * c[1])
            if s > score:
                best, score = g, s
        if best is not None and score >= threshold:
            groups[best].append(sentences[i])
        else:
            centroids.append((v, norm[i])); groups.append([sentences[i]])
    gpu = gpu_status()
    eng = f"cuda: {CFG['embed_model']} via Ollama on {gpu[0]['name']}" if gpu else f"{CFG['embed_model']} via Ollama"
    return {"engine": eng, "threshold": threshold, "groups": groups}


def verify_cached(path):
    st = os.stat(path); key = (path, st.st_mtime, st.st_size, os.path.getmtime(path + ".sig") if os.path.exists(path + ".sig") else 0)
    with LOCK:
        if key in VERIFY_CACHE:
            return VERIFY_CACHE[key]
    ok, rep = pxdsign.verify_bundle(path, CFG["authority"])
    with LOCK:
        VERIFY_CACHE[key] = (ok, rep)
    return ok, rep


# ------------------------------------------------------------------ PXD Pay
CATALOGS = {}


def market_store(t, r, name):
    for part in (t, r, name):
        if not NAME_OK.match(str(part)):
            raise ValueError("bad store address")
    path = os.path.join(CFG["market"], t, r, name + ".pxdz")
    if not os.path.isfile(path):
        raise ValueError(f"no store {t}/{r}/{name}")
    ok, rep = verify_cached(path)
    if not ok:
        raise ValueError(f"{t}/{r}/{name}: merchant not verified")
    key = (path, os.path.getmtime(path))
    if key not in CATALOGS:
        _, files = pxdz.read(path)
        cat = next((json.loads(v) for k, v in files.items() if k.endswith("catalog.json")), {})
        CATALOGS[key] = (cat, json.load(open(path + ".sig"))["cert"]["cert"])
    return CATALOGS[key]


def stripe_session(acct, currency, lines, order, success, cancel, fee_cents):
    form = {"mode": "payment", "success_url": success, "cancel_url": cancel, "metadata[pxd_order]": order,
            "payment_intent_data[metadata][pxd_order]": order}
    for i, (title, cents, qty) in enumerate(lines):
        form.update({f"line_items[{i}][price_data][currency]": currency.lower(), f"line_items[{i}][price_data][unit_amount]": str(cents),
                     f"line_items[{i}][price_data][product_data][name]": title[:250], f"line_items[{i}][quantity]": str(qty)})
    if fee_cents > 0:
        form["payment_intent_data[application_fee_amount]"] = str(fee_cents)
    req = urllib.request.Request(CFG["stripe_api"] + "/v1/checkout/sessions", data=urllib.parse.urlencode(form).encode(),
                                 headers={"Authorization": "Bearer " + CFG["stripe_key"], "Stripe-Account": acct,
                                          "Idempotency-Key": order + "-" + acct, "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def checkout(body, origin):
    lines = body.get("lines") or []
    if not isinstance(lines, list) or not 0 < len(lines) <= 100:
        raise ValueError("lines: 1 to 100 items")
    success = body.get("success_url") or origin + "/?paid={CHECKOUT_SESSION_ID}"
    cancel = body.get("cancel_url") or origin + "/?cart"
    if not all(re.match(r"^https?://", u) for u in (success, cancel)):
        raise ValueError("return addresses must be http(s)")
    by_store = {}
    for ln in lines:
        qty = ln.get("qty", 1)
        if not isinstance(qty, int) or not 1 <= qty <= 99:
            raise ValueError("qty: whole number 1 to 99")
        by_store.setdefault((ln.get("type"), ln.get("region"), ln.get("store")), []).append((str(ln.get("item")), qty))
    order = "pxd_" + secrets.token_hex(8)
    out, grand = [], 0.0
    for (t, r, name), wanted in by_store.items():
        cat, cert = market_store(t, r, name)
        items = {it.get("id"): it for it in (cat.get("items") or cat.get("products") or [])}
        priced, total, bought = [], 0, []
        for iid, qty in wanted:
            it = items.get(iid)
            if not it or it.get("status") in ("sold", "hidden"):
                raise ValueError(f"{name}: no item {iid}")
            price = it.get("price")
            if not isinstance(price, (int, float)) or price <= 0:
                raise ValueError(f"{name}: {it.get('title', iid)} is price on request; ask the shop")
            cents = int(round(price * 100)); priced.append((it.get("title") or iid, cents, qty)); total += cents * qty
            bought.append({"id": iid, "qty": qty, "title": it.get("title") or iid, "ledger": it.get("ledger")})
        cur = cat.get("currency", "USD"); acct = (cert.get("pay_account") or {}).get("stripe")
        method = str(body.get("method") or "card")
        entry = {"merchant": {"id": cert["merchant"], "name": cert["name"]}, "store": f"{t}/{r}/{name}", "currency": cur,
                 "total": total / 100, "lines": [{"title": a, "price": c / 100, "qty": q} for a, c, q in priced]}
        wallet = pxd_crypto.CryptoPay.wallet_for(cert, method[5:]) if method.startswith("usdc:") else None
        if method.startswith("usdc:") and cur != "USD":
            raise ValueError(f"{name}: USDC checkout needs prices in USD")
        if method == "pickup":  # remote and LoRa orders: the shop is paid in person when the buyer collects
            entry.update(pay="pickup", note="Pay the shop when you collect")
        elif wallet:
            entry.update(pay="crypto", crypto=CRYPTO.request(order, method[5:], wallet, total, cert["merchant"], {"items": bought}))
        elif acct and CFG["stripe_key"]:
            fee = int(total * CFG["fee_pct"] / 100)
            sess = stripe_session(acct, cur, priced, order, success, cancel, fee)
            entry.update(pay="pxd-pay", url=sess["url"], session=sess["id"], pxd_fee=fee / 100)
        else:
            links = {k: v for k, v in (cat.get("pay") or {}).items() if v and urllib.parse.urlparse(v).hostname in cert["pay_hosts"]}
            entry.update(pay="merchant-links", pay_links=links,
                         note="PXD Pay is not set up for this merchant yet; pay with the shop's own verified links")
        out.append(entry); grand += total / 100
    with LOCK, open(CFG["orders"], "a", encoding="utf-8") as f:
        f.write(json.dumps({"order": order, "time": time.strftime("%Y-%m-%dT%H:%M:%S"), "checkouts": [
            {k: e[k] for k in ("merchant", "store", "currency", "total", "lines", "pay") if k in e} | ({"session": e["session"]} if "session" in e else {})
            | ({"crypto": {k: e["crypto"][k] for k in ("id", "chain", "to", "amount")}} if "crypto" in e else {})
            for e in out]}) + "\n")
    return {"order": order, "total": round(grand, 2), "checkouts": out}


class H(BaseHTTPRequestHandler):
    server_version = "PXD-Gateway/1.0"

    def _send(self, code, body, ctype="application/json", extra=None):
        data = body if isinstance(body, bytes) else json.dumps(body, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*"); self.send_header("Access-Control-Expose-Headers", "Content-Range, Accept-Ranges")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _stream(self, path, ctype):
        size = os.path.getsize(path)
        self.send_response(200)
        self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(size))
        self.send_header("Access-Control-Allow-Origin", "*"); self.send_header("Cache-Control", "public, max-age=86400")
        self.send_header("Cross-Origin-Resource-Policy", "cross-origin")
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(path, "rb") as fh:
            while True:
                chunk = fh.read(1 << 20)
                if not chunk:
                    break
                self.wfile.write(chunk)

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in (("Access-Control-Allow-Origin", "*"), ("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS"),
                     ("Access-Control-Allow-Headers", "Content-Type, Range")):
            self.send_header(k, v)
        self.end_headers()

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        p = self.path.split("?")[0]
        if p in ("/", "/stores", "/stores/"):
            page = os.path.join(os.path.dirname(HERE), "pxd_browser", "home.html" if p == "/" else "stores.html")
            return self._send(200, open(page, "rb").read(), "text/html; charset=utf-8")
        mj = re.match(r"^/api/intake/([0-9a-f]{24})(/store\.pxdz)?$", p)
        if mj:
            try:
                d = job_dir(mj.group(1))
            except ValueError as e:
                return self._send(404, {"error": str(e)})
            if mj.group(2):
                f = os.path.join(d, "store.pxdz")
                return self._send(200, open(f, "rb").read(), "application/octet-stream") if os.path.isfile(f) else self._send(404, {"error": "not built yet"})
            st = job_state(d)
            return self._send(200, {k: st.get(k) for k in ("state", "shop", "message", "owner", "slug", "market", "updated")})
        if p in ("/mini", "/mini/", "/mini_worker.js"):
            f = "mini.html" if p != "/mini_worker.js" else "mini_worker.js"
            return self._send(200, open(os.path.join(os.path.dirname(HERE), "pxd_browser", f), "rb").read(),
                              "text/html; charset=utf-8" if f.endswith(".html") else "text/javascript; charset=utf-8")
        ma = re.match(r"^/mini-assets/((?:runtime|models)/[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+){0,3}|manifest\.json)$", p)
        if ma:
            rel = ma.group(1)
            if ".." in rel:
                return self._send(400, {"error": "bad path"})
            f = os.path.join(CFG["mini"], *rel.split("/"))
            if not os.path.isfile(f):
                return self._send(404, {"error": "not set up: run tools/mini/setup_mini.py on base1"})
            ctype = {".js": "text/javascript", ".mjs": "text/javascript", ".wasm": "application/wasm", ".json": "application/json"}.get(os.path.splitext(f)[1], "application/octet-stream")
            return self._stream(f, ctype)
        if p == "/api/llm/models":
            try:
                return self._send(200, {"models": [m["name"] for m in ollama("/api/tags", timeout=4).get("models", []) if "embed" not in m["name"]]})
            except Exception:
                return self._send(200, {"models": [], "error": "Ollama not reachable"})
        if p in ("/favicon.ico", "/favicon.svg"):
            return self._send(200, open(os.path.join(os.path.dirname(os.path.dirname(HERE)), "favicon.svg"), "rb").read(), "image/svg+xml")
        if p in ("/build", "/build/"):
            return self._send(200, open(os.path.join(os.path.dirname(HERE), "pxd_browser", "shopbuilder.html"), "rb").read(), "text/html; charset=utf-8")
        if p == "/world.js":
            return self._send(200, open(os.path.join(os.path.dirname(HERE), "pxd_browser", "world.js"), "rb").read(), "text/javascript; charset=utf-8")
        if p == "/api/models/challenge":
            return self._send(200, {"challenge": challenge()})
        mm = re.match(r"^/api/models/([0-9a-f]{24})$", p)
        if mm:
            try:
                st = pxdledger.replay(pxdledger.read_log(ledger_path(mm.group(1))), json.load(open(CFG["authority"])))
            except (pxdledger.LedgerError, TypeError) as e:
                return self._send(404 if "start" in str(e) else 409, {"error": str(e)})
            return self._send(200, {"model": st["model"], "title": st["title"], "creator": st["creator"], "royalty_pct": st["royalty_bps"] / 100,
                                    "tiers": st["tiers"], "sold": st["issued"], "head": st["head"],
                                    "licenses": [{k: l[k] for k in ("token", "tier", "holder_kid", "edition", "expires", "current")} for l in st["licenses"].values()]})
        if p == "/api/crypto/status":
            rid = (urllib.parse.parse_qs(self.path.partition("?")[2]).get("id") or [""])[0]
            try:
                r = CRYPTO.status(rid)
            except OSError as e:
                return self._send(502, {"error": f"chain unreachable: {e}"})
            return self._send(200, r) if r else self._send(404, {"error": "no such payment request"})
        if p.startswith("/vendor/") and re.fullmatch(r"/vendor/[a-z0-9.-]+\.js", p):
            f = os.path.join(os.path.dirname(HERE), "pxd_browser", "vendor", p[8:])
            return self._send(200, open(f, "rb").read(), "text/javascript; charset=utf-8") if os.path.isfile(f) else self._send(404, {"error": "not found"})
        if p == "/names.json":  # the gateway's own copy of the registry, so it works with GitHub unreachable
            return self._send(200, open(os.path.join(os.path.dirname(os.path.dirname(HERE)), "names.json"), "rb").read(), "application/json", {"Cache-Control": "no-cache"})
        if p == "/pxd.js":
            return self._send(200, open(os.path.join(os.path.dirname(os.path.dirname(HERE)), "pxd", "pxd.js"), "rb").read(), "text/javascript; charset=utf-8")
        mk = re.match(r"^/market/((?:[a-z0-9-]+/){0,2}(?:index\.json|[a-z0-9-]+\.pxdz(?:\.sig)?))$", p)
        if mk:
            path = os.path.join(CFG["market"], *mk.group(1).split("/"))
            if not os.path.isfile(path):
                return self._send(404, {"error": "not in this market"})
            ctype = "application/octet-stream" if path.endswith(".pxdz") else "application/json"
            return self._send(200, open(path, "rb").read(), ctype, {"Cache-Control": "no-cache"})
        if p == "/api/status":
            try:
                models = [m["name"] for m in ollama("/api/tags", timeout=3).get("models", [])]
            except Exception:
                models = None
            n = len([f for f in os.listdir(CFG["store"]) if f.endswith(".pxdz")])
            return self._send(200, {"gateway": "PXD Gateway 1.0", "gpu": gpu_status(), "ollama_models": models,
                                    "embed_model": CFG["embed_model"], "bundles": n, "authority": CFG["authority_kid"]})
        if p == "/api/stores":
            out = []
            for f in sorted(os.listdir(CFG["store"])):
                if f.endswith(".pxdz"):
                    ok, rep = verify_cached(os.path.join(CFG["store"], f))
                    out.append({"name": f[:-5], "bytes": os.path.getsize(os.path.join(CFG["store"], f)), "verified": ok,
                                "merchant": rep.get("merchant"), "url": f"/b/{f}", "sig": f"/b/{f}.sig"})
            return self._send(200, {"stores": out})
        m = re.match(r"^/b/([a-z0-9-]+\.pxdz(?:\.sig)?)$", p)
        if m:
            path = os.path.join(CFG["store"], m.group(1))
            if not os.path.isfile(path):
                return self._send(404, {"error": "no such bundle"})
            size = os.path.getsize(path); rng = self.headers.get("Range")
            ctype = "application/json" if path.endswith(".sig") else "application/octet-stream"
            with open(path, "rb") as fh:
                if rng and (mm := re.match(r"bytes=(\d*)-(\d*)$", rng.strip())):
                    a = int(mm.group(1)) if mm.group(1) else max(size - int(mm.group(2)), 0)
                    b = int(mm.group(2)) if mm.group(1) and mm.group(2) else size - 1
                    if a >= size or a > b:
                        return self._send(416, b"", ctype, {"Content-Range": f"bytes */{size}"})
                    b = min(b, size - 1); fh.seek(a)
                    return self._send(206, fh.read(b - a + 1), ctype, {"Content-Range": f"bytes {a}-{b}/{size}", "Accept-Ranges": "bytes"})
                return self._send(200, fh.read(), ctype, {"Accept-Ranges": "bytes"})
        return self._send(404, {"error": "not found"})

    def do_PUT(self):
        m = re.match(r"^/api/intake/([0-9a-f]{24})/files/(.+)$", self.path.split("?")[0])
        if not m:
            return self._send(404, {"error": "not found"})
        try:
            d = job_dir(m.group(1))
        except ValueError as e:
            return self._send(404, {"error": str(e)})
        rel = urllib.parse.unquote(m.group(2))
        if not UPLOAD.match(rel):
            return self._send(400, {"error": "photos as .jpg/.png/.webp, 3D as .glb"})
        if job_state(d)["state"] != "open":
            return self._send(409, {"error": "this store was already sent"})
        n = int(self.headers.get("Content-Length") or 0)
        if n > CFG["max_mb"] * 1_000_000:
            return self._send(413, {"error": f"over {CFG['max_mb']} MB"})
        data = self.rfile.read(n)
        if rel.endswith(".glb") and data[:4] != b"glTF" or not rel.endswith(".glb") and not (data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n" or data[8:12] == b"WEBP"):
            return self._send(400, {"error": "that file isn't the image or 3D model its name says"})
        path = os.path.join(d, "files", *rel.split("/")); os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "wb").write(data)
        return self._send(201, {"kept": rel, "bytes": len(data)})

    def do_POST(self):
        p = self.path.split("?")[0]
        n = int(self.headers.get("Content-Length") or 0)
        if n > CFG["max_mb"] * 1_000_000:
            return self._send(413, {"error": f"over {CFG['max_mb']} MB"})
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return self._send(400, {"error": "body must be JSON"})
        if p == "/api/cog/group":
            sents = [s for s in body.get("sentences", []) if isinstance(s, str) and s.strip()][:2000]
            return self._send(200, group(sents, float(body.get("threshold", 0.9))))
        mi = re.match(r"^/api/intake(?:/([0-9a-f]{24})/(submit|publish))?$", p)
        if mi:
            try:
                return self._send(200, intake_new() if not mi.group(1) else
                                  (intake_submit if mi.group(2) == "submit" else intake_publish)(mi.group(1), body))
            except ValueError as e:
                return self._send(400, {"error": str(e)})
        if p == "/api/llm":  # PXD Mini hands big jobs to base1's Ollama
            try:
                installed = [m["name"] for m in ollama("/api/tags", timeout=4).get("models", [])]
            except Exception:
                return self._send(502, {"error": "Ollama is not running on base1"})
            model = str(body.get("model", ""))
            msgs = [m for m in body.get("messages") or [] if isinstance(m, dict) and m.get("role") in ("system", "user", "assistant") and isinstance(m.get("content"), str)]
            if model not in installed:
                return self._send(400, {"error": f"{model or 'no model'} is not installed on base1"})
            if not msgs or sum(len(m["content"]) for m in msgs) > 200_000:
                return self._send(400, {"error": "messages missing or too long"})
            t0 = time.time()
            try:
                out = ollama("/api/chat", {"model": model, "messages": msgs, "stream": False,
                                           "options": {"num_predict": int(min(max(int(body.get("max_tokens") or 1024), 16), 4096))}}, timeout=600)
            except Exception as e:  # noqa: BLE001
                return self._send(502, {"error": f"base1 model failed: {e}"})
            return self._send(200, {"model": model, "content": out.get("message", {}).get("content", ""), "prompt_tokens": out.get("prompt_eval_count"),
                                    "output_tokens": out.get("eval_count"), "seconds": round(time.time() - t0, 2)})
        if p in ("/api/models/claim", "/api/models/key"):
            try:
                return self._send(200, claim(body) if p.endswith("claim") else model_key(body))
            except (ValueError, pxdledger.LedgerError) as e:
                return self._send(400, {"error": str(e)})
            except OSError as e:
                return self._send(502, {"error": str(e)})
        if p == "/api/checkout":
            origin = f"http://{self.headers.get('Host', 'localhost')}"
            try:
                return self._send(200, checkout(body, origin))
            except ValueError as e:
                return self._send(400, {"error": str(e)})
            except urllib.error.HTTPError as e:
                return self._send(502, {"error": "Stripe refused the checkout", "detail": e.read().decode(errors="replace")[:500]})
            except OSError as e:
                return self._send(502, {"error": f"payment service unreachable: {e}"})
        if p == "/api/publish":
            name = str(body.get("name", ""))
            if not NAME_OK.match(name):
                return self._send(400, {"error": "name: lowercase letters, digits and dashes"})
            tmp = tempfile.mkdtemp()
            try:
                bpath = os.path.join(tmp, name + ".pxdz")
                open(bpath, "wb").write(base64.b64decode(body.get("bundle_b64", "")))
                json.dump(body.get("sig"), open(bpath + ".sig", "w"))
                ok, rep = pxdsign.verify_bundle(bpath, CFG["authority"])
                if not ok:
                    return self._send(403, {"accepted": False, "report": rep})
                dst = os.path.join(CFG["store"], name + ".pxdz")
                existing = dst + ".sig"
                if os.path.exists(existing):  # only the same merchant may replace its own bundle
                    prev = json.load(open(existing))["cert"]["cert"]["merchant"]
                    if prev != rep["merchant"]["id"]:
                        return self._send(403, {"accepted": False, "error": f"{name} belongs to merchant {prev}"})
                shutil.move(bpath, dst); shutil.move(bpath + ".sig", dst + ".sig")
                return self._send(200, {"accepted": True, "report": rep, "url": f"/b/{name}.pxdz"})
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        return self._send(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        sys.stderr.write(time.strftime("%H:%M:%S ") + (fmt % args) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--authority", required=True, help="the PXD authority's PUBLIC record (authority.json)")
    ap.add_argument("--store", default=os.path.join(os.path.expanduser("~"), "PXD Gateway", "bundles"))
    ap.add_argument("--host", default="0.0.0.0"); ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--ollama", default="http://127.0.0.1:11434"); ap.add_argument("--embed-model", default="nomic-embed-text")
    ap.add_argument("--max-mb", type=int, default=200)
    ap.add_argument("--market", default=os.path.join(os.path.dirname(os.path.dirname(HERE)), "market"), help="market folder (type/region/store)")
    ap.add_argument("--stripe-api", default="https://api.stripe.com"); ap.add_argument("--fee-pct", type=float, default=0.0, help="PXD platform fee, percent (default 0)")
    ap.add_argument("--rpc", action="append", default=[], help="chain=url, e.g. base=https://... (default: public RPCs)")
    ap.add_argument("--confirmations", type=int, default=3)
    ap.add_argument("--mini", default=os.path.join(os.path.expanduser("~"), "PXD Gateway", "mini"), help="PXD Mini runtime and model (setup_mini.py)")
    ap.add_argument("--intake", default=os.path.join(os.path.expanduser("~"), "PXD Gateway", "intake"), help="Shop Builder submissions (studio input)")
    ap.add_argument("--market-base", default="https://raw.githubusercontent.com/PxD2/PxD2.github.io/main/")
    ap.add_argument("--ledger", default=os.path.join(os.path.dirname(os.path.dirname(HERE)), "ledger"), help="model ledger folder")
    ap.add_argument("--delegate-key", help="this gateway's key, delegated by artists to issue licenses after payment")
    ap.add_argument("--model-keys", help="JSON {model id: file key} deposited by artists (keep private, never on GitHub)")
    ap.add_argument("--orders", default=os.path.join(os.path.expanduser("~"), "PXD Gateway", "orders.jsonl"))
    a = ap.parse_args()
    os.makedirs(a.store, exist_ok=True)
    os.makedirs(os.path.dirname(a.orders), exist_ok=True)
    os.makedirs(a.intake, exist_ok=True)
    CFG.update(intake=a.intake, market_base=a.market_base, mini=a.mini)
    CFG.update(ledger=a.ledger, delegate=json.load(open(a.delegate_key)) if a.delegate_key else None,
               model_keys=json.load(open(a.model_keys)) if a.model_keys else {}, secret=secrets.token_bytes(32), authority=a.authority)
    global CRYPTO
    CRYPTO = pxd_crypto.CryptoPay(os.path.join(os.path.dirname(a.orders), "crypto_requests.json"),
                                  dict(x.split("=", 1) for x in a.rpc), a.confirmations)
    CFG.update(market=a.market, stripe_api=a.stripe_api.rstrip("/"), stripe_key=os.environ.get("STRIPE_SECRET_KEY", ""), fee_pct=a.fee_pct, orders=a.orders)
    CFG.update(store=a.store, authority=a.authority, ollama=a.ollama.rstrip("/"), embed_model=a.embed_model, max_mb=a.max_mb,
               authority_kid=json.load(open(a.authority))["kid"])
    g = gpu_status()
    print(f"PXD Pay: {'Stripe Connect' if CFG['stripe_key'] else 'off (set STRIPE_SECRET_KEY); merchant links only'} · market {a.market} · fee {a.fee_pct}%")
    print(f"PXD Gateway on :{a.port} · store {a.store} · authority {CFG['authority_kid']} · GPU {g[0]['name'] if g else 'none found'}")
    ThreadingHTTPServer((a.host, a.port), H).serve_forever()


if __name__ == "__main__":
    main()
