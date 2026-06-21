# Lodestar PAC

**Predictive Asteroid Characterization.** An ML-augmented prospecting and feasibility-screening engine for near-Earth asteroids. It ranks asteroids by estimated mineral value, cross-references that against accessibility (the delta-v to reach them), and (in later phases) computes launch windows and predicts composition for the majority of objects that have no measured spectrum, always with uncertainty attached.

This is a **screening tool**, not flight software. Every value and composition figure is an estimate with explicit provenance, never a measurement. See `LODESTAR_PROJECT_SCOPE.md` for the full architecture, roadmap, and scope fence.

## Status

**Phase 0 (foundation) - built.** Repo scaffold, uv environment, lint/test, and an ingestion pipeline pulling JPL SBDB + Asterank into a normalized parquet store.

**Phase 1 data layer - built.** We compute our own value and delta-v for the full near-Earth catalogue, because Asterank's value field returns garbage for NEOs and its API caps at 1000 stale objects. See `DECISIONS.md`.

- **Value:** size to mass to spectral-type composition to commodity value, with an explicit low/high uncertainty band. Objects with no measured spectrum (the ~99% majority) fall back to an assumed type with a wider band, flagged `spec_is_assumed`. This is exactly the gap Phase 4's ML narrows.
- **Delta-v:** Asterank's Benner value where present (reliable), else a transparent patched-conic Hohmann-rendezvous proxy from orbital elements, flagged `computed:hohmann-proxy`. The proxy validates within ~2-25% of published Benner values and surfaces the real low-delta-v targets (Apophis, Itokawa, 2008 EV5). It is screening-grade only; Phase 2 replaces it with ephemeris-based trajectory math.

The React ranked/filterable table + FastAPI endpoint are the remaining Phase 1 pieces.

## Architecture (5 layers)

Data ingestion -> ML characterization -> astrodynamics -> ranking -> React interface. Phase 0 builds the ingestion layer only; the rest light up phase by phase.

## Quickstart

Requires [`uv`](https://docs.astral.sh/uv/) and Python 3.10 or 3.11. Run from the repo root.

```
uv sync --extra api
```

That creates the environment from `pyproject.toml`. (Add `--extra astro` in Phase 2 for hapsira, `--extra ml` in Phase 4.) To include the dev tools - pytest, ruff, jupyter:

```
uv sync --extra api --group dev
```

### Run the Phase 0 ingestion pipeline

These pull live data, so run them on a machine with open internet. Order matters: SBDB and Asterank first, then normalize joins them.

```
uv run python -m backend.ingest.sbdb
```

```
uv run python -m backend.ingest.asterank --limit 50000
```

```
uv run python -m backend.ingest.normalize
```

```
uv run python -m backend.ranking.enrich
```

`normalize` joins SBDB + Asterank into `data/processed/asteroids.parquet`. `enrich` adds the computed value + delta-v (with uncertainty + provenance) and writes `data/processed/asteroids_enriched.parquet`, the store the ranking engine and API serve. Each step prints a coverage report.

If the Asterank API is slow or down, download a JSON or CSV export and load it offline:

```
uv run python -m backend.ingest.asterank --input path/to/asterank_export.json
```

For a quick smoke test without pulling the whole catalog:

```
uv run python -m backend.ingest.sbdb --limit 500
```

### Run the Phase 1 app (prospecting console)

Two processes. Terminal 1, the FastAPI backend (needs the `api` extra):

```
uv run --extra api uvicorn backend.api.main:app --reload --port 8000
```

Terminal 2, the React frontend (first time only: `cd frontend && npm install`):

```
cd frontend && npm run dev
```

Then open http://localhost:5173. The Vite dev server proxies `/api` to the backend, so no CORS setup is needed. The ranked table, value-vs-accessibility slider, filters, the 3D orbit viewer, and the Compute-trajectory button all run against the live store.

### Explore

```
uv run jupyter lab notebooks/01_explore_asterank.ipynb
```

### Test and lint

```
uv run pytest
```

```
uv run ruff check backend/
```

## Layout

```
backend/ingest/   sbdb.py  asterank.py  normalize.py  schema.py   # Layer 1
backend/astro/    deltav.py                                       # Layer 3 (screening proxy)
backend/ranking/  value.py  enrich.py                            # Layer 4
backend/api/                                                      # FastAPI (Phase 1, next)
backend/tests/                                                    # network-free unit tests
frontend/                                                         # React + Vite (Phase 1, next)
data/{raw,processed,models}/                                      # gitignored store
notebooks/                                                        # exploration
```

## The store schema

Columns are defined in `backend/ingest/schema.py`. The honesty contract lives there as real columns: `value_source`, `value_is_estimate`, `value_low`/`value_high`, `size_source`, `spec_is_assumed`, `dv_source`, `dv_rel_unc`, and `spec_source` carry provenance and uncertainty on every row, so an inference is never mistaken for a measurement.
