#!/usr/bin/env python3
"""PXD2 Pinpoint. Sentences in, Mayan path out, sentence back. No Needle name. No weights."""
from __future__ import annotations
import sys
from pathlib import Path

BASE, PLACES = 20, 3
SHELF_LO, SHELF_HI = 4501, 7999
ROOT = Path(__file__).resolve().parent
SHELF = ROOT / "shelf.tsv"


def places_of(i: int) -> list[int]:
    x = max(0, min(SHELF_HI, int(i)))
    low = []
    for _ in range(PLACES):
        low.append(x % BASE)
        x //= BASE
    return list(reversed(low))


def id_of(places: list[int]) -> int:
    n = 0
    for d in places[:PLACES]:
        n = n * BASE + int(d)
    return n


def glyph(d: int) -> str:
    if d <= 0:
        return "⌀"
    bars, dots = divmod(d, 5)
    return ("•" * dots) + ("━" * bars)


def trench(n: int) -> str:
    x = int(n)
    if x == 0:
        return "0"
    out = []
    while x:
        rem = x % 3
        x = int(x / 3)
        if rem == 2:
            rem, x = -1, x + 1
        elif rem == -2:
            rem, x = 1, x - 1
        out.append(rem)
    return "".join("−" if d < 0 else "+" if d > 0 else "0" for d in reversed(out))


def pack(ids: list[int]) -> str:
    use = ids or [0]
    return "-".join(".".join(str(d) for d in places_of(i)) for i in use)


def unpack(path: str) -> list[int]:
    groups = []
    for g in path.strip().split("-"):
        parts = g.split(".")
        if len(parts) != 3:
            continue
        ds = [int(x) for x in parts]
        if all(0 <= d < BASE for d in ds):
            groups.append(id_of(ds))
    return groups or [0]


class Book:
    def __init__(self) -> None:
        self.gloss: dict[int, str] = {}
        self.phrase: dict[str, int] = {}
        for p in sorted((ROOT / "book").glob("*.tsv")):
            for line in p.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                i, g, phrases = line.split("\t", 2)
                n = int(i)
                self.gloss[n] = g
                self.phrase.setdefault(g.lower(), n)
                for ph in phrases.split("|"):
                    self.phrase.setdefault(ph.lower(), n)

    def say(self, text: str) -> tuple[list[int], list[str]]:
        parts = [s.strip() for s in _sentences(text)]
        ids: list[int] = []
        missed: list[str] = []
        if not parts:
            return [0], []
        for sentence in parts:
            key = _norm(sentence)
            hit = self.phrase.get(key)
            if hit:
                ids.append(hit)
                continue
            words = key.split()
            hits: list[int] = []
            i = 0
            while i < len(words):
                found = None
                span = 1
                for n in range(min(12, len(words) - i), 0, -1):
                    ph = " ".join(words[i : i + n])
                    if ph in self.phrase:
                        found = self.phrase[ph]
                        span = n
                        break
                if found is None:
                    break
                hits.append(found)
                i += span
            if hits and i == len(words) and len(set(hits)) == 1:
                ids.append(hits[0])
            else:
                missed.append(sentence)
                ids.append(_shelf_id(sentence))
                _remember(sentence, ids[-1])
        return ids, missed

    def recall(self, path: str) -> str:
        shelf = _read_shelf()
        lines = []
        for i in unpack(path):
            if i == 0:
                lines.append("Empty line. The shell still holds the path.")
            else:
                lines.append(self.gloss.get(i) or shelf.get(i) or f"No sentence for {i}")
        return " ".join(lines)


def _norm(s: str) -> str:
    keep = []
    for ch in s.lower():
        keep.append(ch if ch.isalnum() or ch in " '-" else " ")
    return " ".join("".join(keep).split()).rstrip(".!?").strip()


def _sentences(text: str) -> list[str]:
    buf, out = [], []
    for ch in text.strip():
        buf.append(ch)
        if ch in ".!?":
            s = "".join(buf).strip()
            if s:
                out.append(s)
            buf = []
    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    return out


def _shelf_id(sentence: str) -> int:
    h = 2166136261
    for ch in sentence:
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return SHELF_LO + (h % (SHELF_HI - SHELF_LO + 1))


def _read_shelf() -> dict[int, str]:
    if not SHELF.exists():
        return {}
    out = {}
    for line in SHELF.read_text(encoding="utf-8").splitlines():
        if "\t" not in line:
            continue
        i, s = line.split("\t", 1)
        out[int(i)] = s
    return out


def _remember(sentence: str, i: int) -> None:
    have = _read_shelf()
    have[i] = sentence
    SHELF.write_text("".join(f"{k}\t{v}\n" for k, v in have.items()), encoding="utf-8")


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "pin"
    book = Book()
    if cmd == "pin":
        print(f"sentences {len(book.gloss)} phrases {len(book.phrase)}")
        return 0
    if cmd == "say":
        ids, missed = book.say(" ".join(argv[2:]))
        path = pack(ids)
        print(path)
        print(" ".join(trench(i) for i in ids))
        print(book.recall(path))
        if missed:
            print("stored", *missed)
        return 0
    if cmd == "recall":
        print(book.recall(argv[2]))
        return 0
    print("pin | say SENTENCE | recall PATH")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
