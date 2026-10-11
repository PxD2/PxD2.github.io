"""PXD over LoRa: order and pay from places with no internet, one radio packet at a time.

A buyer's phone or a Pi with a LoRa radio (Meshtastic) sends a signed ORDER frame. Any PXD relay
within mesh range that has internet checks it, places the order through the PXD Gateway and
answers with a signed RECEIPT: accepted, the exact USDC amount and the merchant's own address, or
"pay when you collect". A wallet can sign its payment offline; the signed transaction rides back
over LoRa in TX frames and the relay broadcasts it, then returns a RECEIPT with the transaction
hash. The relay never holds keys or coins: it carries signed messages.

Every frame fits one Meshtastic packet (233 bytes). Little-endian. Signatures: ECDSA P-256 over the
frame bytes before the signature (raw r||s, the same keys as PXD merchant certificates).

  byte 0: version (high nibble, 1) | type (low nibble)
  ORDER   1: nonce 6 | store 8 | method 1 | n 1 | n x (item 4, qty 1) | total_cents 4 | time 4 | buyer_pub 33 | sig 64
  RECEIPT 2: nonce 6 | status 1 | time 4 | flags 1 | [tx 32] | [units 8, chain 1, to 20] | relay sig 64
  TX      3: msg 4 | nonce 6 | chain 1 | seq 1 | count 1 | chunk (<= 219)      msg = SHA-256(raw tx)[:4]

store = SHA-256("type/region/store")[:8]; item = SHA-256(item id)[:4]

    python pxdlora.py keygen --out buyer.key.json
    python pxdlora.py order --key buyer.key.json --store eats/az-apache/demo-pizza --item pepperoni-16:2 \\
        --total 37.98 --method usdc:base                  # prints the frame as hex
    python pxdlora.py tx --raw 0x02f8... --nonce <order nonce hex> --chain base
    python pxdlora.py read <hex> [--relay-pub relay.pub.json]
    python pxdlora.py relay --key relay.key.json --gateway http://127.0.0.1:8790 --stdio            # hex lines in/out
    python pxdlora.py relay --key relay.key.json --gateway http://127.0.0.1:8790 --meshtastic COM5  # a real radio
"""
import argparse, hashlib, json, os, secrets, struct, sys, threading, time, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "pxdz"))
import pxdsign  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
from cryptography.hazmat.primitives import serialization  # noqa: E402

MAX = 233                      # Meshtastic DATA_PAYLOAD_LEN
VERSION = 1
ORDER, RECEIPT, TX = 1, 2, 3
METHODS = {0: "pickup", 1: "usdc:base", 2: "usdc:polygon", 3: "usdc:ethereum", 4: "usdc:arbitrum"}
CHAINS = {1: "base", 2: "polygon", 3: "ethereum", 4: "arbitrum"}
STATUS = {1: "accepted", 2: "pay", 3: "broadcast", 4: "paid", 8: "refused", 9: "bad signature"}
PORTNUM = 256                  # Meshtastic PRIVATE_APP
CHUNK = MAX - 14


def h8(s): return hashlib.sha256(s.encode()).digest()[:8]
def h4(s): return hashlib.sha256(s.encode()).digest()[:4]
def rev(d): return {v: k for k, v in d.items()}


def pub33(priv):
    return priv.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.CompressedPoint)


def from33(b):
    return ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), b)


def sign(priv, data):
    return pxdsign.ub64u(pxdsign.sign(priv, data))


def verify(pub, data, sig):
    return pxdsign.verify(pub, data, pxdsign.b64u(sig))


def load_key(path):
    return pxdsign.load_priv(json.load(open(path)))


# ------------------------------------------------------------------ frames
def make_order(priv, store, lines, total_cents, method, nonce=None, t=None):
    nonce = nonce or secrets.token_bytes(6)
    body = bytes([VERSION << 4 | ORDER]) + nonce + h8(store) + bytes([rev(METHODS)[method], len(lines)])
    body += b"".join(h4(item) + bytes([qty]) for item, qty in lines)
    body += struct.pack("<II", total_cents, int(t or time.time())) + pub33(priv)
    frame = body + sign(priv, body)
    if len(frame) > MAX:
        raise ValueError(f"order is {len(frame)} bytes; one LoRa packet holds {MAX}. Split it.")
    return frame


def make_receipt(priv, nonce, status, tx=None, pay=None, t=None):
    flags = (1 if tx else 0) | (2 if pay else 0)
    body = bytes([VERSION << 4 | RECEIPT]) + nonce + bytes([rev(STATUS)[status]]) + struct.pack("<I", int(t or time.time())) + bytes([flags])
    if tx:
        body += bytes.fromhex(tx[2:] if tx.startswith("0x") else tx)
    if pay:
        body += struct.pack("<Q", pay["units"]) + bytes([rev(CHAINS)[pay["chain"]]]) + bytes.fromhex(pay["to"][2:])
    return body + sign(priv, body)


