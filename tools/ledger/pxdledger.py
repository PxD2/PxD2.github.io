"""PXD Model Ledger: 3D models as license tokens, on PXD's own ledger. No coin, no mining.

A model's artist registers it once; every license after that (a print license, a game or film
license, a lease that expires, one of a limited edition, a full buyout) is an event in that
model's own append-only, hash-chained, signed log: ledger/<model>.jsonl in a GitHub repository.
Anyone can replay a log and check who holds what. Money never passes through the ledger: buyers
pay the artist directly (card through PXD Pay, or USDC to the artist's own wallet).

Events (each signed ECDSA P-256, the same keys as PXD certificates; `prev` chains them):
  register   artist      title, files' SHA-256, tiers, royalty on resale, optional PXD creator certificate
  delegate   artist      lets a key (the PXD Gateway) issue licenses for chosen tiers until a date
  issue      artist or delegate   a license to a holder key: tier, edition number, expiry for leases, payment reference
  renew      artist or delegate   extends a lease
  transfer   holder + cosign by artist or delegate (who confirms the resale royalty was paid)
  revoke     artist or delegate   refund or chargeback, with a reason
  buyout     artist + cosign by the new owner: the model itself changes hands; licenses stay valid

    python pxdledger.py register  --key artist.key.json --model lamp.glb --title "Brass lamp" --tiers tiers.json --royalty 10 -o ledger/
    python pxdledger.py delegate  --key artist.key.json --log ledger/<id>.jsonl --to gateway.pub.json --tiers print,game --days 365
    python pxdledger.py issue     --key gateway.key.json --log ... --tier print --holder buyer.pub.json --payment pxd_123
    python pxdledger.py transfer  --key buyer.key.json --cosign artist.key.json --log ... --token <t> --to friend.pub.json --payment pxd_456
    python pxdledger.py show      --log ...            # verify the whole chain and print who holds what
tiers.json: {"print": {"price": 12, "rights": "personal 3D printing"}, "game": {"price": 150, "edition": 50},
             "film-lease": {"price": 400, "lease_days": 365, "transferable": false}, "buyout": {"price": 5000, "exclusive": true}}
"""
import argparse, datetime, hashlib, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "pxdz"))
import pxdsign  # noqa: E402

GENESIS = "0" * 64
MAX_ROYALTY_BPS = 5000


class LedgerError(ValueError):
    pass


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def pub_of(jwk):
    return {k: jwk[k] for k in ("crv", "kty", "x", "y")}


def kid(jwk):
    return pxdsign.kid(pub_of(jwk))


def unsigned(ev):
    return {k: v for k, v in ev.items() if k not in ("sig", "cosig")}


def ev_hash(ev):
    return hashlib.sha256(pxdsign.canon(ev)).hexdigest()


def sign_ev(priv_jwk, ev):
    return pxdsign.sign(pxdsign.load_priv(priv_jwk), pxdsign.canon(unsigned(ev)))


def check_sig(pub_jwk, ev, sig):
    return bool(sig) and pxdsign.verify(pxdsign.load_pub(pub_jwk), pxdsign.canon(unsigned(ev)), sig)


