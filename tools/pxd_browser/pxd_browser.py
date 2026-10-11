"""PXD Browser — the browser for .pxd.

- Opens .pxd addresses natively (mudforblood.pxd, propshop.pxd, pxd://hornetbell): no DNS setup, no registrar.
- Reads the PXD2 Names registry and every sub-hub registry from GitHub, cached for offline use.
- Discover: instead of one ranked list, every site is sorted into groups shown as tabs
  (Games, Stores & VR, Learning, Tools & making, Studio & company, Social & contact),
  each searchable on its own, so finding sites you didn't know about is easy.
- Normal web addresses still work.

Run:  pip install PyQt6 PyQt6-WebEngine   then   python pxd_browser.py
"""
import html, json, os, sys, threading, urllib.request
from urllib.parse import urljoin, urlparse

from PyQt6.QtCore import QUrl, Qt, pyqtSignal, QObject
from PyQt6.QtGui import QAction, QKeySequence, QIcon
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QToolBar, QLineEdit, QLabel, QWidget, QSizePolicy
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings

APP = "PXD Browser"
MAIN_REGISTRY = os.environ.get("PXD_REGISTRY", "https://pxd2.github.io/names.json")
SITE = "https://pxd2.github.io/"
CACHE = os.path.join(os.path.expanduser("~"), ".pxd", "registry.json")
DISCOVER = QUrl("about:blank")
TLDS = (".pxd", ".pxd2")


