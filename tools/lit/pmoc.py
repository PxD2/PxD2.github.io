""".pmoc v1: the PMOC container (PxD2/PMOC README), on disk and on the wire.

    "PMOC1" | u8 version | u16 flags | u32 n_slices
    slice_table[n]: id[16] | u8 kind | u8 numa_hint | u64 bytes | u32 crc32
    data: the slices, in table order

Kinds: 1 weight (CORE only) · 2 kv · 3 lex (CORE only) · 4 session (expires) · 5 board-map
       6 part: public content named by its own hash. Lit adds this kind: id = first 16 bytes
         of SHA-256(content), so any node may carry it and nobody can forge it.

    python pmoc.py build plates/cog-english-v0.pmoc.json -o cog-english-v0.pmoc   # JSON twin -> binary
    python pmoc.py ls file.pmoc
    python pmoc.py get file.pmoc <id> -o out.bin
    python pmoc.py twin file.pmoc -o file.pmoc.json                               # binary -> JSON twin
All integers little-endian.
"""
import argparse, hashlib, json, struct, sys, zlib

MAGIC, VERSION = b"PMOC1", 1
HEAD = struct.Struct("<5sBHI")          # 12 bytes
ENTRY = struct.Struct("<16sBBQI")       # 30 bytes
KINDS = {1: "weight", 2: "kv", 3: "lex", 4: "session", 5: "board-map", 6: "part"}
CORE_ONLY = {1, 3}


def part_id(data):
    """Lit's content id: the first 16 bytes of SHA-256."""
    return hashlib.sha256(data).digest()[:16]


def write(path, slices, flags=0):
    """slices: [(id16 bytes, kind, numa_hint, data bytes)]"""
    with open(path, "wb") as f:
        f.write(HEAD.pack(MAGIC, VERSION, flags, len(slices)))
        for sid, kind, numa, data in slices:
            if len(sid) != 16:
                raise ValueError("slice id must be 16 bytes")
            f.write(ENTRY.pack(sid, kind, numa, len(data), zlib.crc32(data) & 0xFFFFFFFF))
        for *_, data in slices:
            f.write(data)


class Reader:
    """Index of a .pmoc file; slices are read on demand and checked against their CRC32."""

    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            magic, self.version, self.flags, n = HEAD.unpack(f.read(HEAD.size))
            if magic != MAGIC:
                raise ValueError(f"{path}: not a .pmoc file")
            if self.version != VERSION:
                raise ValueError(f"{path}: .pmoc version {self.version} is newer than this reader")
            off = HEAD.size + n * ENTRY.size
            self.slices = {}
            for _ in range(n):
                sid, kind, numa, size, crc = ENTRY.unpack(f.read(ENTRY.size))
                self.slices[sid] = {"kind": kind, "numa": numa, "bytes": size, "crc": crc, "offset": off}
                off += size

    def read(self, sid):
        s = self.slices[sid]
        with open(self.path, "rb") as f:
            f.seek(s["offset"]); data = f.read(s["bytes"])
        if zlib.crc32(data) & 0xFFFFFFFF != s["crc"]:
            raise ValueError(f"slice {sid.hex()} failed its CRC32")
        if s["kind"] == 6 and part_id(data) != sid:
            raise ValueError(f"part {sid.hex()} does not match its content")
        return data


def from_twin(twin):
    """A PMOC JSON twin (cog plates) -> slices. A slice body is stored as canonical JSON."""
    if twin.get("m") != "PMOC1":
        raise ValueError("not a PMOC JSON twin")
    out = []
    for s in twin["slices"]:
        body = s["body"] if isinstance(s["body"], (bytes, bytearray)) else \
            json.dumps(s["body"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        out.append((bytes.fromhex(s["id"]), int(s["k"]), int(s.get("numa", 0)), body))
    return out, int(twin.get("fl", 0))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    b = sp.add_parser("build"); b.add_argument("twin"); b.add_argument("-o", required=True)
    l = sp.add_parser("ls"); l.add_argument("file")
    g = sp.add_parser("get"); g.add_argument("file"); g.add_argument("id"); g.add_argument("-o", required=True)
    t = sp.add_parser("twin"); t.add_argument("file"); t.add_argument("-o", required=True)
    a = ap.parse_args()
    if a.cmd == "build":
        slices, flags = from_twin(json.load(open(a.twin, encoding="utf-8")))
        write(a.o, slices, flags)
        print(f"{a.o}: {len(slices)} slice(s), {sum(len(s[3]) for s in slices):,} bytes of data")
    elif a.cmd == "ls":
        r = Reader(a.file)
        print(f"{a.file}: PMOC v{r.version}, flags {r.flags}, {len(r.slices)} slice(s)")
        for sid, s in r.slices.items():
            print(f"  {sid.hex()}  {KINDS.get(s['kind'], s['kind']):<9} numa {s['numa']}  {s['bytes']:>10,} B  crc {s['crc']:08x}")
    elif a.cmd == "get":
        open(a.o, "wb").write(Reader(a.file).read(bytes.fromhex(a.id))); print(f"wrote {a.o}")
    elif a.cmd == "twin":
        r = Reader(a.file); sl = []
        for sid, s in r.slices.items():
            data = r.read(sid)
            try:
                body = json.loads(data)
            except ValueError:
                body = {"b64": __import__("base64").b64encode(data).decode()}
            sl.append({"id": sid.hex(), "k": s["kind"], "numa": s["numa"], "crc": s["crc"], "body": body})
        json.dump({"m": "PMOC1", "v": r.version, "fl": r.flags, "slices": sl}, open(a.o, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"wrote {a.o}")


if __name__ == "__main__":
    sys.exit(main())