# ------------------------------------------------------------------ state: replay a log under the rules
def replay(events, authority=None, at=None):
    """Verify every event and return the model's state. Raises LedgerError on the first bad event."""
    at = at or now()
    st = None
    prev = GENESIS
    for i, ev in enumerate(events):
        if ev.get("seq") != i or ev.get("prev") != prev:
            raise LedgerError(f"event {i}: broken chain")
        t, b, by = ev.get("type"), ev.get("body", {}), ev.get("by", {})
        if i == 0:
            if t != "register":
                raise LedgerError("a log starts with register")
            if not check_sig(b["owner"], ev, ev.get("sig")):
                raise LedgerError("register: artist signature")
            if not 0 <= int(b.get("royalty_bps", 0)) <= MAX_ROYALTY_BPS:
                raise LedgerError("register: royalty out of range")
            creator = None
            if b.get("creator_cert") and authority:
                c = b["creator_cert"]["cert"]
                if c["issuer"] != authority["kid"] or not pxdsign.verify(pxdsign.load_pub(authority["key"]), pxdsign.canon(c), b["creator_cert"]["sig"]):
                    raise LedgerError("register: creator certificate not from the PXD authority")
                if pxdsign.kid(c["key"]) != kid(b["owner"]):
                    raise LedgerError("register: creator certificate is for another key")
                creator = {"id": c["merchant"], "name": c["name"]}
            model_id = ev["model"]
            if model_id != hashlib.sha256(pxdsign.canon({"files": b["files"], "owner": kid(b["owner"]), "title": b["title"]})).hexdigest()[:24]:
                raise LedgerError("register: model id does not match its files")
            st = {"model": model_id, "title": b["title"], "files": b["files"], "owner": b["owner"], "creator": creator, "tiers": b["tiers"],
                  "royalty_bps": int(b.get("royalty_bps", 0)), "delegates": {}, "licenses": {}, "issued": {}, "history": [], "head": None}
        else:
            if ev.get("model") != st["model"]:
                raise LedgerError(f"event {i}: wrong model")
            owner_ok = check_sig(st["owner"], ev, ev.get("sig"))

            def delegate_ok(tier=None):
                d = st["delegates"].get(by.get("kid", ""))
                return bool(d) and ev["time"] <= d["until"] and (tier is None or tier in d["tiers"]) and check_sig(d["pub"], ev, ev.get("sig"))
            if t == "delegate":
                if not owner_ok:
                    raise LedgerError(f"event {i}: only the artist delegates")
                st["delegates"][kid(b["pub"])] = {"pub": pub_of(b["pub"]), "tiers": b["tiers"], "until": b["until"]}
            elif t == "issue":
                tier = st["tiers"].get(b["tier"])
                if not tier:
                    raise LedgerError(f"event {i}: no tier {b['tier']}")
                if not (owner_ok or delegate_ok(b["tier"])):
                    raise LedgerError(f"event {i}: issue needs the artist or a delegate for that tier")
                n = st["issued"].get(b["tier"], 0) + 1
                if tier.get("edition") and n > int(tier["edition"]):
                    raise LedgerError(f"event {i}: {b['tier']} edition of {tier['edition']} is sold out")
                if tier.get("exclusive") and any(l["tier"] == b["tier"] and l["active"] for l in st["licenses"].values()):
                    raise LedgerError(f"event {i}: exclusive tier already held")
                tok = b["token"]
                if tok in st["licenses"]:
                    raise LedgerError(f"event {i}: token exists")
                exp = None
                if tier.get("lease_days"):
                    exp = (datetime.datetime.fromisoformat(ev["time"]) + datetime.timedelta(days=int(tier["lease_days"]))).isoformat(timespec="seconds")
                st["issued"][b["tier"]] = n
                st["licenses"][tok] = {"token": tok, "tier": b["tier"], "holder": pub_of(b["holder"]), "holder_kid": kid(b["holder"]),
                                       "edition": n if tier.get("edition") else None, "issued": ev["time"], "expires": exp,
                                       "payment": b.get("payment"), "active": True}
            elif t in ("renew", "revoke", "transfer"):
                lic = st["licenses"].get(b.get("token"))
                if not lic or not lic["active"]:
                    raise LedgerError(f"event {i}: no active license {b.get('token')}")
                if t == "renew":
                    if not (owner_ok or delegate_ok(lic["tier"])) or not lic["expires"]:
                        raise LedgerError(f"event {i}: renew needs a lease and the artist or a delegate")
                    lic["expires"] = (datetime.datetime.fromisoformat(max(lic["expires"], ev["time"])) + datetime.timedelta(days=int(b["days"]))).isoformat(timespec="seconds")
                elif t == "revoke":
                    if not (owner_ok or delegate_ok(lic["tier"])):
                        raise LedgerError(f"event {i}: revoke needs the artist or a delegate")
                    lic.update(active=False, revoked=b.get("reason", ""))
                else:
                    if st["tiers"][lic["tier"]].get("transferable") is False:
                        raise LedgerError(f"event {i}: {lic['tier']} licenses are not transferable")
                    if lic["expires"] and lic["expires"] < ev["time"]:
                        raise LedgerError(f"event {i}: lease expired")
                    if not check_sig(lic["holder"], ev, ev.get("sig")):
                        raise LedgerError(f"event {i}: transfer must be signed by the holder")
                    co = ev.get("cosig") or {}
                    d = st["delegates"].get(co.get("kid", ""))
                    co_ok = (co.get("kid") == kid(st["owner"]) and check_sig(st["owner"], ev, co.get("sig"))) or \
                            (d is not None and ev["time"] <= d["until"] and check_sig(d["pub"], ev, co.get("sig")))
                    if not co_ok:
                        raise LedgerError(f"event {i}: transfer needs the artist's or delegate's countersignature (royalty paid)")
                    lic.update(holder=pub_of(b["to"]), holder_kid=kid(b["to"]), last_payment=b.get("payment"))
            elif t == "buyout":
                co = ev.get("cosig") or {}
                if not owner_ok or not check_sig(b["new_owner"], ev, co.get("sig")):
                    raise LedgerError(f"event {i}: buyout needs the artist and the new owner")
                st["owner"] = pub_of(b["new_owner"]); st["delegates"] = {}
            else:
                raise LedgerError(f"event {i}: unknown type {t}")
        st["history"].append({"seq": i, "type": t, "time": ev["time"]})
        prev = ev_hash(ev)
        st["head"] = prev
    for lic in (st or {}).get("licenses", {}).values():
        lic["current"] = lic["active"] and not (lic["expires"] and lic["expires"] < at)
    return st


