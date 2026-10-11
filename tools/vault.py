"""PXD2 Vault: no site is ever lost to time.

Every PXD2 and client site is kept in four places at once:
  1. Git history (GitHub)            - every version, forever, free
  2. A dated archive on base1 / HOLD - our own disk, offline copy
  3. The Internet Archive            - free public snapshot of every page
  4. Arweave (optional, pay once)    - permanent storage designed for 200+ years

Run on base1 (Python 3, no installs; Arweave step needs the `ardrive` CLI and a
wallet keyfile you keep off git):
    python tools/vault.py                       # steps 1-3
    python tools/vault.py --arweave wallet.json # all four
"""
import argparse, datetime, json, os, shutil, subprocess, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://pxd2.github.io"
VAULT_DIR = os.environ.get("PXD2_VAULT", os.path.join(os.path.expanduser("~"), "PXD2 Vault"))

def urls():
    names = json.load(open(os.path.join(ROOT, "names.json"), encoding="utf-8"))["names"]
    out = {SITE + "/", SITE + "/names/", SITE + "/names.json"}
    for n, e in names.items():
        to = e["to"]
        if to.startswith("/"):
            out.add(SITE + to); out.add(SITE + "/" + n + "/")
    for d in sorted(os.listdir(ROOT)):
        if os.path.isfile(os.path.join(ROOT, d, "index.html")) and not d.startswith((".", "_")):
            out.add(f"{SITE}/{d}/")
    clients = os.path.join(ROOT, "clients")
    for d in sorted(os.listdir(clients)) if os.path.isdir(clients) else []:
        if os.path.isfile(os.path.join(clients, d, "index.html")) and not d.startswith("_"):
            out.add(f"{SITE}/clients/{d}/")
    return sorted(out)

def git_bundle(stamp):
    path = os.path.join(VAULT_DIR, f"pxd2-site-{stamp}.bundle")
    subprocess.run(["git", "-C", ROOT, "bundle", "create", path, "--all"], check=True)
    return path

def archive(stamp):
    base = os.path.join(VAULT_DIR, f"pxd2-site-{stamp}")
    return shutil.make_archive(base, "zip", ROOT, ".")  # whole working tree; history is in the bundle

def wayback(u):
    req = urllib.request.Request("https://web.archive.org/save/" + u, headers={"User-Agent": "PXD2-Vault/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status
    except Exception as e:
        return str(e)[:80]

def arweave(path, wallet):
    if not shutil.which("ardrive"):
        print("  ardrive CLI not installed (npm i -g ardrive-cli); skipping Arweave."); return None
    r = subprocess.run(["ardrive", "upload-file", "--wallet-file", wallet, "--local-path", path, "--turbo"],
                       capture_output=True, text=True)
    print(r.stdout[-600:] or r.stderr[-600:]); return r.returncode

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arweave", metavar="WALLET_JSON", help="also store the archive permanently on Arweave")
    ap.add_argument("--skip-wayback", action="store_true")
    a = ap.parse_args()
    os.makedirs(VAULT_DIR, exist_ok=True)
    stamp = datetime.date.today().isoformat()
    print("1-2. Git bundle + dated archive ->", VAULT_DIR)
    bundle = git_bundle(stamp); zipf = archive(stamp)
    print("   ", os.path.basename(bundle), "and", os.path.basename(zipf))
    log = {"date": stamp, "bundle": bundle, "archive": zipf, "wayback": {}, "arweave": None}
    if not a.skip_wayback:
        print("3. Internet Archive snapshots")
        for u in urls():
            log["wayback"][u] = wayback(u); print("   ", log["wayback"][u], u); time.sleep(6)  # be polite to archive.org
    if a.arweave:
        print("4. Arweave permanent copy"); log["arweave"] = arweave(zipf, a.arweave)
    json.dump(log, open(os.path.join(VAULT_DIR, f"vault-{stamp}.json"), "w"), indent=2)
    print("Vault run logged:", os.path.join(VAULT_DIR, f"vault-{stamp}.json"))

if __name__ == "__main__":
    sys.exit(main())
