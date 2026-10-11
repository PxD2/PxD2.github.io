# PXD Shop Builder and Studio: from shop photos to a walk-in store

**1. The owner** opens Shop Builder: `/build` on the PXD Gateway, or "List your shop" on PXD home.
- **Shop details:** name, type, region, contact, and optionally their own USDC wallet.
- **360° photos** of each spot (phone panorama or Street View photo sphere). Partial panoramas are accepted and flagged.
- **Items of highest interest:** photos, price, size, and an optional 3D scan (.glb).
- **Placing:** pick an item or a doorway and tap where it is in the photo. They see exactly what buyers will see.
- **Send:** the files upload to the gateway's intake folder.
- **Their key:** the browser makes a shop key and keeps it. Only the public half is sent.

**2. The studio** (base1): `python tools/studio/build_store.py watch`
- **Photos:** panoramas are turned upright, padded to a full sphere and capped at 4096 px; item photos at 1400 px; 3D scans are checked.
- **Output:** `world.json` (spots, pins, doorways) plus `catalog.json`, packed into one PXDZ store bundle. The owner previews it from their job link.
- **Next stage (not built):** a GPU Gaussian-splat walk-through from the same photos.

**3. PXD approves** the merchant: `build_store.py approve <job> --authority keys/` (or `reject <job> --reason ...`).
- This issues the merchant certificate for the owner's key, with their wallet pinned in it.
- The authority key never leaves base1.

**4. The owner signs** in their browser (same browser, same key). The gateway checks the signature and certificate, places the store in `market/<type>/<region>/` (reusing a region folder with the same name) and rebuilds the market index. The store appears in PXD search right away.

**5. Buyers walk in** from PXD home → "Walk in". The Stores view verifies the merchant, renders the 360° shop with item pins and doorways, and taps on a pin jump to that item. Everything is fetched part by part through pxd.js (and Lit), so the buyer's browser loads the store data without any website to host.

Publish to GitHub: commit and push `market/` (or run `pxd_mirror.py`).

**Tested in Chromium, end to end:**
- builder → upload → studio build → approval → owner signs → search → walk-in
- pins in place, a doorway between spots, a pin tap highlighting its item
- another browser refused when it tried to sign the owner's shop
