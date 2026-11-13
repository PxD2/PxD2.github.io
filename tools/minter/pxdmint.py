"""PXD Minter: mint, secure and keep .pxd names, held on git by PXD2.

A .pxd name works like a .com name: it points somewhere, and the PXD roots answer for it, with no ICANN
registrar in the middle. Ownership is kept three ways, all in this repository:

  names.json              the live registry every PXD root and the PXD Browser read
  names/ledger.jsonl      every mint, change and transfer ever made, each line chained to the one before
                          (change or delete one old line and every later hash breaks; `verify` shows where)
  names/certs/<name>.json the name's deed: owner, where it points, ledger position, signed by the PXD authority

Signing uses the PXD authority key, which lives only in keys/ on base1 (never in git). Without it the minter
still mints and chains; deeds and the registry are signed the next time it runs on the machine with the key.

    python tools/minter/pxdmint.py gui                    # the control panel in your browser (Run_Minter.bat does this)
    python tools/minter/pxdmint.py init                   # once, on base1: make the PXD authority key
    python tools/minter/pxdmint.py check bearwallow
    python tools/minter/pxdmint.py mint showlowtire --to /clients/show-low-tire/ --title "Show Low Tire" --owner "Show Low Tire" --group "Client sites"
    python tools/minter/pxdmint.py update showlowtire --to https://showlowtire.com
    python tools/minter/pxdmint.py transfer showlowtire --owner "New Owner LLC"
    python tools/minter/pxdmint.py whois showlowtire
    python tools/minter/pxdmint.py verify                 # ledger chain, deeds and registry signature
    python tools/minter/pxdmint.py publish                # git commit + push (only when you run it)
"""
import argparse, datetime, hashlib, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(os.path.dirname(HERE))
REG = os.path.join(SITE, "names.json")
LEDGER = os.path.join(SITE, "names", "ledger.jsonl")
CERTS = os.path.join(SITE, "names", "certs")
KEYS = os.path.join(SITE, "keys")                       # gitignored: the authority's private key and owners' contacts
PUBLIC_AUTH = os.path.join(SITE, "pxd", "authority.json")
OWNERS_PRIVATE = os.path.join(KEYS, "owners.json")

sys.path.insert(0, os.path.join(SITE, "tools", "pxdz"))

NAME_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
RESERVED = {"www", "mail", "root", "api", "admin", "pxd", "lit", "names", "registry", "hub", "hubs",
            "localhost", "status", "zone", "dns", "dns-query", "resolve", "wpad", "isatap"}


