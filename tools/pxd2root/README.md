# PXD2 Root — the `.pxd` top-level domain (alias `.pxd2`)

Our own domain ending, controlled by nobody but PXD2, free and never renewed.

- **On our network** (base1, laptops, Pi 5 droids, Hackspace): `http://mudforblood.pxd`, `http://hornetbell.pxd`, every name in `/names.json`.
- **For the public internet**: the same names at `https://pxd2.github.io/<name>` (built by `tools/names_build.py`).

## Run it on base1 (Windows, as administrator)
```
python tools\pxd2root\pxd2root.py
```
On a Pi: `sudo python3 tools/pxd2root/pxd2root.py`

Then set each device's DNS server to base1's LAN IP (router DHCP setting does every device at once).
Names reload from pxd2.github.io/names.json every 10 minutes.

## Add a name
1. Add it to `names.json` (`"name": {"to": "/page/" or "https://...", "title": "..."}`).
2. `python tools/names_build.py` and push. It is live on the web and on `.pxd`.

Limits: `.pxd` answers only on devices using PXD2's DNS, over plain HTTP (no public certificate authority signs private endings).
Public visitors always reach the names through pxd2.github.io.
