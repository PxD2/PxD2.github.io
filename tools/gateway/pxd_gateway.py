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
"""
import argparse, base64, json, math, os, re, shutil, subprocess, sys, tempfile, threading, time, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "pxdz"))
import pxdsign  # noqa: E402

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

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in (("Access-Control-Allow-Origin", "*"), ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
                     ("Access-Control-Allow-Headers", "Content-Type, Range")):
            self.send_header(k, v)
        self.end_headers()

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        p = self.path.split("?")[0]
        if p in ("/", "/stores", "/stores/"):
            page = os.path.join(os.path.dirname(HERE), "pxd_browser", "stores.html")
            return self._send(200, open(page, "rb").read(), "text/html; charset=utf-8")
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
    a = ap.parse_args()
    os.makedirs(a.store, exist_ok=True)
    CFG.update(store=a.store, authority=a.authority, ollama=a.ollama.rstrip("/"), embed_model=a.embed_model, max_mb=a.max_mb,
               authority_kid=json.load(open(a.authority))["kid"])
    g = gpu_status()
    print(f"PXD Gateway on :{a.port} · store {a.store} · authority {CFG['authority_kid']} · GPU {g[0]['name'] if g else 'none found'}")
    ThreadingHTTPServer((a.host, a.port), H).serve_forever()


if __name__ == "__main__":
    main()
