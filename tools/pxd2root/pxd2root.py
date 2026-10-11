"""PXD Root Server: the root of the .pxd namespace, run by PXD on our own machines.

The .pxd ending (alias .pxd2) answers from the PXD registry on GitHub and every sub-hub
registry, not from ICANN's root. Anything that is not .pxd is passed through to the
ordinary internet, so a device or a whole network can use this as its only DNS server.

What it serves
  DNS on UDP and TCP :53            routers, PCs, Pi 5 droids, the Hackspace network
  DNS-over-HTTPS  /dns-query        phones and browsers (RFC 8484); works through a tunnel
  DNS-over-TLS    :853              Android "Private DNS" (needs --tls-cert/--tls-key)
  Web on :80                        http://mudforblood.pxd -> where the registry points
  /resolve?name=x.pxd               the registry entry as JSON, for apps and the PXD Browser
  /zone                             the .pxd zone as a standard zone file (BIND, Knot, CoreDNS)
  /pxd.mobileconfig                 one-tap iPhone/iPad/Mac profile (needs --public-url)
  /status                           names, hubs, serial, signature state

Names
  <name>.pxd           a name on the main hub, or on a sub-hub if the main hub doesn't have it
  <name>.<hub>.pxd     a name on a sub-hub, always (shop.eats.pxd)
  <anything>.<name>.pxd  subdomains follow their name
  TXT records carry the registry entry (to=, group=, world=, store=, sig=)

Trust
  With --authority pxd/authority.json the server checks names.json.sig (signed by the PXD
  authority key with `pxdsign.py registry-sign`) before using a registry, and never accepts
  a registry signed earlier than the one it already has. --require-signed refuses unsigned
  registries. Anyone can run a PXD root; nobody without the authority key can change it.

    python pxd2root.py                                    # :53 + :80 (administrator/sudo)
    python pxd2root.py --dns-port 5353 --web-port 8080    # test without admin
    python pxd2root.py --authority ../../pxd/authority.json --require-signed
    python pxd2root.py --export-zone zones/               # write pxd.zone and pxd2.zone, then exit
"""
import argparse, base64, hashlib, html, json, os, re, socket, socketserver, ssl, struct, sys, threading, time, urllib.parse, urllib.request, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN_REGISTRY = "https://pxd2.github.io/names.json"
LOCAL_REGISTRY = os.path.normpath(os.path.join(HERE, "..", "..", "names.json"))
STATE_DIR = os.path.join(os.path.expanduser("~"), ".pxd")
TLDS = ("pxd", "pxd2")
A, NS, CNAME, SOA, TXT, AAAA, OPT, ANY = 1, 2, 5, 6, 16, 28, 41, 255
TTL, NEG_TTL = 300, 60
KEY_OK = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)?$")
CFG = None
ZONE = None
ZLOCK = threading.Lock()


def log(msg):
    sys.stderr.write(time.strftime("%H:%M:%S ") + msg + "\n"); sys.stderr.flush()


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1)); return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


