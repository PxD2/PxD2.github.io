"""PXD base1 bring-up: one script that checks base1 and gets every PXD service ready.

    python tools\\base1\\bringup.py              # check, install, set up keys, sign, write START-PXD.bat
    python tools\\base1\\bringup.py --check      # only report what's ready and what isn't
    python tools\\base1\\bringup.py --with-mini  # also download PXD Mini's small model (~300 MB)

What it does, in order (each step is skipped if it's already done):
  1. Checks Python, git, the GPU (nvidia-smi) and Ollama with its models.
  2. Installs the Python parts PXD uses (all MIT / Apache / BSD) and Playwright's Chromium.
  3. Creates the PXD authority key in %USERPROFILE%\\PXD Keys (offline, never on GitHub) if it doesn't exist,
     adds its PUBLIC half to names.json and pxd/authority.json, and signs names.json with it.
  4. Optionally sets up PXD Mini (runtime + small model).
  5. Writes START-PXD.bat next to the repo: one double-click starts the gateway, PXD Root, the Lit node,
     the studio and the Operator, each in its own window.
It never pushes to GitHub, never prints the private key, and never overwrites an existing key.
"""
import argparse, json, os, platform, shutil, subprocess, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
TOOLS = os.path.join(REPO, "tools")
KEYS = os.path.join(os.path.expanduser("~"), "PXD Keys")
PIP = ["cryptography", "pillow", "playwright", "mss", "pyautogui", "rapidocr_onnxruntime"] + (["uiautomation"] if sys.platform == "win32" else [])
WANT_MODELS = ["qwen2.5:14b", "gpt-oss:20b", "nomic-embed-text"]
OK, NO, SKIP = "  ok  ", "  !!  ", "  --  "


