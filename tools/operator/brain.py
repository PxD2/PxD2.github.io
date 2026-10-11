"""PXD Operator brain: asks a local model (Ollama, MIT) for the next action, one step at a time.

The model sees the goal, what it has done so far, and the screen as a numbered list of marks (and, for vision
models such as qwen2.5vl, the screenshot with the numbers drawn on it). It answers with exactly one action in
JSON. Nothing leaves the machine.
"""
import base64, io, json, re, urllib.request

ACTIONS = """Actions (reply with ONE as JSON, nothing else):
{"thought": "...", "action": "click", "mark": 12}
{"thought": "...", "action": "type", "mark": 7, "text": "hello", "enter": false}
{"thought": "...", "action": "select", "mark": 9, "text": "option label"}            (browser dropdowns)
{"thought": "...", "action": "key", "keys": "ctrl+s"}
{"thought": "...", "action": "scroll", "direction": "down"}
{"thought": "...", "action": "goto", "url": "https://..."}                          (browser only)
{"thought": "...", "action": "wait", "seconds": 2}
{"thought": "...", "action": "ask", "question": "..."}          when you need the person (a choice, a missing detail)
{"thought": "...", "action": "done", "result": "what was accomplished"}
Rules: use mark numbers exactly as listed. One action per reply. Never invent information the goal does not give you;
ask instead. Say done only when the goal is visibly complete on screen."""

VALID = {"click", "double_click", "right_click", "type", "select", "key", "scroll", "goto", "back", "wait", "ask", "done"}


class Brain:
    def __init__(self, ollama="http://127.0.0.1:11434", model="qwen2.5:14b", vision=False, timeout=300):
        self.url, self.model, self.vision, self.timeout = ollama.rstrip("/"), model, vision, timeout
        self.tokens_in = self.tokens_out = 0

    def prompt(self, goal, history, obs, note=""):
        lines = [f"[{m['id']}] {m['role']}: {m['label']}" + (" (careful: this may send, pay, delete or sign in)" if m.get("risky") else "")
                 for m in obs["marks"]]
        where = f"Window: {obs['title']}  {obs['url']}".strip() if (obs.get("title") or obs.get("url")) else ""
        hist = "\n".join(history[-10:]) or "(nothing yet)"
        return (f"GOAL: {goal}\n\nDONE SO FAR:\n{hist}\n\n{where}\nON SCREEN NOW ({obs['surface']}):\n" + "\n".join(lines[:120]) +
                (f"\n\nNOTE: {note}" if note else "") + f"\n\n{ACTIONS}")

    def decide(self, goal, history, obs, marked_image=None, note=""):
        msg = {"role": "user", "content": self.prompt(goal, history, obs, note)}
        if self.vision and marked_image is not None:
            buf = io.BytesIO(); im = marked_image.copy(); im.thumbnail((1280, 1280)); im.save(buf, "PNG")
            msg["images"] = [base64.b64encode(buf.getvalue()).decode()]
        body = {"model": self.model, "stream": False, "format": "json", "options": {"temperature": 0.1, "num_predict": 300},
                "messages": [{"role": "system", "content": "You operate a computer for the user, carefully, one step at a time. Reply only with JSON."}, msg]}
        req = urllib.request.Request(self.url + "/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            out = json.load(r)
        self.tokens_in += out.get("prompt_eval_count") or 0; self.tokens_out += out.get("eval_count") or 0
        return parse(out.get("message", {}).get("content", ""))


def parse(text):
    """The model's reply as a checked action. Small models wrap JSON in prose or code fences; tolerate that."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"no JSON in the model's reply: {text[:120]!r}")
    a = json.loads(m.group(0))
    act = str(a.get("action", "")).lower().strip()
    if act not in VALID:
        raise ValueError(f"unknown action {act!r}")
    a["action"] = act
    if "mark" in a and a["mark"] is not None:
        a["mark"] = int(re.sub(r"\D", "", str(a["mark"])) or -1)
    if act in ("click", "double_click", "right_click", "select") and a.get("mark") is None:
        raise ValueError(f"{act} needs a mark number")
    if act in ("type", "select") and not isinstance(a.get("text"), str):
        raise ValueError(f"{act} needs text")
    return a


def describe(a, marks):
    """A short line for the history and the log: 'click [12] Save'."""
    m = next((x for x in marks if x["id"] == a.get("mark")), None)
    tgt = f" [{a['mark']}] {m['label'][:40]}" if m else ""
    extra = {"type": lambda: f" ← {a.get('text', '')[:40]!r}", "select": lambda: f" = {a.get('text', '')!r}", "key": lambda: f" {a.get('keys')}",
             "scroll": lambda: f" {a.get('direction', 'down')}", "goto": lambda: f" {a.get('url')}", "ask": lambda: f" {a.get('question')}",
             "done": lambda: f" {a.get('result', '')[:80]}", "wait": lambda: f" {a.get('seconds', 1.5)}s"}.get(a["action"], lambda: "")()
    return f"{a['action']}{tgt}{extra}"
