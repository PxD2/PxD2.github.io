"""PXD Net2: the personal kit for the clean second web.

Everyone downloads three things once:
  1. a personal kit       their own encrypt/decrypt keys (X25519) and signing key (Ed25519), locked with a passphrase
  2. the dictionary       the PXD shared dictionary (built from .pxd data, published on GitHub, numbered, never changed)
  3. contacts             other people's public kits (a 40-byte card each)
After that, what crosses the wire is only what the receiver doesn't already know, sealed so only they can read it.

Two ways to send:
  seal / open     one message to one person: dictionary-compressed, encrypted to them, provably from you
  Session         a live link (chat, orders, telemetry, game state): one handshake, then each frame carries only
                  what changed since the last one, ~20 bytes of overhead, a fresh key per direction, replay refused

    python tools/net2/net2.py kit --out me.n2kit                 # make your kit (asks for a passphrase)
    python tools/net2/net2.py card me.n2kit                      # your public card, to give people
    python tools/net2/net2.py seal me.n2kit --to friend.n2card msg.txt -o msg.n2
    python tools/net2/net2.py open me.n2kit --from friend.n2card msg.n2
    python tools/net2/net2.py dict-build                         # rebuild the shared dictionary from the site
    python tools/net2/net2.py bench                              # bytes on the wire: raw vs gzip vs Net2
"""
import argparse, base64, getpass, hashlib, json, os, random, struct, sys, zlib

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.exceptions import InvalidTag

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(os.path.dirname(HERE))
DICTS = os.path.join(HERE, "dicts")
VERSION = 1
RAW = serialization.Encoding.Raw
PUB = serialization.PublicFormat.Raw
PRIV = serialization.PrivateFormat.Raw
NOENC = serialization.NoEncryption()


# ------------------------------------------------------------------ dictionary
def dict_path(did):
    return os.path.join(DICTS, f"pxd-{did}.n2dict")


def load_dict(did):
    """The shared dictionary by number. Its SHA-256 is in dicts/index.json, so a swapped file is refused."""
    if did == 0:
        return b""
    data = open(dict_path(did), "rb").read()
    idx = json.load(open(os.path.join(DICTS, "index.json")))
    want = idx["dicts"][str(did)]["sha256"]
    if hashlib.sha256(data).hexdigest() != want:
        raise ValueError(f"dictionary {did} does not match its published hash")
    return data


def latest_dict():
    try:
        idx = json.load(open(os.path.join(DICTS, "index.json")))
        return max(int(k) for k in idx["dicts"])
    except (OSError, ValueError, KeyError):
        return 0


def corpus_files(exclude=()):
    keep = (".json", ".html", ".js", ".txt", ".md", ".csv")
    skip_dirs = {".git", "node_modules", "reports", "dicts", "vendor", "assets", "certs", "exports", "cad", "cad2", "pxd2cad", "opencad"}
    for d, dirs, fs in os.walk(SITE):
        dirs[:] = sorted(x for x in dirs if x not in skip_dirs and not x.startswith("."))
        for f in sorted(fs):
            p = os.path.join(d, f)
            if f.endswith(keep) and p not in exclude and os.path.getsize(p) < 400_000 and not f.endswith(".min.js"):
                yield p


