"""PXD2 Soak: hold every .pxd name and every page behind it under steady load, and report what breaks.

What one round does, for every name in the registry (names.json + sub-hubs, as the root sees them):
  DNS   A over UDP, A over TCP, TXT over UDP, DoH GET and POST, /resolve JSON
  WEB   GET http://<name>.pxd/ through the root (private hosting or redirect), then every
        local file that page loads (scripts, styles, images, models, links to other local pages)
Rounds repeat until --minutes runs out. While it runs, the root's memory, threads and open
files are sampled so a slow leak shows up as a climbing line, not a crash next week.

    python tools/soak/pxdsoak.py --spawn                      # start a private-hosting root on test ports and soak it
    python tools/soak/pxdsoak.py --spawn --minutes 30 --workers 16
    python tools/soak/pxdsoak.py --root 192.168.1.20 --dns-port 53 --web-port 80   # soak a root already running (base1, a Pi)
    python tools/soak/pxdsoak.py --live --minutes 5           # soak the public pxd2.github.io/<name>/ pages too

Reports go to tools/soak/reports/: soak-<time>.json (everything), soak-<time>.md (short), soak-<time>.html (open it).
Exit code 0 = clean, 1 = something failed. Nothing is changed on any site; this only reads.
"""
import argparse, base64, collections, html, json, os, random, re, socket, struct, subprocess, sys, threading, time
import urllib.parse, urllib.request
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(os.path.dirname(HERE))
REPORTS = os.path.join(HERE, "reports")
LIVE_BASE = "https://pxd2.github.io"


# ------------------------------------------------------------------ DNS
def dns_query(name, qtype=1, qid=None):
    qid = qid if qid is not None else random.randint(0, 65535)
    q = b"".join(bytes([len(p)]) + p.encode() for p in name.rstrip(".").split(".")) + b"\0"
    return struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0) + q + struct.pack(">HH", qtype, 1)


def dns_check(resp, qid):
    if len(resp) < 12:
        raise ValueError("short DNS reply")
    rid, flags, _qd, an = struct.unpack(">HHHH", resp[:8])
    if rid != qid:
        raise ValueError("reply id mismatch")
    rcode = flags & 0xF
    if rcode:
        raise ValueError(f"rcode {rcode}")
    if an < 1:
        raise ValueError("no answer")
    return an


def udp_ask(host, port, data, timeout):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(timeout)
    try:
        s.sendto(data, (host, port)); return s.recv(4096)
    finally:
        s.close()


def tcp_ask(host, port, data, timeout):
    with socket.create_connection((host, port), timeout=timeout) as s:
        s.sendall(struct.pack(">H", len(data)) + data)
        n = struct.unpack(">H", recvn(s, 2))[0]
        return recvn(s, n)


def recvn(s, n):
    b = b""
    while len(b) < n:
        c = s.recv(n - len(b))
        if not c:
            raise ConnectionError("connection closed")
        b += c
    return b


# ------------------------------------------------------------------ HTTP
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


OPENER = urllib.request.build_opener(NoRedirect, urllib.request.ProxyHandler({}))
LIVE_OPENER = urllib.request.build_opener()  # live mode honours the system proxy and follows redirects


def http_get(url, host=None, timeout=15, live=False, method="GET", body=None, ctype=None):
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("User-Agent", "PXD2-Soak/1")
    if host:
        req.add_header("Host", host)
    if ctype:
        req.add_header("Content-Type", ctype)
    try:
        r = (LIVE_OPENER if live else OPENER).open(req, timeout=timeout)
        return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), e.read() if e.fp else b""


class Refs(HTMLParser):
    """Every local file a page asks the browser for."""
    ATTRS = {"src", "href", "data-src", "poster", "data-model", "data-glb"}

    def __init__(self):
        super().__init__(); self.refs = []

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if not v or k not in self.ATTRS:
                continue
            if tag == "a" and k == "href" and not re.search(r"\.(html?|json|glb|gltf|png|jpe?g|webp|svg|pdf|mp4)$|/$", v.split("#")[0].split("?")[0]):
                continue  # plain links: only follow ones that clearly point at a page or file
            self.refs.append(v)
        if tag == "link":
            pass


CODE_REF = re.compile(r"""["'(`]((?:\.{0,2}/)?[A-Za-z0-9_./-]+\.(?:json|js|mjs|css|png|jpe?g|webp|gif|svg|glb|gltf|bin|mp4|webm|mp3|wav|ogg|ico|woff2?|ttf|txt|csv|html))["')`?#]""")


