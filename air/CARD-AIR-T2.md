# CARD-AIR-T2 — Digital Air Tunnel Tier 2 (commercial path)

**From:** Steve (product adversary / executive rail)  
**To:** CFD Lead (cast of one for this card; ≤3 floor rule)  
**Date:** 2026-09-21  
**Front door:** https://pxd2.github.io/air/  
**Related:** YOLO1 Gen-1 CARD-002 (`PxD2/yolo1-gen1`) — aero numbers are NOT invented by Systems; CFD owns tunnel truth.

## Why

`/air` today is Tier 1: browser estimate (`Cl ~ 2*pi*alpha`, `Cd = Cd0 + k*Cl^2`). Labeled honest. **Not commercial.** Chad ordered Tier 2.

## Outcome

Two validated cases land beside the estimate lane in the same UI:

1. **Plane — NACA 0012 (or equivalent public airfoil)** at stated Re, incompressible, clean wing section.  
2. **Drone — multirotor / small fixed-wing reference** Chad or CAD names (or a published quadrotor drag polar if no private geo yet).

Plus a **case contract** so `/air` Export JSON and YOLO1 geometry can feed your mesh/solver without a second product.

## Fidelity tiers (product law)

| Tier | Name | Allowed claim |
|------|------|----------------|
| 1 | Estimate | Digital tunnel estimate — not a RANS proof (live now) |
| 2 | Validated | Matches published or private bench within DONE-BAR tolerance |
| 3 | Solver | Mesh + RANS/LES (or licensed partner) on real geometry — later card |

Never mix labels in the UI.

## DONE-BAR (CFD Lead)

| # | Item | Proof |
|---|------|--------|
| 1 | Case contract schema | `air/case-contract.schema.json` (or private CFD repo twin) — fields: vehicle, medium, geometry_ref, AoA, speed, Re, rho, Cl, Cd, L/D, Lift, Drag, fidelity, source, uncertainty |
| 2 | Plane validation pack | Table or JSON: ≥5 AoA points Cl/Cd vs published NACA 0012 (cite source). Max |ΔCl| and |ΔCd| vs reference stated. |
| 3 | Drone validation pack | Same shape for chosen drone reference; geometry_ref path if YOLO1/CAD STL |
| 4 | Wire to `/air` | Files under `air/cases/` that the page loads for Tier 2 compare (estimate vs validated columns) |
| 5 | YOLO1 hook | One-pager: how Gen-1 envelope STL enters mesh/case (no public Pages; private path OK) |
| 6 | Reviewer-ready | Reviewer can fail any “commercial CFD” claim that cites Tier 1 only |

## Out of scope this card

- Full OpenFOAM product UI  
- Sea/Sub validation (Tier 2b later)  
- Standing cast bloat — CFD Lead owns; CAD only if geometry block  
- Cloud Agents (plan limit)  

## Cast

1. **CFD Lead** — validation packs, case contract, solver path recommendation  
Steve stays executive: product bar + `/air` fidelity UI.  

## Steve parallel

- `/air` UI: fidelity toggle Estimate | Validated; side-by-side when case JSON present  
- Keep PXD2 mark; no hall junk  

## Pass / fail

- **PASS:** Two packs + schema + `/air` shows validated column for plane and drone without calling it RANS.  
- **FAIL:** Only prettier particles; or Tier 1 sold as commercial.
