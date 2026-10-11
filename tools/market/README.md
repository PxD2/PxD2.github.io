# PXD Market: every store, by type, then region

The PXD home page (`tools/pxd_browser/home.html`, the PXD Browser's start page and the gateway's `/`) is one search box over every approved store and every `.pxd` site, with one cart across all stores.

```
market/<type>/<region>/<store>.pxdz (+ .sig)     eats/az-apache/demo-pizza.pxdz
python tools/market/pxd_market.py --authority pxd/authority.json
```
The indexer writes `market/index.json` → `market/<type>/index.json` → `market/<type>/<region>/index.json`.
- **Approved stores only:** a store is listed only if its bundle verifies against a merchant certificate from the PXD authority. Forged, edited and foreign-authority stores are refused, and sealed stores are never listed.
- **Searched on the buyer's device:** the home page downloads the small indexes and searches them locally. There is no search server.
- **Sub-hubs:** a type can live in its own GitHub org (PXD Eats, PXD Retail). Its `index` URL in `market/index.json` points there.
- **Mirrors:** the market travels with `pxd_mirror.py`.

## PXD Pay (checkout finalized through PXD)
- **The cart:** the buyer checks out on PXD. The gateway's `/api/checkout` reads each item's price from the store's signed bundle, never from the cart.
- **The payment:** it creates one Stripe Checkout per merchant as a direct charge on the merchant's own connected account, which is named in its certificate (`pxdsign.py issue --stripe-account acct_...`). The money lands with the shop; PXD never holds it.
- **Platform fee:** optional (`--fee-pct`, default 0).
- **Merchants without Stripe:** their certified pay links are offered instead.
- **Orders:** logged to `orders.jsonl` on the gateway.

Turn on: create a Stripe Connect platform account, onboard each shop as a connected account, put its `acct_` id in its certificate, then run the gateway with `STRIPE_SECRET_KEY=sk_live_...`.

Tested:
- **Checkout:** a mock Stripe received the merchant's account, cart-independent prices, quantities and an idempotency key.
- **Refused:** price-on-request items, path traversal, quantities over 99, unknown items, a forged store.
- **Browser:** home, search, cart, the checkout handoff, the paid return, the phone layout, and walk-in verification, in Chromium.
