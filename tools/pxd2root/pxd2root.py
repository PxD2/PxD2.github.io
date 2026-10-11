"""PXD2 Root: our own top-level domain, .pxd (alias .pxd2), run on our own machines.

Every name in names.json also answers as <name>.pxd (mudforblood.pxd,
hornetbell.pxd ...) on any device that uses PXD2's DNS: base1, the laptops,
the Pi 5 droids, the Hackspace network. Nobody else controls it and it never
renews. Public visitors use https://pxd2.github.io/<name> instead.

Run on base1 or a Pi (Python 3, no installs):
    python pxd2root.py                # DNS on :53 + web on :80 (needs admin/sudo)
    python pxd2root.py --dns-port 5353 --web-port 8080   # no admin, for testing
Then point a device's DNS at this machine's LAN IP.
"""
import argparse, json, os, socket, socketserver, struct, threading, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL_NAMES = os.path.join(HERE, "..", "..", "names.json")
REMOTE_NAMES = "https://pxd2.github.io/names.json"
SITE = "https://pxd2.github.io"
TLDS = ("pxd", "pxd2")  # .pxd is the house ending; .pxd2 kept as an alias
TLD = TLDS[0]

def load_names():
    try:
        with urllib.request.urlopen(REMOTE_NAMES, timeout=5) as r:
            return json.load(r)["names"]
    except Exception:
        with open(LOCAL_NAMES, encoding="utf-8") as f:
            return json.load(f)["names"]

def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1)); return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()

class Root:
    def __init__(self):
        self.names = load_names(); self.ip = lan_ip(); self.upstream = ("1.1.1.1", 53)
    def refresh(self):
        self.names = load_names()

ROOT = None

# ---------- DNS: answer *.pxd2 ourselves, forward everything else ----------
def parse_qname(data, off=12):
    labels = []
    while data[off]:
        n = data[off]; labels.append(data[off + 1:off + 1 + n].decode("ascii", "replace")); off += n + 1
    return ".".join(labels).lower(), off + 1

class DNS(socketserver.BaseRequestHandler):
    def handle(self):
        data, sock = self.request
        try:
            qname, end = parse_qname(data)
            qtype = struct.unpack(">H", data[end:end + 2])[0]
        except Exception:
            return
        parts = qname.split(".")
        if parts[-1] in TLDS:
            known = len(parts) >= 2 and parts[-2] in ROOT.names
            flags = 0x8580 if known else 0x8583  # authoritative answer / NXDOMAIN
            ans = 1 if known and qtype in (1, 255) else 0
            hdr = data[:2] + struct.pack(">HHHHH", flags, 1, ans, 0, 0)
            body = data[12:end + 4]
            if ans:
                body += b"\xc0\x0c" + struct.pack(">HHIH", 1, 1, 300, 4) + socket.inet_aton(ROOT.ip)
            sock.sendto(hdr + body, self.client_address); return
        up = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); up.settimeout(3)
        try:
            up.sendto(data, ROOT.upstream); sock.sendto(up.recv(4096), self.client_address)
        except Exception:
            pass
        finally:
            up.close()

# ---------- Web: mudforblood.pxd2 -> where names.json says ----------
class Web(BaseHTTPRequestHandler):
    def do_GET(self):
        host = (self.headers.get("Host") or "").split(":")[0].lower()
        tld = next((t for t in TLDS if host.endswith("." + t) or host == t), "")
        name = host[:-len(tld) - 1].split(".")[-1] if tld and host != tld else ""
        e = ROOT.names.get(name)
        if not e:
            if host in TLDS or not name:
                self.send_response(302); self.send_header("Location", SITE + "/names/"); self.end_headers(); return
            self.send_response(404); self.send_header("Content-Type", "text/plain"); self.end_headers()
            self.wfile.write(f"{host} is not registered. See {SITE}/names/".encode()); return
        to = e["to"]; to = to if to.startswith(("http", "mailto:")) else SITE + to
        self.send_response(302); self.send_header("Location", to); self.end_headers()
    def log_message(self, *a):
        pass

def main():
    global ROOT
    ap = argparse.ArgumentParser(description="PXD2 Root: the .pxd2 top-level domain on our own network")
    ap.add_argument("--dns-port", type=int, default=53); ap.add_argument("--web-port", type=int, default=80)
    a = ap.parse_args(); ROOT = Root()
    threading.Thread(target=socketserver.ThreadingUDPServer(("0.0.0.0", a.dns_port), DNS).serve_forever, daemon=True).start()
    def tick():
        ROOT.refresh(); threading.Timer(600, tick).start()
    threading.Timer(600, tick).start()
    print(f"PXD2 Root up: {len(ROOT.names)} names as <name>.{TLD} -> this machine {ROOT.ip}")
    print(f"DNS :{a.dns_port}  web :{a.web_port}  e.g. http://mudforblood.{TLD}/")
    HTTPServer(("0.0.0.0", a.web_port), Web).serve_forever()

if __name__ == "__main__":
    main()