# ------------------------------------------------------------------ helpers
def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def canon(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def load_reg():
    return json.load(open(REG, encoding="utf-8"))


def save_reg(reg):
    tmp = REG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(reg, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, REG)


def ledger_lines():
    if not os.path.exists(LEDGER):
        return []
    return [json.loads(l) for l in open(LEDGER, encoding="utf-8") if l.strip()]


def ledger_add(op, name, entry, owner, note=""):
    lines = ledger_lines()
    prev = lines[-1]["hash"] if lines else "0" * 64
    rec = {"n": len(lines) + 1, "op": op, "name": name, "at": now(), "entry": entry, "owner": owner, "prev": prev}
    if note:
        rec["note"] = note
    rec["hash"] = hashlib.sha256(canon(rec)).hexdigest()
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n")
    return rec


def authority():
    """(private key, public record) when this machine holds the authority key, else (None, public record or None)."""
    pub = json.load(open(PUBLIC_AUTH)) if os.path.exists(PUBLIC_AUTH) else None
    kp = os.path.join(KEYS, "authority.key.json")
    if os.path.exists(kp) and os.path.exists(os.path.join(KEYS, "authority.json")):
        import pxdsign
        return pxdsign.load_priv(json.load(open(kp))), json.load(open(os.path.join(KEYS, "authority.json")))
    return None, pub


def problem_with(name, reg, minting=True):
    if not NAME_RE.fullmatch(name):
        return "letters, digits and dashes only, 1 to 63 long, no dash at either end"
    if name in RESERVED or re.fullmatch(r"ns\d+", name):
        return "reserved for the PXD root itself"
    if minting and name.startswith("pxd2") and not getattr(problem_with, "pxd2_ok", False):
        return "pxd2… names are kept for PXD2 itself (mint with --pxd2 if this is PXD2's)"
    hub_ids = {h.get("id") for h in reg.get("hubs", [])}
    if name in hub_ids:
        return "that is a sub-hub's name"
    if minting and name in reg["names"]:
        return "already minted"
    return None


def folder_status(name, to):
    """Can names_build make this name's folder? -> (native flag, problem)"""
    d = os.path.join(SITE, name)
    f = os.path.join(d, "index.html")
    if not os.path.isdir(d):
        return False, None
    if os.path.isfile(f) and "<!-- pxd2-names:generated -->" in open(f, encoding="utf-8", errors="replace").read(400):
        return False, None
    if to.rstrip("/") == "/" + name:
        return True, None                      # the real site folder IS this name's page
    return False, f"a real site folder /{name}/ already exists and points elsewhere"


def write_cert(name, reg, rec):
    priv, auth = authority()
    e = reg["names"][name]
    body = {"type": "pxd-name-cert/1", "name": f"{name}{reg.get('tld', '.pxd')}", "to": e.get("to"), "title": e.get("title"),
            "owner": e.get("owner") or "PXD2", "minted": e.get("minted") or e.get("added"), "ledger": {"n": rec["n"], "hash": rec["hash"]},
            "registry": reg.get("registry", "PXD2 Names"), "issued": now()}
    doc = {"cert": body}
    if priv:
        import pxdsign
        body["issuer"] = auth["kid"]
        doc["signature"] = pxdsign.sign(priv, canon(body))
    else:
        doc["signature"] = None                # signed on base1 by `pxdmint.py sign`
    os.makedirs(CERTS, exist_ok=True)
    json.dump(doc, open(os.path.join(CERTS, f"{name}.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)


def last_rec(name):
    for r in reversed(ledger_lines()):
        if r["name"] == name:
            return r
    return None


def after_change(say=print):
    """Rebuild name folders, sign the registry if the key is here."""
    r = subprocess.run([sys.executable, os.path.join(SITE, "tools", "names_build.py")], cwd=SITE, capture_output=True, text=True)
    if r.returncode:
        say("names_build: " + (r.stderr or r.stdout).strip())
    priv, auth = authority()
    if priv:
        import pxdsign
        pxdsign.sign_registry(REG, KEYS)
        say("registry signed by the PXD authority")
    else:
        say("registry not signed here (no authority key on this machine); run `pxdmint.py sign` on base1")


def save_owner_contact(name, contact):
    if not contact:
        return
    os.makedirs(KEYS, exist_ok=True)
    d = json.load(open(OWNERS_PRIVATE)) if os.path.exists(OWNERS_PRIVATE) else {}
    d[name] = {"contact": contact, "at": now()}
    json.dump(d, open(OWNERS_PRIVATE, "w"), indent=2)


# ------------------------------------------------------------------ operations (shared by the CLI and the panel)
def op_check(name):
    reg = load_reg(); name = name.lower().strip().removesuffix(".pxd").removesuffix(".pxd2")
    why = problem_with(name, reg)
    if why == "already minted":
        e = reg["names"][name]
        return {"name": name, "free": False, "why": why, "owner": e.get("owner") or "PXD2", "to": e.get("to")}
    return {"name": name, "free": why is None, "why": why}


def op_mint(name, to, title="", owner="", group="Client sites", contact="", pxd2=False, status=""):
    reg = load_reg(); name = name.lower().strip().removesuffix(".pxd")
    problem_with.pxd2_ok = pxd2
    try:
        why = problem_with(name, reg)
    finally:
        problem_with.pxd2_ok = False
    if why:
        raise ValueError(f"{name}.pxd: {why}")
    if not to or not (to.startswith("/") or re.match(r"https?://", to)):
        raise ValueError("--to must be a site path like /clients/shop/ or a full https:// address")
    native, fprob = folder_status(name, to)
    if fprob:
        raise ValueError(f"{name}.pxd: {fprob}")
    e = {"to": to, "title": title or name, "added": datetime.date.today().isoformat(), "group": group,
         "owner": owner or "PXD2", "minted": now()}
    if native:
        e["native"] = True
    if status:
        e["status"] = status
    if group and group not in reg.get("groups", []) and group != "Client sites":
        reg.setdefault("groups", []).append(group)
    reg["names"][name] = e
    save_reg(reg)
    rec = ledger_add("mint", name, e, e["owner"])
    write_cert(name, reg, rec); save_owner_contact(name, contact)
    return rec


def op_update(name, **changes):
    reg = load_reg()
    if name not in reg["names"]:
        raise ValueError(f"{name}.pxd is not minted")
    e = reg["names"][name]
    for k in ("to", "title", "group", "status"):
        v = changes.get(k)
        if v:
            e[k] = v
    if e.get("to", "").startswith("/"):
        native, fprob = folder_status(name, e["to"])
        if fprob and not e.get("native"):
            raise ValueError(fprob)
    save_reg(reg)
    rec = ledger_add("update", name, e, e.get("owner") or "PXD2")
    write_cert(name, reg, rec)
    return rec


def op_transfer(name, owner, contact=""):
    reg = load_reg()
    if name not in reg["names"]:
        raise ValueError(f"{name}.pxd is not minted")
    e = reg["names"][name]; old = e.get("owner") or "PXD2"
    e["owner"] = owner
    save_reg(reg)
    rec = ledger_add("transfer", name, e, owner, note=f"from {old}")
    write_cert(name, reg, rec); save_owner_contact(name, contact)
    return rec


def op_release(name, reason):
    reg = load_reg()
    if name not in reg["names"]:
        raise ValueError(f"{name}.pxd is not minted")
    e = reg["names"].pop(name)
    save_reg(reg)
    rec = ledger_add("release", name, e, e.get("owner") or "PXD2", note=reason or "released")
    cp = os.path.join(CERTS, f"{name}.json")
    if os.path.exists(cp):
        os.remove(cp)
    gen = os.path.join(SITE, name, "index.html")
    if os.path.isfile(gen) and "<!-- pxd2-names:generated -->" in open(gen, encoding="utf-8").read(400):
        os.remove(gen)
        try:
            os.rmdir(os.path.dirname(gen))
        except OSError:
            pass
    return rec


def op_whois(name):
    reg = load_reg()
    hist = [r for r in ledger_lines() if r["name"] == name]
    cert = None
    cp = os.path.join(CERTS, f"{name}.json")
    if os.path.exists(cp):
        cert = json.load(open(cp, encoding="utf-8"))
    return {"name": f"{name}.pxd", "entry": reg["names"].get(name), "history": hist, "deed": cert}


def op_verify():
    """The ledger chain, every deed against the ledger and the authority, the registry signature."""
    out = {"ledger": "ok", "problems": [], "deeds_signed": 0, "deeds_unsigned": 0, "registry": "unsigned"}
    prev = "0" * 64
    for i, r in enumerate(ledger_lines(), 1):
        h = r.get("hash"); body = {k: v for k, v in r.items() if k != "hash"}
        if r.get("n") != i or r.get("prev") != prev or hashlib.sha256(canon(body)).hexdigest() != h:
            out["ledger"] = f"BROKEN at line {i}"; out["problems"].append(f"ledger line {i} was changed or removed"); break
        prev = h
    reg = load_reg()
    _, auth = authority()
    if auth:
        import pxdsign
        pub = pxdsign.load_pub(auth["key"])
    last = {}
    for r in ledger_lines():
        last[r["name"]] = r
    for name in reg["names"]:
        if name not in last:
            out["problems"].append(f"{name}: in names.json but never minted in the ledger")
            continue
        cp = os.path.join(CERTS, f"{name}.json")
        if not os.path.exists(cp):
            out["problems"].append(f"{name}: no deed"); continue
        doc = json.load(open(cp, encoding="utf-8")); c = doc["cert"]
        if c["ledger"]["hash"] != last[name]["hash"]:
            out["problems"].append(f"{name}: deed is not for the latest ledger line")
        if c.get("to") != reg["names"][name].get("to"):
            out["problems"].append(f"{name}: deed points somewhere other than names.json")
        if doc.get("signature"):
            if auth and pxdsign.verify(pub, canon(c), doc["signature"]):
                out["deeds_signed"] += 1
            else:
                out["problems"].append(f"{name}: deed signature does not match the PXD authority")
        else:
            out["deeds_unsigned"] += 1
    sigp = REG + ".sig"
    if os.path.exists(sigp) and auth:
        import pxdsign
        ok, why = pxdsign.verify_registry(open(REG, "rb").read(), json.load(open(sigp)), auth)
        out["registry"] = f"signed {why}" if ok else f"BAD: {why}"
        if not ok:
            out["problems"].append(f"names.json signature: {why}")
    out["names"] = len(reg["names"]); out["ledger_lines"] = len(ledger_lines())
    out["clean"] = not out["problems"]
    return out


def op_backfill():
    """Put every name already in names.json on the ledger once (genesis), with a deed."""
    reg = load_reg(); have = {r["name"] for r in ledger_lines()}; n = 0
    for name, e in reg["names"].items():
        if name in have:
            continue
        e.setdefault("owner", "PXD2")
        rec = ledger_add("genesis", name, e, e["owner"], note="on the registry before the minter")
        write_cert(name, reg, rec); n += 1
    if n:
        save_reg(reg)
    return n


def op_sign():
    """On base1 with the key: sign every unsigned deed and the registry."""
    priv, auth = authority()
    if not priv:
        raise ValueError("no authority key here: run `pxdmint.py init` on base1 first")
    reg = load_reg(); n = 0
    for name in reg["names"]:
        cp = os.path.join(CERTS, f"{name}.json")
        rec = last_rec(name)
        if not rec:
            continue
        doc = json.load(open(cp, encoding="utf-8")) if os.path.exists(cp) else None
        if not doc or not doc.get("signature") or doc["cert"].get("issuer") != auth["kid"]:
            write_cert(name, reg, rec); n += 1
    import pxdsign
    pxdsign.sign_registry(REG, KEYS)
    return n


def op_init(name="PXD2 Authority"):
    if os.path.exists(os.path.join(KEYS, "authority.key.json")):
        raise ValueError("this machine already holds the PXD authority key")
    import pxdsign
    pxdsign.authority_init(KEYS, name)
    rec = json.load(open(os.path.join(KEYS, "authority.json")))
    json.dump(rec, open(PUBLIC_AUTH, "w"), indent=2)
    return rec


def op_publish(message="PXD Names: mint"):
    def git(*a):
        return subprocess.run(["git", *a], cwd=SITE, capture_output=True, text=True)
    git("add", "names.json", "names.json.sig", "names", "pxd/authority.json")
    reg = load_reg()
    git("add", *[n for n in reg["names"] if os.path.isdir(os.path.join(SITE, n))])
    c = git("commit", "-m", message)
    if c.returncode and "nothing to commit" in (c.stdout + c.stderr):
        return "nothing new to publish"
    p = git("push")
    return "published" if p.returncode == 0 else "committed; push failed: " + p.stderr.strip()[-300:]


# ------------------------------------------------------------------ the panel
PANEL = """<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>PXD Minter</title><style>
:root{--bg:#0b0b0a;--panel:#161513;--line:#2e2a24;--fg:#e8dfc8;--muted:#a39a88;--tan:#c9a46a;--blood:#c8282c;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
.wrap{max-width:980px;margin:0 auto;padding:28px 16px 60px;display:grid;gap:18px}h1{margin:0;font-size:30px;letter-spacing:.04em}h1 b{color:var(--blood)}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px;display:grid;gap:10px}
h2{margin:0;font-size:16px;color:var(--tan);letter-spacing:.08em;text-transform:uppercase}
.row{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}
input,select{width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:6px;background:#0f0f0d;color:var(--fg);font:inherit}
button{padding:10px 16px;border:0;border-radius:6px;background:var(--tan);color:#111;font-weight:700;cursor:pointer}button.alt{background:#2a2722;color:var(--fg)}
.out{white-space:pre-wrap;font:13px ui-monospace,monospace;color:var(--muted)}.ok{color:#8ac96a}.bad{color:#ff8a7a}
table{width:100%;border-collapse:collapse;font-size:13px}td,th{text-align:left;padding:6px;border-bottom:1px solid var(--line)}th{color:var(--muted)}
.pill{font-size:12px;padding:2px 8px;border-radius:99px;background:#2a2722}</style></head><body><div class=wrap>
<h1>PXD <b>MINTER</b></h1><div id=auth class=out></div>
<div class=card><h2>Mint a .pxd name</h2>
<div class=row><input id=m_name placeholder="name (no .pxd)"><input id=m_to placeholder="/clients/shop/ or https://..."><input id=m_title placeholder="title"></div>
<div class=row><input id=m_owner placeholder="owner (business name, public)"><input id=m_contact placeholder="owner contact (kept private, never in git)"><input id=m_group value="Client sites"></div>
<div><button onclick=check()>Check</button> <button onclick=mint()>Mint</button> <label><input type=checkbox id=m_pxd2 style="width:auto"> PXD2's own name</label></div><div id=m_out class=out></div></div>
<div class=card><h2>Change or transfer</h2>
<div class=row><input id=u_name placeholder=name><input id=u_to placeholder="new destination (optional)"><input id=u_title placeholder="new title (optional)"><input id=u_owner placeholder="new owner (transfer)"></div>
<div><button onclick=upd()>Change</button> <button onclick=xfer()>Transfer</button> <button class=alt onclick=whois()>Whois</button></div><div id=u_out class=out></div></div>
<div class=card><h2>Keep it secure</h2><div><button onclick=verify()>Verify everything</button> <button class=alt onclick=sign()>Sign deeds + registry</button> <button class=alt onclick=publish()>Publish to git</button></div><div id=v_out class=out></div></div>
<div class=card><h2>Every name (<span id=count></span>)</h2><input id=filter placeholder=filter oninput=paint()><table id=list></table></div>
</div><script>
const $=id=>document.getElementById(id);let NAMES={};
async function api(p,b){const r=await fetch('/api/'+p,{method:'POST',body:JSON.stringify(b||{})});const j=await r.json();if(!r.ok)throw new Error(j.error);return j}
function show(el,t,ok){$(el).className='out '+(ok===false?'bad':ok?'ok':'');$(el).textContent=typeof t=='string'?t:JSON.stringify(t,null,2)}
async function load(){const j=await api('list');NAMES=j.names;$('auth').textContent=j.authority;paint()}
function paint(){const f=$('filter').value.toLowerCase();const ks=Object.keys(NAMES).filter(k=>!f||(k+JSON.stringify(NAMES[k])).toLowerCase().includes(f)).sort();
$('count').textContent=Object.keys(NAMES).length;$('list').innerHTML='<tr><th>name</th><th>points to</th><th>owner</th><th>group</th></tr>'+ks.map(k=>{const e=NAMES[k];return `<tr><td><b>${k}</b>.pxd</td><td>${esc(e.to)}</td><td>${esc(e.owner||'PXD2')}</td><td><span class=pill>${esc(e.group||'')}</span></td></tr>`}).join('')}
function esc(s){return String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
async function check(){try{const j=await api('check',{name:$('m_name').value});show('m_out',j.free?j.name+'.pxd is free':j.name+'.pxd: '+j.why+(j.owner?' (owner '+j.owner+')':''),j.free)}catch(e){show('m_out',e.message,false)}}
async function mint(){try{const j=await api('mint',{name:$('m_name').value,to:$('m_to').value,title:$('m_title').value,owner:$('m_owner').value,contact:$('m_contact').value,group:$('m_group').value,pxd2:$('m_pxd2').checked});show('m_out',j.say,true);load()}catch(e){show('m_out',e.message,false)}}
async function upd(){try{const j=await api('update',{name:$('u_name').value,to:$('u_to').value,title:$('u_title').value});show('u_out',j.say,true);load()}catch(e){show('u_out',e.message,false)}}
async function xfer(){try{const j=await api('transfer',{name:$('u_name').value,owner:$('u_owner').value});show('u_out',j.say,true);load()}catch(e){show('u_out',e.message,false)}}
async function whois(){try{show('u_out',await api('whois',{name:$('u_name').value}))}catch(e){show('u_out',e.message,false)}}
async function verify(){try{const j=await api('verify');show('v_out',j,j.clean)}catch(e){show('v_out',e.message,false)}}
async function sign(){try{const j=await api('sign');show('v_out',j.say,true)}catch(e){show('v_out',e.message,false)}}
async function publish(){if(!confirm('Commit the registry, ledger and deeds and push them to GitHub?'))return;try{const j=await api('publish');show('v_out',j.say,true)}catch(e){show('v_out',e.message,false)}}
load()</script></body></html>"""


def gui(port):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading, webbrowser

    class H(BaseHTTPRequestHandler):
        def _j(self, code, obj):
            b = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
            self.end_headers(); self.wfile.write(b)

        def do_GET(self):
            b = PANEL.encode()
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(b)))
            self.end_headers(); self.wfile.write(b)

        def do_POST(self):
            if self.headers.get("Host", "").split(":")[0] not in ("127.0.0.1", "localhost"):
                return self._j(403, {"error": "local only"})
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            act = self.path.rsplit("/", 1)[-1]; said = []
            try:
                if act == "list":
                    priv, auth = authority()
                    return self._j(200, {"names": load_reg()["names"], "authority":
                                         "PXD authority key on this machine: deeds and registry are signed as you mint." if priv else
                                         "No PXD authority key here: names are minted and chained; sign them on base1."})
                if act == "check":
                    return self._j(200, op_check(body.get("name", "")))
                if act == "whois":
                    return self._j(200, op_whois(body.get("name", "").strip().lower()))
                if act == "verify":
                    return self._j(200, op_verify())
                if act == "mint":
                    rec = op_mint(body["name"], body.get("to", ""), body.get("title", ""), body.get("owner", ""), body.get("group") or "Client sites",
                                  body.get("contact", ""), bool(body.get("pxd2")))
                    after_change(said.append); said.insert(0, f"minted {rec['name']}.pxd · ledger #{rec['n']} {rec['hash'][:12]}")
                elif act == "update":
                    rec = op_update(body["name"].strip().lower(), to=body.get("to"), title=body.get("title"))
                    after_change(said.append); said.insert(0, f"changed {rec['name']}.pxd · ledger #{rec['n']}")
                elif act == "transfer":
                    if not body.get("owner"):
                        raise ValueError("enter the new owner")
                    rec = op_transfer(body["name"].strip().lower(), body["owner"])
                    after_change(said.append); said.insert(0, f"{rec['name']}.pxd now belongs to {rec['owner']} · ledger #{rec['n']}")
                elif act == "sign":
                    said.append(f"signed {op_sign()} deed(s) and the registry")
                elif act == "publish":
                    said.append(op_publish())
                else:
                    return self._j(404, {"error": "unknown"})
                return self._j(200, {"say": "\n".join(said)})
            except Exception as e:  # noqa: BLE001
                return self._j(400, {"error": str(e)})

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    url = f"http://127.0.0.1:{port}/"
    print(f"PXD Minter panel: {url}  (close this window to stop)")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    srv.serve_forever()


# ------------------------------------------------------------------ CLI
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    g = sp.add_parser("gui"); g.add_argument("--port", type=int, default=8765)
    i = sp.add_parser("init"); i.add_argument("--name", default="PXD2 Authority")
    c = sp.add_parser("check"); c.add_argument("name")
    m = sp.add_parser("mint"); m.add_argument("name"); m.add_argument("--to", required=True); m.add_argument("--title", default="")
    m.add_argument("--owner", default=""); m.add_argument("--group", default="Client sites"); m.add_argument("--contact", default="")
    m.add_argument("--status", default=""); m.add_argument("--pxd2", action="store_true")
    u = sp.add_parser("update"); u.add_argument("name"); u.add_argument("--to"); u.add_argument("--title"); u.add_argument("--group"); u.add_argument("--status")
    t = sp.add_parser("transfer"); t.add_argument("name"); t.add_argument("--owner", required=True); t.add_argument("--contact", default="")
    r = sp.add_parser("release"); r.add_argument("name"); r.add_argument("--reason", required=True)
    w = sp.add_parser("whois"); w.add_argument("name")
    sp.add_parser("verify"); sp.add_parser("sign"); sp.add_parser("backfill")
    sp.add_parser("list")
    p = sp.add_parser("publish"); p.add_argument("-m", "--message", default="PXD Names: mint")
    a = ap.parse_args()
    try:
        if a.cmd == "gui":
            return gui(a.port)
        if a.cmd == "init":
            rec = op_init(a.name); print(f"PXD authority {rec['kid']} made. Public half: pxd/authority.json. Private key: keys/ (never commit, back it up offline)."); return
        if a.cmd == "check":
            j = op_check(a.name); print(f"{j['name']}.pxd: " + ("free" if j["free"] else j["why"] + (f" (owner {j['owner']})" if j.get("owner") else ""))); return
        if a.cmd == "mint":
            rec = op_mint(a.name, a.to, a.title, a.owner, a.group, a.contact, a.pxd2, a.status); print(f"minted {rec['name']}.pxd · ledger #{rec['n']} {rec['hash'][:12]}")
        elif a.cmd == "update":
            rec = op_update(a.name, to=a.to, title=a.title, group=a.group, status=a.status); print(f"changed {a.name}.pxd · ledger #{rec['n']}")
        elif a.cmd == "transfer":
            rec = op_transfer(a.name, a.owner, a.contact); print(f"{a.name}.pxd → {a.owner} · ledger #{rec['n']}")
        elif a.cmd == "release":
            rec = op_release(a.name, a.reason); print(f"released {a.name}.pxd · ledger #{rec['n']} (history kept)")
        elif a.cmd == "whois":
            print(json.dumps(op_whois(a.name), indent=2, ensure_ascii=False)); return
        elif a.cmd == "verify":
            j = op_verify(); print(json.dumps(j, indent=2)); sys.exit(0 if j["clean"] else 1)
        elif a.cmd == "sign":
            print(f"signed {op_sign()} deed(s) and the registry"); return
        elif a.cmd == "backfill":
            print(f"put {op_backfill()} existing name(s) on the ledger")
        elif a.cmd == "list":
            for k, e in sorted(load_reg()["names"].items()):
                print(f"{k}.pxd  ->  {e.get('to')}   [{e.get('owner') or 'PXD2'}]")
            return
        elif a.cmd == "publish":
            print(op_publish(a.message)); return
        after_change()
    except ValueError as e:
        raise SystemExit(f"refused: {e}")


if __name__ == "__main__":
    main()