# ---------------------------------------------------------------- registry
class Registry(QObject):
    changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.names, self.groups, self.hubs, self.status = {}, [], [], "Loading registry…"
        self._load_cache()

    def _load_cache(self):
        try:
            with open(CACHE, encoding="utf-8") as f:
                d = json.load(f)
            self.names, self.groups, self.hubs = d["names"], d["groups"], d["hubs"]
            self.status = f"{len(self.names)} .pxd names (saved copy)"
        except Exception:
            pass

    def refresh(self):
        threading.Thread(target=self._fetch, daemon=True).start()

    @staticmethod
    def _get(url):
        if os.path.isfile(url):  # a local registry file (testing, or fully offline hubs)
            with open(url, encoding="utf-8") as f:
                return json.load(f)
        req = urllib.request.Request(url, headers={"User-Agent": "PXD-Browser/1.0", "Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=12) as r:
            return json.load(r)

    def _fetch(self):
        try:
            main = self._get(MAIN_REGISTRY)
        except Exception:
            self.status = (self.status if self.names else "Offline: no registry yet"); self.changed.emit(); return
        names = {}
        for k, e in main.get("names", {}).items():
            names[k] = dict(e, hub="pxd2", url=urljoin(SITE, e["to"]))
        hubs = main.get("hubs", [])
        for h in hubs:
            reg = h.get("registry", "")
            if not reg or reg.rstrip("/") == MAIN_REGISTRY:
                continue
            try:
                sub = self._get(reg)
            except Exception:
                continue  # a sub-hub being down never breaks the browser
            for k, e in sub.get("names", {}).items():
                key = k if k not in names else f"{k}.{h['id']}"
                names[key] = dict(e, hub=h["id"], url=urljoin(reg, e["to"]))
        groups = main.get("groups") or sorted({e.get("group", "More") for e in names.values()})
        self.names, self.groups, self.hubs = names, groups, hubs
        self.status = f"{len(names)} .pxd names · {max(len(hubs), 1)} hub{'s' if len(hubs) > 1 else ''}"
        try:
            os.makedirs(os.path.dirname(CACHE), exist_ok=True)
            with open(CACHE, "w", encoding="utf-8") as f:
                json.dump({"names": names, "groups": groups, "hubs": hubs}, f)
        except Exception:
            pass
        self.changed.emit()

    def resolve(self, text):
        """Return (url, pxd_name) for a .pxd address, or (None, None)."""
        t = text.strip().lower()
        if t.startswith("pxd://"):
            t = t[6:]
        host = t.split("/")[0]
        for tld in TLDS:
            if host.endswith(tld):
                host = host[: -len(tld)]
                break
        e = self.names.get(host)
        return (e["url"], host) if e else (None, None)

    def name_for(self, url):
        u = url.rstrip("/")
        best = None
        for k, e in self.names.items():
            if e["url"].rstrip("/") == u and (best is None or len(k) < len(best)):
                best = k
        return best


# ---------------------------------------------------------------- discover page
def discover_html(reg, query=""):
    data = [{"name": k, "title": e.get("title", ""), "url": e["url"], "group": e.get("group", "More"),
             "hub": e.get("hub", "pxd2"), "added": e.get("added", ""), "world": e.get("world", "")}
            for k, e in sorted(reg.names.items())]
    groups = list(reg.groups) + sorted({d["group"] for d in data} - set(reg.groups))
    payload = json.dumps({"items": data, "groups": groups, "q": query, "status": reg.status}).replace("</", "<\\/")
    return """<!doctype html><html><head><meta charset="utf-8"><title>Discover · PXD</title><style>
:root{--bg:#0b0b0a;--panel:#161513;--line:#2e2a24;--fg:#e8dfc8;--muted:#a39a88;--tan:#c9a46a;--red:#c8282c}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 "Segoe UI",system-ui,sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:28px 18px 60px}
h1{font:800 34px Impact,"Arial Narrow",sans-serif;letter-spacing:.04em;margin:0}h1 span{color:var(--red)}
.st{color:var(--muted);font:13px Consolas,monospace;margin:4px 0 18px}
#q{width:100%;font:500 18px "Segoe UI",sans-serif;padding:13px 16px;border:2px solid var(--fg);border-radius:8px;background:var(--panel);color:var(--fg)}
#q:focus{outline:none;border-color:var(--tan)}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin:16px 0 14px}
.tabs button{font:600 14px "Segoe UI",sans-serif;padding:8px 14px;border-radius:999px;border:1px solid var(--line);background:var(--panel);color:var(--fg);cursor:pointer}
.tabs button[aria-selected=true]{background:var(--tan);color:#14100a;border-color:var(--tan)}
.tabs button b{font-weight:400;opacity:.7;margin-left:6px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px}
.card{display:grid;gap:4px;padding:14px;background:var(--panel);border:1px solid var(--line);border-radius:8px;color:var(--fg);text-decoration:none}
.card:hover,.card:focus{border-color:var(--tan);outline:none}
.card .n{font:600 16px Consolas,monospace;color:var(--tan);overflow-wrap:anywhere}
.card .t{color:var(--fg)}.card .m{font:12px Consolas,monospace;color:var(--muted)}
.tag{display:inline-block;font:600 10px Consolas,monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--red);border:1px solid currentColor;border-radius:999px;padding:1px 7px;margin-left:6px}
.sec h2{font:600 13px Consolas,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin:22px 0 8px}
.empty{color:var(--muted);padding:20px 0}
</style></head><body><div class="wrap">
<h1>PXD <span>Discover</span></h1><div class="st" id="st"></div>
<input id="q" type="search" placeholder="Search every .pxd site, or pick a group" autofocus>
<div class="tabs" id="tabs" role="tablist"></div><div id="out"></div></div>
<script>
const D=__DATA__;let tab="All";const $=s=>document.querySelector(s);$("#st").textContent=D.status;$("#q").value=D.q||"";
function match(i,q){return !q||(i.name+" "+i.title+" "+i.group).toLowerCase().includes(q)}
function card(i){const a=document.createElement("a");a.className="card";a.href=i.url;
 const n=document.createElement("span");n.className="n";n.textContent=i.name+".pxd";if(i.world){const t=document.createElement("span");t.className="tag";t.textContent=i.world==="store"?"VR store":"world";n.append(t)}
 const t=document.createElement("span");t.className="t";t.textContent=i.title||"";
 const m=document.createElement("span");m.className="m";m.textContent=(i.hub!=="pxd2"?"hub "+i.hub+" · ":"")+(i.added?"added "+i.added:"");
 a.append(n,t,m);return a}
function render(){const q=$("#q").value.trim().toLowerCase(),tabs=$("#tabs"),out=$("#out");tabs.textContent="";out.textContent="";
 const hits=D.items.filter(i=>match(i,q));["All",...D.groups].forEach(g=>{const c=g==="All"?hits.length:hits.filter(i=>i.group===g).length;if(g!=="All"&&!c)return;
  const b=document.createElement("button");b.type="button";b.setAttribute("role","tab");b.setAttribute("aria-selected",String(g===tab));b.textContent=g;const s=document.createElement("b");s.textContent=c;b.append(s);
  b.onclick=()=>{tab=g;render()};tabs.append(b)});
 if(tab!=="All"&&!hits.some(i=>i.group===tab))tab="All";
 const show=tab==="All"?D.groups:[tab];let any=false;
 show.forEach(g=>{const list=hits.filter(i=>i.group===g);if(!list.length)return;any=true;const sec=document.createElement("section");sec.className="sec";
  const h=document.createElement("h2");h.textContent=g;const grid=document.createElement("div");grid.className="grid";list.forEach(i=>grid.append(card(i)));sec.append(h,grid);out.append(sec)});
 if(!any){const e=document.createElement("p");e.className="empty";e.textContent="No .pxd site matches that yet.";out.append(e)}}
$("#q").addEventListener("input",render);render();
</script></body></html>""".replace("__DATA__", payload)


# ---------------------------------------------------------------- browser
class Page(QWebEnginePage):
    def __init__(self, win, profile=None):
        super().__init__(win)
        self.win = win

    def acceptNavigationRequest(self, url, nav_type, is_main):
        host = (url.host() or "").lower()
        if url.scheme() == "pxd" or host.endswith(TLDS):
            target, _ = self.win.reg.resolve(url.toString().replace("http://", "").replace("https://", ""))
            if target:
                self.win.current().setUrl(QUrl(target))
            else:
                self.win.show_discover(url.host() or url.toString())
            return False
        return super().acceptNavigationRequest(url, nav_type, is_main)

    def createWindow(self, _type):
        return self.win.new_tab().page()


class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP)
        self.resize(1320, 860)
        self.reg = Registry()
        self.discovering = set()
        self.tabs = QTabWidget(documentMode=True, tabsClosable=True, movable=True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(lambda _: self.sync_bar())
        self.setCentralWidget(self.tabs)

        bar = QToolBar(movable=False)
        self.addToolBar(bar)
        for label, key, fn in (("◀", QKeySequence.StandardKey.Back, lambda: self.current().back()),
                               ("▶", QKeySequence.StandardKey.Forward, lambda: self.current().forward()),
                               ("⟳", QKeySequence.StandardKey.Refresh, lambda: self.current().reload()),
                               ("Discover", None, lambda: self.show_discover()),
                               ("Stores", None, lambda: self.show_stores())):
            a = QAction(label, self)
            if key:
                a.setShortcut(key)
            a.triggered.connect(fn)
            bar.addAction(a)
        self.addr = QLineEdit(placeholderText="Type a .pxd name (mudforblood.pxd), a web address, or words to discover")
        self.addr.returnPressed.connect(self.go)
        bar.addWidget(self.addr)
        self.status = QLabel()
        bar.addWidget(self.status)
        for key, fn in ((QKeySequence.StandardKey.AddTab, lambda: self.new_tab()),
                        (QKeySequence("Ctrl+L"), lambda: (self.addr.setFocus(), self.addr.selectAll())),
                        (QKeySequence.StandardKey.Close, lambda: self.close_tab(self.tabs.currentIndex()))):
            a = QAction(self)
            a.setShortcut(key)
            a.triggered.connect(fn)
            self.addAction(a)

        self.setStyleSheet("""
            QMainWindow,QToolBar{background:#0b0b0a;color:#e8dfc8;border:0}
            QToolBar{padding:6px;spacing:6px}
            QToolButton{color:#e8dfc8;padding:5px 9px;border:1px solid #2e2a24;border-radius:6px;background:#161513}
            QToolButton:hover{border-color:#c9a46a}
            QLineEdit{background:#161513;color:#e8dfc8;border:1px solid #2e2a24;border-radius:14px;padding:6px 12px;font:14px Consolas}
            QLineEdit:focus{border-color:#c9a46a}
            QLabel{color:#a39a88;font:12px Consolas;padding:0 6px}
            QTabBar::tab{background:#161513;color:#a39a88;padding:7px 14px;border:1px solid #2e2a24;border-bottom:0;margin-right:2px}
            QTabBar::tab:selected{color:#e8dfc8;border-color:#c9a46a}
        """)
        self.reg.changed.connect(self.on_registry)
        self.status.setText(self.reg.status)
        self.new_tab()
        self.reg.refresh()

    # tabs
    def current(self):
        return self.tabs.currentWidget()

    def new_tab(self, url=None):
        view = QWebEngineView()
        view.setPage(Page(self))
        view.urlChanged.connect(lambda u, v=view: self.on_url(v, u))
        view.titleChanged.connect(lambda t, v=view: self.tabs.setTabText(self.tabs.indexOf(v), (t or "PXD")[:24]))
        i = self.tabs.addTab(view, "Discover")
        self.tabs.setCurrentIndex(i)
        if url:
            view.setUrl(QUrl(url))
        else:
            self.show_discover(view=view)
        return view

    def close_tab(self, i):
        if self.tabs.count() > 1:
            w = self.tabs.widget(i)
            self.discovering.discard(w)
            self.tabs.removeTab(i)
            w.deleteLater()
        else:
            self.show_discover()

    # navigation
    def show_stores(self):
        """Universal store view: renders every .pxd store's data stream and checks its merchant certificate."""
        v = self.current()
        v.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        self.discovering.discard(v)
        v.setUrl(QUrl.fromLocalFile(os.path.join(os.path.dirname(os.path.abspath(__file__)), "stores.html")))
        self.addr.setText("stores.pxd")

    def show_discover(self, query="", view=None):
        v = view or self.current()
        self.discovering.add(v)
        v.setHtml(discover_html(self.reg, query), DISCOVER)
        self.tabs.setTabText(self.tabs.indexOf(v), "Discover")
        self.addr.setText("")

    def go(self):
        text = self.addr.text().strip()
        if not text:
            return self.show_discover()
        if text.lower().rstrip("/") in ("stores", "stores.pxd", "pxd://stores"):
            return self.show_stores()
        target, _ = self.reg.resolve(text)
        if target:
            return self.current().setUrl(QUrl(target))
        if text.startswith(("http://", "https://")):
            return self.current().setUrl(QUrl(text))
        if " " not in text and "." in text:
            return self.current().setUrl(QUrl("https://" + text))
        self.show_discover(text)

    def on_url(self, v, u):
        if u.scheme() in ("http", "https"):
            self.discovering.discard(v)
        self.sync_bar(v)

    def sync_bar(self, view=None):
        v = view or self.current()
        if v is not self.current() or v is None:
            return
        if v in self.discovering:
            self.addr.setText(""); return
        url = v.url().toString()
        name = self.reg.name_for(url)
        self.addr.setText(f"{name}.pxd" if name else url)

    def on_registry(self):
        self.status.setText(self.reg.status)
        for i in range(self.tabs.count()):
            v = self.tabs.widget(i)
            if v in self.discovering:
                self.show_discover(view=v)


def main():
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--enable-features=WebXR")
    app = QApplication(sys.argv)
    app.setApplicationName(APP)
    w = Browser()
    w.show()
    for arg in sys.argv[1:]:
        w.addr.setText(arg)
        w.go()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
