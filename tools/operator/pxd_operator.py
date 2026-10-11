"""PXD Operator: an offline agent that operates the computer to finish tasks and workflows.

It looks (screenshot + numbered marks), asks a local model in Ollama what to do next, acts with the mouse and
keyboard (or inside a browser), and repeats until the goal is done, it needs you, or a limit is hit.
Everything runs on base1: no cloud, no tokens billed.

Safety, on by default
  - Autonomy "careful": it asks you before anything that could pay, send, delete, submit, sign in or install,
    and before typing into a password field. "ask" approves every step; "auto" trusts it (you chose that).
  - It has no shell action and never types secrets it wasn't given.
  - Stop button in the page; on the desktop, throw the mouse into a screen corner to halt instantly.
  - Step limit (default 40) and a stuck detector (the screen stops changing).
  - Every step is logged with its screenshot: runs/<id>/.
  - The control page listens on this machine only, unless you give --host and --token.

Workflows: save a finished run and replay it later. Replays find each button by its label, not by position,
so most replays use no model at all; when a label is missing the model steps in for that one step.

    python pxd_operator.py                                # http://127.0.0.1:8793
    python pxd_operator.py --model qwen2.5:14b --vision-model qwen2.5vl:7b
"""
import argparse, datetime, difflib, json, os, re, secrets, sys, threading, time, traceback, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import brain as B  # noqa: E402
import surfaces as S  # noqa: E402

CFG = {}
LOCK = threading.Lock()
RUN = {"status": "idle"}
CTRL = {"stop": False, "answer": None, "event": threading.Event()}


