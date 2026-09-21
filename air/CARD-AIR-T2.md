# CARD-AIR-T2 — Commercial-path Tier 2 (Air)

**Owner:** CFD Lead (cast of one)
**Site:** https://pxd2.github.io/air/
**Ordered:** Chad via Steve (executive) — Tier 1 estimate is not commercial.

## DONE-BAR

1. Case contract schema → `air/cases/case-contract.schema.json`
2. Plane validation pack ≥5 AoA Cl/Cd vs Ladson NASA TM-4074 → `air/cases/plane/`
3. Drone validation pack (same shape; YOLO1 STL deferred under CARD-002C HOLD) → `air/cases/drone/`
4. JSON under `air/cases/` + `manifest.json` for Estimate vs Validated
5. YOLO1 Gen-1 envelope → mesh/case hook one-pager → private `PxD2/yolo1-cfd/docs/YOLO1-GEN1-AIR-HOOK.md`
6. Reviewer may fail any commercial CFD claim that only cites Tier 1

## Proof

See `air/cases/manifest.json` for max |ΔCl| / |ΔCd| vs Tier 1 estimate.

## Out of scope

Full OpenFOAM UI · Sea/Sub T2b · Cloud Agents