# ------------------------------------------------------------------ writing
def read_log(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()] if os.path.exists(path) else []


def append(path, priv_jwk, etype, body, cosign_jwk=None, authority=None):
    """Build, sign, check against the whole log, then append. Nothing invalid is ever written."""
    events = read_log(path)
    state = replay(events, authority) if events else None
    signer = pub_of(priv_jwk)
    ev = {"v": 1, "seq": len(events), "prev": ev_hash(events[-1]) if events else GENESIS, "model": state["model"] if state else None,
          "type": etype, "time": now(), "by": {"kid": pxdsign.kid(signer)}, "body": body}
    if etype == "register":
        ev["model"] = hashlib.sha256(pxdsign.canon({"files": body["files"], "owner": kid(body["owner"]), "title": body["title"]})).hexdigest()[:24]
    ev["sig"] = sign_ev(priv_jwk, ev)
    if cosign_jwk:
        ev["cosig"] = {"kid": kid(cosign_jwk), "sig": sign_ev(cosign_jwk, ev)}
    replay(events + [ev], authority)  # refuse before writing
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(ev, separators=(",", ":"), ensure_ascii=False) + "\n")
    return ev


def file_hashes(paths):
    return [{"name": os.path.basename(p), "sha256": hashlib.sha256(open(p, "rb").read()).hexdigest(), "bytes": os.path.getsize(p)}
            for p in sorted(paths)]


