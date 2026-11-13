"""PXD2 Game Test: PXD2's own playtest / beta system. Invited people play PXD2 games; the code never leaves PXD2.

How it keeps the code secured
  - Stream mode (the default): the game runs on base1 / base2 (Unreal Pixel Streaming on the GPU) and testers play it
    in their browser. Only video goes out and only input comes back. No executable, no paks, no source ever ship.
  - Download mode (only for builds you mark download): the file is served from your machine, never from GitHub,
    only to a signed-in tester, every download logged against that tester. Ship only Shipping builds with
    pak encryption and signing turned on (see README).
  - Testers get a personal pass from a one-time invite. The gate stores only a hash of each pass; revoke any tester
    and their pass and sessions stop working at once.
  - Feedback, screenshots and crash reports come back here into a private folder (never the public site repo).

    python pxdplaytest.py invite --name "Mike" [--uses 1] [--days 14]   # one-time invite code to send a tester
    python pxdplaytest.py testers                                       # who has passes, last seen
    python pxdplaytest.py revoke <tester id>
    python pxdplaytest.py build add gt-alpha --title "Global Theaters alpha 0.3" [--mode stream|download] [--file PATH]
    python pxdplaytest.py build list | build remove <id>
    python pxdplaytest.py serve [--port 8095] [--stream http://127.0.0.1:80] [--tunnel] [--max-players 1]
    python pxdplaytest.py reports                                       # newest feedback and crash reports

Private data lives in  keys/playtest/  next to the site copy (gitignored), or in PXD_PLAYTEST_DATA.
"""
import argparse, asyncio, base64, datetime, hashlib, hmac, json, mimetypes, os, re, secrets, subprocess, sys, threading, time
from urllib.parse import parse_qs, unquote, urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DATA = os.environ.get("PXD_PLAYTEST_DATA", os.path.join(REPO, "keys", "playtest"))
DB = os.path.join(DATA, "testers.json")
BUILDS = os.path.join(DATA, "builds.json")
SECRET = os.path.join(DATA, "session.key")
REPORTS = os.path.join(DATA, "reports")
LOG = os.path.join(DATA, "sessions.jsonl")
COOKIE = "pxdgt"
SESSION_HOURS = 12
MAX_BODY = 16 * 1024 * 1024          # feedback with screenshots, crash zips
_lock = threading.Lock()


# ---------- private store ----------
def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(path, empty):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return json.loads(json.dumps(empty))


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def h(s):
    return hashlib.sha256(s.encode()).hexdigest()


def secret():
    os.makedirs(DATA, exist_ok=True)
    if not os.path.exists(SECRET):
        with open(SECRET, "wb") as f:
            f.write(secrets.token_bytes(32))
    return open(SECRET, "rb").read()


def event(kind, **kw):
    os.makedirs(DATA, exist_ok=True)
    with _lock, open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": now(), "e": kind, **kw}) + "\n")


# ---------- testers ----------
def make_invite(name, uses=1, days=14):
    db = load(DB, {"invites": {}, "testers": {}})
    code = "-".join(secrets.token_hex(2).upper() for _ in range(4))         # e.g. 9F3A-11C2-77B0-4E1D
    exp = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    db["invites"][h(code)] = {"name": name, "uses": uses, "expires": exp, "made": now()}
    save(DB, db)
    return code, exp


def redeem(code, name):
    code = (code or "").strip().upper()
    with _lock:
        db = load(DB, {"invites": {}, "testers": {}})
        inv = db["invites"].get(h(code))
        if not inv or inv["uses"] < 1 or inv["expires"] < now():
            return None
        inv["uses"] -= 1
        if inv["uses"] < 1:
            del db["invites"][h(code)]
        tid = "t" + secrets.token_hex(4)
        pas = "pxdgt_" + secrets.token_urlsafe(24)
        db["testers"][tid] = {"name": (name or inv["name"])[:60], "pass": h(pas), "joined": now(), "seen": "", "revoked": False,
                              "invited_as": inv["name"]}
        save(DB, db)
    event("redeem", tester=tid)
    return tid, pas


def tester_by_pass(pas):
    db = load(DB, {"invites": {}, "testers": {}})
    hp = h(pas or "")
    for tid, t in db["testers"].items():
        if hmac.compare_digest(t["pass"], hp) and not t.get("revoked"):
            return tid, t
    return None, None