def code_refs(base_path, body):
    """Raw local file names a script, stylesheet or JSON catalog mentions."""
    out = set()
    for r in CODE_REF.findall(body.decode("utf-8", "replace")):
        if r.startswith("//") or "${" in r or "node_modules/" in r or "/dist/" in r:
            continue
        out.add(r)
    return out


_SITE_FILES = None


def exists_anywhere(name):
    """Is a file with this name anywhere in the site? (if so, a code string that names it is probably built at runtime)"""
    global _SITE_FILES
    if _SITE_FILES is None:
        _SITE_FILES = set()
        for d, dirs, fs in os.walk(SITE):
            dirs[:] = [x for x in dirs if not x.startswith(".") and x != "reports"]
            _SITE_FILES.update(fs)
    return os.path.basename(name) in _SITE_FILES


def norm(path):
    import posixpath
    if not path.startswith("/"):
        path = "/" + path
    tail = "/" if path.endswith("/") else ""
    return "/" if path == "/" else (posixpath.normpath(path) + tail).replace("//", "/")


def local_refs(page_url_path, body):
    p = Refs()
    try:
        p.feed(body.decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001
        return []
    out = set()
    for r in p.refs:
        r = r.strip()
        if not r or r.startswith(("#", "mailto:", "tel:", "javascript:", "data:", "sms:", "blob:", "{", "$")) or "${" in r:
            continue
        u = urllib.parse.urlsplit(r)
        if u.scheme or u.netloc:
            continue  # another website: not ours to soak
        path = urllib.parse.urljoin(page_url_path, u.path)
        if path and not path.startswith("/"):
            path = "/" + path                 # a browser never climbs above the host root; Python's urljoin can drop the slash
        if path:
            import posixpath
            tail = "/" if path.endswith("/") else ""
            path = posixpath.normpath(path) + tail if path != "/" else "/"
            path = path.replace("//", "/")
            out.add(path)
    return sorted(out)


# ------------------------------------------------------------------ stats
class Stats:
    def __init__(self):
        self.lock = threading.Lock()
        self.lat = collections.defaultdict(list)
        self.ok = collections.Counter(); self.fail = collections.Counter()
        self.errors = collections.OrderedDict()  # (kind, target, reason) -> count

    def run(self, kind, target, fn):
        t = time.perf_counter()
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            ms = (time.perf_counter() - t) * 1000
            reason = str(e) or type(e).__name__
            with self.lock:
                self.fail[kind] += 1; self.lat[kind].append(ms)
                k = (kind, target, reason[:200]); self.errors[k] = self.errors.get(k, 0) + 1
            return False
        ms = (time.perf_counter() - t) * 1000
        with self.lock:
            self.ok[kind] += 1; self.lat[kind].append(ms)
        return True


def pct(xs, p):
    if not xs:
        return 0.0
    xs = sorted(xs); return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]


# ------------------------------------------------------------------ process sampling (root health over time)
def proc_sample(pid):
    try:
        st = open(f"/proc/{pid}/status").read()
        rss = int(re.search(r"VmRSS:\s+(\d+)", st).group(1)) // 1024
        thr = int(re.search(r"Threads:\s+(\d+)", st).group(1))
        fds = len(os.listdir(f"/proc/{pid}/fd"))
        return {"rss_mb": rss, "threads": thr, "fds": fds}
    except Exception:  # noqa: BLE001
        pass
    try:
        import psutil  # Windows / macOS
        p = psutil.Process(pid)
        return {"rss_mb": p.memory_info().rss // 2**20, "threads": p.num_threads(),
                "fds": (p.num_handles() if hasattr(p, "num_handles") else p.num_fds())}
    except Exception:  # noqa: BLE001
        return None


DISCOVER_CAP = 600


