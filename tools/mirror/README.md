# Multi-main repositories

`pxd_mirror.py` copies the registry and every signed store bundle into each main repository in `mirrors.json`, and writes every copy into `names.json`. The PXD Browser, the Stores view and `pxd.js` try the sources in order and use the first that answers; the merchant signature proves any copy is identical.

1. Create the repositories on GitHub (public), ideally under organizations such as PXD2Games: GitHub allows one free personal account per person, so add organizations, not extra personal accounts.
2. List them in `mirrors.json`: `{"mirrors": [{"repo": "PXD2Games/pxd-main-1", "branch": "main"}, {"url": "https://<your gateway>/b/", "kind": "gateway"}]}`
3. On base1: `python tools/mirror/pxd_mirror.py`, then push this repo.

Buyers shop in **PXD Stores**: the PXD Browser's Stores view, or any PXD Gateway's home page. GitHub holds the data; the buying page is served by the gateway, not by GitHub Pages, whose terms don't allow sites built to process sales.
