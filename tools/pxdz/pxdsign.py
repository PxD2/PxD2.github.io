"""PXD merchant authentication.

A chain of trust in three links, all ECDSA P-256 / SHA-256 (verifiable natively in every browser):
  1. The PXD authority key (kept OFFLINE on base1) issues merchant certificates.
  2. A merchant certificate names the merchant, its public key, the payment hosts its
     pay links may use, and an expiry, signed by the authority.
  3. The merchant signs each bundle (SHA-256 of the whole .pxdz). The signature travels
     beside it as <bundle>.pxdz.sig.

Readers check authority -> certificate -> bundle, then refuse any pay link whose host the
certificate does not allow. That stops a copied or edited store from redirecting payments.

    python pxdsign.py authority-init --dir keys/                       # once; keep keys/ offline
    python pxdsign.py merchant-key --out keys/smiths.key.json          # merchant's own key
    python pxdsign.py issue --authority keys/ --merchant-pub keys/smiths.pub.json \
        --id smiths-antiques --name "Smith's Antiques" --pay-hosts buy.stripe.com,www.paypal.com --days 365 \
        -o certs/smiths-antiques.cert.json
    python pxdsign.py sign site.pxdz --key keys/smiths.key.json --cert certs/smiths-antiques.cert.json
    python pxdsign.py verify site.pxdz --authority-pub pxd/authority.json
    python pxdsign.py registry-sign names.json --authority keys/          # after every names.json change
    python pxdsign.py registry-verify names.json --authority-pub pxd/authority.json
"""
import argparse, base64, datetime, hashlib, json, os, sys
from urllib.parse import urlparse
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature, encode_dss_signature
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidSignature

DEFAULT_PAY_HOSTS = ["buy.stripe.com", "checkout.stripe.com", "www.paypal.com", "paypal.me", "square.link", "checkout.square.site",
                     "cash.app", "venmo.com", "commerce.coinbase.com"]


def b64u(b): return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
def ub64u(s): return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def jwk_public(pub):
    n = pub.public_numbers()
    return {"kty": "EC", "crv": "P-256", "x": b64u(n.x.to_bytes(32, "big")), "y": b64u(n.y.to_bytes(32, "big"))}


def jwk_private(priv):
    j = jwk_public(priv.public_key()); j["d"] = b64u(priv.private_numbers().private_value.to_bytes(32, "big")); return j


def load_priv(j):
    return ec.derive_private_key(int.from_bytes(ub64u(j["d"]), "big"), ec.SECP256R1())


def load_pub(j):
    return ec.EllipticCurvePublicNumbers(int.from_bytes(ub64u(j["x"]), "big"), int.from_bytes(ub64u(j["y"]), "big"), ec.SECP256R1()).public_key()


