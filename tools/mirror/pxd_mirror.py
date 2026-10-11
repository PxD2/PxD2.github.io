"""PXD multi-main repositories: one registry and store data, many homes.

Copies the registry and every store bundle (with its signature) from the main hub into each
main repository listed in mirrors.json, commits, pushes, and writes every copy's address back into
names.json, so the PXD Browser, the Stores view and pxd.js can fail over between them.
Bundles are signed, so a copy from any mirror is proven identical before it is used.

    python tools/mirror/pxd_mirror.py            # sync every mirror in tools/mirror/mirrors.json
    python tools/mirror/pxd_mirror.py --dry-run  # show what would change

mirrors.json:
  {"mirrors": [
     {"repo": "PxD2/pxd-main-1", "branch": "main"},
     {"repo": "PXD2Games/pxd-main-2", "branch": "main"},
     {"url": "https://gateway.example/b/", "kind": "gateway"}      # a PXD Gateway (no push; it pulls)
  ]}

Create each repository on GitHub first (public, empty is fine). Organizations are a good home for
mirrors; GitHub allows one free personal account per person, so use orgs, not extra accounts.
"""
import argparse, glob, json, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mirrors.json")
MAIN_RAW = "https://raw.githubusercontent.com/PxD2/PxD2.github.io/main/"
PAYLOAD = ["names.json", "pxd/authority*.json", "pxd/demo/*.pxdz", "pxd/demo/*.pxdz.sig", "stores/*.pxdz", "stores/*.pxdz.sig"]


def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"{' '.join(cmd)}\n{r.stderr.strip()}")
    return r.stdout.strip()


def payload_files():
    out = []
    for pat in PAYLOAD:
        out += [os.path.relpath(p, ROOT).replace("\\", "/") for p in glob.glob(os.path.join(ROOT, pat))]
    return sorted(set(out))


def raw_base(m):
    return f"https://raw.githubusercontent.com/{m['repo']}/{m.get('branch', 'main')}/"


def update_registry(mirrors, dry):
    """Every store source and the registry itself become lists: main hub first, then each mirror."""
    path = os.path.join(ROOT, "names.json"); reg = json.load(open(path, encoding="utf-8"))
    bases = [MAIN_RAW] + [raw_base(m) for m in mirrors if m.get("repo")]
    gateways = [m["url"].rstrip("/") + "/" for m in mirrors if m.get("kind") == "gateway"]
    reg["mirrors"] = {"registry": ["https://pxd2.github.io/names.json"] + [b + "names.json" for b in bases[1:]],
                      "repos": ["PxD2/PxD2.github.io"] + [m["repo"] for m in mirrors if m.get("repo")], "gateways": gateways}
    for name, e in reg["names"].items():
        st = e.get("store")
        if not st:
            continue
        first = st["bundle"][0] if isinstance(st["bundle"], list) else st["bundle"]
        rel = first.split("/main/", 1)[1] if "/main/" in first else None
        if not rel:
            continue
        fname = os.path.basename(rel)
        st["bundle"] = [b + rel for b in bases] + [g + fname for g in gateways]
        st["sig"] = [b + rel + ".sig" for b in bases] + [g + fname + ".sig" for g in gateways]
    if dry:
        print(json.dumps(reg["mirrors"], indent=2)); return
    json.dump(reg, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)


def sync(m, files, dry):
    repo, branch = m["repo"], m.get("branch", "main")
    tmp = tempfile.mkdtemp(prefix="pxdmirror-")
    try:
        url = m.get("clone_url") or f"https://github.com/{repo}.git"
        try:
            run(["git", "clone", "--depth", "1", "--branch", branch, url, tmp])
        except RuntimeError:
            run(["git", "clone", "--depth", "1", url, tmp])  # empty repo: no branch yet
            run(["git", "checkout", "-B", branch], cwd=tmp)
        for f in files:
            dst = os.path.join(tmp, f); os.makedirs(os.path.dirname(dst) or tmp, exist_ok=True); shutil.copy2(os.path.join(ROOT, f), dst)
        if not os.path.exists(os.path.join(tmp, "README.md")):
            open(os.path.join(tmp, "README.md"), "w").write(f"# PXD main repository mirror\n\nA signed copy of the PXD registry and store data from PxD2/PxD2.github.io. Readers verify every bundle's merchant signature, so this copy is as trustworthy as the original.\n")
        run(["git", "add", "-A"], cwd=tmp)
        if not run(["git", "status", "--porcelain"], cwd=tmp):
            print(f"  {repo}: already up to date"); return True
        if dry:
            print(f"  {repo}: would update {run(['git', 'status', '--porcelain'], cwd=tmp).count(chr(10)) + 1} file(s)"); return True
        run(["git", "-c", "user.name=PXD2", "-c", "user.email=pxd2games@gmail.com", "commit", "-q", "-m", "Sync from PXD main hub"], cwd=tmp)
        run(["git", "push", "-q", "origin", f"HEAD:{branch}"], cwd=tmp)
        print(f"  {repo}: synced"); return True
    except RuntimeError as e:
        print(f"  {repo}: FAILED ({str(e).splitlines()[-1]})"); return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--config", default=CONF)
    a = ap.parse_args()
    if not os.path.exists(a.config):
        json.dump({"mirrors": []}, open(a.config, "w"), indent=2)
        print(f"Created {a.config}. Add your main repositories, then run again."); return 0
    mirrors = json.load(open(a.config))["mirrors"]
    update_registry(mirrors, a.dry_run)
    files = payload_files()
    print(f"{len(files)} file(s) to {len([m for m in mirrors if m.get('repo')])} repositories")
    ok = all([sync(m, files, a.dry_run) for m in mirrors if m.get("repo")])
    print("Push the main hub too, so names.json lists every mirror." if not a.dry_run else "")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
