"""PXD Operator surfaces: how the agent sees and acts.

Every surface returns the same observation: a screenshot plus numbered "marks" (things it can act on,
each with a label and a box). The model picks a mark by number, so even a text-only model can operate a
screen, and a vision model also gets the screenshot with the numbers drawn on it.

  DesktopSurface  the real screen. Sees with OCR (RapidOCR, bundled models, Apache-2.0; or Tesseract) and, on
                  Windows, the accessibility tree (uiautomation, Apache-2.0). Acts with PyAutoGUI (BSD-3).
                  Moving the mouse into a screen corner stops it at once (PyAutoGUI fail-safe).
  BrowserSurface  a Chromium window driven by Playwright (Apache-2.0). Sees the page's real buttons, links and
                  fields (no OCR guessing) and acts on them directly.
"""
import hashlib, io, json, os, re, shutil, subprocess, sys, tempfile, time

from PIL import Image, ImageDraw, ImageFont

RISKY = re.compile(r"\b(pay|payment|purchase|buy|checkout|place order|order now|delete|remove|erase|send|submit|confirm|transfer|wire|"
                   r"password|passcode|sign in|log ?in|install|uninstall|format|shut ?down|restart|empty trash|unsubscribe|publish)\b", re.I)


def font(size=14):
    for p in ("C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def draw_marks(img, marks):
    """The screenshot with each mark's number drawn on it (for vision models and for the operator GUI)."""
    im = img.convert("RGB").copy(); d = ImageDraw.Draw(im); f = font(13)
    for m in marks:
        x0, y0, x1, y1 = m["box"]
        col = (208, 48, 47) if m.get("risky") else (118, 185, 0)
        d.rectangle([x0, y0, x1, y1], outline=col, width=2)
        tag = str(m["id"]); tw = d.textlength(tag, font=f)
        d.rectangle([x0, max(0, y0 - 16), x0 + tw + 6, max(16, y0)], fill=col)
        d.text((x0 + 3, max(0, y0 - 16)), tag, fill=(255, 255, 255), font=f)
    return im


def finish(marks, limit=120):
    """Number the marks top-to-bottom, left-to-right, and flag risky ones."""
    marks = [m for m in marks if m.get("label", "").strip() and m["box"][2] > m["box"][0] and m["box"][3] > m["box"][1]]
    marks.sort(key=lambda m: (round(m["box"][1] / 12), m["box"][0]))
    out = []
    for i, m in enumerate(marks[:limit], 1):
        m = dict(m, id=i, label=re.sub(r"\s+", " ", m["label"]).strip()[:80])
        m["risky"] = bool(RISKY.search(m["label"])) or m.get("role") == "password"
        out.append(m)
    return out


# ------------------------------------------------------------------ desktop
class XHands:
    """Mouse and keyboard on Linux/X11 through XTest (python-xlib), for machines where PyAutoGUI cannot load
    (it needs Tk on Linux). Same calls as PyAutoGUI; same fail-safe: a mouse in a screen corner stops everything."""
    NAMES = {"enter": "Return", "return": "Return", "esc": "Escape", "escape": "Escape", "tab": "Tab", "backspace": "BackSpace", "delete": "Delete",
             "del": "Delete", "space": "space", "up": "Up", "down": "Down", "left": "Left", "right": "Right", "home": "Home", "end": "End",
             "pageup": "Prior", "pagedown": "Next", "ctrl": "Control_L", "control": "Control_L", "shift": "Shift_L", "alt": "Alt_L",
             "win": "Super_L", "cmd": "Super_L", "super": "Super_L", **{f"f{i}": f"F{i}" for i in range(1, 13)}}

    def __init__(self):
        from Xlib import X, XK, display
        from Xlib.ext import xtest
        self.X, self.XK, self.xtest = X, XK, xtest
        self.d = display.Display(); self.root = self.d.screen().root

    def size(self):
        sc = self.d.screen(); return sc.width_in_pixels, sc.height_in_pixels

    def _failsafe(self):
        p = self.root.query_pointer(); w, h = self.size()
        if (p.root_x in (0, w - 1)) and (p.root_y in (0, h - 1)):
            raise RuntimeError("fail-safe: the mouse is in a screen corner, so the operator stopped")

    def _move(self, x, y):
        self.xtest.fake_input(self.d, self.X.MotionNotify, x=int(x), y=int(y)); self.d.sync(); time.sleep(0.05)

    def _button(self, b, times=1):
        for _ in range(times):
            self.xtest.fake_input(self.d, self.X.ButtonPress, b); self.xtest.fake_input(self.d, self.X.ButtonRelease, b); self.d.sync(); time.sleep(0.06)

    def click(self, x, y):
        self._failsafe(); self._move(x, y); self._button(1)

    def doubleClick(self, x, y):
        self._failsafe(); self._move(x, y); self._button(1, 2)

    def rightClick(self, x, y):
        self._failsafe(); self._move(x, y); self._button(3)

    def scroll(self, amount):
        self._failsafe(); self._button(4 if amount > 0 else 5, max(1, abs(int(amount)) // 120))

    def _code(self, key):
        name = self.NAMES.get(key.lower())
        sym = self.XK.string_to_keysym(name) if name else (ord(key) if len(key) == 1 else self.XK.string_to_keysym(key))
        kc = self.d.keysym_to_keycode(sym)
        if not kc:
            raise ValueError(f"no key for {key!r}")
        shift = len(key) == 1 and self.d.keycode_to_keysym(kc, 0) != sym and self.d.keycode_to_keysym(kc, 1) == sym
        return kc, shift

    def _tap(self, kc, shift=False):
        sh = self.d.keysym_to_keycode(self.XK.string_to_keysym("Shift_L"))
        if shift:
            self.xtest.fake_input(self.d, self.X.KeyPress, sh)
        self.xtest.fake_input(self.d, self.X.KeyPress, kc); self.xtest.fake_input(self.d, self.X.KeyRelease, kc)
        if shift:
            self.xtest.fake_input(self.d, self.X.KeyRelease, sh)
        self.d.sync()

    def press(self, key):
        self._failsafe(); self._tap(*self._code(key))

    def hotkey(self, *keys):
        self._failsafe(); codes = [self._code(k)[0] for k in keys]
        for kc in codes:
            self.xtest.fake_input(self.d, self.X.KeyPress, kc)
        for kc in reversed(codes):
            self.xtest.fake_input(self.d, self.X.KeyRelease, kc)
        self.d.sync()

    def write(self, text, interval=0.02):
        self._failsafe()
        for ch in text:
            self._tap(*self._code("enter" if ch == "\n" else "tab" if ch == "\t" else ch)); time.sleep(interval)


def hands():
    """PyAutoGUI where it loads (Windows, Mac, Linux with Tk); XTest on other Linux machines."""
    try:
        import pyautogui  # BSD-3
        pyautogui.FAILSAFE = True          # mouse into a corner = stop
        pyautogui.PAUSE = 0.15
        return pyautogui
    except (ImportError, SystemExit, Exception):  # noqa: BLE001  PyAutoGUI calls sys.exit() on Linux without Tk
        if sys.platform.startswith("linux"):
            return XHands()
        raise


class DesktopSurface:
    kind = "desktop"

    def __init__(self, ocr="auto"):
        import mss  # MIT
        self.mss, self.gui = mss.mss(), hands()
        self.ocr_kind, self._ocr = ocr, None
        self.scale = 1.0

    def _shot(self):
        mon = self.mss.monitors[1]
        raw = self.mss.grab(mon)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        sw, sh = self.gui.size()            # screen coordinates can differ from pixels (Windows display scaling)
        self.scale = sw / img.width
        return img

    def _ocr_lines(self, img):
        if self._ocr is None and self.ocr_kind in ("auto", "rapidocr"):
            try:
                from rapidocr_onnxruntime import RapidOCR  # Apache-2.0, models bundled: works offline
                self._ocr = ("rapid", RapidOCR())
            except ImportError:
                self._ocr = ("tess", None)
        if self._ocr is None:
            self._ocr = ("tess", None)
        if self._ocr[0] == "rapid":
            buf = io.BytesIO(); img.save(buf, "PNG")
            res, _ = self._ocr[1](buf.getvalue())
            out = []
            for box, text, conf in res or []:
                xs, ys = [p[0] for p in box], [p[1] for p in box]
                if float(conf) >= 0.5:
                    out.append({"label": text, "box": [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))], "role": "text", "src": "ocr"})
            return out
        exe = shutil.which("tesseract")
        if not exe:
            return []
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as t:
            img.save(t.name)
        try:
            tsv = subprocess.run([exe, t.name, "-", "--psm", "11", "tsv"], capture_output=True, text=True, timeout=60).stdout
        finally:
            os.unlink(t.name)
        lines = {}
        for row in tsv.splitlines()[1:]:
            c = row.split("\t")
            if len(c) < 12 or not c[11].strip() or float(c[10] or -1) < 40:
                continue
            key = (c[2], c[3], c[4])
            x, y, w, h = map(int, c[6:10])
            l = lines.setdefault(key, {"words": [], "box": [x, y, x + w, y + h]})
            l["words"].append(c[11]); b = l["box"]
            l["box"] = [min(b[0], x), min(b[1], y), max(b[2], x + w), max(b[3], y + h)]
        return [{"label": " ".join(l["words"]), "box": l["box"], "role": "text", "src": "ocr"} for l in lines.values()]

    def _uia(self):
        """Windows accessibility tree: real buttons, fields and menus with names (untested off Windows)."""
        if sys.platform != "win32":
            return []
        try:
            import uiautomation as auto  # Apache-2.0
        except ImportError:
            return []
        out, roles = [], {"ButtonControl": "button", "EditControl": "field", "MenuItemControl": "menu", "HyperlinkControl": "link",
                          "CheckBoxControl": "checkbox", "ComboBoxControl": "dropdown", "ListItemControl": "item", "TabItemControl": "tab"}
        try:
            win = auto.GetForegroundControl().GetTopLevelControl()
            for c, _ in auto.WalkControl(win, maxDepth=12):
                role = roles.get(c.ControlTypeName)
                if not role:
                    continue
                r = c.BoundingRectangle
                if r.width() <= 2 or r.height() <= 2:
                    continue
                label = c.Name or (c.GetValuePattern().Value if role == "field" and c.GetPattern(auto.PatternId.ValuePattern) else "") or role
                if role == "field" and getattr(c, "IsPassword", False):
                    role = "password"
                out.append({"label": label, "box": [r.left, r.top, r.right, r.bottom], "role": role, "src": "uia", "screen": True})
        except Exception:  # noqa: BLE001  accessibility can fail on some apps; OCR still works
            return []
        return out

    def observe(self):
        img = self._shot()
        uia = self._uia()
        if uia:  # accessibility gives screen coordinates: convert to pixels for drawing
            for m in uia:
                m["box"] = [int(v / self.scale) for v in m["box"]]
        ocr = self._ocr_lines(img)
        if uia:  # keep OCR text that is not inside an accessibility element
            ocr = [o for o in ocr if not any(u["box"][0] <= o["box"][0] and o["box"][2] <= u["box"][2] and u["box"][1] <= o["box"][1] and o["box"][3] <= u["box"][3] for u in uia)]
        marks = finish(uia + ocr)
        return {"surface": "desktop", "image": img, "marks": marks, "title": "", "url": "",
                "hash": hashlib.sha256(img.resize((64, 36)).tobytes()).hexdigest()[:16]}

    def _center(self, m):
        x0, y0, x1, y1 = m["box"]
        return int((x0 + x1) / 2 * self.scale), int((y0 + y1) / 2 * self.scale)

    def act(self, a, marks):
        g, t = self.gui, a["action"]
        m = next((x for x in marks if x["id"] == a.get("mark")), None)
        if t in ("click", "double_click", "right_click", "type") and a.get("mark") is not None and not m:
            raise ValueError(f"no mark {a.get('mark')} on screen")
        if t == "click":
            g.click(*self._center(m))
        elif t == "double_click":
            g.doubleClick(*self._center(m))
        elif t == "right_click":
            g.rightClick(*self._center(m))
        elif t == "type":
            if m:
                g.click(*self._center(m))
            if a.get("clear"):
                g.hotkey("ctrl", "a")
            g.write(str(a.get("text", "")), interval=0.02)
            if a.get("enter"):
                g.press("enter")
        elif t == "key":
            keys = [k.strip().lower() for k in str(a.get("keys", "")).split("+") if k.strip()]
            g.hotkey(*keys) if len(keys) > 1 else g.press(keys[0])
        elif t == "scroll":
            g.scroll(-600 if a.get("direction", "down") == "down" else 600)
        elif t == "wait":
            time.sleep(min(float(a.get("seconds", 1.5)), 10))
        else:
            raise ValueError(f"desktop cannot {t}")

    def close(self):
        pass


# ------------------------------------------------------------------ browser
MARK_JS = r"""() => {
  const sel = 'a[href],button,input,select,textarea,[role=button],[role=link],[role=tab],[role=menuitem],[role=checkbox],[contenteditable=true],summary,label[for]';
  const out = [];
  document.querySelectorAll('[data-pxd-mark]').forEach(e => e.removeAttribute('data-pxd-mark'));
  let n = 0;
  for (const e of document.querySelectorAll(sel)) {
    const r = e.getBoundingClientRect(), st = getComputedStyle(e);
    if (r.width < 4 || r.height < 4 || st.visibility === 'hidden' || st.display === 'none' || r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > innerWidth) continue;
    const tag = e.tagName.toLowerCase(), type = (e.getAttribute('type') || '').toLowerCase();
    let lab = (e.getAttribute('aria-label') || e.innerText || e.value || e.getAttribute('placeholder') || e.getAttribute('title') || e.getAttribute('name') || '').trim();
    if ((tag === 'input' || tag === 'select' || tag === 'textarea') && e.id) { const l = document.querySelector('label[for="' + e.id + '"]'); if (l) lab = (l.innerText.trim() + (e.value && type !== 'password' ? ': ' + e.value : '')) || lab; }
    if (tag === 'select') lab = (lab.split('\n')[0]) + ' [choices: ' + [...e.options].map(o => o.text).slice(0, 12).join(' | ') + ']';
    const role = type === 'password' ? 'password' : tag === 'a' ? 'link' : (tag === 'input' || tag === 'textarea' || e.isContentEditable) ? 'field' : tag === 'select' ? 'dropdown' : 'button';
    e.setAttribute('data-pxd-mark', ++n);
    out.push({ key: n, label: lab || role, role, box: [r.left, r.top, r.right, r.bottom].map(Math.round) });
  }
  // visible headings and text give the model context, without being clickable
  for (const e of document.querySelectorAll('h1,h2,h3,p,li,td,th,[role=alert],.error,.message')) {
    const r = e.getBoundingClientRect(); const t = (e.innerText || '').trim();
    if (!t || r.width < 4 || r.height < 4 || r.bottom < 0 || r.top > innerHeight || e.closest('[data-pxd-mark]')) continue;
    out.push({ key: null, label: t.slice(0, 120), role: 'text', box: [r.left, r.top, r.right, r.bottom].map(Math.round) });
  }
  return out;
}"""


class BrowserSurface:
    kind = "browser"

    def __init__(self, start_url="about:blank", profile=None, headless=False, executable=None):
        from playwright.sync_api import sync_playwright  # Apache-2.0
        self.pw = sync_playwright().start()
        args = {"headless": headless, "viewport": {"width": 1280, "height": 800}}
        if executable:
            args["executable_path"] = executable
        self.ctx = self.pw.chromium.launch_persistent_context(profile or tempfile.mkdtemp(prefix="pxd-operator-"), **args)
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        if start_url and start_url != "about:blank":
            self.page.goto(start_url, wait_until="domcontentloaded")

    def observe(self):
        self.page.wait_for_load_state("domcontentloaded")
        raw = self.page.evaluate(MARK_JS)
        img = Image.open(io.BytesIO(self.page.screenshot()))
        marks = finish([dict(r, src="dom", dom=r["key"]) for r in raw])
        return {"surface": "browser", "image": img, "marks": marks, "title": self.page.title(), "url": self.page.url,
                "hash": hashlib.sha256((self.page.url + json.dumps([m["label"] for m in marks])).encode()).hexdigest()[:16]}

    def _el(self, m):
        if not m or not m.get("dom"):
            raise ValueError("that mark is text, not something to click or type into")
        return self.page.locator(f'[data-pxd-mark="{m["dom"]}"]').first

    def act(self, a, marks):
        t = a["action"]; m = next((x for x in marks if x["id"] == a.get("mark")), None)
        if t in ("click", "double_click", "type", "select") and a.get("mark") is not None and not m:
            raise ValueError(f"no mark {a.get('mark')} on the page")
        if t == "click":
            self._el(m).click(timeout=5000)
        elif t == "double_click":
            self._el(m).dblclick(timeout=5000)
        elif t == "type":
            el = self._el(m)
            el.fill(str(a.get("text", "")), timeout=5000) if a.get("clear", True) else el.type(str(a.get("text", "")))
            if a.get("enter"):
                el.press("Enter")
        elif t == "select":
            self._el(m).select_option(label=str(a.get("text", "")), timeout=5000)
        elif t == "key":
            self.page.keyboard.press("+".join(k.strip().capitalize() if len(k.strip()) > 1 else k.strip() for k in str(a.get("keys", "")).split("+")))
        elif t == "scroll":
            self.page.mouse.wheel(0, 600 if a.get("direction", "down") == "down" else -600)
        elif t == "goto":
            url = str(a.get("url", ""))
            if not re.match(r"^https?://", url):
                raise ValueError("goto needs an http(s) address")
            self.page.goto(url, wait_until="domcontentloaded")
        elif t == "back":
            self.page.go_back()
        elif t == "wait":
            time.sleep(min(float(a.get("seconds", 1.5)), 10))
        else:
            raise ValueError(f"browser cannot {t}")
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:  # noqa: BLE001
            pass

    def close(self):
        try:
            self.ctx.close(); self.pw.stop()
        except Exception:  # noqa: BLE001
            pass