def now():
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def ollama(path, payload=None, timeout=10):
    req = urllib.request.Request(CFG["ollama"] + path, data=json.dumps(payload).encode() if payload else None, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def update(**kw):
    with LOCK:
        RUN.update(kw)


def wait_for_person(kind, text, shot):
    """Pause the run until the person answers in the page (or stops it)."""
    CTRL["answer"] = None; CTRL["event"].clear()
    update(status="waiting", pending={"kind": kind, "text": text, "shot": shot})
    while not CTRL["event"].wait(0.5):
        if CTRL["stop"]:
            return None
    update(status="running", pending=None)
    return CTRL["answer"]


def risky(a, marks):
    m = next((x for x in marks if x["id"] == a.get("mark")), None)
    if a["action"] in ("goto",):
        return False
    if m and m.get("risky") and a["action"] in ("click", "double_click", "type", "select"):
        return True
    if a["action"] == "type" and (S.RISKY.search(str(a.get("text", ""))) or (m and m.get("role") == "password")):
        return True
    if a["action"] == "key" and re.search(r"\b(delete|del)\b", str(a.get("keys", "")), re.I):
        return True
    if a.get("enter") or (a["action"] == "key" and str(a.get("keys", "")).lower() == "enter"):
        return any(x.get("risky") for x in marks)   # pressing Enter on a page with a send/pay/delete button
    return False


def find_mark(step, marks):
    """Workflow replay: the mark whose label best matches the recorded one (no model)."""
    want, role = step.get("label", "").lower(), step.get("role")
    if not want:
        return None
    same = [m for m in marks if not role or m["role"] == role or m["role"] == "text"]
    for m in same:
        if m["label"].lower() == want:
            return m
    for m in same:
        if want in m["label"].lower() or m["label"].lower() in want and len(m["label"]) > 3:
            return m
    best = max(same, key=lambda m: difflib.SequenceMatcher(None, want, m["label"].lower()).ratio(), default=None)
    if best and difflib.SequenceMatcher(None, want, best["label"].lower()).ratio() >= 0.75:
        return best
    return None


def fill(text, params):
    return re.sub(r"\{\{(\w+)\}\}", lambda m: str(params.get(m.group(1), m.group(0))), str(text))


def run_task(job):
    rid = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(2)
    rdir = os.path.join(CFG["runs"], rid); os.makedirs(rdir)
    CTRL["stop"] = False
    steps, history = [], []
    update(status="running", id=rid, goal=job["goal"], surface=job["surface"], steps=steps, result="", error="", pending=None,
           started=now(), model=job.get("model"), workflow=job.get("workflow", {}).get("name"))
    surf = None
    try:
        surf = S.DesktopSurface(ocr=CFG["ocr"]) if job["surface"] == "desktop" else \
            S.BrowserSurface(job.get("start_url") or "about:blank", profile=CFG.get("profile"), headless=CFG["headless"], executable=CFG.get("chromium"))
        brain = B.Brain(CFG["ollama"], job.get("model") or CFG["model"], vision=bool(job.get("vision")))
        wf, wi = job.get("workflow"), 0
        note, last_hash, same, bad = "", None, 0, 0
        for n in range(1, int(job.get("max_steps") or CFG["max_steps"]) + 1):
            if CTRL["stop"]:
                return update(status="stopped", error="Stopped by you")
            obs = surf.observe()
            if last_hash and obs["hash"] == last_hash and steps and steps[-1].get("act") in ("click", "key", "select", "goto", "scroll"):
                same += 1; note = "The last action changed nothing on screen. Try something else, or ask."
                if same >= 3:
                    return update(status="failed", error="Stuck: the screen stopped changing")
            else:
                same = 0
            marked = S.draw_marks(obs["image"], obs["marks"])
            shot = f"step-{n:03d}.png"; im = marked.copy(); im.thumbnail((1400, 1400)); im.save(os.path.join(rdir, shot))
            used_model = False
            if wf and wi < len(wf["steps"]):
                st = dict(wf["steps"][wi]); st["text"] = fill(st.get("text", ""), job.get("params", {}))
                if st["action"] in ("click", "double_click", "type", "select"):
                    m = find_mark(st, obs["marks"])
                    a = dict(st, mark=m["id"]) if m else None
                else:
                    a = st
                if a is None:   # the label moved or changed: let the model do this one step
                    a = brain.decide(f"{job['goal']} (Current step: {st['action']} '{st.get('label', '')}' {st.get('text', '')})", history, obs,
                                     marked if job.get("vision") else None, note); used_model = True
                wi += 1
                if wi >= len(wf["steps"]) and a["action"] != "done":
                    pass
            elif wf:
                a = {"action": "done", "result": f"Workflow {wf['name']} finished"}
            else:
                try:
                    a = brain.decide(job["goal"], history, obs, marked if job.get("vision") else None, note); used_model = True; bad = 0
                except (ValueError, json.JSONDecodeError) as e:
                    bad += 1; note = f"Your last reply was not a valid action ({e}). Reply with one JSON action."
                    if bad >= 3:
                        return update(status="failed", error=f"The model kept answering in the wrong format: {e}")
                    continue
            note = ""
            desc = B.describe(a, obs["marks"])
            rec = {"n": n, "act": a["action"], "desc": desc, "thought": str(a.get("thought", ""))[:300], "shot": shot, "url": obs.get("url", ""),
                   "risky": risky(a, obs["marks"]), "model": used_model, "ok": None,
                   "target": next(({"label": m["label"], "role": m["role"]} for m in obs["marks"] if m["id"] == a.get("mark")), None),
                   "raw": {k: a[k] for k in ("action", "text", "keys", "direction", "url", "seconds", "enter", "clear") if k in a}}
            steps.append(rec); update(steps=steps, tokens=[brain.tokens_in, brain.tokens_out])
            if a["action"] == "done":
                rec["ok"] = True
                return update(status="done", result=str(a.get("result", "")))
            if a["action"] == "ask":
                ans = wait_for_person("ask", str(a.get("question", "")), shot)
                if ans is None:
                    return update(status="stopped", error="Stopped by you")
                rec["ok"] = True; history.append(f"{n}. asked: {a.get('question')} → person answered: {ans}")
                continue
            mode = job.get("autonomy", "careful")
            if mode == "ask" or (mode == "careful" and rec["risky"]):
                ans = wait_for_person("approve", desc, shot)
                if ans is None:
                    return update(status="stopped", error="Stopped by you")
                if str(ans).lower() not in ("yes", "approve", "ok"):
                    rec["ok"] = False; rec["declined"] = True
                    history.append(f"{n}. {desc} → the person DECLINED this; do something else or ask")
                    continue
            try:
                surf.act(a, obs["marks"]); rec["ok"] = True; history.append(f"{n}. {desc} → done")
            except Exception as e:  # noqa: BLE001
                rec["ok"] = False; rec["error"] = str(e)[:200]; history.append(f"{n}. {desc} → FAILED: {str(e)[:120]}")
                note = f"That action failed: {str(e)[:160]}"
            update(steps=steps)
            last_hash = obs["hash"]
            time.sleep(CFG["settle"])
        update(status="failed", error=f"Reached the step limit ({job.get('max_steps') or CFG['max_steps']})")
    except BaseException as e:  # noqa: BLE001  includes SystemExit from a library: a run never hangs as "running"
        traceback.print_exc()
        update(status="failed", error=f"{type(e).__name__}: {str(e)[:300]}")
    finally:
        if surf and not (job["surface"] == "browser" and CFG.get("keep_browser")):
            surf.close()
        with LOCK:
            RUN["finished"] = now()
            json.dump({k: v for k, v in RUN.items() if k != "pending"}, open(os.path.join(rdir, "run.json"), "w"), indent=1)


# ------------------------------------------------------------------ workflows
WF_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,60}$")


