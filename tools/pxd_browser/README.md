# PXD Browser

The browser for `.pxd`. Opens `mudforblood.pxd`, `propshop.pxd`, `pxd://hornetbell` directly, with no DNS setup, by reading the PXD2 Names registry and every sub-hub's registry on GitHub (cached for offline).

**Discover** replaces one ranked list with groups as tabs: Games, Stores & VR, Learning, Tools & making, Studio & company, Social & contact. Each group is searchable, so unknown sites are easy to find. Normal web addresses still work.

## Run (Windows, base1)
```
pip install PyQt6 PyQt6-WebEngine
python pxd_browser.py
```
or double-click `run_pxd_browser.bat`.

Keys: Ctrl+T new tab · Ctrl+L address bar · Ctrl+W close tab · Alt+Left/Right back/forward.
Add a site: add it to `names.json` with a `group`; every PXD Browser picks it up on next start.