def new_token(model, tier, holder_jwk, seq):
    return hashlib.sha256(f"{model}|{tier}|{kid(holder_jwk)}|{seq}".encode()).hexdigest()[:20]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    ap.add_argument("--authority", help="PXD authority public record, to check creator certificates")
    r = sp.add_parser("register"); r.add_argument("--key", required=True); r.add_argument("--model", action="append", required=True)
    r.add_argument("--title", required=True); r.add_argument("--tiers", required=True); r.add_argument("--royalty", type=float, default=10.0)
    r.add_argument("--cert", help="the artist's PXD certificate (verified creator)"); r.add_argument("-o", default="ledger")
    d = sp.add_parser("delegate"); d.add_argument("--key", required=True); d.add_argument("--log", required=True); d.add_argument("--to", required=True)
    d.add_argument("--tiers", required=True); d.add_argument("--days", type=int, default=365)
    i = sp.add_parser("issue"); i.add_argument("--key", required=True); i.add_argument("--log", required=True); i.add_argument("--tier", required=True)
    i.add_argument("--holder", required=True); i.add_argument("--payment", default="")
    n = sp.add_parser("renew"); n.add_argument("--key", required=True); n.add_argument("--log", required=True); n.add_argument("--token", required=True); n.add_argument("--days", type=int, required=True)
    v = sp.add_parser("revoke"); v.add_argument("--key", required=True); v.add_argument("--log", required=True); v.add_argument("--token", required=True); v.add_argument("--reason", default="refund")
    t = sp.add_parser("transfer"); t.add_argument("--key", required=True); t.add_argument("--cosign", required=True); t.add_argument("--log", required=True)
    t.add_argument("--token", required=True); t.add_argument("--to", required=True); t.add_argument("--payment", default="")
    b = sp.add_parser("buyout"); b.add_argument("--key", required=True); b.add_argument("--new-owner-key", required=True); b.add_argument("--log", required=True)
    s = sp.add_parser("show"); s.add_argument("--log", required=True)
    a = ap.parse_args()
    auth = json.load(open(a.authority)) if a.authority else None
    J = lambda p: json.load(open(p))  # noqa: E731
    try:
        if a.cmd == "register":
            key = J(a.key)
            body = {"title": a.title, "files": file_hashes(a.model), "owner": pub_of(key), "tiers": J(a.tiers), "royalty_bps": int(round(a.royalty * 100))}
            if a.cert:
                body["creator_cert"] = J(a.cert)
            mid = hashlib.sha256(pxdsign.canon({"files": body["files"], "owner": kid(key), "title": a.title})).hexdigest()[:24]
            path = os.path.join(a.o, mid + ".jsonl")
            if os.path.exists(path):
                raise LedgerError(f"{path} already exists")
            append(path, key, "register", body, authority=auth); print(f"registered model {mid} -> {path}")
        elif a.cmd == "delegate":
            until = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=a.days)).isoformat(timespec="seconds")
            append(a.log, J(a.key), "delegate", {"pub": pub_of(J(a.to)), "tiers": a.tiers.split(","), "until": until}, authority=auth)
            print(f"delegated {a.tiers} until {until}")
        elif a.cmd == "issue":
            holder = J(a.holder); st = replay(read_log(a.log), auth)
            tok = new_token(st["model"], a.tier, holder, len(read_log(a.log)))
            append(a.log, J(a.key), "issue", {"token": tok, "tier": a.tier, "holder": pub_of(holder), "payment": a.payment}, authority=auth)
            print(f"license {tok} ({a.tier}) -> {kid(holder)}")
        elif a.cmd == "renew":
            append(a.log, J(a.key), "renew", {"token": a.token, "days": a.days}, authority=auth); print("renewed")
        elif a.cmd == "revoke":
            append(a.log, J(a.key), "revoke", {"token": a.token, "reason": a.reason}, authority=auth); print("revoked")
        elif a.cmd == "transfer":
            append(a.log, J(a.key), "transfer", {"token": a.token, "to": pub_of(J(a.to)), "payment": a.payment}, cosign_jwk=J(a.cosign), authority=auth)
            print("transferred")
        elif a.cmd == "buyout":
            append(a.log, J(a.key), "buyout", {"new_owner": pub_of(J(a.new_owner_key))}, cosign_jwk=J(a.new_owner_key), authority=auth); print("model bought out")
        elif a.cmd == "show":
            st = replay(read_log(a.log), auth)
            print(json.dumps({"model": st["model"], "title": st["title"], "owner": kid(st["owner"]), "creator": st["creator"],
                              "royalty_pct": st["royalty_bps"] / 100, "tiers": st["tiers"], "sold": st["issued"], "events": len(st["history"]),
                              "head": st["head"], "licenses": [{k: l[k] for k in ("token", "tier", "holder_kid", "edition", "expires", "current")}
                                                                for l in st["licenses"].values()]}, indent=1))
    except LedgerError as e:
        raise SystemExit(f"refused: {e}")


if __name__ == "__main__":
    main()
