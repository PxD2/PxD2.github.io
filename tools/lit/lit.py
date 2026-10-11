"""Lit node: linked internet traffic. Content travels between neighbors, named by its hash.

Every public part of every PXD site (models, images, databases, pages) is named by the
SHA-256 of its bytes. A Lit node keeps parts and hands them to anyone nearby who asks, so a
part leaves GitHub or the gateway once per network, not once per person. A node checks every
part against its name before keeping or serving it, so a neighbor can carry data but cannot
fake it. Sealed (encrypted) parts never enter Lit.

Run one on base1, each Pi 5, the Hackspace box, a shop's or restaurant's Wi-Fi machine:
    python lit.py                                  # :7470, store in ~/.pxd/lit
    python lit.py --peer http://192.168.1.20:7470  # ask this node when a part is missing
    python lit.py --mount cog-english-v0.pmoc      # serve the slices of a .pmoc file
Nodes on one network find each other by a UDP beacon (port 7471) unless --no-beacon.
PXD Root answers lit.pxd with this node's address (pxd2root.py --lit-ip).

HTTP (CORS open, so the PXD Browser and pages can use it)
  GET  /lit/status              parts held, bytes, served locally vs fetched, peers
  POST /lit/have  {"ids": [...]}   which of these SHA-256 ids this node holds
  GET  /lit/s/<sha256>          the part (asks peers once on a miss)
  PUT  /lit/s/<sha256>          give a part; kept only if SHA-256(body) is the id
  POST /lit/warm  {"bundle": url | [urls]}   fetch a .pxdz and keep its public parts
  GET  /lit/pack                every part as one .pmoc file (kind 6), for GitHub or a USB stick
"""
import argparse, hashlib, json, os, re, socket, struct, sys, tempfile, threading, time, urllib.request, zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pmoc  # noqa: E402

SHA = re.compile(r"^[0-9a-f]{64}$")
CFG, MOUNTS, PEERS = None, [], {}
STATS = {"served_local": 0, "served_from_peers": 0, "received": 0, "warmed": 0, "refused": 0}
LOCK = threading.Lock()


def log(msg):
    sys.stderr.write(time.strftime("%H:%M:%S ") + msg + "\n"); sys.stderr.flush()


# ------------------------------------------------------------------ store
def path_of(h):
    return os.path.join(CFG.store, h[:2], h)


def has(h):
    if os.path.exists(path_of(h)):
        return True
    sid = bytes.fromhex(h[:32])
    return any(sid in m.slices for m in MOUNTS)


def get_local(h):
    p = path_of(h)
    if os.path.exists(p):
        data = open(p, "rb").read()
        if hashlib.sha256(data).hexdigest() == h:
            return data
        os.remove(p)  # disk damage: drop it, a neighbor or the origin will refill it
    sid = bytes.fromhex(h[:32])
    for m in MOUNTS:
        if sid in m.slices:
            data = m.read(sid)
            if hashlib.sha256(data).hexdigest() == h:
                return data
    return None


def used_bytes():
    total = 0
    for root, _, files in os.walk(CFG.store):
        total += sum(os.path.getsize(os.path.join(root, f)) for f in files)
    return total


def keep(h, data):
    """Store a part only if it is what its name says. Returns True if kept or already held."""
    if hashlib.sha256(data).hexdigest() != h:
        with LOCK:
            STATS["refused"] += 1
        return False
    p = path_of(h)
    if os.path.exists(p):
        return True
    if CFG.max_bytes and used_bytes() + len(data) > CFG.max_bytes:
        return False
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp%d" % threading.get_ident()
    open(tmp, "wb").write(data); os.replace(tmp, p)
    return True


def all_ids():
    out = []
    for root, _, files in os.walk(CFG.store):
        out += [f for f in files if SHA.match(f)]
    return out


# ------------------------------------------------------------------ peers
def ask_peers(h):
    for url in list(PEERS):
        try:
            req = urllib.request.Request(f"{url}/lit/s/{h}", headers={"X-Lit-Hop": "1"})
            with urllib.request.urlopen(req, timeout=4) as r:
                data = r.read()
            if keep(h, data):
                with LOCK:
                    STATS["served_from_peers"] += len(data)
                return data
        except Exception:  # noqa: BLE001
            continue
    return None


def beacon():
    """Announce this node and learn the others on the same network (UDP broadcast)."""
    me = f"http://{lan_ip()}:{CFG.port}"
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("", CFG.beacon_port)); s.settimeout(1)
    last = 0
    while True:
        if time.time() - last > 30:
            try:
                s.sendto(f"LIT1 {me}".encode(), ("255.255.255.255", CFG.beacon_port))
            except OSError:
                pass
            last = time.time()
        try:
            msg, _ = s.recvfrom(256)
            m = re.fullmatch(r"LIT1 (http://[0-9.]+:\d+)", msg.decode(errors="replace"))
            if m and m.group(1) != me and m.group(1) not in PEERS:
                PEERS[m.group(1)] = "beacon"; log(f"found Lit node {m.group(1)}")
        except OSError:
            pass


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1)); return s.getsockname()[0]
    except Exception:  # noqa: BLE001
        return "127.0.0.1"
    finally:
        s.close()


