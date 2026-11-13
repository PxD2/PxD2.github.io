# PXD Browser

The browser for `.pxd`. Opens `mudforblood.pxd`, `propshop.pxd`, `pxd://hornetbell` directly, with no DNS setup, by reading the PXD2 Names registry and every sub-hub's registry on GitHub (cached for offline).

**Discover** replaces one ranked list with groups as tabs: Games, Stores & VR, Learning, Tools & making, Studio & company, Social & contact. Each group is searchable, so unknown sites are easy to find. Normal web addresses still work.

## Run (Windows, base1)
```
pip install PyQt6 PyQt6-WebEngine
python pxd_browser.py
```
or double-click `run_pxd_browser.bat`.

## Google · Shield
Press **Google · Shield** (Ctrl+Shift+G), or type `g <words>` in the address bar. You get the real google.com search, with Google kept from building a profile on you:
- Nothing is kept on disk: no history and no cookies after the tab closes. Third-party cookies are refused.
- Google's tracking and ad calls are blocked, on Google and on every other site (Analytics, Tag Manager, DoubleClick, AdSense, measurement pings).
- Result links go straight to the site, skipping Google's click logging (`google.com/url?q=`).
- Every request carries **Global Privacy Control**, a legal "do not sell or share my data" signal under California law, plus Do Not Track.
- **Exit:** put `{"exit": "socks5://host:port"}` in `%USERPROFILE%\.pxd\shield.json`. Then only Google's traffic leaves through PXD's exit server, so Google sees PXD and not you. If the exit is down, Google waits instead of falling back to your connection.

Keys: Ctrl+T new tab · Ctrl+L address bar · Ctrl+W close tab · Alt+Left/Right back/forward.
Add a site: add it to `names.json` with a `group`; every PXD Browser picks it up on next start.