def say(mark, text):
    print(f"{mark}{text}", flush=True)


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def check():
    report = {}
    say(OK if sys.version_info >= (3, 10) else NO, f"Python {platform.python_version()} ({sys.executable})")
    report["git"] = bool(shutil.which("git")); say(OK if report["git"] else NO, "git " + ("found" if report["git"] else "missing: install Git for Windows"))
    smi = shutil.which("nvidia-smi")
    if smi:
        g = run([smi, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"]).stdout.strip()
        say(OK, f"GPU: {g}"); report["gpu"] = g
    else:
        say(NO, "nvidia-smi not found (GPU driver?)")
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=4) as r:
            models = [m["name"] for m in json.load(r).get("models", [])]
        report["models"] = models
        say(OK, f"Ollama running, {len(models)} model(s): {', '.join(models[:12])}{' …' if len(models) > 12 else ''}")
        for w in WANT_MODELS:
            if not any(m.split(":")[0] == w.split(":")[0] and (":" not in w or m == w or m.startswith(w)) for m in models):
                say(SKIP, f"suggested model not found: {w}  (ollama pull {w})")
    except Exception:  # noqa: BLE001
        say(NO, "Ollama not reachable on 127.0.0.1:11434 (start Ollama)")
    missing = []
    for p in PIP:
        mod = {"pillow": "PIL", "rapidocr_onnxruntime": "rapidocr_onnxruntime"}.get(p, p)
        try:
            __import__(mod)
        except Exception:  # noqa: BLE001
            missing.append(p)
    report["missing_pip"] = missing
    say(OK if not missing else SKIP, "Python parts: " + ("all installed" if not missing else "missing " + ", ".join(missing)))
    report["authority"] = os.path.exists(os.path.join(KEYS, "authority.key.json"))
    say(OK if report["authority"] else SKIP, f"PXD authority key: {'present' if report['authority'] else 'not created yet'} in {KEYS}")
    report["mini"] = os.path.exists(os.path.join(os.path.expanduser("~"), "PXD Gateway", "mini", "manifest.json"))
    say(OK if report["mini"] else SKIP, "PXD Mini model: " + ("installed" if report["mini"] else "not installed (--with-mini)"))
    return report


def install(missing):
    if missing:
        say(SKIP, "installing " + ", ".join(missing) + " …")
        r = run([sys.executable, "-m", "pip", "install", "--upgrade", *missing])
        say(OK if r.returncode == 0 else NO, "pip " + ("done" if r.returncode == 0 else r.stderr.strip().splitlines()[-1]))
    r = run([sys.executable, "-m", "playwright", "install", "chromium"])
    say(OK if r.returncode == 0 else NO, "Playwright Chromium " + ("ready" if r.returncode == 0 else r.stderr.strip()[-200:]))


def authority():
    sys.path.insert(0, os.path.join(TOOLS, "pxdz"))
    import pxdsign
    key = os.path.join(KEYS, "authority.key.json"); pub = os.path.join(KEYS, "authority.json")
    if not os.path.exists(key):
        pxdsign.authority_init(KEYS, "PXD Authority")
        say(OK, f"created the PXD authority key in {KEYS}. Back this folder up offline (USB); never put it on GitHub.")
    rec = json.load(open(pub))
    json.dump(rec, open(os.path.join(REPO, "pxd", "authority.json"), "w"), indent=2)
    names = os.path.join(REPO, "names.json"); reg = json.load(open(names, encoding="utf-8"))
    auths = reg.setdefault("authorities", [])
    if not any(a.get("kid") == rec["kid"] for a in auths):
        auths.insert(0, {"name": "PXD Authority", "kid": rec["kid"], "key": rec["key"]})
        json.dump(reg, open(names, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        say(OK, f"added authority {rec['kid']} (public half) to names.json")
    pxdsign.sign_registry(names, KEYS)
    ok, detail = pxdsign.verify_registry(open(names, "rb").read(), json.load(open(names + ".sig")), rec)
    say(OK if ok else NO, f"names.json signed and verified ({detail})")
    return rec


def mini():
    r = subprocess.run([sys.executable, os.path.join(TOOLS, "mini", "setup_mini.py")])
    say(OK if r.returncode == 0 else NO, "PXD Mini " + ("installed" if r.returncode == 0 else "setup failed (see above)"))


def start_bat(model):
    py = f'"{sys.executable}"'
    auth = os.path.join(REPO, "pxd", "authority.json")
    gw = os.path.join(os.path.expanduser("~"), "PXD Gateway")
    lines = ["@echo off", "REM PXD on base1: each service opens in its own window. Close a window to stop that service.",
             f'cd /d "{REPO}"',
             f'start "PXD Gateway :8790" cmd /k {py} tools\\gateway\\pxd_gateway.py --authority "{auth}" --store "{gw}\\bundles" --port 8790',
             f'start "PXD Root (DNS :5353, web :8053)" cmd /k {py} tools\\pxd2root\\pxd2root.py --registry names.json --authority "{auth}" --require-signed --dns-port 5353 --web-port 8053',
             f'start "PXD Lit node :7470" cmd /k {py} tools\\lit\\lit.py',
             f'start "PXD Studio" cmd /k {py} tools\\studio\\build_store.py watch',
             f'start "PXD Operator :8793" cmd /k {py} tools\\operator\\pxd_operator.py --model {model}',
             "timeout /t 4 >nul",
             "start \"\" http://127.0.0.1:8790/",
             "start \"\" http://127.0.0.1:8793/",
             "echo PXD started. Gateway http://127.0.0.1:8790  Operator http://127.0.0.1:8793  Mini http://127.0.0.1:8790/mini  Shop Builder http://127.0.0.1:8790/build",
             "echo For real .pxd DNS on port 53, run PXD Root as administrator with --dns-port 53 --web-port 80."]
    path = os.path.join(REPO, "START-PXD.bat")
    open(path, "w", newline="\r\n").write("\n".join(lines) + "\n")
    say(OK, f"wrote {path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true"); ap.add_argument("--with-mini", action="store_true")
    ap.add_argument("--skip-install", action="store_true"); ap.add_argument("--model", default="")
    a = ap.parse_args()
    print(f"PXD base1 bring-up · repo {REPO}\n")
    rep = check()
    if a.check:
        return
    print()
    if not a.skip_install:
        install(rep.get("missing_pip", []))
    authority()
    if a.with_mini and not rep.get("mini"):
        mini()
    models = rep.get("models") or []
    model = a.model or next((m for w in WANT_MODELS[:2] for m in models if m.startswith(w)), models[0] if models else "qwen2.5:14b")
    start_bat(model)
    print("\nNext: double-click START-PXD.bat. To publish the signed registry, commit names.json, names.json.sig and pxd/authority.json and push.")


if __name__ == "__main__":
    main()
