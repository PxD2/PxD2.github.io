"""PXDZ — the .pxd data format.

One file carries a whole site or dataset: COG-coded text, compressed data, 3D models and a
full SQL database, each part hashed, optionally encrypted for private clients.

    python pxdz.py pack <folder> -o site.pxdz [--book hub.json] [--public-book DIR] [--key PASSPHRASE]
    python pxdz.py sql catalog.json -o data.db          # JSON catalog -> SQLite tables
    python pxdz.py inspect site.pxdz
    python pxdz.py unpack site.pxdz -o outdir [--key PASSPHRASE]

Layout:  "PXDZ" | u8 version | u32 manifest length (LE) | manifest JSON | part blobs
Each part: codec pipeline applied in order on pack (cog -> deflate -> aes), reversed on read;
sha256 of the original bytes is stored, so every unpack is verified bit for bit.

COG text: sentences become (meaning.variant) addresses into append-only books. Sentences already
in the public COG library use its numbers; everything else goes to the hub book ("h" addresses).
A private client's hub book never enters the public library.
"""
import argparse, base64, hashlib, json, os, re, sqlite3, struct, sys, time, zlib

MAGIC, VERSION = b"PXDZ", 1
TEXT_EXT = {".json", ".txt", ".md"}
DEFLATE_EXT = {".html", ".htm", ".css", ".js", ".svg", ".csv", ".xml", ".json", ".txt", ".md", ".db", ".sqlite", ".glb", ".gltf", ".bin", ".obj"}
SENT = re.compile(r"(?<=[.!?])(\s+)(?=[A-Z0-9\"'(])")
MARK = "§cog:"           # a JSON string value replaced by COG addresses


