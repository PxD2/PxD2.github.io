"""PXD Host: a small server (a Raspberry Pi 5, base2, any Linux box) that serves .pxd sites and their 3D assets
from your own hardware.

  - serves a copy of the PXD2 site (and any store folders you add) through the PXD root, by .pxd name and by path,
    with HTTP Range so 3D models and PXDZ bundles stream
  - reaches the internet through an outbound Cloudflare tunnel, so a home connection with no open ports works
    (Verizon home internet, a hotspot, Starlink)
  - tells the PXD registry where it is: hosts.json on GitHub gets this host's current address, and every PXD
    Browser and PXD Web finds sites marked  "host": "<id>"  here

    python3 pxdhost.py run          # what the service runs: root + tunnel + publish the address
    python3 pxdhost.py update       # bring the site copy up to date (only when you run it)
    python3 pxdhost.py status
Config: /etc/pxd-host.json   {"id": "pi1", "site": "/opt/pxd-host/site", "repo": "PxD2/PxD2.github.io", "port": 8080}
Token (optional, lets this host publish its address): /etc/pxd-host.token, a GitHub fine-grained token with
Contents: read and write on the site repo only.
"""
import base64, json, os, re, signal, subprocess, sys, threading, time, urllib.request

CONF = os.environ.get("PXD_HOST_CONF", "/etc/pxd-host.json")
TOKEN = os.environ.get("PXD_HOST_TOKEN_FILE", "/etc/pxd-host.token")
HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(os.path.dirname(CONF) if os.access(os.path.dirname(CONF), os.W_OK) else HERE, "pxd-host.state.json")


def log(m):
    print(time.strftime("%H:%M:%S ") + m, flush=True)


def conf():
    c = {"id": "pi1", "site": "/opt/pxd-host/site", "repo": "PxD2/PxD2.github.io", "port": 8080, "name": "PXD Host"}
    if os.path.exists(CONF):
        c.update(json.load(open(CONF)))
    return c


def gh(method, path, token, body=None):
    req = urllib.request.Request("https://api.github.com" + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                                          "User-Agent": "pxd-host", "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read() or b"{}")


def publish(c, url):
    """Write this host's address into hosts.json in the site repo (one small commit, only when the address changes)."""
    if not os.path.exists(TOKEN):
        log(f"address {url} (not published: no token at {TOKEN}; add it so browsers find this host)")
        return False
    token = open(TOKEN).read().strip()
    path = f"/repos/{c['repo']}/contents/hosts.json"
    for _ in range(3):
        try:
            try:
                cur = gh("GET", path, token); sha = cur["sha"]; data = json.loads(base64.b64decode(cur["content"]))
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    raise
                sha, data = None, {"hosts": {}}
            old = data.setdefault("hosts", {}).get(c["id"], {})
            if old.get("url") == url:
                log(f"address unchanged in hosts.json: {url}"); return True
            data["hosts"][c["id"]] = {"url": url, "name": c.get("name", "PXD Host"), "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            body = {"message": f"PXD Host {c['id']}: {url}", "content": base64.b64encode((json.dumps(data, indent=2) + "\n").encode()).decode()}
            if sha:
                body["sha"] = sha
            gh("PUT", path, token, body)
            log(f"published {c['id']} -> {url} in hosts.json"); return True
        except urllib.error.HTTPError as e:
            if e.code == 409:
                time.sleep(2); continue          # someone else changed the file: read again and retry
            log(f"publish failed: HTTP {e.code} {e.read()[:200]!r}"); return False
        except Exception as e:  # noqa: BLE001
            log(f"publish failed: {e}"); return False
    return False


def run():
    c = conf(); port = int(c.get("port", 8080))
    root = os.path.join(c["site"], "tools", "pxd2root", "pxd2root.py")
    if not os.path.exists(root):
        sys.exit(f"site copy not found at {c['site']} (run the installer, or set 'site' in {CONF})")
    procs = []

    def stop(*_):
        for p in procs:
            p.terminate()
        sys.exit(0)
    signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
    rootp = subprocess.Popen([sys.executable, root, "--registry", os.path.join(c["site"], "names.json"), "--site", c["site"],
                              "--host", "127.0.0.1", "--web-port", str(port), "--dns-port", str(c.get("dns_port", 5353)),
                              "--edge-ip", "127.0.0.1", "--ns-ip", "127.0.0.1", "--no-forward"], cwd=c["site"])
    procs.append(rootp)
    log(f"PXD root serving {c['site']} on 127.0.0.1:{port}")
    cf = subprocess.Popen(["cloudflared", "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{port}"],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    procs.append(cf)
    url = None
    for line in cf.stdout:
        m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
        if m and not url:
            url = m.group(0)
            log(f"tunnel up: {url}")
            json.dump({"url": url, "since": time.time()}, open(STATE, "w"))
            threading.Thread(target=publish, args=(c, url), daemon=True).start()
        if rootp.poll() is not None:
            log("PXD root stopped"); break
    stop()


def update():
    c = conf()
    r = subprocess.run(["git", "-C", c["site"], "pull", "--ff-only", "--depth", "1"], capture_output=True, text=True)
    print((r.stdout + r.stderr).strip() or "up to date")
    print("restart the host to load new names:  sudo systemctl restart pxd-host")


def status():
    c = conf()
    st = json.load(open(STATE)) if os.path.exists(STATE) else {}
    print(f"host id: {c['id']}   site: {c['site']}")
    print(f"address: {st.get('url', 'not up yet')}")
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{c.get('port', 8080)}/status", timeout=3) as r:
            s = json.loads(r.read()); print(f"root: {s['names']} names, registry {s['registry']['state']}")
    except Exception as e:  # noqa: BLE001
        print(f"root: not answering ({e})")
    print(f"publishes its address: {'yes' if os.path.exists(TOKEN) else 'no (no token)'}")


if __name__ == "__main__":
    {"run": run, "update": update, "status": status}.get(sys.argv[1] if len(sys.argv) > 1 else "status", status)()