def save_workflow(name, rid):
    if not WF_NAME.match(name):
        raise ValueError("name: lowercase letters, digits and dashes")
    run = json.load(open(os.path.join(CFG["runs"], rid, "run.json")))
    if run.get("status") != "done":
        raise ValueError("only a finished run can become a workflow")
    steps = []
    for s in run["steps"]:
        if s.get("ok") and s["act"] not in ("done", "ask"):
            st = dict(s["raw"]); st.update(s.get("target") or {}); steps.append(st)
    wf = {"name": name, "goal": run["goal"], "surface": run["surface"], "start_url": (run["steps"][0].get("url") if run["steps"] else ""),
          "steps": steps, "made": now(), "from_run": rid}
    json.dump(wf, open(os.path.join(CFG["workflows"], name + ".json"), "w"), indent=1)
    return wf


def list_workflows():
    out = []
    for f in sorted(os.listdir(CFG["workflows"])):
        if f.endswith(".json"):
            w = json.load(open(os.path.join(CFG["workflows"], f)))
            params = sorted(set(re.findall(r"\{\{(\w+)\}\}", json.dumps(w["steps"]))))
            out.append({"name": w["name"], "goal": w["goal"], "surface": w["surface"], "steps": len(w["steps"]), "params": params})
    return out


# ------------------------------------------------------------------ control page
class H(BaseHTTPRequestHandler):
    server_version = "PXD-Operator/1"

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, indent=1).encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(data)

    def _authed(self):
        if not CFG["token"]:
            return True
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        return secrets.compare_digest(self.headers.get("X-Operator-Token") or (q.get("token") or [""])[0], CFG["token"])

    def do_GET(self):
        p = urllib.parse.urlsplit(self.path).path
        if p == "/":
            return self._send(200, open(os.path.join(HERE, "operator.html"), "rb").read(), "text/html; charset=utf-8")
        if not self._authed():
            return self._send(403, {"error": "token required"})
        if p == "/api/state":
            with LOCK:
                return self._send(200, {k: v for k, v in RUN.items()})
        if p == "/api/models":
            try:
                return self._send(200, {"models": [m["name"] for m in ollama("/api/tags", timeout=4).get("models", []) if "embed" not in m["name"]], "default": CFG["model"]})
            except Exception as e:  # noqa: BLE001
                return self._send(200, {"models": [], "default": CFG["model"], "error": f"Ollama not reachable: {e}"})
        if p == "/api/workflows":
            return self._send(200, {"workflows": list_workflows()})
        m = re.match(r"^/api/shot/([0-9a-z-]+)/(step-\d{3}\.png)$", p)
        if m:
            f = os.path.join(CFG["runs"], m.group(1), m.group(2))
            return self._send(200, open(f, "rb").read(), "image/png") if os.path.isfile(f) else self._send(404, {"error": "no shot"})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        p = urllib.parse.urlsplit(self.path).path
        if not self._authed():
            return self._send(403, {"error": "token required"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except ValueError:
            return self._send(400, {"error": "JSON body"})
        if p in ("/api/run", "/api/workflows/run"):
            with LOCK:
                if RUN.get("status") in ("running", "waiting"):
                    return self._send(409, {"error": "a task is already running"})
            if p.endswith("workflows/run"):
                name = str(body.get("name", ""))
                if not WF_NAME.match(name) or not os.path.exists(os.path.join(CFG["workflows"], name + ".json")):
                    return self._send(404, {"error": "no such workflow"})
                wf = json.load(open(os.path.join(CFG["workflows"], name + ".json")))
                job = {"goal": wf["goal"], "surface": wf["surface"], "start_url": wf.get("start_url"), "workflow": wf, "params": body.get("params") or {},
                       "autonomy": body.get("autonomy", "careful"), "model": body.get("model"), "max_steps": len(wf["steps"]) + 10}
            else:
                goal = str(body.get("goal", "")).strip()
                if not goal:
                    return self._send(400, {"error": "say what to do"})
                if body.get("surface") not in ("desktop", "browser"):
                    return self._send(400, {"error": "surface: desktop or browser"})
                if body.get("autonomy", "careful") not in ("ask", "careful", "auto"):
                    return self._send(400, {"error": "autonomy: ask, careful or auto"})
                job = {k: body.get(k) for k in ("goal", "surface", "start_url", "model", "vision", "autonomy", "max_steps")}
                job["goal"] = goal; job["autonomy"] = job.get("autonomy") or "careful"
                job["max_steps"] = max(1, min(int(job.get("max_steps") or CFG["max_steps"]), 200))
            threading.Thread(target=run_task, args=(job,), daemon=True).start()
            time.sleep(0.2)
            return self._send(200, {"started": True})
        if p == "/api/answer":
            CTRL["answer"] = str(body.get("answer", "")); CTRL["event"].set()
            return self._send(200, {"ok": True})
        if p == "/api/stop":
            CTRL["stop"] = True; CTRL["answer"] = None; CTRL["event"].set()
            return self._send(200, {"ok": True})
        if p == "/api/workflows/save":
            try:
                return self._send(200, save_workflow(str(body.get("name", "")), str(body.get("run", ""))))
            except (ValueError, OSError) as e:
                return self._send(400, {"error": str(e)})
        return self._send(404, {"error": "not found"})

    def log_message(self, *a):
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    home = os.path.join(os.path.expanduser("~"), "PXD Operator")
    ap.add_argument("--host", default="127.0.0.1"); ap.add_argument("--port", type=int, default=8793)
    ap.add_argument("--token", default="", help="required when --host is not 127.0.0.1")
    ap.add_argument("--ollama", default="http://127.0.0.1:11434"); ap.add_argument("--model", default="qwen2.5:14b")
    ap.add_argument("--ocr", default="auto", choices=["auto", "rapidocr", "tesseract"])
    ap.add_argument("--max-steps", type=int, default=40); ap.add_argument("--settle", type=float, default=0.8, help="seconds to let the screen settle")
    ap.add_argument("--home", default=home); ap.add_argument("--headless", action="store_true"); ap.add_argument("--chromium")
    ap.add_argument("--keep-browser", action="store_true")
    a = ap.parse_args()
    if a.host not in ("127.0.0.1", "localhost") and len(a.token) < 16:
        ap.error("listening beyond this machine needs --token (16+ characters): this page controls the computer")
    CFG.update(ollama=a.ollama.rstrip("/"), model=a.model, ocr=a.ocr, max_steps=a.max_steps, settle=a.settle, token=a.token, headless=a.headless,
               chromium=a.chromium, keep_browser=a.keep_browser, runs=os.path.join(a.home, "runs"), workflows=os.path.join(a.home, "workflows"),
               profile=os.path.join(a.home, "browser-profile"))
    os.makedirs(CFG["runs"], exist_ok=True); os.makedirs(CFG["workflows"], exist_ok=True)
    print(f"PXD Operator on http://{a.host}:{a.port} · model {a.model} via {a.ollama} · logs in {a.home}")
    ThreadingHTTPServer((a.host, a.port), H).serve_forever()


if __name__ == "__main__":
    main()