def canon(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sign(priv, data):
    """Raw r||s (IEEE P1363), the form WebCrypto verifies."""
    r, s = decode_dss_signature(priv.sign(data, ec.ECDSA(hashes.SHA256())))
    return b64u(r.to_bytes(32, "big") + s.to_bytes(32, "big"))


def verify(pub, data, sig):
    raw = ub64u(sig)
    try:
        pub.verify(encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")), data, ec.ECDSA(hashes.SHA256()))
        return True
    except InvalidSignature:
        return False


def kid(pubjwk):
    return hashlib.sha256(canon({k: pubjwk[k] for k in ("crv", "kty", "x", "y")})).hexdigest()[:16]


# ---------------------------------------------------------------- commands
def authority_init(d, name):
    os.makedirs(d, exist_ok=True)
    priv = ec.generate_private_key(ec.SECP256R1()); pub = jwk_public(priv.public_key())
    json.dump(jwk_private(priv), open(os.path.join(d, "authority.key.json"), "w"))
    rec = {"authority": name, "kid": kid(pub), "key": pub, "created": datetime.date.today().isoformat()}
    json.dump(rec, open(os.path.join(d, "authority.json"), "w"), indent=2)
    print(f"Authority {name} ({rec['kid']}). Publish {d}/authority.json; keep {d}/authority.key.json offline.")


def merchant_key(out):
    priv = ec.generate_private_key(ec.SECP256R1())
    json.dump(jwk_private(priv), open(out, "w"))
    pub_path = out.replace(".key.json", ".pub.json") if out.endswith(".key.json") else out + ".pub"
    json.dump(jwk_public(priv.public_key()), open(pub_path, "w"), indent=2)
    print(f"Merchant key {out}; public half {pub_path} goes to the authority.")


def issue(auth_dir, merchant_pub, mid, name, pay_hosts, days, out):
    a_priv = load_priv(json.load(open(os.path.join(auth_dir, "authority.key.json"))))
    a_rec = json.load(open(os.path.join(auth_dir, "authority.json")))
    m_pub = json.load(open(merchant_pub))
    today = datetime.date.today()
    body = {"type": "pxd-merchant-cert/1", "merchant": mid, "name": name, "key": {k: m_pub[k] for k in ("crv", "kty", "x", "y")},
            "kid": kid(m_pub), "pay_hosts": sorted(set(pay_hosts)), "issued": today.isoformat(),
            "expires": (today + datetime.timedelta(days=days)).isoformat(), "issuer": a_rec["kid"]}
    cert = {"cert": body, "sig": sign(a_priv, canon(body))}
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    json.dump(cert, open(out, "w"), indent=2)
    print(f"Certified {name} ({mid}) until {body['expires']} -> {out}")


def sign_bundle(bundle, key, cert):
    data = open(bundle, "rb").read()
    body = {"type": "pxd-bundle-sig/1", "bundle": os.path.basename(bundle), "sha256": hashlib.sha256(data).hexdigest(),
            "signed": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
    sig = {"sig": body, "signature": sign(load_priv(json.load(open(key))), canon(body)), "cert": json.load(open(cert))}
    json.dump(sig, open(bundle + ".sig", "w"), indent=2)
    print(f"Signed {bundle} -> {bundle}.sig")


def pay_links(bundle_path):
    """Every https link under a 'pay' key in the bundle's JSON parts (needs the open bundle)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import pxdz
    try:
        _, files = pxdz.read(bundle_path)
    except SystemExit:
        return None  # sealed: links are checked by the key holder's reader
    links = []
    def walk(o, under_pay=False):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, under_pay or k == "pay")
        elif isinstance(o, list):
            for v in o: walk(v, under_pay)
        elif isinstance(o, str) and under_pay and o.startswith("http"):
            links.append(o)
    for p, data in files.items():
        if p.endswith(".json"):
            walk(json.loads(data))
    return links


def verify_bundle(bundle, authority_pub, today=None):
    """Returns (ok, report dict)."""
    rep = {"bundle": os.path.basename(bundle), "checks": []}
    def chk(name, ok, detail=""):
        rep["checks"].append({"check": name, "ok": bool(ok), "detail": detail}); return ok
    sigp = bundle + ".sig"
    if not chk("signature file present", os.path.isfile(sigp), sigp):
        return False, rep
    s = json.load(open(sigp)); auth = json.load(open(authority_pub)); cert = s["cert"]["cert"]
    ok = chk("certificate issued by this authority", cert["issuer"] == auth["kid"], cert["issuer"])
    ok &= chk("authority signature on certificate", verify(load_pub(auth["key"]), canon(cert), s["cert"]["sig"]))
    t = (today or datetime.date.today()).isoformat()
    ok &= chk("certificate in date", cert["issued"] <= t <= cert["expires"], f"{cert['issued']} to {cert['expires']}")
    data = open(bundle, "rb").read()
    ok &= chk("bundle unchanged since signing", hashlib.sha256(data).hexdigest() == s["sig"]["sha256"])
    ok &= chk("merchant signature on bundle", verify(load_pub(cert["key"]), canon(s["sig"]), s["signature"]))
    if not ok:
        rep["merchant"] = {"id": cert["merchant"], "name": cert["name"], "expires": cert["expires"]}
        return False, rep  # never read an unverified bundle
    try:
        links = pay_links(bundle)
    except Exception as e:  # noqa: BLE001
        chk("pay links within certificate", False, f"could not read bundle: {e}")
        return False, rep
    if links is None:
        chk("pay links within certificate", True, "sealed bundle: checked by the key holder")
    else:
        bad = [u for u in links if urlparse(u).hostname not in cert["pay_hosts"]]
        ok &= chk("pay links within certificate", not bad, ", ".join(bad) or f"{len(links)} link(s) allowed")
    rep["merchant"] = {"id": cert["merchant"], "name": cert["name"], "expires": cert["expires"]}
    return ok, rep


def sign_registry(path, auth_dir):
    """The authority signs the registry itself, so every PXD root server can prove it is genuine."""
    a_priv = load_priv(json.load(open(os.path.join(auth_dir, "authority.key.json"))))
    a_rec = json.load(open(os.path.join(auth_dir, "authority.json")))
    data = open(path, "rb").read()
    body = {"type": "pxd-registry-sig/1", "file": os.path.basename(path), "sha256": hashlib.sha256(data).hexdigest(),
            "signed": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "issuer": a_rec["kid"]}
    json.dump({"sig": body, "signature": sign(a_priv, canon(body))}, open(path + ".sig", "w"), indent=2)
    print(f"Signed registry {path} ({body['sha256'][:12]}) at {body['signed']} -> {path}.sig")


def verify_registry(data, sigobj, authority):
    """(ok, signed time or reason). `authority` is the public record (authority.json)."""
    try:
        body = sigobj["sig"]
        if body.get("type") != "pxd-registry-sig/1":
            return False, "not a registry signature"
        if body.get("issuer") != authority["kid"]:
            return False, f"signed by {body.get('issuer')}, not this authority"
        if hashlib.sha256(data).hexdigest() != body.get("sha256"):
            return False, "registry changed since signing"
        if not verify(load_pub(authority["key"]), canon(body), sigobj["signature"]):
            return False, "authority signature does not match"
        return True, body["signed"]
    except (KeyError, TypeError, ValueError) as e:
        return False, f"malformed signature ({e})"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("authority-init"); a.add_argument("--dir", required=True); a.add_argument("--name", default="PXD Authority")
    b = sp.add_parser("merchant-key"); b.add_argument("--out", required=True)
    c = sp.add_parser("issue"); c.add_argument("--authority", required=True); c.add_argument("--merchant-pub", required=True)
    c.add_argument("--id", required=True); c.add_argument("--name", required=True); c.add_argument("--pay-hosts", default=",".join(DEFAULT_PAY_HOSTS))
    c.add_argument("--days", type=int, default=365); c.add_argument("-o", required=True)
    d = sp.add_parser("sign"); d.add_argument("bundle"); d.add_argument("--key", required=True); d.add_argument("--cert", required=True)
    e = sp.add_parser("verify"); e.add_argument("bundle"); e.add_argument("--authority-pub", required=True)
    f = sp.add_parser("registry-sign"); f.add_argument("registry"); f.add_argument("--authority", required=True)
    g = sp.add_parser("registry-verify"); g.add_argument("registry"); g.add_argument("--authority-pub", required=True)
    x = ap.parse_args()
    if x.cmd == "authority-init": authority_init(x.dir, x.name)
    elif x.cmd == "merchant-key": merchant_key(x.out)
    elif x.cmd == "issue": issue(x.authority, x.merchant_pub, x.id, x.name, [h.strip() for h in x.pay_hosts.split(",") if h.strip()], x.days, x.o)
    elif x.cmd == "sign": sign_bundle(x.bundle, x.key, x.cert)
    elif x.cmd == "registry-sign": sign_registry(x.registry, x.authority)
    elif x.cmd == "registry-verify":
        ok, detail = verify_registry(open(x.registry, "rb").read(), json.load(open(x.registry + ".sig")), json.load(open(x.authority_pub)))
        print(("REGISTRY VERIFIED, signed " if ok else "NOT VERIFIED: ") + detail); sys.exit(0 if ok else 1)
    elif x.cmd == "verify":
        ok, rep = verify_bundle(x.bundle, x.authority_pub)
        for c_ in rep["checks"]:
            print(("PASS " if c_["ok"] else "FAIL ") + c_["check"] + (f"  ({c_['detail']})" if c_["detail"] else ""))
        print("VERIFIED MERCHANT: " + rep["merchant"]["name"] if ok else "NOT VERIFIED")
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