# ------------------------------------------------------------------ registry -> zone
def fetch(src, timeout=10):
    if os.path.isfile(src):
        return open(src, "rb").read()
    req = urllib.request.Request(src, headers={"User-Agent": "PXD-Root/2", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def load_registry(src):
    """(registry, trust) where trust is {'state': 'signed'|'unsigned', 'signed': iso or ''}."""
    raw = fetch(src)
    trust = {"state": "unsigned", "signed": ""}
    if CFG.authority:
        try:
            sig = json.loads(fetch(src + ".sig"))
        except Exception:
            sig = None
        if sig:
            import pxdsign
            ok, detail = pxdsign.verify_registry(raw, sig, CFG.authority)
            if not ok:
                raise ValueError("registry signature FAILED: " + detail)
            trust = {"state": "signed", "signed": detail}
    if CFG.require_signed and trust["state"] != "signed":
        raise ValueError("unsigned, and --require-signed is on")
    return json.loads(raw), trust


def absolute(base, to):
    if to.startswith(("http://", "https://", "mailto:")):
        return to
    return urllib.parse.urljoin(base, to)


class Zone:
    def __init__(self, names, hubs, source, trust, errors):
        self.names, self.hubs, self.source, self.trust, self.errors = names, hubs, source, trust, errors
        self.digest = hashlib.sha256(json.dumps(names, sort_keys=True).encode()).hexdigest()
        self.serial = 0
        self.loaded = time.strftime("%Y-%m-%dT%H:%M:%S")


def mirror_cache():
    try:
        return json.load(open(os.path.join(STATE_DIR, "root-mirrors.json")))
    except Exception:
        return []


def build_zone():
    errors, main, used, trust = [], None, "", None
    sources = CFG.registry + [m for m in mirror_cache() if m not in CFG.registry] + [LOCAL_REGISTRY]
    for src in sources:
        try:
            main, trust = load_registry(src); used = src; break
        except Exception as e:  # noqa: BLE001
            errors.append(f"{src}: {e}")
    if main is None:
        raise RuntimeError("no registry answered: " + " | ".join(errors))
    mirrors = (main.get("mirrors") or {}).get("registry") or []
    if mirrors:
        try:
            os.makedirs(STATE_DIR, exist_ok=True); json.dump(mirrors, open(os.path.join(STATE_DIR, "root-mirrors.json"), "w"))
        except OSError:
            pass
    base = main.get("base") or "https://pxd2.github.io/"
    main_id = (main.get("hubs") or [{"id": "pxd2"}])[0].get("id", "pxd2")
    names = {}
    for k, e in main.get("names", {}).items():
        if KEY_OK.match(k):
            names[k] = dict(e, hub=main_id, url=absolute(base, e.get("to", "/")))
    hubs = main.get("hubs", [])
    for h in hubs:
        reg, hid = h.get("registry", ""), h.get("id", "")
        if not reg or not KEY_OK.match(hid) or reg in (used, MAIN_REGISTRY) or hid == main_id:
            continue
        try:
            sub, _ = load_registry(reg)
        except Exception as e:  # noqa: BLE001  a sub-hub being down never breaks the root
            errors.append(f"hub {hid}: {e}"); continue
        for k, e in sub.get("names", {}).items():
            if not KEY_OK.match(k) or "." in k:
                continue
            ent = dict(e, hub=hid, url=absolute(reg, e.get("to", "/")))
            names[f"{k}.{hid}"] = ent
            names.setdefault(k, ent)
        names.setdefault(hid, {"title": h.get("name", hid), "hub": hid, "group": "Hubs",
                               "url": f"https://github.com/{h['repo']}" if h.get("repo") else reg})
    return Zone(names, hubs, used, trust, errors)


def refresh(first=False):
    global ZONE
    try:
        z = build_zone()
    except Exception as e:  # noqa: BLE001
        log(f"registry refresh failed, keeping the current zone: {e}")
        if first:
            raise
        return
    with ZLOCK:
        old = ZONE
        if old and old.trust["state"] == "signed" and (z.trust["state"] != "signed" or z.trust["signed"] < old.trust["signed"]):
            log(f"refused registry from {z.source}: older than, or less trusted than, the one in use"); return
        z.serial = old.serial if old and old.digest == z.digest else max((old.serial + 1) if old else 0, int(time.time()))
        ZONE = z
    if not old or old.digest != z.digest:
        log(f"zone serial {z.serial}: {len(z.names)} names, {max(len(z.hubs), 1)} hub(s), {z.trust['state']} registry from {z.source}"
            + (f"; {len(z.errors)} source problem(s)" if z.errors else ""))


def lookup(z, labels):
    """labels without the TLD -> (kind, value): apex, ns, name, or None."""
    if not labels:
        return "apex", None
    m = re.fullmatch(r"ns(\d+)", labels[0])
    if len(labels) == 1 and m and 1 <= int(m.group(1)) <= len(CFG.ns_ips):
        return "ns", CFG.ns_ips[int(m.group(1)) - 1]
    for i in range(len(labels)):  # longest registered suffix wins; anything left of it is a subdomain
        key = ".".join(labels[i:])
        if key in z.names:
            return "name", (key, z.names[key])
    return None, None


def txt_strings(key, e):
    store = e.get("store") or {}
    first = lambda v: (v[0] if isinstance(v, list) else v) if v else ""  # noqa: E731
    out = ["v=pxd1", f"name={key}", f"to={e.get('url', '')}"]
    for k in ("title", "group", "world", "hub"):
        if e.get(k):
            out.append(f"{k}={e[k]}")
    if store:
        out += [f"store={first(store.get('bundle'))}", f"sig={first(store.get('sig'))}"]
    return [s.encode()[:255] for s in out]


# ------------------------------------------------------------------ DNS wire format
class Query:
    __slots__ = ("id", "flags", "labels", "qtype", "qend", "edns", "opcode")


def parse(data):
    q = Query()
    q.id, q.flags, qd, _an, _ns, ar = struct.unpack(">HHHHHH", data[:12])
    if q.flags & 0x8000 or qd != 1:
        raise ValueError("not a single-question query")
    q.opcode, off, labels = (q.flags >> 11) & 0xF, 12, []
    while True:
        n = data[off]
        if n == 0:
            off += 1; break
        if n & 0xC0 or off + 1 + n > len(data):
            raise ValueError("bad name")
        labels.append(data[off + 1:off + 1 + n].decode("ascii").lower()); off += 1 + n
    q.qtype = struct.unpack(">H", data[off:off + 2])[0]
    struct.unpack(">H", data[off + 2:off + 4])
    q.labels, q.qend, q.edns = labels, off + 4, ar > 0
    return q


def enc_name(name):
    return b"".join(bytes([len(l)]) + l.encode() for l in name.split(".") if l) + b"\x00"


def rr(owner, rtype, ttl, rdata):
    return owner + struct.pack(">HHIH", rtype, 1, ttl, len(rdata)) + rdata


def soa_rdata(tld, serial):
    return enc_name(f"ns1.{tld}") + enc_name(f"hostmaster.{tld}") + struct.pack(">IIIII", serial, 3600, 600, 604800, NEG_TTL)


def message(q, data, rcode, answers=(), authority=(), aa=True):
    flags = 0x8000 | (0x0400 if aa else 0) | (q.flags & 0x0100) | 0x0080 | rcode
    out = struct.pack(">HHHHHH", q.id, flags, 1, len(answers), len(authority), 1 if q.edns else 0)
    out += data[12:q.qend] + b"".join(answers) + b"".join(authority)
    if q.edns:
        out += b"\x00" + struct.pack(">HHIH", OPT, 1232, 0, 0)
    return out


def truncated(q, data):
    return struct.pack(">HHHHHH", q.id, 0x8000 | 0x0400 | 0x0200 | (q.flags & 0x0100) | 0x0080, 1, 0, 0, 0) + data[12:q.qend]


def answer_pxd(q, data):
    with ZLOCK:
        z = ZONE
    tld, rest, t, owner = q.labels[-1], q.labels[:-1], q.qtype, b"\xc0\x0c"
    soa_auth = [rr(enc_name(tld), SOA, NEG_TTL, soa_rdata(tld, z.serial))]
    kind, val = lookup(z, rest)
    if kind is None:
        return message(q, data, 3, authority=soa_auth)
    ans = []
    edge_a = [rr(owner, A, TTL, socket.inet_aton(ip)) for ip in CFG.edge_ips] if t in (A, ANY) else []
    edge_aaaa = [rr(owner, AAAA, TTL, socket.inet_pton(socket.AF_INET6, ip)) for ip in CFG.edge_ips6] if t in (AAAA, ANY) else []
    if kind == "apex":
        if t in (SOA, ANY):
            ans.append(rr(owner, SOA, TTL, soa_rdata(tld, z.serial)))
        if t in (NS, ANY):
            ans += [rr(owner, NS, TTL, enc_name(f"ns{i + 1}.{tld}")) for i in range(len(CFG.ns_ips))]
        if t in (TXT, ANY):
            ans.append(rr(owner, TXT, TTL, b"".join(bytes([len(s)]) + s for s in
                       [b"v=pxd1", f"root=PXD Root Server 2".encode(), f"names={len(z.names)}".encode(), f"registry={z.trust['state']}".encode()])))
        ans += edge_a + edge_aaaa
    elif kind == "ns":
        if t in (A, ANY):
            ans.append(rr(owner, A, TTL, socket.inet_aton(val)))
    else:
        key, e = val
        ans += edge_a + edge_aaaa
        if t in (TXT, ANY):
            ans.append(rr(owner, TXT, TTL, b"".join(bytes([len(s)]) + s for s in txt_strings(key, e))))
    return message(q, data, 0, ans, [] if ans else soa_auth)


CACHE, CLOCK = {}, threading.Lock()


def recvn(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def tcp_ask(server, data):
    with socket.create_connection(server, timeout=4) as s:
        s.sendall(struct.pack(">H", len(data)) + data)
        n = recvn(s, 2)
        return recvn(s, struct.unpack(">H", n)[0]) if n else None


def forward(q, data):
    key = data[2:q.qend]
    with CLOCK:
        hit = CACHE.get(key)
    if hit and hit[0] > time.time():
        return data[:2] + hit[1][2:]
    for up in CFG.upstreams:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(3)
            try:
                s.sendto(data, up); resp = s.recv(65535)
            finally:
                s.close()
            if resp[:2] != data[:2]:
                continue
            if resp[2] & 0x02:  # truncated: ask again over TCP
                resp = tcp_ask(up, data) or resp
            if resp[3] & 0x0F in (0, 3):
                with CLOCK:
                    if len(CACHE) > 20000:
                        CACHE.clear()
                    CACHE[key] = (time.time() + 60, resp)
            return resp
        except OSError:
            continue
    return message(q, data, 2, aa=False)  # SERVFAIL: no upstream answered


def handle_query(data, limit=None):
    try:
        q = parse(data)
    except Exception:  # noqa: BLE001
        return None
    if q.opcode != 0:
        resp = message(q, data, 4, aa=False)
    elif q.labels and q.labels[-1] in TLDS:
        resp = answer_pxd(q, data)
    elif CFG.no_forward:
        resp = message(q, data, 5, aa=False)  # REFUSED: this root answers .pxd only
    else:
        resp = forward(q, data)
    if limit and len(resp) > (1232 if q.edns else 512):
        resp = truncated(q, data)
    return resp


class UDPDNS(socketserver.BaseRequestHandler):
    def handle(self):
        data, sock = self.request
        resp = handle_query(data, limit=True)
        if resp:
            sock.sendto(resp, self.client_address)


class TCPDNS(socketserver.BaseRequestHandler):
    def handle(self):
        sock = self.request
        try:
            if getattr(self.server, "tls", None):
                sock = self.server.tls.wrap_socket(sock, server_side=True)
            sock.settimeout(10)
            while True:
                n = recvn(sock, 2)
                if not n:
                    return
                data = recvn(sock, struct.unpack(">H", n)[0])
                resp = handle_query(data) if data else None
                if not resp:
                    return
                sock.sendall(struct.pack(">H", len(resp)) + resp)
        except (OSError, ssl.SSLError):
            return


class TCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address, daemon_threads = True, True


class UDPServer(socketserver.ThreadingUDPServer):
    allow_reuse_address, daemon_threads = True, True


# ------------------------------------------------------------------ zone file, profile
def zone_text(tld):
    with ZLOCK:
        z = ZONE
    q = lambda s: '"' + s.decode().replace("\\", "\\\\").replace('"', '\\"') + '"'  # noqa: E731
    lines = [f"; .{tld} zone from the PXD registry ({z.trust['state']}, {z.source})", f"$ORIGIN {tld}.", f"$TTL {TTL}",
             f"@ IN SOA ns1.{tld}. hostmaster.{tld}. ( {z.serial} 3600 600 604800 {NEG_TTL} )"]
    lines += [f"@ IN NS ns{i + 1}.{tld}." for i in range(len(CFG.ns_ips))]
    lines += [f"ns{i + 1} IN A {ip}" for i, ip in enumerate(CFG.ns_ips)]
    lines += [f"@ IN A {ip}" for ip in CFG.edge_ips] + [f"@ IN AAAA {ip}" for ip in CFG.edge_ips6]
    for key in sorted(z.names):
        for owner in (key, f"*.{key}"):
            lines += [f"{owner} IN A {ip}" for ip in CFG.edge_ips] + [f"{owner} IN AAAA {ip}" for ip in CFG.edge_ips6]
        lines.append(f"{key} IN TXT " + " ".join(q(s) for s in txt_strings(key, z.names[key])))
    return "\n".join(lines) + "\n"


def mobileconfig():
    url = CFG.public_url.rstrip("/") + "/dns-query"
    root_id = str(uuid.uuid5(uuid.NAMESPACE_URL, url)).upper()
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
 <key>PayloadContent</key><array><dict>
  <key>DNSSettings</key><dict><key>DNSProtocol</key><string>HTTPS</string><key>ServerURL</key><string>{html.escape(url)}</string></dict>
  <key>PayloadDisplayName</key><string>PXD Root DNS</string>
  <key>PayloadIdentifier</key><string>pxd.root.dns.settings</string>
  <key>PayloadType</key><string>com.apple.dnsSettings.managed</string>
  <key>PayloadUUID</key><string>{str(uuid.uuid5(uuid.NAMESPACE_URL, url + "#dns")).upper()}</string>
  <key>PayloadVersion</key><integer>1</integer>
 </dict></array>
 <key>PayloadDescription</key><string>Opens every .pxd name and keeps the rest of the internet working.</string>
 <key>PayloadDisplayName</key><string>PXD Root</string>
 <key>PayloadIdentifier</key><string>pxd.root</string>
 <key>PayloadType</key><string>Configuration</string>
 <key>PayloadUUID</key><string>{root_id}</string>
 <key>PayloadVersion</key><integer>1</integer>
</dict></plist>
"""


# ------------------------------------------------------------------ web: DoH, JSON, redirects
class Web(BaseHTTPRequestHandler):
    server_version = "PXD-Root/2"
    timeout = 15

    def _send(self, code, body, ctype="application/json", extra=None):
        data = body if isinstance(body, bytes) else (body.encode() if isinstance(body, str) else json.dumps(body, indent=2).encode())
        self.send_response(code)
        self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _doh(self, data):
        resp = handle_query(data or b"")
        if not resp:
            return self._send(400, {"error": "not a DNS query"})
        self._send(200, resp, "application/dns-message", {"Cache-Control": "max-age=60"})

    def do_POST(self):
        if self.path.split("?")[0] != "/dns-query":
            return self._send(404, {"error": "not found"})
        n = int(self.headers.get("Content-Length") or 0)
        self._doh(self.rfile.read(min(n, 65535)))

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        u = urllib.parse.urlsplit(self.path); qs = urllib.parse.parse_qs(u.query)
        host = (self.headers.get("Host") or "").split(":")[0].lower().rstrip(".")
        labels = host.split(".") if host else []
        if labels and labels[-1] in TLDS:
            return self._redirect(labels)
        if u.path == "/dns-query":
            try:
                s = qs["dns"][0]; data = base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
            except Exception:  # noqa: BLE001
                return self._send(400, {"error": "missing or bad ?dns="})
            return self._doh(data)
        if u.path == "/resolve":
            name = (qs.get("name") or [""])[0].lower().rstrip(".")
            parts = name.split(".")
            if not name or parts[-1] not in TLDS:
                return self._send(400, {"error": "name must end in .pxd; use /dns-query for every other name"})
            with ZLOCK:
                z = ZONE
            kind, val = lookup(z, parts[:-1])
            if kind != "name":
                return self._send(200, {"Status": 0 if kind else 3, "name": name, "serial": z.serial})
            return self._send(200, {"Status": 0, "name": name, "key": val[0], "serial": z.serial, "registry": z.trust["state"],
                                    "Answer": [{"name": name, "type": 1, "TTL": TTL, "data": ip} for ip in CFG.edge_ips], "pxd": val[1]})
        if u.path in ("/zone", "/pxd.zone", "/pxd2.zone"):
            return self._send(200, zone_text("pxd2" if "pxd2" in u.path else "pxd"), "text/plain; charset=utf-8")
        if u.path == "/pxd.mobileconfig":
            if not CFG.public_url:
                return self._send(404, {"error": "start the root with --public-url https://... to offer the profile"})
            return self._send(200, mobileconfig(), "application/x-apple-aspen-config",
                              {"Content-Disposition": 'attachment; filename="pxd.mobileconfig"'})
        if u.path in ("/", "/status"):
            with ZLOCK:
                z = ZONE
            return self._send(200, {"root": "PXD Root Server 2", "tlds": list(TLDS), "serial": z.serial, "names": len(z.names),
                                    "hubs": [h.get("id") for h in z.hubs], "registry": {"source": z.source, **z.trust},
                                    "loaded": z.loaded, "problems": z.errors, "edge": CFG.edge_ips + CFG.edge_ips6, "ns": CFG.ns_ips,
                                    "forwarding": not CFG.no_forward, "doh": "/dns-query"})
        return self._send(404, {"error": "not found"})

    def _redirect(self, labels):
        with ZLOCK:
            z = ZONE
        kind, val = lookup(z, labels[:-1])
        if kind == "name":
            self.send_response(302); self.send_header("Location", val[1]["url"]); self.end_headers(); return
        if kind == "apex":
            self.send_response(302); self.send_header("Location", "https://pxd2.github.io/names/"); self.end_headers(); return
        self._send(404, f"{'.'.join(labels)} is not registered. See https://pxd2.github.io/names/", "text/plain; charset=utf-8")

    def log_message(self, *a):
        pass


# ------------------------------------------------------------------ main
def main():
    global CFG
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--registry", action="append", help=f"registry URL or file, in order (default {MAIN_REGISTRY})")
    ap.add_argument("--authority", help="PXD authority PUBLIC record (pxd/authority.json): check registry signatures")
    ap.add_argument("--require-signed", action="store_true", help="refuse any registry without a valid authority signature")
    ap.add_argument("--edge-ip", action="append", default=[], help="IPv4 that .pxd names point to (default: this machine)")
    ap.add_argument("--edge-ip6", action="append", default=[], help="IPv6 that .pxd names point to")
    ap.add_argument("--ns-ip", action="append", default=[], help="IPv4 of each PXD root server, in order: ns1, ns2 ... (default: this machine)")
    ap.add_argument("--upstream", action="append", default=[], help="resolver for non-.pxd names (default 1.1.1.1, 9.9.9.9)")
    ap.add_argument("--no-forward", action="store_true", help="answer .pxd only; refuse everything else")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--dns-port", type=int, default=53); ap.add_argument("--web-port", type=int, default=80)
    ap.add_argument("--tls-cert"); ap.add_argument("--tls-key")
    ap.add_argument("--https-port", type=int, default=443); ap.add_argument("--dot-port", type=int, default=853)
    ap.add_argument("--public-url", default="", help="public https address of this root (for the iPhone profile)")
    ap.add_argument("--refresh", type=int, default=600, help="seconds between registry reloads")
    ap.add_argument("--export-zone", metavar="DIR", help="write pxd.zone and pxd2.zone to DIR, then exit")
    a = ap.parse_args()
    if a.authority:
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "pxdz"))
        a.authority = json.load(open(a.authority))
    elif a.require_signed:
        ap.error("--require-signed needs --authority")
    a.registry = a.registry or [MAIN_REGISTRY]
    a.edge_ips = a.edge_ip or [lan_ip()]; a.edge_ips6 = a.edge_ip6; a.ns_ips = a.ns_ip or [lan_ip()]
    a.upstreams = [(u.split(":")[0], int(u.split(":")[1]) if ":" in u else 53) for u in (a.upstream or ["1.1.1.1", "9.9.9.9"])]
    CFG = a
    try:
        refresh(first=True)
    except RuntimeError as e:
        raise SystemExit(f"PXD Root did not start: {e}")
    if a.export_zone:
        os.makedirs(a.export_zone, exist_ok=True)
        for t in TLDS:
            open(os.path.join(a.export_zone, f"{t}.zone"), "w", encoding="utf-8").write(zone_text(t))
        print(f"wrote {', '.join(t + '.zone' for t in TLDS)} to {a.export_zone} (serial {ZONE.serial}, {len(ZONE.names)} names)")
        return
    servers = [UDPServer((a.host, a.dns_port), UDPDNS), TCPServer((a.host, a.dns_port), TCPDNS)]
    webs = [ThreadingHTTPServer((a.host, a.web_port), Web)]
    if a.tls_cert:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.load_cert_chain(a.tls_cert, a.tls_key)
        dot = TCPServer((a.host, a.dot_port), TCPDNS); dot.tls = ctx; servers.append(dot)
        https = ThreadingHTTPServer((a.host, a.https_port), Web); https.socket = ctx.wrap_socket(https.socket, server_side=True, do_handshake_on_connect=False); webs.append(https)
    for s in servers + webs[1:]:
        threading.Thread(target=s.serve_forever, daemon=True).start()

    def tick():
        refresh(); t = threading.Timer(a.refresh, tick); t.daemon = True; t.start()
    t = threading.Timer(a.refresh, tick); t.daemon = True; t.start()
    print(f"PXD Root Server 2: {len(ZONE.names)} names under .{' .'.join(TLDS)} · serial {ZONE.serial} · registry {ZONE.trust['state']}")
    print(f"  DNS udp/tcp :{a.dns_port}  web + DoH :{a.web_port}/dns-query" + (f"  DoT :{a.dot_port}  HTTPS :{a.https_port}" if a.tls_cert else ""))
    print(f"  names point to {', '.join(a.edge_ips + a.edge_ips6)} · forwarding {'off' if a.no_forward else ', '.join(h for h, _ in a.upstreams)}")
    webs[0].serve_forever()


if __name__ == "__main__":
    main()