def make_tx(raw, nonce, chain):
    msg = hashlib.sha256(raw).digest()[:4]
    parts = [raw[i:i + CHUNK] for i in range(0, len(raw), CHUNK)] or [b""]
    if len(parts) > 255:
        raise ValueError("transaction too large for LoRa")
    return [bytes([VERSION << 4 | TX]) + msg + nonce + bytes([rev(CHAINS)[chain], i, len(parts)]) + p for i, p in enumerate(parts)]


def parse(frame):
    if not frame or frame[0] >> 4 != VERSION:
        raise ValueError("not a PXD LoRa frame")
    t = frame[0] & 0x0F
    if t == ORDER:
        nonce, store, method, n = frame[1:7], frame[7:15], frame[15], frame[16]
        off = 17; lines = []
        for _ in range(n):
            lines.append((frame[off:off + 4], frame[off + 4])); off += 5
        total, ts = struct.unpack("<II", frame[off:off + 8]); off += 8
        pub = frame[off:off + 33]; off += 33
        body, sig = frame[:off], frame[off:off + 64]
        if len(sig) != 64 or len(frame) != off + 64:
            raise ValueError("truncated order")
        return {"type": "order", "nonce": nonce.hex(), "store": store, "method": METHODS.get(method, "?"), "lines": lines,
                "total_cents": total, "time": ts, "buyer": pub, "ok": verify(from33(pub), body, sig)}
    if t == RECEIPT:
        nonce, status, (ts,), flags = frame[1:7], frame[7], struct.unpack("<I", frame[8:12]), frame[12]
        off = 13; out = {"type": "receipt", "nonce": nonce.hex(), "status": STATUS.get(status, "?"), "time": ts}
        if flags & 1:
            out["tx"] = "0x" + frame[off:off + 32].hex(); off += 32
        if flags & 2:
            (units,) = struct.unpack("<Q", frame[off:off + 8]); out["pay"] = {"units": units, "amount": f"{units / 1e6:.6f}", "token": "USDC",
                                                                             "chain": CHAINS.get(frame[off + 8], "?"), "to": "0x" + frame[off + 9:off + 29].hex()}
            off += 29
        out["body"], out["sig"] = frame[:off], frame[off:off + 64]
        return out
    if t == TX:
        return {"type": "tx", "msg": frame[1:5], "nonce": frame[5:11].hex(), "chain": CHAINS.get(frame[11], "?"),
                "seq": frame[12], "count": frame[13], "chunk": frame[14:]}
    raise ValueError(f"unknown frame type {t}")


# ------------------------------------------------------------------ relay (an internet-connected mesh node)
class Relay:
    def __init__(self, key, gateway, rpc=None, max_age=86400):
        self.key, self.gw, self.rpc, self.max_age = key, gateway.rstrip("/"), rpc or {}, max_age
        self.seen, self.tx_parts, self.lock = {}, {}, threading.Lock()
        self.map = {}
        self.load_market()

    def get(self, path):
        with urllib.request.urlopen(self.gw + path, timeout=15) as r:
            return json.load(r)

    def load_market(self):
        """store/item hashes -> real addresses, from the gateway's market indexes."""
        top = self.get("/market/index.json")
        for t in top["types"]:
            for r in self.get(f"/market/{t['id']}/index.json")["regions"]:
                for s in self.get(f"/market/{t['id']}/{r['id']}/index.json")["stores"]:
                    addr = f"{s['type']}/{s['region']}/{s['name']}"
                    self.map[h8(addr)] = (s, {h4(i["id"]): i for i in s["items"]})

    def receipt(self, nonce, status, **kw):
        return make_receipt(self.key, bytes.fromhex(nonce), status, **kw)

    def handle(self, frame):
        f = parse(frame)
        if f["type"] == "order":
            if not f["ok"]:
                return [self.receipt(f["nonce"], "bad signature")]
            key = (f["buyer"], f["nonce"])
            with self.lock:
                if key in self.seen:            # the same packet heard twice (mesh repeats) gets the same answer
                    return [self.seen[key]]
            if abs(time.time() - f["time"]) > self.max_age or f["store"] not in self.map:
                return [self.receipt(f["nonce"], "refused")]
            s, items = self.map[f["store"]]
            try:
                lines = [{"type": s["type"], "region": s["region"], "store": s["name"], "item": items[i]["id"], "qty": q} for i, q in f["lines"]]
            except KeyError:
                return [self.receipt(f["nonce"], "refused")]
            req = urllib.request.Request(self.gw + "/api/checkout", data=json.dumps({"method": f["method"], "lines": lines}).encode(),
                                         headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    d = json.load(r)
            except urllib.error.HTTPError:
                return [self.receipt(f["nonce"], "refused")]
            c = d["checkouts"][0]
            if round(c["total"] * 100) != f["total_cents"]:   # the buyer saw an old price: refuse, they ask again
                out = self.receipt(f["nonce"], "refused")
            elif c.get("crypto"):
                cr = c["crypto"]; out = self.receipt(f["nonce"], "pay", pay={"units": cr["units"], "chain": cr["chain"], "to": cr["to"]})
            else:
                out = self.receipt(f["nonce"], "accepted")
            with self.lock:
                self.seen[key] = out
            return [out]
        if f["type"] == "tx":
            with self.lock:
                parts = self.tx_parts.setdefault(f["msg"], {})
                parts[f["seq"]] = f["chunk"]
                if len(parts) < f["count"]:
                    return []
                raw = b"".join(parts[i] for i in range(f["count"]))
                del self.tx_parts[f["msg"]]
            if hashlib.sha256(raw).digest()[:4] != f["msg"]:
                return [self.receipt(f["nonce"], "refused")]
            url = self.rpc.get(f["chain"])
            if not url:
                return [self.receipt(f["nonce"], "refused")]
            body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_sendRawTransaction", "params": ["0x" + raw.hex()]}).encode()
            with urllib.request.urlopen(urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}), timeout=20) as r:
                res = json.load(r)
            if "error" in res:
                return [self.receipt(f["nonce"], "refused")]
            return [self.receipt(f["nonce"], "broadcast", tx=res["result"])]
        return []


