# Lodestar build decisions

Dated, one entry per non-obvious call. The scope doc (`LODESTAR_PROJECT_SCOPE.md`) is the north star; this is where reality updated the plan.

## 2026-06-20 — Phase 0 + Phase 1 data layer

**Env: uv, matplotlib left unpinned.** hapsira 0.18 (Phase 2 astrodynamics) hard-pins `matplotlib<3.8`; a high floor in the dev group made the whole environment unresolvable. matplotlib is unpinned so the full env (incl. the astro extra) resolves.

**Join key: canonical designation, not raw strings.** SBDB writes numbered bodies as `433 Eros (A898 PA)` and Asterank as `433 Eros`; provisional bodies look like `2010 AB`. `schema.desig_key` normalizes both sides (number for numbered, packed provisional otherwise), with regression tests for the traps: `4179 Toutatis (1989 AC)` and `101955 Bennu (1999 RQ36)` must key on their number, `2001 Einstein` is numbered not provisional. SBDB and Asterank `spkid` differ by JPL's zero-padding era (`20000433` vs `2000001`), so spkid is not used directly.

**Asterank is a baseline, not the source of truth.** Three findings from the real pull:
1. The API hard-caps at 1000 rows and returns them ordered by asteroid number, so unfiltered it is the first ~1000 (giant main-belt bodies), almost no NEOs.
2. Its `neo` flag is the string `"Y"`/`"N"`, not `1` (so `{"neo":1}` returns nothing; use `{"neo":"Y"}`).
3. Its `price` (value) field returns garbage for NEOs (433 Eros came back at 6.7e-42, should be ~1e18). Its `dv` field is correct (it is the Benner table: Eros 6.11, Albert 7.72, Alinda 7.07).

Conclusion: **compute value and delta-v ourselves** over the full SBDB catalogue. Keep Asterank only as a sanity baseline (`asterank_value_usd`) and as the preferred dv source where present (`asterank_dv_kms`, Benner).

**Value model (`ranking/value.py`).** size -> mass (bulk density by C/S/M complex) -> commodity value-per-kg, with an explicit low/high band. Order-of-magnitude class factors, not an appraisal. Size provenance tiers: measured diameter, else H + measured albedo, else H + an albedo assumed from the complex (this last tier is what gives ~100% catalogue coverage, at a wider band). Unmeasured taxonomy (~99%) defaults to S-complex, flagged `spec_is_assumed`, wider band. All flagged, all uncertain.

**Delta-v proxy (`astro/deltav.py`).** Patched-conic two-impulse Hohmann rendezvous from (a, e, i): LEO departure + plane change at the slower apsis + arrival velocity match. NO Lambert/porkchop/ephemerides (that is Phase 2). Validated against the three real Benner values: Albert/Alinda within 2-3%, Eros 24% high (conservative on easy low-e Amors). Flagged `computed:hohmann-proxy` with a 0.35 relative uncertainty. Sanity check passed: the lowest-dv high-value objects are the real mission targets (Apophis, Itokawa, 2008 EV5).

**Scope fence held.** The dv proxy is algebraic (same category as "a precomputed dv"), not the trajectory math the scope reserves for Phase 2. No ML yet (Phase 4). No flight-grade claims anywhere; every figure ships with uncertainty.

**Open follow-ups.** Re-pull Asterank with `{"neo":"Y"}` to widen Benner-dv coverage from 3 to ~1000 (quality, not blocking). Phase 2 replaces the dv proxy with ephemeris-based transfers and can validate against the full Benner table.

## 2026-06-21 — Phase 1 interface (React + FastAPI + 3D)

**Built the real Phase 1 console** (replaces the static HTML preview): FastAPI backend (`backend/api/`) serving the enriched store with live ranking, filtering, detail, and an on-demand `/trajectory` task; React + Vite frontend (`frontend/`) with the ranked table, value-vs-accessibility weight slider, spectral/dv/search filters, a per-object detail panel, and a **Three.js heliocentric orbit viewer** drawn from the real Keplerian elements.

**Scope fence on "flight-path simulation."** Connor wants flight-path simulation; that is Phase 2 (Lambert + porkchop + Horizons ephemerides) and Phase 3 (optimized 3D transfers, rendezvous), NOT Phase 1. What shipped now: real orbits from real elements (honest), plus a **schematic** transfer arc clearly labeled illustrative. The `/api/trajectory/{id}` endpoint returns the screening-grade breakdown today and is shaped so the Phase 2 Lambert/porkchop solve drops in behind the same response, no UI change. Horizons can't be reached from the sandbox, so Phase 2 ephemeris work runs on Connor's Mac.

**Run model.** Backend `uv run --extra api uvicorn backend.api.main:app --port 8000`; frontend `cd frontend && npm run dev` (proxies `/api` to :8000). Verified end to end in-sandbox: frontend builds (39 modules), dev proxy routes to the API, ranking returns correct value-sorted results.
