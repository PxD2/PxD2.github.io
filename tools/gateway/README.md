# PXD Gateway — the second stream

Runs on base1 beside GitHub. It streams store data, authenticates merchants and uses the RTX GPU.

## One-time: create the real PXD authority (keep it offline)
```
python tools\pxdz\pxdsign.py authority-init --dir "D:\PXD Authority" --name "PXD Authority"
```
Copy only `authority.json` (the public half) into `pxd/authority.json` and the `authorities` list in `names.json`.
`authority.key.json` never goes on GitHub, a cloud drive or any machine that browses the web. Back it up on two USB drives.

## Certify a merchant
1. The merchant (or you, for them) runs `pxdsign.py merchant-key --out smiths.key.json` and keeps the key.
2. You issue the certificate with the payment hosts their pay links may use:
   `pxdsign.py issue --authority "D:\PXD Authority" --merchant-pub smiths.pub.json --id smiths-antiques --name "Smith's Antiques" --pay-hosts buy.stripe.com,www.paypal.com -o certs\smiths-antiques.cert.json`
3. They sign each bundle: `pxdsign.py sign smiths.pxdz --key smiths.key.json --cert certs\smiths-antiques.cert.json`

## Run the gateway
```
python tools\gateway\pxd_gateway.py --authority pxd\authority.json --store "C:\PXD Gateway\bundles"
```
- `GET /api/status` — GPU (from nvidia-smi), Ollama models, bundles, authority
- `GET /api/stores` — every bundle with its verification
- `GET /b/<name>.pxdz` — the data stream, with HTTP Range
- `POST /api/publish` — accepted only when the authority → certificate → bundle chain checks out, every pay link uses a host in the certificate, and the name is new or already owned by the same merchant
- `POST /api/cog/group` — sentences grouped into COG meanings by `nomic-embed-text` on the GPU through Ollama (CUDA); falls back to exact grouping when Ollama is off

The PXD Browser's **Stores** button (or typing `stores.pxd`) renders every store listed in the registry from its data, shows the checks, and only shows pay buttons for verified merchants.
