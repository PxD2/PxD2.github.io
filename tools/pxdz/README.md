# PXDZ — the .pxd data format

One file per site or dataset: COG-coded text, compressed data and 3D models, a full SQLite database, a SHA-256 on every part, optional AES-256-GCM sealing for private clients.

- Pack: `python tools/pxdz/pxdz.py pack <folder> -o site.pxdz --book hub.json [--public-book <cog>/books] [--key PASSPHRASE]`
- Catalog to SQL: `python tools/pxdz/pxdz.py sql catalog.json -o data.db`
- Inspect / unpack (verified): `inspect site.pxdz`, `unpack site.pxdz -o out [--key ...]`
- Browser runtime: `/pxd/pxd.js` (`PXDZ.open(url, {key})` → `bytes/text/json/sql(path)`); live demo at pxd2.github.io/pxd
- Spec: layout `"PXDZ" | u8 version | u32 LE manifest length | manifest JSON | part blobs`; codecs applied in order `cog-json → deflate (raw) → aes-gcm`, reversed on read.
- Private text: sentences that are not already in the public COG library go into the bundle's hub book, which travels sealed with the bundle. Client text never enters the public library.

## Merchant authentication (`pxdsign.py`)
ECDSA P-256 chain: PXD authority (offline) → merchant certificate (name, key, allowed payment hosts, expiry) → bundle signature (`<bundle>.pxdz.sig`). `pxdsign.py verify` and `PXDZ.verify()` in the browser check the whole chain and refuse any pay link outside the certificate. `pxd/authority-demo.json` is a test authority for the demo store only.