def run_stdio(relay):
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            for out in relay.handle(bytes.fromhex(line)):
                print(out.hex(), flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"# dropped frame: {e}", file=sys.stderr, flush=True)


def run_meshtastic(relay, port):
    """Untested without a radio: needs `pip install meshtastic` and a Meshtastic node on USB."""
    import meshtastic.serial_interface  # noqa: F401
    from pubsub import pub
    iface = meshtastic.serial_interface.SerialInterface(port)

    def on_receive(packet, interface):
        d = packet.get("decoded") or {}
        if d.get("portnum") not in ("PRIVATE_APP", PORTNUM):
            return
        try:
            for out in relay.handle(d["payload"]):
                interface.sendData(out, destinationId=packet["from"], portNum=PORTNUM)
        except Exception as e:  # noqa: BLE001
            print(f"dropped frame from {packet.get('fromId')}: {e}", file=sys.stderr)
    pub.subscribe(on_receive, "meshtastic.receive")
    print(f"PXD LoRa relay on {port}, port {PORTNUM}; Ctrl+C to stop")
    while True:
        time.sleep(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    k = sp.add_parser("keygen"); k.add_argument("--out", required=True)
    o = sp.add_parser("order"); o.add_argument("--key", required=True); o.add_argument("--store", required=True)
    o.add_argument("--item", action="append", required=True, help="item id[:qty]"); o.add_argument("--total", type=float, required=True)
    o.add_argument("--method", default="pickup", choices=list(METHODS.values()))
    t = sp.add_parser("tx"); t.add_argument("--raw", required=True); t.add_argument("--nonce", required=True); t.add_argument("--chain", default="base", choices=list(CHAINS.values()))
    r = sp.add_parser("read"); r.add_argument("hex"); r.add_argument("--relay-pub")
    y = sp.add_parser("relay"); y.add_argument("--key", required=True); y.add_argument("--gateway", required=True)
    y.add_argument("--rpc", action="append", default=[], help="chain=url for broadcasting transactions")
    g = y.add_mutually_exclusive_group(required=True); g.add_argument("--stdio", action="store_true"); g.add_argument("--meshtastic", metavar="PORT")
    a = ap.parse_args()
    if a.cmd == "keygen":
        pxdsign.merchant_key(a.out)
    elif a.cmd == "order":
        lines = [(i.split(":")[0], int(i.split(":")[1]) if ":" in i else 1) for i in a.item]
        f = make_order(load_key(a.key), a.store, lines, int(round(a.total * 100)), a.method)
        print(f.hex()); print(f"# {len(f)} bytes of {MAX}; nonce {f[1:7].hex()}", file=sys.stderr)
    elif a.cmd == "tx":
        for f in make_tx(bytes.fromhex(a.raw[2:] if a.raw.startswith("0x") else a.raw), bytes.fromhex(a.nonce), a.chain):
            print(f.hex())
    elif a.cmd == "read":
        f = parse(bytes.fromhex(a.hex))
        if f["type"] == "receipt":
            ok = None
            if a.relay_pub:
                ok = verify(pxdsign.load_pub(json.load(open(a.relay_pub))), f["body"], f["sig"])
            f = {k: v for k, v in f.items() if k not in ("body", "sig")} | ({"relay_signature_ok": ok} if ok is not None else {})
        print(json.dumps({k: (v.hex() if isinstance(v, bytes) else v) for k, v in f.items() if k != "lines"}, indent=1))
    elif a.cmd == "relay":
        relay = Relay(load_key(a.key), a.gateway, dict(x.split("=", 1) for x in a.rpc))
        print(f"# relay ready: {len(relay.map)} store(s) reachable", file=sys.stderr, flush=True)
        run_stdio(relay) if a.stdio else run_meshtastic(relay, a.meshtastic)


if __name__ == "__main__":
    main()