# ------------------------------------------------------------------ books (append-only)
class Book:
    """Hub book: rows [meaning, [start], [variants]]; addresses 'h<m>.<v>'. Never rewrites an id."""
    def __init__(self, path=None, book_id="hub"):
        self.path, self.id, self.rows, self.index = path, book_id, [], {}
        if path and os.path.isfile(path):
            d = json.load(open(path, encoding="utf-8")); self.id = d.get("id", book_id); self.rows = d["rows"]
        for m, start, vs in self.rows:
            for i, s in enumerate(vs):
                self.index[s] = f"h{m}.{start[0] + i}"
        self.added = 0

    def address(self, sentence):
        a = self.index.get(sentence)
        if a:
            return a
        m = len(self.rows) + 1
        self.rows.append([m, [0], [sentence]]); a = f"h{m}.0"; self.index[sentence] = a; self.added += 1
        return a

    def lookup(self):
        return {f"h{m}.{start[0] + i}": s for m, start, vs in self.rows for i, s in enumerate(vs)}

    def save(self):
        if self.path:
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
            json.dump({"id": self.id, "format": "cog-book/hub", "rows": self.rows}, open(self.path, "w", encoding="utf-8"),
                      ensure_ascii=False, separators=(",", ":"))

    def digest(self):
        return hashlib.sha256(json.dumps(self.rows, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def load_public(dirpath):
    """Exact-sentence index of the public COG library (books/core-m-*.json)."""
    idx = {}
    if not dirpath or not os.path.isdir(dirpath):
        return idx
    for f in sorted(os.listdir(dirpath)):
        if f.startswith("core-m-") and f.endswith(".json"):
            for r in json.load(open(os.path.join(dirpath, f), encoding="utf-8"))["s"]:
                for i, s in enumerate(r[3]):
                    idx.setdefault(s, f"{r[0]}.{r[2][0] + i}")
    return idx


# ------------------------------------------------------------------ COG text codec (lossless)
def cog_encode_text(text, book, public):
    """Sentences -> addresses. Separators: ' ' implicit, '\\n\\n' -> '|', anything else -> '~' + JSON."""
    parts = SENT.split(text)
    out = []
    for i, piece in enumerate(parts):
        if i % 2:  # separator
            out.append("" if piece == " " else "|" if piece == "\n\n" else "~" + json.dumps(piece).replace(" ", "\\u0020"))
        else:
            if not piece:
                out.append("=")
                continue
            out.append(public.get(piece) or book.address(piece))
    return " ".join(t for t in out if t)


def cog_decode_text(code, lookup):
    toks, sep_next = code.split(" "), False
    res = []
    for t in toks:
        if t == "|":
            res.append("\n\n"); sep_next = False; continue
        if t.startswith("~"):
            res.append(json.loads(t[1:])); sep_next = False; continue
        if res and sep_next:
            res.append(" ")
        res.append("" if t == "=" else lookup[t])
        sep_next = True
    return "".join(res)


def _norm(o):
    """JSON has one number type: 89.0 and 89 are the same value (matches JavaScript)."""
    if isinstance(o, float) and o.is_integer():
        return int(o)
    if isinstance(o, list):
        return [_norm(v) for v in o]
    if isinstance(o, dict):
        return {k: _norm(v) for k, v in o.items()}
    return o


def canon(obj):
    return hashlib.sha256(json.dumps(_norm(obj), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def cog_json(obj, book, public, stats):
    if isinstance(obj, dict):
        return {k: cog_json(v, book, public, stats) for k, v in obj.items()}
    if isinstance(obj, list):
        return [cog_json(v, book, public, stats) for v in obj]
    if isinstance(obj, str) and len(obj) >= 40 and " " in obj and not obj.startswith(("http", "models/", "/", MARK)):
        code = cog_encode_text(obj, book, public)
        if code and cog_decode_text(code, {**{v: k for k, v in public.items()}, **book.lookup()}) == obj:
            stats["strings"] += 1
            return MARK + code
    return obj


def uncog_json(obj, lookup):
    if isinstance(obj, dict):
        return {k: uncog_json(v, lookup) for k, v in obj.items()}
    if isinstance(obj, list):
        return [uncog_json(v, lookup) for v in obj]
    if isinstance(obj, str) and obj.startswith(MARK):
        return cog_decode_text(obj[len(MARK):], lookup)
    return obj


# ------------------------------------------------------------------ encryption (AES-256-GCM, PBKDF2-SHA256)
def derive(passphrase, salt, iters=200_000):
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode(), salt, iters, 32)


def seal(data, key):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = os.urandom(12)
    return nonce + AESGCM(key).encrypt(nonce, data, None)


def unseal(data, key):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.exceptions import InvalidTag
    try:
        return AESGCM(key).decrypt(data[:12], data[12:], None)
    except InvalidTag:
        raise SystemExit("Wrong key, or the bundle was altered: AES-GCM authentication failed.")


# ------------------------------------------------------------------ pack / read
def deflate(b):
    c = zlib.compressobj(9, zlib.DEFLATED, -15)  # raw deflate: browsers inflate it natively ("deflate-raw")
    return c.compress(b) + c.flush()


def inflate(b):
    return zlib.decompress(b, -15)


def pack(folder, out, book_path=None, public_dir=None, passphrase=None, name=None):
    book, public = Book(book_path, book_id=os.path.splitext(os.path.basename(book_path or "hub"))[0]), load_public(public_dir)
    pub_rev = {}
    enc, key = None, None
    if passphrase:
        salt = os.urandom(16); key = derive(passphrase, salt)
        enc = {"alg": "AES-256-GCM", "kdf": "PBKDF2-SHA256", "iter": 200_000, "salt": base64.b64encode(salt).decode()}
    parts, blobs, offset, stats = [], [], 0, {"strings": 0}
    for root, _, files in os.walk(folder):
        for f in sorted(files):
            full = os.path.join(root, f); rel = os.path.relpath(full, folder).replace("\\", "/")
            if rel.endswith(".pxdz") or "/." in "/" + rel:
                continue
            raw = open(full, "rb").read(); data = raw; codec = []; canon_sha = None
            ext = os.path.splitext(f)[1].lower()
            if ext == ".json":
                try:
                    obj = json.loads(raw)
                    before = stats["strings"]
                    coded = cog_json(obj, book, public, stats)
                    if stats["strings"] > before:
                        data = json.dumps(coded, ensure_ascii=False, separators=(",", ":")).encode(); codec.append("cog-json")
                        canon_sha = canon(obj)
                except ValueError:
                    pass
            if ext in DEFLATE_EXT:
                d = deflate(data)
                if len(d) < len(data):
                    data = d; codec.append("deflate")
            if key:
                data = seal(data, key); codec.append("aes-gcm")
            parts.append({"path": rel, "codec": codec, "offset": offset, "length": len(data), "size": len(raw),
                          "sha256": hashlib.sha256(raw).hexdigest(), **({"sha256_json": canon_sha} if canon_sha else {})})
            blobs.append(data); offset += len(data)
    # the hub book travels inside the bundle (sealed for private clients) unless it is published separately
    bdata = deflate(json.dumps({"id": book.id, "rows": book.rows}, ensure_ascii=False, separators=(",", ":")).encode())
    if key:
        bdata = seal(bdata, key)
    books = [{"id": book.id, "kind": "hub", "rows": len(book.rows), "sha256": book.digest(), "offset": offset, "length": len(bdata),
              "codec": ["deflate"] + (["aes-gcm"] if key else [])}]
    if public:
        books.append({"id": "cog-public", "kind": "public", "url": "https://pxd2.github.io/cog/books/catalog.json"})
    blobs.append(bdata); offset += len(bdata)
    manifest = {"format": "pxdz/1", "name": name or os.path.basename(os.path.abspath(folder)),
                "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "encryption": enc,
                "books": books, "parts": parts, "stats": {"cog_strings": stats["strings"], "hub_sentences_added": book.added}}
    mj = json.dumps(manifest, ensure_ascii=False, separators=(",", ":")).encode()
    with open(out, "wb") as fh:
        fh.write(MAGIC + struct.pack("<BI", VERSION, len(mj)) + mj)
        for b in blobs:
            fh.write(b)
    book.save()
    return manifest, os.path.getsize(out)


def read(path, passphrase=None, public_dir=None):
    blob = open(path, "rb").read()
    if blob[:4] != MAGIC:
        raise SystemExit("Not a PXDZ file.")
    ver, mlen = struct.unpack("<BI", blob[4:9]); m = json.loads(blob[9:9 + mlen]); base = 9 + mlen
    key = None
    if m.get("encryption"):
        if not passphrase:
            raise SystemExit("This bundle is encrypted. Pass --key.")
        key = derive(passphrase, base64.b64decode(m["encryption"]["salt"]), m["encryption"]["iter"])

    def undo(data, codec):
        for c in reversed(codec):
            if c == "aes-gcm":
                data = unseal(data, key)
            elif c == "deflate":
                data = inflate(data)
        return data
    hub = next(b for b in m["books"] if b["kind"] == "hub")
    rows = json.loads(undo(blob[base + hub["offset"]: base + hub["offset"] + hub["length"]], hub["codec"]))["rows"]
    lookup = {f"h{mm}.{st[0] + i}": s for mm, st, vs in rows for i, s in enumerate(vs)}
    lookup.update({v: k for k, v in load_public(public_dir).items()})
    files = {}
    for p in m["parts"]:
        data = undo(blob[base + p["offset"]: base + p["offset"] + p["length"]], p["codec"])
        if "cog-json" in p["codec"]:
            obj = uncog_json(json.loads(data), lookup)
            if canon(obj) != p["sha256_json"]:
                raise SystemExit(f"Integrity check failed for {p['path']}")
            data = json.dumps(obj, ensure_ascii=False, indent=2).encode()  # every value exact; whitespace re-laid
        elif hashlib.sha256(data).hexdigest() != p["sha256"]:
            raise SystemExit(f"Integrity check failed for {p['path']}")
        files[p["path"]] = data
    return m, files


# ------------------------------------------------------------------ SQL from a catalog
def catalog_to_sql(src, out):
    cat = json.load(open(src, encoding="utf-8"))
    if os.path.exists(out):
        os.remove(out)
    db = sqlite3.connect(out)
    for table, rows in cat.items():
        if not (isinstance(rows, list) and rows and all(isinstance(r, dict) for r in rows)):
            continue
        cols = sorted({k for r in rows for k in r})
        def typ(c):
            vals = [r.get(c) for r in rows if r.get(c) is not None]
            return "REAL" if vals and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals) else "TEXT"
        db.execute(f'CREATE TABLE "{table}" ({", ".join(f"{chr(34)}{c}{chr(34)} {typ(c)}" for c in cols)})')
        for r in rows:
            db.execute(f'INSERT INTO "{table}" VALUES ({",".join("?" * len(cols))})',
                       [json.dumps(r[c]) if isinstance(r.get(c), (list, dict)) else r.get(c) for c in cols])
    meta = {k: v for k, v in cat.items() if not isinstance(v, list)}
    db.execute("CREATE TABLE meta (key TEXT, value TEXT)")
    db.executemany("INSERT INTO meta VALUES (?, ?)", [(k, json.dumps(v) if not isinstance(v, str) else v) for k, v in meta.items()])
    db.commit(); db.execute("VACUUM"); db.close()
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("pack"); a.add_argument("folder"); a.add_argument("-o", required=True); a.add_argument("--book"); a.add_argument("--public-book"); a.add_argument("--key"); a.add_argument("--name")
    b = sp.add_parser("unpack"); b.add_argument("file"); b.add_argument("-o", required=True); b.add_argument("--key"); b.add_argument("--public-book")
    c = sp.add_parser("inspect"); c.add_argument("file")
    d = sp.add_parser("sql"); d.add_argument("catalog"); d.add_argument("-o", required=True)
    x = ap.parse_args()
    if x.cmd == "pack":
        m, size = pack(x.folder, x.o, x.book, x.public_book, x.key, x.name)
        raw = sum(p["size"] for p in m["parts"])
        print(f"{x.o}: {len(m['parts'])} parts, {raw:,} B raw -> {size:,} B ({raw / max(size, 1):.1f}x), "
              f"{m['stats']['cog_strings']} strings COG-coded, {'encrypted' if m['encryption'] else 'open'}")
    elif x.cmd == "unpack":
        m, files = read(x.file, x.key, x.public_book)
        for p, data in files.items():
            dst = os.path.join(x.o, p); os.makedirs(os.path.dirname(dst) or ".", exist_ok=True); open(dst, "wb").write(data)
        print(f"Unpacked and verified {len(files)} parts to {x.o}")
    elif x.cmd == "inspect":
        blob = open(x.file, "rb").read(); _, mlen = struct.unpack("<BI", blob[4:9]); m = json.loads(blob[9:9 + mlen])
        print(json.dumps({k: v for k, v in m.items() if k != "parts"}, indent=2))
        for p in m["parts"]:
            print(f"  {p['path']:<40} {p['size']:>10,} -> {p['length']:>10,}  {'+'.join(p['codec']) or 'store'}")
    elif x.cmd == "sql":
        print("SQLite written:", catalog_to_sql(x.catalog, x.o))


if __name__ == "__main__":
    main()
