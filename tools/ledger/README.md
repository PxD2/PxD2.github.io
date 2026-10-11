# PXD Model Ledger: 3D models as license tokens

The artist registers a model once and sets the tiers. Every sale after that is a signed event in the model's own chain:

| Tier example | Rule the ledger enforces |
|---|---|
| print: $12, personal 3D printing | unlimited unless `edition` is set |
| game: $150, edition of 50 | the 51st is refused |
| film-lease: $400, 365 days, not transferable | expires; renewals extend it; resale refused |
| buyout: $5,000, exclusive | only one active holder |
| resale of any transferable license | signed by the holder and countersigned by the artist or PXD Gateway, which confirms the royalty (set at registration) was paid |
| buyout of the model itself | the artist and the new owner both sign; existing licenses stay valid; old delegations end |

**Verified artists:** a creator certificate from the PXD authority marks the artist as verified, and fake certificates are refused.

**Attacks the ledger refuses:**
- edited history
- deleted events
- someone who isn't the holder trying to transfer a license
- a missing royalty countersignature

**Buying through PXD:**
1. The artist delegates print/game issuing to the gateway (`pxdledger.py delegate`).
2. The buyer pays the artist's own wallet (USDC) at checkout.
3. The home page claims the license to a key kept in the buyer's browser (`/api/models/claim`).
4. "Unlock file" proves the holder signed a fresh challenge, and the gateway returns the file key the artist deposited (`--model-keys`, kept off GitHub).

Card purchases claim the same way once the Stripe webhook is added.

**Tested:**
- the full lifecycle and every refusal above (CLI)
- pay → claim → unlock, a double claim, a stranger's claim, a stranger's unlock, unlock after revocation (API)
- the same flow in the home page in Chromium
