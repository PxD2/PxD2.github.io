# PXD Minter

Mints `.pxd` names for PXD2 and keeps them secure on GitHub. A `.pxd` name works like a `.com`, with no ICANN registrar and no yearly renewal.

**Double-click `Run_Minter.bat`** (base1). The panel opens in your browser: Check, Mint, Change, Transfer, Whois, Verify, Sign, and Publish (which commits and pushes, only when you click it).

| File | What it holds |
|---|---|
| `names.json` | the live registry: what every PXD root and PXD Browser reads |
| `names/ledger.jsonl` | every mint, change, transfer and release, each line chained to the one before by SHA-256; edit or delete an old line and `verify` names the line |
| `names/certs/<name>.json` | the name's deed: owner, destination, ledger line, signed by the PXD authority |
| `names.json.sig` | the authority's signature on the registry; PXD roots refuse a registry edited after signing |
| `keys/` (never in git) | the PXD authority's private key, and owners' private contact details |

## First time on base1
1. Run `py -3 tools\minter\pxdmint.py init`. This makes the PXD authority key in `keys\` and publishes the public half to `pxd\authority.json`. Back up `keys\` offline. Anyone holding it can sign names.
2. In the panel, click **Sign deeds + registry**. That signs all 115 existing deeds and `names.json`.
3. Click **Publish to git**.
4. Run `python tools\pxdweb\build.py`, then publish again. PXD Web downloads now carry the authority key and check signatures.

## Rules
- Names use letters, digits and dashes, 1–63 characters, with no dash at either end. `ns1`, `www`, `lit`, `api` and other root names are reserved.
- `pxd2…` names are PXD2's own: tick **PXD2's own name** in the panel, or pass `--pxd2`.
- A name can't take over a real site folder unless it points at that folder.
- The owner's business name is public in the registry. Phone and email go only to `keys\owners.json` on base1.
- **Publish** also queues the name pages with Bing, Yandex, Naver, Seznam and Yep (IndexNow). Google needs Search Console (verify pxd2.github.io once, submit sitemap.xml).
- Names are for life. `release` exists for mistakes; the ledger keeps the history either way.