def build_dict(files, size=32768, kind="web"):
    """Pick the phrases that recur most across PXD data and pack them into zlib's 32 KB preset window,
    most valuable last (zlib reaches the end of the dictionary most cheaply)."""
    import re, collections
    cnt = collections.Counter()
    splitter = re.compile(r'(?<=[>\n,;{}\]])|(?=[<\n{\[])') if kind == "web" else re.compile(r'(?<=[,{}\[\]\n])|(?=[{}\[\]\n])|(?<=":)|(?<=": )')
    for p in files:
        try:
            t = open(p, encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            continue
        seen = set()
        for piece in splitter.split(t):
            piece = piece.strip(" \t") if kind == "web" else piece.strip()
            if (6 if kind == "web" else 3) <= len(piece) <= 160 and piece not in seen:
                seen.add(piece); cnt[piece] += 1                 # count each phrase once per file: shared, not repeated
    scored = sorted(((c * len(s), s) for s, c in cnt.items() if c >= 3), reverse=True)
    out, total = [], 0
    for _, s in scored:
        b = s.encode("utf-8")
        if total + len(b) + 1 > size:
            continue
        out.append(b); total += len(b) + 1
    return b"\n".join(reversed(out))


# ------------------------------------------------------------------ compression (the dictionary layer)
def pack(data, zd):
    c = zlib.compressobj(9, zlib.DEFLATED, -15, 9, zlib.Z_DEFAULT_STRATEGY, zd) if zd else zlib.compressobj(9, zlib.DEFLATED, -15)
    return c.compress(data) + c.flush()


def unpack(blob, zd):
    d = zlib.decompressobj(-15, zd) if zd else zlib.decompressobj(-15)
    out = d.decompress(blob, 64 * 2**20)
    if d.unconsumed_tail:
        raise ValueError("message expands past 64 MB")
    return out + d.flush()


# ------------------------------------------------------------------ the personal kit
class Kit:
    """Your private kit: box key (X25519) to receive, sign key (Ed25519) to prove it's you."""

    def __init__(self, box=None, sign=None, name=""):
        self.box = box or X25519PrivateKey.generate()
        self.sign = sign or Ed25519PrivateKey.generate()
        self.name = name

    def card(self):
        return Card(self.box.public_key().public_bytes(RAW, PUB), self.sign.public_key().public_bytes(RAW, PUB), self.name)

    def save(self, path, passphrase):
        salt = os.urandom(16)
        key = Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(passphrase.encode())
        secret = self.box.private_bytes(RAW, PRIV, NOENC) + self.sign.private_bytes(RAW, PRIV, NOENC)
        nonce = os.urandom(12)
        doc = {"type": "pxd-net2-kit/1", "name": self.name, "card": self.card().text(),
               "lock": {"kdf": "scrypt", "n": 2**15, "r": 8, "p": 1, "salt": b64(salt), "nonce": b64(nonce)},
               "secret": b64(ChaCha20Poly1305(key).encrypt(nonce, secret, b"pxd-net2-kit"))}
        with open(path, "w") as f:
            json.dump(doc, f, indent=2)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    @classmethod
    def load(cls, path, passphrase):
        doc = json.load(open(path))
        L = doc["lock"]
        key = Scrypt(salt=ub64(L["salt"]), length=32, n=L["n"], r=L["r"], p=L["p"]).derive(passphrase.encode())
        try:
            s = ChaCha20Poly1305(key).decrypt(ub64(L["nonce"]), ub64(doc["secret"]), b"pxd-net2-kit")
        except InvalidTag:
            raise ValueError("wrong passphrase for this kit") from None
        return cls(X25519PrivateKey.from_private_bytes(s[:32]), Ed25519PrivateKey.from_private_bytes(s[32:]), doc.get("name", ""))


class Card:
    """The public half: 64 bytes, shared freely. Its first 8 bytes of SHA-256 are the person's Net2 id."""

    def __init__(self, box_pub, sign_pub, name=""):
        self.box_pub, self.sign_pub, self.name = box_pub, sign_pub, name
        self.id = hashlib.sha256(box_pub + sign_pub).digest()[:8]

    def text(self):
        return "n2:" + b64(self.box_pub + self.sign_pub) + (":" + self.name if self.name else "")

    @classmethod
    def parse(cls, s):
        s = s.strip()
        if s.startswith("{"):
            s = json.loads(s)["card"]
        parts = s.split(":", 2)
        if parts[0] != "n2":
            raise ValueError("not a Net2 card")
        raw = ub64(parts[1])
        return cls(raw[:32], raw[32:64], parts[2] if len(parts) > 2 else "")


def b64(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def ub64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def hkdf(material, info, n=32):
    return HKDF(algorithm=hashes.SHA256(), length=n, salt=b"pxd-net2-v1", info=info).derive(material)


# ------------------------------------------------------------------ one message to one person
# frame: 'N' | ver | dict u16 | sender id 8 | ephemeral pub 32 | ciphertext+tag(16)      (nonce derived, never sent)
HDR = struct.Struct(">cBH8s32s")


def published_dicts():
    try:
        return sorted(int(k) for k in json.load(open(os.path.join(DICTS, "index.json")))["dicts"])
    except (OSError, ValueError, KeyError):
        return []


def best_dict(data):
    """Try every published dictionary (and none); keep whichever makes this message smallest."""
    best = (len(pack(data, b"")), 0)
    for did in published_dicts():
        best = min(best, (len(pack(data, load_dict(did))), did))
    return best[1]


def seal(kit, to, data, did=None):
    did = best_dict(data) if did is None else did
    zd = load_dict(did)
    eph = X25519PrivateKey.generate(); eph_pub = eph.public_key().public_bytes(RAW, PUB)
    to_box = X25519PublicKey.from_public_bytes(to.box_pub)
    me = kit.card()
    # ephemeral-static gives forward secrecy for the message; static-static proves it came from the sender's kit
    secret = eph.exchange(to_box) + kit.box.exchange(to_box)
    head = HDR.pack(b"N", VERSION, did, me.id, eph_pub)
    k = hkdf(secret + head, b"seal", 44)
    return head + ChaCha20Poly1305(k[:32]).encrypt(k[32:], pack(data, zd), head)


def open_sealed(kit, frm, blob):
    if len(blob) < HDR.size + 16 or blob[:1] != b"N":
        raise ValueError("not a Net2 message")
    _, ver, did, sid, eph_pub = HDR.unpack(blob[:HDR.size])
    if ver != VERSION:
        raise ValueError(f"Net2 version {ver} not supported")
    if sid != frm.id:
        raise ValueError("this message says it is from someone else")
    head = blob[:HDR.size]
    secret = kit.box.exchange(X25519PublicKey.from_public_bytes(eph_pub)) + kit.box.exchange(X25519PublicKey.from_public_bytes(frm.box_pub))
    k = hkdf(secret + head, b"seal", 44)
    try:
        packed = ChaCha20Poly1305(k[:32]).decrypt(k[32:], blob[HDR.size:], head)
    except InvalidTag:
        raise ValueError("message was changed, or is not from this person, or not for you") from None
    return unpack(packed, load_dict(did))


# ------------------------------------------------------------------ a live link
class Session:
    """One handshake, then frames. Each frame: varint counter + ciphertext + 16-byte tag.
    Compression runs across the whole session (the dictionary first, then everything already said),
    so a frame that repeats the shape of earlier ones costs only the part that changed."""

    def __init__(self, kit, peer, initiator, did=None):
        self.kit, self.peer, self.initiator = kit, peer, initiator
        self.did = latest_dict() if did is None else did
        self.eph = X25519PrivateKey.generate()
        self.hello_out = HDR.pack(b"H", VERSION, self.did, kit.card().id, self.eph.public_key().public_bytes(RAW, PUB))
        self.tx = self.rx = None

    def hello(self):
        return self.hello_out

    def accept(self, hello_in):
        mark, ver, did, sid, eph_pub = HDR.unpack(hello_in[:HDR.size])
        if mark != b"H" or ver != VERSION or sid != self.peer.id or did != self.did:
            raise ValueError("handshake refused (wrong person, version or dictionary)")
        peer_box = X25519PublicKey.from_public_bytes(self.peer.box_pub)
        theirs = X25519PublicKey.from_public_bytes(eph_pub)
        a, b = (self.hello_out, hello_in) if self.initiator else (hello_in, self.hello_out)
        # both ephemerals (forward secrecy) + each side's static key against the other's ephemeral (proves who)
        es1 = self.eph.exchange(peer_box) if self.initiator else self.kit.box.exchange(theirs)
        es2 = self.kit.box.exchange(theirs) if self.initiator else self.eph.exchange(peer_box)
        keys = hkdf(self.eph.exchange(theirs) + es1 + es2 + a + b, b"session", 64)
        k_i, k_r = keys[:32], keys[32:]
        self.tx = ChaCha20Poly1305(k_i if self.initiator else k_r)
        self.rx = ChaCha20Poly1305(k_r if self.initiator else k_i)
        zd = load_dict(self.did)
        self.c = zlib.compressobj(9, zlib.DEFLATED, -15, 9, zlib.Z_DEFAULT_STRATEGY, zd) if zd else zlib.compressobj(9, zlib.DEFLATED, -15)
        self.d = zlib.decompressobj(-15, zd) if zd else zlib.decompressobj(-15)
        self.n_tx = self.n_rx = 0

    @staticmethod
    def _varint(n):
        out = bytearray()
        while True:
            b = n & 0x7F; n >>= 7
            out.append(b | (0x80 if n else 0))
            if not n:
                return bytes(out)

    def send(self, data):
        z = self.c.compress(data) + self.c.flush(zlib.Z_SYNC_FLUSH)
        z = z[:-4]                                   # every sync flush ends 00 00 FF FF: both sides know it, so it never travels
        ctr = self._varint(self.n_tx)
        frame = ctr + self.tx.encrypt(struct.pack(">4xQ", self.n_tx), z, ctr)
        self.n_tx += 1
        return frame

    def recv(self, frame):
        n, i = 0, 0
        while True:
            b = frame[i]; n |= (b & 0x7F) << (7 * i); i += 1
            if not b & 0x80:
                break
        if n != self.n_rx:
            raise ValueError(f"frame {n} out of order or replayed (expected {self.n_rx})")
        try:
            z = self.rx.decrypt(struct.pack(">4xQ", n), frame[i:], frame[:i])
        except InvalidTag:
            raise ValueError("frame was changed in transit") from None
        self.n_rx += 1
        return self.d.decompress(z + b"\x00\x00\xff\xff")


# ------------------------------------------------------------------ bench
def bench():
    """Bytes on the wire for real PXD traffic, on files the dictionary was NOT built from."""
    rnd = random.Random(7)
    files = list(corpus_files())
    rnd.shuffle(files)
    held = set(files[:max(30, len(files) // 10)])
    train = [f for f in files if f not in held]
    zd = build_dict([f for f in train if not f.endswith(".json")], kind="web")
    zj = build_dict([f for f in train if f.endswith(".json")], kind="data")
    alice, bob = Kit(name="alice"), Kit(name="bob")

    def gz(b):
        return len(zlib.compress(b, 9))

    samples = []
    jsonish = [f for f in held if f.endswith(".json") and 200 < os.path.getsize(f) < 60000][:12]
    pages = [f for f in held if f.endswith(".html") and 2000 < os.path.getsize(f) < 120000][:12]
    for f in jsonish + pages:
        samples.append((os.path.relpath(f, SITE), open(f, "rb").read()))
    msgs = [("chat: short", b"On my way, be there in 20. Bring the QR sign for Bear Wallow."),
            ("order: restaurant", json.dumps({"type": "order", "store": "demodiner.pxd", "items": [{"sku": "burger-classic", "qty": 2, "mods": ["no onion"]}, {"sku": "fries-large", "qty": 1}], "pickup": "18:30", "pay": "card"}).encode()),
            ("store item", json.dumps({"code": "BW-0042", "title": "Oak washstand with mirror", "price": 185, "condition": "good", "room": "front-room", "tags": ["furniture", "oak", "antique"], "photo": "photos/bw-0042.jpg"}).encode())]
    rows = []
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        global DICTS
        old = DICTS; DICTS = td
        open(dict_path(1), "wb").write(zd); open(dict_path(2), "wb").write(zj)
        json.dump({"dicts": {"1": {"sha256": hashlib.sha256(zd).hexdigest()}, "2": {"sha256": hashlib.sha256(zj).hexdigest()}}},
                  open(os.path.join(td, "index.json"), "w"))
        try:
            for name, data in msgs + samples:
                sealed = seal(alice, bob.card(), data)
                assert open_sealed(bob, alice.card(), sealed) == data
                rows.append({"what": name, "raw": len(data), "gzip": gz(data), "net2_sealed": len(sealed),
                             "net2_payload": len(sealed) - HDR.size - 16})
            # live link: 200 order-status frames that keep the same shape
            A, B = Session(alice, bob.card(), True, did=2), Session(bob, alice.card(), False, did=2)
            A.accept(B.hello()); B.accept(A.hello())
            raw = wire = gzsum = 0
            for i in range(200):
                m = json.dumps({"type": "status", "order": f"DD-{1000 + i}", "store": "demodiner.pxd", "state": rnd.choice(["received", "cooking", "ready"]),
                                "eta_min": rnd.randint(1, 25), "items": 2 + i % 3}).encode()
                fr = A.send(m); assert B.recv(fr) == m
                raw += len(m); wire += len(fr); gzsum += gz(m)
            rows.append({"what": "live link: 200 order updates", "raw": raw, "gzip": gzsum, "net2_sealed": wire + 2 * HDR.size, "net2_payload": wire})
        finally:
            DICTS = old
    print(f"dictionaries: web {len(zd)} B, data {len(zj)} B, built from {len(files) - len(held)} site files; measured on {len(held)} held-out files\n")
    print(f"{'what':44} {'raw':>8} {'gzip':>8} {'Net2':>8}  {'vs raw':>7} {'vs gzip':>7}")
    for r in rows:
        print(f"{r['what'][:44]:44} {r['raw']:>8} {r['gzip']:>8} {r['net2_sealed']:>8}  {100 * r['net2_sealed'] / r['raw']:>6.1f}% {100 * r['net2_sealed'] / r['gzip']:>6.1f}%")
    tr = sum(r["raw"] for r in rows); tg = sum(r["gzip"] for r in rows); tn = sum(r["net2_sealed"] for r in rows)
    print(f"{'TOTAL':44} {tr:>8} {tg:>8} {tn:>8}  {100 * tn / tr:>6.1f}% {100 * tn / tg:>6.1f}%")
    print("Net2 column is the full sealed message: encrypted, authenticated, header included.")
    return rows


# ------------------------------------------------------------------ CLI
def ask_pass(confirm=False):
    p = os.environ.get("NET2_PASS") or getpass.getpass("Kit passphrase: ")
    if confirm and not os.environ.get("NET2_PASS") and getpass.getpass("Again: ") != p:
        raise SystemExit("passphrases differ")
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    k = sp.add_parser("kit"); k.add_argument("--out", required=True); k.add_argument("--name", default="")
    c = sp.add_parser("card"); c.add_argument("kit")
    s = sp.add_parser("seal"); s.add_argument("kit"); s.add_argument("--to", required=True); s.add_argument("file"); s.add_argument("-o", "--out", required=True)
    o = sp.add_parser("open"); o.add_argument("kit"); o.add_argument("--from", dest="frm", required=True); o.add_argument("file"); o.add_argument("-o", "--out")
    sp.add_parser("dict-build"); sp.add_parser("bench")
    a = ap.parse_args()
    if a.cmd == "kit":
        if os.path.exists(a.out):
            raise SystemExit(f"{a.out} exists; a kit is never overwritten")
        kt = Kit(name=a.name); kt.save(a.out, ask_pass(True))
        card = a.out.rsplit(".", 1)[0] + ".n2card"
        open(card, "w").write(kt.card().text() + "\n")
        print(f"kit {a.out} (keep it, back it up, never share it)\ncard {card} (give this to people): {kt.card().text()}")
    elif a.cmd == "card":
        print(json.load(open(a.kit))["card"])
    elif a.cmd == "seal":
        kt = Kit.load(a.kit, ask_pass()); to = Card.parse(open(a.to).read())
        data = open(a.file, "rb").read(); blob = seal(kt, to, data)
        open(a.out, "wb").write(blob)
        print(f"{len(data)} bytes -> {len(blob)} bytes sealed for {to.name or to.id.hex()}")
    elif a.cmd == "open":
        kt = Kit.load(a.kit, ask_pass()); frm = Card.parse(open(a.frm).read())
        data = open_sealed(kt, frm, open(a.file, "rb").read())
        if a.out:
            open(a.out, "wb").write(data); print(f"opened {len(data)} bytes -> {a.out}")
        else:
            sys.stdout.buffer.write(data)
    elif a.cmd == "dict-build":
        os.makedirs(DICTS, exist_ok=True)
        allf = list(corpus_files())
        ip = os.path.join(DICTS, "index.json")
        idx = json.load(open(ip)) if os.path.exists(ip) else {"dicts": {}}
        for kind, fs in (("web", [f for f in allf if not f.endswith(".json")]), ("data", [f for f in allf if f.endswith(".json")])):
            zd = build_dict(fs, kind=kind)
            did = latest_dict() + 1
            open(dict_path(did), "wb").write(zd)
            idx["dicts"][str(did)] = {"kind": kind, "sha256": hashlib.sha256(zd).hexdigest(), "bytes": len(zd),
                                      "built": __import__("datetime").date.today().isoformat()}
            json.dump(idx, open(ip, "w"), indent=2)
            print(f"dictionary {did} ({kind}): {len(zd)} bytes (published dictionaries never change; new data makes a new number)")
    elif a.cmd == "bench":
        bench()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, FileNotFoundError) as e:
        raise SystemExit(f"Net2: {e}")