# ------------------------------------------------------------------ warm from a .pxdz
def warm(urls):
    """Fetch a bundle and keep each public part it carries (verified against its manifest hash)."""
    last = None
    for u in urls if isinstance(urls, list) else [urls]:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "PXD-Lit/1"})
            with urllib.request.urlopen(req, timeout=60) as r:
                blob = r.read()
            break
        except Exception as e:  # noqa: BLE001
            last = e
    else:
        raise RuntimeError(f"no source answered: {last}")
    if blob[:4] != b"PXDZ":
        raise ValueError("not a PXDZ bundle")
    mlen = struct.unpack("<I", blob[5:9])[0]
    man = json.loads(blob[9:9 + mlen]); base = 9 + mlen
    if man.get("encryption"):
        return {"kept": 0, "skipped": len(man["parts"]), "note": "sealed bundle: nothing enters Lit"}
    kept = skipped = 0
    for p in man["parts"]:
        if "cog-json" in p["codec"] or "aes-gcm" in p["codec"]:
            skipped += 1; continue
        data = blob[base + p["offset"]: base + p["offset"] + p["length"]]
        if "deflate" in p["codec"]:
            data = zlib.decompress(data, -15)
        if keep(p["sha256"], data):
            kept += 1
            with LOCK:
                STATS["warmed"] += len(data)
        else:
            skipped += 1
    return {"kept": kept, "skipped": skipped, "bundle": man.get("name")}


# ------------------------------------------------------------------ HTTP
class H(BaseHTTPRequestHandler):
    server_version = "PXD-Lit/1"
    timeout = 30

    def _send(self, code, body=b"", ctype="application/json", extra=None):
        data = body if isinstance(body, bytes) else json.dumps(body, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(data)))
        self._cors()
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def do_OPTIONS(self):
        self.send_response(204); self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET, PUT, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Lit-Hop")
        self.send_header("Access-Control-Max-Age", "86400"); self.end_headers()

    def _body(self, cap):
        n = int(self.headers.get("Content-Length") or 0)
        if n > cap:
            return None
        return self.rfile.read(n)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        p = self.path.split("?")[0]
        m = re.fullmatch(r"/lit/s/([0-9a-f]{64})", p)
        if m:
            h = m.group(1)
            data = get_local(h)
            if data is None and not self.headers.get("X-Lit-Hop"):
                data = ask_peers(h)
            if data is None:
                return self._send(404, {"error": "not held here"})
            with LOCK:
                STATS["served_local"] += len(data)
            return self._send(200, data, "application/octet-stream", {"Cache-Control": "public, max-age=31536000, immutable", "ETag": f'"{h}"'})
        if p in ("/", "/lit/status"):
            ids = all_ids()
            return self._send(200, {"lit": "PXD Lit node 1", "parts": len(ids) + sum(len(m.slices) for m in MOUNTS),
                                    "bytes": used_bytes(), "mounts": [m.path for m in MOUNTS], "peers": PEERS, "stats": STATS,
                                    "cap_bytes": CFG.max_bytes})
        if p == "/lit/pack":
            ids = all_ids()
            fd, tmp = tempfile.mkstemp(suffix=".pmoc"); os.close(fd)
            try:
                pmoc.write(tmp, [(bytes.fromhex(h[:32]), 6, 0, get_local(h)) for h in ids])
                return self._send(200, open(tmp, "rb").read(), "application/octet-stream",
                                  {"Content-Disposition": 'attachment; filename="lit-parts.pmoc"'})
            finally:
                os.remove(tmp)
        return self._send(404, {"error": "not found"})

    def do_PUT(self):
        m = re.fullmatch(r"/lit/s/([0-9a-f]{64})", self.path.split("?")[0])
        if not m:
            return self._send(404, {"error": "not found"})
        data = self._body(CFG.max_part)
        if data is None:
            return self._send(413, {"error": "part too large"})
        if keep(m.group(1), data):
            with LOCK:
                STATS["received"] += len(data)
            return self._send(201, {"kept": True})
        return self._send(422, {"kept": False, "error": "content does not match its id, or the store is full"})

    def do_POST(self):
        p = self.path.split("?")[0]
        body = self._body(1_000_000)
        try:
            req = json.loads(body or b"{}")
        except ValueError:
            return self._send(400, {"error": "body must be JSON"})
        if p == "/lit/have":
            ids = [i for i in req.get("ids", [])[:10000] if isinstance(i, str) and SHA.match(i)]
            return self._send(200, {"have": [i for i in ids if has(i)]})
        if p == "/lit/warm":
            try:
                return self._send(200, warm(req.get("bundle")))
            except Exception as e:  # noqa: BLE001
                return self._send(502, {"error": str(e)})
        return self._send(404, {"error": "not found"})

    def log_message(self, *a):
        pass


def main():
    global CFG
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--store", default=os.path.join(os.path.expanduser("~"), ".pxd", "lit"))
    ap.add_argument("--host", default="0.0.0.0"); ap.add_argument("--port", type=int, default=7470)
    ap.add_argument("--peer", action="append", default=[], help="another Lit node to ask on a miss")
    ap.add_argument("--mount", action="append", default=[], help=".pmoc file whose slices this node serves")
    ap.add_argument("--max-gb", type=float, default=0, help="cap on stored parts (0 = no cap)")
    ap.add_argument("--max-part-mb", type=int, default=256)
    ap.add_argument("--beacon-port", type=int, default=7471); ap.add_argument("--no-beacon", action="store_true")
    a = ap.parse_args()
    a.max_bytes = int(a.max_gb * 1e9); a.max_part = a.max_part_mb * 1_000_000
    CFG = a
    os.makedirs(a.store, exist_ok=True)
    for f in a.mount:
        MOUNTS.append(pmoc.Reader(f))
    for p in a.peer:
        PEERS[p.rstrip("/")] = "configured"
    if not a.no_beacon:
        threading.Thread(target=beacon, daemon=True).start()
    print(f"PXD Lit node :{a.port} · store {a.store} · {len(all_ids())} parts · {len(MOUNTS)} .pmoc mount(s) · peers {list(PEERS) or 'by beacon'}")
    ThreadingHTTPServer((a.host, a.port), H).serve_forever()


if __name__ == "__main__":
    main()