def touch(tid):
    with _lock:
        db = load(DB, {"invites": {}, "testers": {}})
        if tid in db["testers"]:
            db["testers"][tid]["seen"] = now(); save(DB, db)


def alive(tid):
    t = load(DB, {"invites": {}, "testers": {}})["testers"].get(tid)
    return bool(t) and not t.get("revoked")


# ---------- sessions: signed cookie  tid.expiry.mac ----------
def sign_session(tid):
    exp = str(int(time.time()) + SESSION_HOURS * 3600)
    mac = hmac.new(secret(), f"{tid}.{exp}".encode(), "sha256").hexdigest()[:32]
    return f"{tid}.{exp}.{mac}"


def check_session(cookie_header):
    m = re.search(rf"(?:^|;\s*){COOKIE}=([A-Za-z0-9.]+)", cookie_header or "")
    if not m:
        return None
    try:
        tid, exp, mac = m.group(1).split(".")
    except ValueError:
        return None
    good = hmac.new(secret(), f"{tid}.{exp}".encode(), "sha256").hexdigest()[:32]
    if not hmac.compare_digest(mac, good) or int(exp) < time.time() or not alive(tid):
        return None
    return tid


# ---------- the gate ----------
class Gate:
    def __init__(self, stream, max_players, port):
        u = urlsplit(stream)
        self.up_host, self.up_port = u.hostname or "127.0.0.1", u.port or 80
        self.max_players, self.port = max_players, port
        self.players = {}          # connection id -> tester id (live game streams)
        self.live = {}             # connection id -> the tester's socket, so a revoke ends a stream already running

    async def watchdog(self):
        while True:
            await asyncio.sleep(5)
            for cid, tid in list(self.players.items()):
                if not alive(tid):
                    w = self.live.get(cid)
                    if w:
                        w.close(); event("play-cut", tester=tid)

    async def handle(self, reader, writer):
        try:
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 30)
        except Exception:  # noqa: BLE001
            writer.close(); return
        try:
            line, *hdrs = head.decode("latin-1").split("\r\n")
            method, target, _ = line.split(" ", 2)
        except ValueError:
            writer.close(); return
        H = {}
        for x in hdrs:
            if ":" in x:
                k, v = x.split(":", 1); H[k.strip().lower()] = v.strip()
        path = unquote(urlsplit(target).path)
        tid = check_session(H.get("cookie"))
        try:
            if path.startswith("/gate"):
                await self.gate(method, path, target, H, tid, reader, writer)
            elif not tid:
                await self.send(writer, 302, b"", headers={"Location": "/gate/"})
            else:
                await self.proxy(head, H, tid, reader, writer)
        except Exception as e:  # noqa: BLE001
            try:
                await self.send(writer, 500, json.dumps({"error": str(e)[:200]}).encode(), "application/json")
            except Exception:  # noqa: BLE001
                pass
        finally:
            try:
                writer.close()
            except Exception:  # noqa: BLE001
                pass

    async def send(self, w, code, body=b"", ctype="text/plain; charset=utf-8", headers=None):
        reason = {200: "OK", 206: "Partial Content", 302: "Found", 400: "Bad Request", 401: "Unauthorized", 403: "Forbidden",
                  404: "Not Found", 413: "Too Large", 416: "Range Not Satisfiable", 429: "Busy", 500: "Error", 502: "Bad Gateway"}.get(code, "OK")
        hd = {"Content-Type": ctype, "Content-Length": str(len(body)), "Cache-Control": "no-store", "Connection": "close",
              "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "X-Frame-Options": "SAMEORIGIN"}
        hd.update(headers or {})
        w.write((f"HTTP/1.1 {code} {reason}\r\n" + "".join(f"{k}: {v}\r\n" for k, v in hd.items()) + "\r\n").encode() + body)
        await w.drain()

    async def body(self, reader, H):
        n = int(H.get("content-length") or 0)
        if n > MAX_BODY:
            raise ValueError("too large")
        return await reader.readexactly(n) if n else b""

    async def gate(self, method, path, target, H, tid, reader, writer):
        if path in ("/gate", "/gate/"):
            page = open(os.path.join(HERE, "gate.html"), "rb").read()
            return await self.send(writer, 200, page, "text/html; charset=utf-8",
                                   {"Content-Security-Policy": "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'"})
        J = lambda code, obj, hd=None: self.send(writer, code, json.dumps(obj).encode(), "application/json", hd)  # noqa: E731
        if path == "/gate/api/redeem" and method == "POST":
            d = json.loads(await self.body(reader, H) or b"{}")
            r = redeem(d.get("invite"), d.get("name"))
            if not r:
                return await J(403, {"error": "That invite is not valid (used, expired or mistyped)."})
            tid, pas = r
            return await J(200, {"pass": pas, "tester": tid}, {"Set-Cookie": self.cookie(tid)})
        if path == "/gate/api/login" and method == "POST":
            d = json.loads(await self.body(reader, H) or b"{}")
            t_id, _ = tester_by_pass(d.get("pass"))
            if not t_id:
                event("login-refused"); return await J(401, {"error": "That pass is not active."})
            event("login", tester=t_id); touch(t_id)
            return await J(200, {"ok": True}, {"Set-Cookie": self.cookie(t_id)})
        if path == "/gate/api/logout":
            return await J(200, {"ok": True}, {"Set-Cookie": f"{COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict"})
        if not tid:
            return await J(401, {"error": "sign in"})
        if path == "/gate/api/me":
            t = load(DB, {"testers": {}})["testers"][tid]
            builds = [{"id": k, "title": b["title"], "mode": b["mode"], "notes": b.get("notes", ""), "added": b.get("added", ""),
                       "size": os.path.getsize(b["file"]) if b["mode"] == "download" and os.path.exists(b.get("file", "")) else None}
                      for k, b in load(BUILDS, {"builds": {}})["builds"].items() if b.get("live", True)]
            return await J(200, {"tester": tid, "name": t["name"], "builds": builds, "playing": len(self.players),
                                 "slots": self.max_players})
        if path == "/gate/api/feedback" and method == "POST":
            d = json.loads(await self.body(reader, H) or b"{}")
            day = datetime.date.today().isoformat(); os.makedirs(os.path.join(REPORTS, day), exist_ok=True)
            rid = time.strftime("%H%M%S-") + tid
            rec = {"tester": tid, "t": now(), "build": str(d.get("build", ""))[:40], "kind": str(d.get("kind", "note"))[:20],
                   "text": str(d.get("text", ""))[:20000], "ua": H.get("user-agent", "")[:200]}
            shot = d.get("image") or ""
            m = re.match(r"data:image/(png|jpeg|webp);base64,(.+)$", shot, re.S)
            if m:
                fn = f"{rid}.{m.group(1).replace('jpeg', 'jpg')}"
                open(os.path.join(REPORTS, day, fn), "wb").write(base64.b64decode(m.group(2)))
                rec["image"] = fn
            save(os.path.join(REPORTS, day, rid + ".json"), rec)
            event("feedback", tester=tid, build=rec["build"])
            return await J(200, {"ok": True, "id": rid})
        if path == "/gate/api/crash" and method == "POST":         # the game's crash reporter or a tester's zip
            data = await self.body(reader, H)
            day = datetime.date.today().isoformat(); os.makedirs(os.path.join(REPORTS, day), exist_ok=True)
            fn = time.strftime("%H%M%S-") + tid + "-crash.bin"
            open(os.path.join(REPORTS, day, fn), "wb").write(data)
            event("crash", tester=tid, bytes=len(data))
            return await J(200, {"ok": True})
        m = re.match(r"^/gate/dl/([a-z0-9-]+)$", path)
        if m:
            return await self.download(m.group(1), H, tid, method, writer)
        return await J(404, {"error": "not found"})

    def cookie(self, tid):
        return f"{COOKIE}={sign_session(tid)}; Path=/; Max-Age={SESSION_HOURS * 3600}; HttpOnly; Secure; SameSite=Strict"

    async def download(self, bid, H, tid, method, writer):
        b = load(BUILDS, {"builds": {}})["builds"].get(bid)
        if not b or b["mode"] != "download" or not b.get("live", True) or not os.path.isfile(b.get("file", "")):
            return await self.send(writer, 404, b"no such download")
        f, size = b["file"], os.path.getsize(b["file"])
        start, end, code = 0, size - 1, 200
        m = re.match(r"bytes=(\d*)-(\d*)$", H.get("range", ""))
        if m and (m.group(1) or m.group(2)):
            if m.group(1):
                start = int(m.group(1)); end = min(int(m.group(2) or end), size - 1)
            else:
                start = max(0, size - int(m.group(2)))
            if start > end:
                return await self.send(writer, 416, b"", headers={"Content-Range": f"bytes */{size}"})
            code = 206
        if start == 0:
            event("download", tester=tid, build=bid, bytes=size)
        n = end - start + 1
        hd = {"Content-Type": "application/octet-stream", "Content-Length": str(n), "Accept-Ranges": "bytes",
              "Content-Disposition": f'attachment; filename="{os.path.basename(f)}"', "Cache-Control": "no-store", "Connection": "close"}
        if code == 206:
            hd["Content-Range"] = f"bytes {start}-{end}/{size}"
        writer.write((f"HTTP/1.1 {code} {'Partial Content' if code == 206 else 'OK'}\r\n" + "".join(f"{k}: {v}\r\n" for k, v in hd.items()) + "\r\n").encode())
        if method == "HEAD":
            return await writer.drain()
        with open(f, "rb") as fh:
            fh.seek(start)
            while n > 0:
                chunk = fh.read(min(1 << 20, n))
                if not chunk:
                    break
                writer.write(chunk); n -= len(chunk)
                await writer.drain()

    async def proxy(self, head, H, tid, reader, writer):
        """Signed-in tester: pass the request to the game stream (Pixel Streaming signalling + player page).
        Ordinary requests are forced to Connection: close so every request is checked; a WebSocket upgrade is the
        live game stream and counts against the player slots."""
        upgrade = "websocket" in H.get("upgrade", "").lower()
        cid = None
        if upgrade:
            if len(self.players) >= self.max_players and tid not in self.players.values():
                return await self.send(writer, 429, b"All test seats are in use. Try again in a few minutes.")
            cid = secrets.token_hex(4); self.players[cid] = tid; self.live[cid] = writer
            event("play-start", tester=tid); touch(tid)
        lines = head.decode("latin-1").split("\r\n")
        out = [lines[0]]
        for x in lines[1:]:
            k = x.split(":", 1)[0].strip().lower()
            if not x or k in ("cookie", "x-forwarded-for") or (not upgrade and k in ("connection", "keep-alive")):
                continue
            out.append(x)
        if not upgrade:
            out.append("Connection: close")
        out.append(f"X-PXD-Tester: {tid}")
        try:
            ur, uw = await asyncio.open_connection(self.up_host, self.up_port)
        except OSError:
            if cid:
                self.players.pop(cid, None); self.live.pop(cid, None)
            return await self.send(writer, 502, b"The game server is not running right now.")
        uw.write(("\r\n".join(out) + "\r\n\r\n").encode("latin-1"))
        t0 = time.time()

        async def pipe(a, b):
            try:
                while True:
                    d = await a.read(65536)
                    if not d:
                        break
                    b.write(d); await b.drain()
            except Exception:  # noqa: BLE001
                pass
            finally:
                try:
                    b.close()
                except Exception:  # noqa: BLE001
                    pass
        try:
            await asyncio.gather(pipe(reader, uw), pipe(ur, writer))
        finally:
            if cid:
                self.players.pop(cid, None); self.live.pop(cid, None)
                event("play-end", tester=tid, seconds=int(time.time() - t0))


def tunnel(port):
    """Outbound Cloudflare tunnel; publishes the address as hosts.json "playtest" so /playtest/ finds it."""
    sys.path.insert(0, os.path.join(REPO, "tools", "pxdhost"))
    import pxdhost  # noqa: E402
    c = pxdhost.conf()
    try:
        cf = subprocess.Popen(["cloudflared", "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{port}"],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    except FileNotFoundError:
        print("cloudflared is not installed; the gate is only on this machine. Install it, or put the gate behind your own address.")
        return

    def watch():
        for line in cf.stdout:
            m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
            if m:
                print(f"PXD2 Game Test is live at {m.group(0)}/gate/", flush=True)
                pxdhost.publish(c, m.group(0) + "/gate/", "playtest"); break
        for _ in cf.stdout:
            pass
    threading.Thread(target=watch, daemon=True).start()


def serve(a):
    secret()
    g = Gate(a.stream, a.max_players, a.port)

    async def main():
        srv = await asyncio.start_server(g.handle, a.bind, a.port, limit=1 << 16)
        print(f"PXD2 Game Test gate on http://{a.bind}:{a.port}/gate/  ->  game stream {a.stream}  ({a.max_players} seat(s))", flush=True)
        if a.tunnel:
            tunnel(a.port)
        asyncio.create_task(g.watchdog())
        async with srv:
            await srv.serve_forever()
    asyncio.run(main())


def cli():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    i = sp.add_parser("invite"); i.add_argument("--name", required=True); i.add_argument("--uses", type=int, default=1); i.add_argument("--days", type=int, default=14)
    sp.add_parser("testers")
    r = sp.add_parser("revoke"); r.add_argument("tester")
    b = sp.add_parser("build"); b.add_argument("op", choices=["add", "list", "remove", "hide", "show"]); b.add_argument("id", nargs="?")
    b.add_argument("--title", default=""); b.add_argument("--mode", choices=["stream", "download"], default="stream")
    b.add_argument("--file", default=""); b.add_argument("--notes", default="")
    s = sp.add_parser("serve"); s.add_argument("--port", type=int, default=8095); s.add_argument("--bind", default="127.0.0.1")
    s.add_argument("--stream", default="http://127.0.0.1:80", help="Pixel Streaming signalling server (player side)")
    s.add_argument("--max-players", type=int, default=1); s.add_argument("--tunnel", action="store_true")
    sp.add_parser("reports")
    a = ap.parse_args()
    if a.cmd == "invite":
        code, exp = make_invite(a.name, a.uses, a.days)
        print(f"Invite for {a.name}: {code}\n  good for {a.uses} use(s) until {exp}\n  they open pxd2gametest.pxd (pxd2.github.io/playtest/), press Join, and enter it")
    elif a.cmd == "testers":
        db = load(DB, {"invites": {}, "testers": {}})
        for tid, t in db["testers"].items():
            print(f"{tid}  {t['name']:<24} joined {t['joined'][:10]}  last seen {t['seen'][:16] or '-':<16} {'REVOKED' if t.get('revoked') else ''}")
        print(f"{len(db['testers'])} tester(s), {len(db['invites'])} open invite(s)")
    elif a.cmd == "revoke":
        db = load(DB, {"invites": {}, "testers": {}})
        if a.tester not in db["testers"]:
            sys.exit("no such tester")
        db["testers"][a.tester]["revoked"] = True; save(DB, db); event("revoke", tester=a.tester)
        print(f"{a.tester} revoked: pass and open sessions stop working now")
    elif a.cmd == "build":
        bd = load(BUILDS, {"builds": {}})
        if a.op == "list":
            for k, v in bd["builds"].items():
                print(f"{k:<16} {v['mode']:<9} {'live' if v.get('live', True) else 'hidden':<7} {v['title']}  {v.get('file', '')}")
            return
        if not a.id or not re.match(r"^[a-z0-9-]{2,40}$", a.id):
            sys.exit("build id: 2-40 lowercase letters, digits, dashes")
        if a.op == "add":
            if a.mode == "download" and not os.path.isfile(a.file):
                sys.exit("download builds need --file pointing at the packaged (Shipping, encrypted) build zip")
            bd["builds"][a.id] = {"title": a.title or a.id, "mode": a.mode, "file": os.path.abspath(a.file) if a.file else "",
                                  "notes": a.notes, "added": now(), "live": True}
        elif a.op == "remove":
            bd["builds"].pop(a.id, None)
        else:
            bd["builds"][a.id]["live"] = a.op == "show"
        save(BUILDS, bd); print(f"build {a.id}: {a.op} done")
    elif a.cmd == "reports":
        if not os.path.isdir(REPORTS):
            return print("no reports yet")
        for day in sorted(os.listdir(REPORTS))[-3:]:
            for fn in sorted(os.listdir(os.path.join(REPORTS, day))):
                if fn.endswith(".json"):
                    r = json.load(open(os.path.join(REPORTS, day, fn), encoding="utf-8"))
                    print(f"{day} {fn[:6]} {r['tester']} [{r['kind']}] {r['build']}: {r['text'][:100]!r}{' +image' if r.get('image') else ''}")
                elif fn.endswith("-crash.bin"):
                    print(f"{day} {fn}  crash report")
        print(f"folder: {REPORTS}")
    elif a.cmd == "serve":
        serve(a)


if __name__ == "__main__":
    cli()
