# Lit: linked internet traffic

The PMOC rule applied to the whole web: **if two machines already share a book, send ids, not paragraphs.**

| Layer | What travels | Where it comes from |
|---|---|---|
| COG / lex | a sentence becomes `meaning.variant` ids against a shared book | the book is cached once, forever (append-only) |
| PXDZ | a site is a signed manifest plus parts, each named by SHA-256 | only the parts on screen are fetched (HTTP Range) |
| Lit | parts move between neighbors | this device → your network's Lit nodes → the gateway → GitHub |
| .pmoc | slices on disk: lex books, weights, parts | one file per section, stored on GitHub, mountable on any node |

## How a page loads in the PXD Browser
1. **Header:** the manifest arrives (about 16 KB) and is checked against the merchant's signature.
2. **This device:** each part on screen is taken from here if it was ever seen before, on any site.
3. **Your network:** if not, the browser asks your Lit node (`lit.pxd`, base1, a Pi, the shop's box), which asks its peers once.
4. **The origin:** if no neighbor has it, the part comes from the gateway or GitHub, and the browser gives it to the Lit node for the next device nearby.
5. **Checks:** every part is checked against its SHA-256 at each step. A neighbor can carry data; it cannot fake it.
6. **Sealed parts:** they never enter Lit or the shared device cache.

## Measured (headless Chromium, 4.5 MB store, 1.5 MB model)
| | from the origin | from the network |
|---|---:|---:|
| Browse the whole catalog, verified | 16.8 KB | |
| Device 1 opens a model (first on the network) | 1.52 MB | |
| Device 2 opens the same model, via a different Lit node | **16.8 KB** | 1.51 MB |
| A second shop carrying the same model | 16 KB | (device cache) |

## Run
```
python tools/lit/lit.py                                 # every machine in the fleet; nodes find each other by UDP beacon
python tools/lit/lit.py --peer http://base1:7470        # or name peers
python tools/lit/lit.py --mount library-01.pmoc         # serve a .pmoc section (COG books, Alexandria, store parts)
python tools/pxd2root/pxd2root.py --lit-ip 192.168.1.20 # so lit.pxd finds the node
curl -X POST -d '{"bundle":"https://.../store.pxdz"}' http://lit.pxd:7470/lit/warm   # pre-load a store
curl http://lit.pxd:7470/lit/pack -o parts.pmoc         # everything this node holds, as one .pmoc
```
`.pmoc` tool: `python tools/lit/pmoc.py build|ls|get|twin` (v1 layout from PxD2/PMOC; kind 6 = part, id = first 16 bytes of SHA-256).

Rules kept from PMOC:
- Lex and weight slices are written only by the CORE, and arrive as mounted `.pmoc` files.
- Parts are self-verifying, so any node may relay them.

On the open web, a page uses Lit only on devices that opt in (`localStorage["pxd-lit"]`); the PXD Browser uses it by default.