def discover(get, start):
    """Walk one name's site: the page, everything it loads, and what those scripts/styles/catalogs load in turn.
    Returns [(kind, path)]. web-asset: a file the HTML or CSS names. web-code: a file only code names, found.
    web-missing: a file code names that is not at any base the browser could use and not anywhere in the site."""
    seen, out, queue = {start}, [], [(start, start)]
    cache = {}

    def fetch(p):
        if p not in cache:
            try:
                cache[p] = get(p)
            except Exception as e:  # noqa: BLE001
                cache[p] = (0, {}, str(e).encode())
        return cache[p]

    while queue and len(seen) < DISCOVER_CAP:
        path, page_base = queue.pop(0)
        c, h, b = fetch(path)
        if c != 200:
            continue
        ct = h.get("Content-Type", "")
        is_page = ct.startswith("text/html") or path.endswith(("/", ".html", ".htm"))
        found = []                                   # (resolved path, kind, page base for what it loads)
        if is_page:
            found += [(r, "web-asset") for r in local_refs(path, b)]
            code, bases = code_refs(path, b), [path]
        elif "css" in ct or path.endswith(".css"):
            found += [(norm(urllib.parse.urljoin(path, r)), "web-asset") for r in code_refs(path, b)]
            code, bases = set(), []
        elif "javascript" in ct or path.endswith((".js", ".mjs")) or "json" in ct or path.endswith(".json"):
            code, bases = code_refs(page_base, b), [page_base, path, "/"]
        else:
            code, bases = set(), []
        for r in code:
            cands = list(dict.fromkeys(norm(urllib.parse.urljoin(x, r)) for x in bases))
            hit = next((cand for cand in cands if cand in seen or fetch(cand)[0] == 200), None)
            if hit:
                found.append((hit, "web-code"))
            elif not exists_anywhere(r):
                found.append((cands[0], "web-missing"))
        for r, kind in found:
            if r in seen:
                continue
            seen.add(r); out.append((kind, r))
            if r.endswith((".html", ".htm", "/")) and path != start:
                continue                             # other pages: covered by their own .pxd name
            if kind != "web-missing":
                queue.append((r, r if r.endswith((".html", ".htm", "/")) else page_base))
    return out


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default="127.0.0.1", help="address of the PXD root to soak")
    ap.add_argument("--dns-port", type=int, default=5353); ap.add_argument("--web-port", type=int, default=8080)
    ap.add_argument("--spawn", action="store_true", help="start a private-hosting root from this copy of the site on the test ports, soak it, stop it")
    ap.add_argument("--pid", type=int, help="process id of a root already running, to sample its memory/threads/files")
    ap.add_argument("--minutes", type=float, default=10, help="how long to hold the load (default 10)")
    ap.add_argument("--workers", type=int, default=12, help="checks in flight at once (default 12)")
    ap.add_argument("--live", action="store_true", help="also soak the public https://pxd2.github.io/<name>/ pages")
    ap.add_argument("--live-only", action="store_true", help="only soak the public pages (no root needed)")
    ap.add_argument("--timeout", type=float, default=10)
    ap.add_argument("--names", help="comma list: soak only these names")
    a = ap.parse_args()
    if a.live_only:
        a.live = True

    reg = json.load(open(os.path.join(SITE, "names.json"), encoding="utf-8"))
    names = reg["names"]
    if a.names:
        keep = set(a.names.split(",")); names = {k: v for k, v in names.items() if k in keep}
    tld = (reg.get("tld") or ".pxd").lstrip(".")

    proc = None
    if a.spawn and not a.live_only:
        cmd = [sys.executable, os.path.join(SITE, "tools", "pxd2root", "pxd2root.py"), "--registry", "names.json", "--site", ".",
               "--host", "127.0.0.1", "--dns-port", str(a.dns_port), "--web-port", str(a.web_port),
               "--edge-ip", "127.0.0.1", "--ns-ip", "127.0.0.1", "--no-forward", "--refresh", "60"]
        proc = subprocess.Popen(cmd, cwd=SITE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        a.pid = proc.pid; a.root = "127.0.0.1"
        for _ in range(100):
            try:
                if http_get(f"http://127.0.0.1:{a.web_port}/status", timeout=1)[0] == 200:
                    break
            except Exception:  # noqa: BLE001
                time.sleep(0.1)
        else:
            proc.kill(); raise SystemExit("root did not start:\n" + (proc.stdout.read() if proc.stdout else ""))

    S = Stats()
    web = f"http://{a.root}:{a.web_port}"
    status = {}
    if not a.live_only:
        try:
            status = json.loads(http_get(web + "/status", timeout=a.timeout)[2])
        except Exception as e:  # noqa: BLE001
            raise SystemExit(f"no PXD root answering at {web}: {e}  (start one, or use --spawn)")

    # ---- the checks
    def dns(kind, fqdn, qtype, via):
        def f():
            qid = random.randint(0, 65535); data = dns_query(fqdn, qtype, qid)
            if via == "udp":
                dns_check(udp_ask(a.root, a.dns_port, data, a.timeout), qid)
            elif via == "tcp":
                dns_check(tcp_ask(a.root, a.dns_port, data, a.timeout), qid)
            elif via == "doh-get":
                q = base64.urlsafe_b64encode(data).rstrip(b"=").decode()
                c, _, b = http_get(f"{web}/dns-query?dns={q}", timeout=a.timeout)
                if c != 200: raise ValueError(f"HTTP {c}")
                dns_check(b, qid)
            else:
                c, _, b = http_get(f"{web}/dns-query", timeout=a.timeout, method="POST", body=data, ctype="application/dns-message")
                if c != 200: raise ValueError(f"HTTP {c}")
                dns_check(b, qid)
        S.run(kind, fqdn, f)

    def resolve(fqdn):
        def f():
            c, _, b = http_get(f"{web}/resolve?name={fqdn}", timeout=a.timeout)
            j = json.loads(b)
            if c != 200 or j.get("Status") != 0 or "pxd" not in j:
                raise ValueError(f"HTTP {c} Status {j.get('Status')}")
        S.run("resolve", fqdn, f)

    def page(kind, url, host, path, entry, collect=None, live=False):
        def f():
            c, h, b = http_get(url, host=host, timeout=a.timeout, live=live)
            if live:
                if c != 200: raise ValueError(f"HTTP {c}")
            else:
                to = entry.get("to", "") if entry else ""
                if c in (301, 302):
                    loc = h.get("Location", "")
                    if to.startswith("/") and not loc.endswith("/"):
                        raise ValueError(f"private hosting redirected away to {loc}")
                    if not loc: raise ValueError(f"{c} with no Location")
                    return
                if c != 200: raise ValueError(f"HTTP {c}")
                if to.startswith("/") and h.get("X-PXD-Host") != "pxd2-private":
                    raise ValueError("served without X-PXD-Host: pxd2-private")
            if collect is not None and (h.get("Content-Type", "").startswith("text/html") or path.endswith(("/", ".html"))):
                collect.extend(local_refs(path, b))
        return S.run(kind, f"{host or ''}{path if not live else url}", f)

    # ---- discover every file each name loads (once), then soak that fixed set so load stays steady
    work, notes = [], set()
    print(f"PXD2 Soak: {len(names)} names · root {'(none, live only)' if a.live_only else web} · "
          f"{a.minutes:g} min · {a.workers} workers" + (" · live pages too" if a.live else ""))
    for key, e in sorted(names.items()):
        fqdn = f"{key}.{tld}"
        if not a.live_only:
            for via in ("udp", "tcp", "doh-get", "doh-post"):
                work.append(("dns", (f"dns-{via}", fqdn, 1, via)))
            work.append(("dns", ("dns-txt", fqdn, 16, "udp")))
            work.append(("resolve", (fqdn,)))
        local = (e.get("to") or "").startswith("/")
        if not a.live_only:
            work.append(("page", ("web-page", f"{web}/", fqdn, "/", e)))
            if local:
                for kind, r in discover(lambda path: http_get(f"{web}{urllib.parse.quote(path)}", host=fqdn, timeout=a.timeout), "/"):
                    if kind == "web-missing":
                        notes.add((fqdn, r)); continue
                    work.append(("page", (kind, f"{web}{urllib.parse.quote(r)}", fqdn, r, e)))
        if a.live and local:
            to = e["to"]
            work.append(("page", ("live-page", LIVE_BASE + to, None, to, e, None, True)))
            for kind, r in discover(lambda path: http_get(LIVE_BASE + urllib.parse.quote(path), timeout=a.timeout, live=True), to):
                if kind == "web-missing":
                    notes.add(("live", r)); continue
                work.append(("page", ("live-" + kind.split("-", 1)[1], LIVE_BASE + urllib.parse.quote(r), None, r, e, None, True)))
    # dedupe identical web-asset checks shared across names (e.g. the shared /sites.js) — keep them per host though,
    # because each host is a different private-hosting path lookup
    seen, uniq = set(), []
    for w in work:
        k = (w[0],) + tuple(x if not isinstance(x, dict) else id(x) for x in w[1])
        if k not in seen:
            seen.add(k); uniq.append(w)
    work = uniq
    print(f"  {len(work)} checks per round (DNS, DoH, resolve, pages, and every local file the pages load)")

    def do(w):
        t, args = w
        if t == "dns": dns(*args)
        elif t == "resolve": resolve(*args)
        else: page(*args)

    samples = []
    stop_at = time.time() + a.minutes * 60
    rounds = 0
    sampler_stop = threading.Event()

    def sampler():
        t0 = time.time()
        while not sampler_stop.is_set():
            if a.pid:
                s = proc_sample(a.pid)
                if s: samples.append(dict(s, t=round(time.time() - t0, 1)))
            sampler_stop.wait(5)
    threading.Thread(target=sampler, daemon=True).start()

    t_start = time.time()
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        while time.time() < stop_at:
            batch = work[:]; random.shuffle(batch)
            list(pool.map(do, batch)); rounds += 1
            done = sum(S.ok.values()) + sum(S.fail.values())
            print(f"  round {rounds}: {done} checks, {sum(S.fail.values())} failed, "
                  f"{done / max(time.time() - t_start, 0.001):.0f}/s" + (f", root {samples[-1]['rss_mb']} MB {samples[-1]['threads']} thr {samples[-1]['fds']} files" if samples else ""))
            if proc and proc.poll() is not None:
                print("  ROOT EXITED during the soak"); break
    sampler_stop.set()
    elapsed = time.time() - t_start
    root_died = bool(proc and proc.poll() is not None)
    root_out = ""
    if proc:
        proc.terminate()
        try:
            root_out = proc.communicate(timeout=5)[0] or ""
        except Exception:  # noqa: BLE001
            proc.kill()

    # ---- report
    kinds = sorted(set(S.ok) | set(S.fail))
    table = [{"check": k, "ok": S.ok[k], "failed": S.fail[k], "p50_ms": round(pct(S.lat[k], 50), 1),
              "p95_ms": round(pct(S.lat[k], 95), 1), "p99_ms": round(pct(S.lat[k], 99), 1),
              "max_ms": round(max(S.lat[k] or [0]), 1)} for k in kinds]
    errs = [{"check": k[0], "target": k[1], "reason": k[2], "times": n}
            for k, n in sorted(S.errors.items(), key=lambda kv: (-kv[1], kv[0]))]
    growth = None
    if len(samples) >= 4:
        q = max(1, len(samples) // 4)
        first, last = samples[:q], samples[-q:]
        avg = lambda xs, f: sum(x[f] for x in xs) / len(xs)  # noqa: E731
        growth = {f: round(avg(last, f) - avg(first, f), 1) for f in ("rss_mb", "threads", "fds")}
    total_ok, total_fail = sum(S.ok.values()), sum(S.fail.values())
    clean = total_fail == 0 and not root_died
    rep = {"when": time.strftime("%Y-%m-%d %H:%M:%S"), "clean": clean, "minutes": round(elapsed / 60, 2), "rounds": rounds,
           "workers": a.workers, "names": len(names), "checks_per_round": len(work), "ok": total_ok, "failed": total_fail,
           "rate_per_s": round((total_ok + total_fail) / max(elapsed, 0.001), 1), "root": status, "root_died": root_died,
           "table": table, "errors": errs, "root_samples": samples, "root_growth_first_to_last_quarter": growth,
           "root_output_tail": root_out[-3000:],
           "named_in_code_not_on_disk": [{"host": h, "path": p} for h, p in sorted(notes)]}
    os.makedirs(REPORTS, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    base = os.path.join(REPORTS, f"soak-{stamp}")
    json.dump(rep, open(base + ".json", "w", encoding="utf-8"), indent=2)
    md = [f"# PXD2 soak {rep['when']}", "",
          f"**{'CLEAN' if clean else 'PROBLEMS FOUND'}** · {len(names)} names · {rounds} rounds in {rep['minutes']} min · "
          f"{total_ok + total_fail} checks ({total_fail} failed) · {rep['rate_per_s']}/s · {a.workers} workers", "",
          "| check | ok | failed | p50 ms | p95 ms | p99 ms | max ms |", "|---|---|---|---|---|---|---|"]
    md += [f"| {r['check']} | {r['ok']} | {r['failed']} | {r['p50_ms']} | {r['p95_ms']} | {r['p99_ms']} | {r['max_ms']} |" for r in table]
    if growth:
        md += ["", f"Root over the soak (last quarter vs first): memory {growth['rss_mb']:+} MB, threads {growth['threads']:+}, open files {growth['fds']:+}"]
    if root_died:
        md += ["", "**The root process exited during the soak.**"]
    if errs:
        md += ["", "## Failures", "", "| check | target | reason | times |", "|---|---|---|---|"]
        md += [f"| {e['check']} | `{e['target']}` | {e['reason']} | {e['times']} |" for e in errs[:300]]
    if notes:
        md += ["", f"## Named in code, not on disk ({len(notes)}, not failures)", "",
               "Usually a placeholder the page already handles (shop photos not sent yet, items.json before inventory),",
               "a download name, or a file loaded from a CDN. Listed so nothing is hidden.", ""]
        md += [f"- `{h}{p}`" for h, p in sorted(notes)[:400]]
    open(base + ".md", "w", encoding="utf-8").write("\n".join(md) + "\n")
    open(base + ".html", "w", encoding="utf-8").write(html_report(rep))
    print("\n".join(md[:4]))
    print(f"  report: {base}.html")
    sys.exit(0 if clean else 1)


def html_report(r):
    e = html.escape
    rows = "".join(f"<tr><td>{e(t['check'])}</td><td>{t['ok']}</td><td class='{'bad' if t['failed'] else ''}'>{t['failed']}</td>"
                   f"<td>{t['p50_ms']}</td><td>{t['p95_ms']}</td><td>{t['p99_ms']}</td><td>{t['max_ms']}</td></tr>" for t in r["table"])
    errs = "".join(f"<tr><td>{e(x['check'])}</td><td><code>{e(x['target'])}</code></td><td>{e(x['reason'])}</td><td>{x['times']}</td></tr>"
                   for x in r["errors"][:500]) or "<tr><td colspan=4>None.</td></tr>"
    pts = r["root_samples"]
    spark = ""
    if len(pts) > 1:
        W, H = 640, 120
        def line(f, color):
            vs = [p[f] for p in pts]; lo, hi = min(vs), max(vs); span = (hi - lo) or 1
            xy = " ".join(f"{i * W / (len(vs) - 1):.1f},{H - 8 - (v - lo) / span * (H - 16):.1f}" for i, v in enumerate(vs))
            return f"<polyline fill='none' stroke='{color}' stroke-width='2' points='{xy}'/>"
        spark = (f"<h2>Root over time</h2><p class=dim>memory <span style='color:#c9a46a'>■</span> {pts[0]['rss_mb']}→{pts[-1]['rss_mb']} MB · "
                 f"threads <span style='color:#6aa0c9'>■</span> {pts[0]['threads']}→{pts[-1]['threads']} · open files <span style='color:#8ac96a'>■</span> {pts[0]['fds']}→{pts[-1]['fds']}</p>"
                 f"<svg viewBox='0 0 {W} {H}' width='100%' style='max-width:{W}px;background:#141412;border-radius:8px'>"
                 + line("rss_mb", "#c9a46a") + line("threads", "#6aa0c9") + line("fds", "#8ac96a") + "</svg>")
    verdict = "CLEAN" if r["clean"] else "PROBLEMS FOUND"
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>PXD2 soak {e(r['when'])}</title><style>
body{{background:#0b0b0a;color:#e8e6e3;font:15px/1.5 system-ui,sans-serif;max-width:1000px;margin:0 auto;padding:24px}}
h1{{font-size:22px;margin:0 0 4px}} .dim{{color:#9aa4ae}} table{{border-collapse:collapse;width:100%;margin:12px 0 28px;font-size:13px}}
td,th{{border-bottom:1px solid #2a2a27;padding:6px 8px;text-align:left;vertical-align:top}} th{{color:#9aa4ae;font-weight:600}}
.v{{display:inline-block;padding:4px 10px;border-radius:6px;font-weight:700;background:{'#1f3a1f' if r['clean'] else '#4a1d1d'};color:{'#8ac96a' if r['clean'] else '#ff8a7a'}}}
.bad{{color:#ff8a7a;font-weight:700}} code{{font-size:12px;word-break:break-all}}</style></head><body>
<h1>PXD2 soak · {e(r['when'])}</h1><p><span class=v>{verdict}</span></p>
<p class=dim>{r['names']} .pxd names · {r['checks_per_round']} checks a round · {r['rounds']} rounds in {r['minutes']} min ·
{r['ok'] + r['failed']} checks, {r['failed']} failed · {r['rate_per_s']}/s with {r['workers']} workers</p>
<table><tr><th>check</th><th>ok</th><th>failed</th><th>p50 ms</th><th>p95 ms</th><th>p99 ms</th><th>max ms</th></tr>{rows}</table>
{spark}<h2>Failures</h2><table><tr><th>check</th><th>target</th><th>reason</th><th>times</th></tr>{errs}</table></body></html>"""


if __name__ == "__main__":
    main()
