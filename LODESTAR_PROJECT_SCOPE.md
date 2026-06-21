# LODESTAR PAC — Project Scope & Roadmap

**Lodestar PAC — Predictive Asteroid Characterization.** An ML-augmented prospecting and feasibility-screening engine for near-Earth asteroids.

> **The name:** *Lodestar* is a guiding star (a north star); a *lode* is a vein of ore — the name fuses "guiding-light reference" with the mining domain. **PAC = Predictive Asteroid Characterization**, the system's core job: predicting what each asteroid is made of, how reachable it is, and when to go. Read it like "GPT" — a crisp tag for the engine.

| | |
|---|---|
| **Document type** | North-star scope, architecture, and phased roadmap |
| **Status** | Living document — update as the build evolves |
| **Version** | 1.1 |
| **Audience** | You (solo builder), future collaborators, anyone evaluating the project |
| **How to use it** | Reference while building. Phase 1 is the MVP target. Everything past it is the long arc. |

---

## 0. North Star — what this is and why it matters *now*

**Lodestar answers one question at scale: *of all the near-Earth asteroids we know about, which ones are worth going to, how hard are they to reach, and when is the best time to launch?*** It ranks asteroids by estimated mineral value, cross-references that against accessibility (the energy budget to get there), and computes the optimal launch windows and transfer trajectories — then uses machine learning to fill in the enormous gaps in what we actually know about each object.

This is timely, not academic, because two things are converging right now:

1. **Cheap, frequent commercial missions are real.** The current leader in private asteroid mining builds spacecraft for single-digit millions in under a year and intends to fly often, targeting platinum-group metals that are ~5,000× more concentrated on asteroids than in Earth's crust. When you fly cheap and fast, *picking the right target and window* stops being a research curiosity and becomes a competitive bottleneck.

2. **The data firehose just opened.** A new survey observatory is discovering thousands of new asteroids every few nights and is expected to triple the number of known asteroids over its survey, producing millions of detections nightly. But these come as sparse *colors* and lightcurves — not full spectra — so the vast majority of objects are uncharacterized. Hand-curated tables cannot keep pace. Automated, ML-driven screening at scale is exactly the gap that opens.

**Lodestar is the tool that sits in that gap.** Not the thing that flies the spacecraft — the thing that tells you *where to point it* and *whether it's worth the fuel*.

### The one-sentence pitch
> A Rubin-era asteroid prospecting engine that ranks near-Earth targets by ML-predicted mineral content, computes launch windows and trajectory feasibility, and surfaces the handful worth a closer look.

---

## 1. What it IS / What it ISN'T

Defining the boundary is the single most important thing in this document. Scope creep is the main way this project dies; this table is the fence.

| Lodestar **IS** | Lodestar is **NOT** |
|---|---|
| A target-**prospecting** and feasibility-**screening** tool for near-Earth asteroids | Flight-grade mission-planning or spacecraft navigation/GNC software |
| A ranked, filterable, ML-augmented catalog cross-referencing **value × accessibility × launch timing** | A substitute for professional astrodynamics suites (GMAT, Orekit, JPL tools) for certified trajectory design |
| A producer of **estimates with explicit uncertainty** | A source of ground-truth composition — it never claims to *measure* what an asteroid is made of |
| A **first-pass screening layer** built to scale to the modern flood of newly discovered objects | A real-time observatory alert pipeline (until/unless a far-future phase) |
| An **educational + decision-support** visualization (porkchop plots, 3D transfers, ranked tables) | A financial or investment instrument — value figures are order-of-magnitude, not appraisals |
| A **portfolio-grade** demonstration of data engineering + applied astrodynamics + ML | A claim to "locate" metals on a specific asteroid's *surface* (that requires a close-up mission) |
| Built in **honest phases**, each independently shippable | A monolith that only has value when "finished" |

**The litmus test for any new feature:** *Does it help someone decide which asteroid to study or visit next?* If yes, it's in scope. If it's drifting toward "actually fly the mission," it's out.

---

## 2. Core concept & architecture

Lodestar is a pipeline of five layers. Each is independently testable, and the phased roadmap (§8) lights them up one at a time.

```
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 1 — DATA INGESTION                                             │
│  Orbital elements (JPL SBDB) · Composition/value baseline (Asterank)  │
│  Spectral labels (SMASS / Bus–DeMeo / MITHNEOS) · Colors (Rubin/SDSS) │
│  Meteorite spectra + lab composition (RELAB)                          │
└───────────────────────────────┬─────────────────────────────────────┘
                                 │  normalize → local store (parquet/SQLite)
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 2 — ML CHARACTERIZATION  (the differentiator)                  │
│  Predict taxonomy + mineral composition + UNCERTAINTY for the         │
│  large majority of objects that have no measured spectrum             │
└───────────────────────────────┬─────────────────────────────────────┘
                                 │  enriched per-asteroid record
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 3 — ASTRODYNAMICS                                              │
│  Lambert solver → porkchop grid → best launch window + Δv + flight    │
│  time per target  (intercept first, rendezvous later)                 │
└───────────────────────────────┬─────────────────────────────────────┘
                                 │  Δv, window, transfer geometry
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 4 — RANKING ENGINE                                             │
│  Composite score = f(value, accessibility, window quality, confidence)│
│  User-adjustable weights · spectral-type filters                      │
└───────────────────────────────┬─────────────────────────────────────┘
                                 │  ranked, scored, filterable list
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 5 — INTERFACE                                                  │
│  Ranked table + weight sliders + filters · Porkchop plot ·            │
│  3D trajectory/orbit visualization                                    │
└─────────────────────────────────────────────────────────────────────┘
```

**Design principle: precompute where you can, compute on demand where you must.** Ranking the whole catalog should run offline into a static store. Expensive per-target trajectory optimization runs only when a user drills into a specific asteroid.

---

## 3. Tech stack

Specific, current, and chosen for "solo builder who wants to ship." Swap as you like — but note the deliberate calls below.

### Astrodynamics (Layer 3)
- **`hapsira`** — the actively maintained fork of the (archived Oct 2023) `poliastro`. Pure-Python orbit objects, Lambert's problem, element conversion, quick plotting. **Use this, not poliastro** — poliastro is archived and unmaintained. Validated to match poliastro's results. Python 3.8–3.11.
- **`pykep`** (ESA) — purpose-built trajectory *optimization*: Lambert, multi-leg, gravity assists, low-thrust. Bring this in at Phase 3 when you go beyond simple transfers. Heavier than hapsira; worth it for the hard stuff.
- **`pygmo`** (ESA) — global optimization, pairs with pykep for trajectory search. Phase 3+ / stretch.
- **`astropy` + `astroquery`** — units, time handling, and the clean interface to JPL Horizons ephemerides. The connective tissue under everything.

### Data & ML (Layers 1–2)
- **Python data stack** — `pandas` / `polars`, `numpy`, `pyarrow` (parquet), `requests`/`httpx`.
- **Storage** — start with parquet files or SQLite; graduate to Postgres only if you need it. Don't over-engineer the DB early.
- **ML** — `scikit-learn` for baselines (logistic regression, random forest, gradient boosting). `PyTorch` for the 1D-CNN-on-spectra and probabilistic models. `scikit-learn` ensembles or MC-dropout for uncertainty.

### Backend & frontend (Layer 5)
- **`FastAPI`** — thin API serving precomputed rankings + on-demand trajectory computation. Async, fast, typed.
- **React** (Vite) — the UI. Ranked table, weight sliders, filters.
- **Visualization** — `Plotly` (2D porkchop contours + quick 3D, lowest effort) or **Three.js** (richer, Asterank-style 3D orbits). Start with Plotly, upgrade trajectory viz to Three.js if you want polish.

### Tooling
- `uv` or `poetry` for Python env/deps · `ruff` for lint/format · `pytest` for tests · GitHub for repo + CI.

---

## 4. Data sources

| Source | What it gives you | Role | Phase |
|---|---|---|---|
| **JPL Small-Body Database (SBDB)** | Keplerian orbital elements, physical params, for ~all known objects (query API) | Backbone — every asteroid's orbit | 0 |
| **Asterank** (open data + GitHub `typpo/asterank`) | ~600k asteroids with spectral-type-inferred composition, estimated value, **precomputed Δv** | MVP shortcut + sanity baseline | 0–1 |
| **JPL Horizons** (via `astroquery.jplhorizons`) | Precise ephemerides (body position/velocity at any instant) | Feeds the Lambert solver | 2 |
| **SMASS II / Bus–DeMeo taxonomy** | Labeled asteroid spectral classes (the ML ground truth) | ML training labels | 4 |
| **MITHNEOS** | Near-infrared spectra for 1000+ near-Earth objects | ML training data | 4 |
| **RELAB spectral library** | Meteorite reflectance spectra with **lab-measured composition** | ML ground truth (taxonomy → mineralogy mapping) | 4 |
| **Rubin / LSST data products + Asteroid Discoveries Dashboard** | Colors (g–r, r–i…), lightcurves, orbits for the modern flood of new objects | The scaling use case for ML characterization | 4–5 |
| **SDSS Moving Object Catalog** | Multi-band colors for hundreds of thousands of asteroids | Additional ML feature source | 4 |

**Caveat to bake in from day one:** the overwhelming majority of asteroids have *no* spectral classification. "Ranked by mineral content" is therefore mostly *inference*, not measurement — which is the entire reason Layer 2 (ML) exists, and why every estimate must ship with an uncertainty flag.

---

## 5. The ranking engine (Layer 4)

The heart of "categorized and ranked by mineral content cross-referenced with ease of access."

### Component scores (each normalized 0–1)
- **Value (V)** — estimated worth: predicted composition × mass × current metal market prices. Log-scale it; values span many orders of magnitude.
- **Accessibility (A)** — inverse of total mission Δv. Lower Δv = easier = higher score. Sourced from Asterank in Phase 1, from your own porkchop minimum in Phase 2+.
- **Window quality (W)** — how good the *best* launch opportunity is within the user's date horizon: low Δv + reasonable flight time + how often it recurs (synodic period).
- **Confidence (C)** — from the ML layer's uncertainty. How sure are we this object is what we think it is?

### Composite
```
score = weighted_combine(V_norm, A_norm, W_norm)  ×  confidence_discount(C)
```
Use a **weighted geometric mean** (punishes a near-zero in any dimension — a worthless-but-easy rock shouldn't rank high) or weighted sum, with **user-set sliders** for the weights. The confidence discount keeps low-information objects from topping the list on the strength of a wild guess.

### Δv → feasibility, via the rocket equation
Translate the abstract Δv score into something a human believes:
```
Δv = Isp · g₀ · ln(m₀ / m_f)   →   propellant mass fraction   →   rough cost/feasibility
```
This is what turns "ease of access" from a number into a fuel-and-dollars story, and it's a clean, impressive Phase 3 addition.

---

## 6. The ML layer (Layer 2) — the differentiator

This is what elevates Lodestar from "nice data-viz over Asterank" to genuinely novel, and it leans directly on an AI/ML background. **If you go deep in exactly one place, make it here.**

### The problem
Predict an asteroid's **taxonomic class** (and, where possible, **mineral modal composition**) plus **calibrated uncertainty**, for the large majority of objects that have only sparse data.

### Features, by data-availability tier
- **Tier A — full VIS-NIR reflectance spectra** (best signal, smallest population). Diagnostic absorption bands around 1.0 and 2.0 µm reveal pyroxene/olivine content.
- **Tier B — multi-band colors** (e.g., Rubin/SDSS g–r, r–i). Weaker features, but *vastly* more objects — this is the scalable path and the whole point in the Rubin era.
- **Tier C — albedo + orbital parameters** as weak priors.

### Ground truth & the meteorite trick
Labeled asteroid composition is rare. The standard, validated workaround: train on **meteorite spectra with lab-measured composition (RELAB)** as ground truth, using meteorites as analogs for asteroid mineralogy, plus the **labeled asteroids (SMASS / Bus–DeMeo / MITHNEOS)** for taxonomy. This is exactly how the published research does it.

### Model progression
1. **Baseline** — logistic regression / random forest / gradient boosting on colors → taxonomy class. Fast, interpretable, a real result.
2. **Spectral model** — 1D CNN on full reflectance spectra → composition regression (for Tier-A objects).
3. **Probabilistic** — ensembles, MC-dropout, or Gaussian processes → calibrated **uncertainty**, so every prediction has error bars.

### Evaluation — and honesty
- Stratify by class; report confusion matrices; **respect class imbalance** (some types are rare).
- Validate against held-out spectroscopically-confirmed objects — the only real ground truth.
- **There is no ground truth for the unlabeled majority.** Say so. Don't pretend a prediction is a fact.

### Caveats to build in (these make it credible, not weaker)
- **Space weathering** alters spectra (e.g., apparent olivine depletion) — a known bias the literature flags.
- **Grain-size effects** shift spectral features.
- **Training data is small and biased**; meteorite analogs are imperfect proxies for asteroid surfaces.
- **Colors are weaker than spectra** — Tier-B predictions are inherently probabilistic.

→ The mitigation for all of the above is the same: **uncertainty is a first-class output**, never hidden.

---

## 7. Repository scaffold

A clean monorepo. Build the tree first; fill it phase by phase.

```
lodestar/
├── README.md                  # quickstart + what/why
├── LODESTAR_PROJECT_SCOPE.md  # this document (the north star)
├── pyproject.toml             # uv/poetry deps
├── data/
│   ├── raw/                   # pulled SBDB, Asterank, spectral libs (gitignored)
│   ├── processed/             # normalized parquet
│   └── models/                # trained ML artifacts
├── backend/
│   ├── ingest/                # LAYER 1
│   │   ├── sbdb.py            # orbital elements
│   │   ├── asterank.py       # composition/value/Δv baseline
│   │   ├── spectra.py        # SMASS / MITHNEOS / RELAB
│   │   └── rubin.py          # colors + lightcurves (Phase 4+)
│   ├── ml/                    # LAYER 2
│   │   ├── features.py       # build feature tiers (spectra/colors/orbital)
│   │   ├── taxonomy_clf.py   # taxonomy classifier
│   │   ├── composition_reg.py# composition regression
│   │   └── uncertainty.py    # calibrated error bars
│   ├── astro/                 # LAYER 3
│   │   ├── ephemeris.py      # Horizons wrappers
│   │   ├── lambert.py        # transfer solver
│   │   ├── porkchop.py       # date-grid sweep → windows
│   │   └── deltav.py         # Δv + rocket-equation cost model
│   ├── ranking/               # LAYER 4
│   │   └── score.py          # composite scoring + weights
│   ├── api/                   # FastAPI (serves precomputed + on-demand)
│   │   ├── main.py
│   │   └── routes/
│   └── tests/
├── frontend/                  # LAYER 5 — React (Vite)
│   ├── src/
│   │   ├── components/
│   │   │   ├── RankingTable.jsx
│   │   │   ├── WeightControls.jsx   # the sliders
│   │   │   ├── FilterPanel.jsx      # spectral-type filters
│   │   │   ├── PorkchopPlot.jsx
│   │   │   └── TrajectoryViz.jsx
│   │   ├── api/
│   │   └── App.jsx
│   └── package.json
└── notebooks/                 # exploration + model training
    ├── 01_explore_asterank.ipynb
    ├── 02_lambert_sanity.ipynb
    └── 03_taxonomy_baseline.ipynb
```

---

## 8. Roadmap — phases & definition of done

Each phase is **independently shippable** and proves something concrete. Don't start a phase until the previous one's "Definition of Done" is met.

### Phase 0 — Foundation *(a weekend)*
**Goal:** scaffold + data flowing.
- Stand up the repo tree, env, lint/test.
- Ingest SBDB orbital elements + Asterank composition/value into a normalized parquet store.
- One exploration notebook over the data.

**Definition of Done:** you can load a clean dataframe of *N* asteroids with orbital elements + Asterank composition/value/Δv, locally, repeatably.

---

### Phase 1 — MVP: Static Ranking Tool *(1–2 weeks)* ⭐ **THE MVP**
**Goal:** a shippable web app that ranks and filters asteroids — using Asterank's *precomputed* Δv and value. **No trajectory math yet.**
- React ranked table: sortable columns (value, Δv, spectral type, size).
- Weight sliders (value vs accessibility) → live re-rank.
- Spectral-type filter (M-type for metals, C-type for volatiles, etc.).
- FastAPI serving the precomputed ranked store.

**Definition of Done:** a user opens the app, weights value-vs-accessibility, filters by spectral type, and gets a sensible ranked shortlist. **This is the MVP — it is genuinely useful and demoable on its own.**

> ⛳ **This is your first north-star checkpoint.** Everything before it is plumbing; this is the first thing that *is the product*.

---

### Phase 2 — Live Launch Windows *(2–4 weeks)*
**Goal:** real astrodynamics replaces the static baseline.
- Wire `astroquery.jplhorizons` for ephemerides.
- Implement Lambert solve (hapsira/pykep) for a chosen asteroid.
- Sweep a departure × arrival date grid → **porkchop plot** → extract optimal launch window + flight time + Δv.
- Replace Asterank's static Δv with your *own computed* values in the ranking.

**Definition of Done:** select any asteroid → generate a correct porkchop plot → report the ideal launch date(s), flight time, and Δv. The "predict ideal times and booster paths" core is now real.

---

### Phase 3 — Visualization & Optimization *(1–2 months)*
**Goal:** make it tangible and add fidelity.
- 3D transfer/orbit visualization (Plotly → Three.js).
- Rocket-equation cost model (Δv → propellant fraction → rough $).
- **Rendezvous matching** (match the asteroid's velocity at arrival, not just intercept it).
- Optional deep cut: gravity-assist / low-thrust optimization via `pykep` + `pygmo`.

**Definition of Done:** interactive 3D trajectory for a selected transfer + a believable propellant/cost estimate, with rendezvous (not just flyby) Δv.

---

### Phase 4 — ML Characterization *(1–2 months)* ⭐ **THE DIFFERENTIATOR**
**Goal:** fill the data gaps with ML; this is what makes Lodestar novel.
- Assemble training data (SMASS/Bus–DeMeo/MITHNEOS labels + RELAB meteorite ground truth).
- Build the model progression (§6): baseline on colors → CNN on spectra → uncertainty.
- Predict taxonomy + composition + confidence for unclassified objects.
- **Re-rank using ML-predicted composition**, discounted by confidence.

**Definition of Done:** a model ingests Rubin-style sparse colors and outputs probable taxonomy + composition + calibrated uncertainty, integrated into the ranking, evaluated honestly on held-out labeled asteroids.

> ⛳ **Second north-star checkpoint.** With Phase 4 done, Lodestar does something the existing tools don't — characterize the un-characterized majority at scale.

---

### Phase 5 — Stretch / Long Arc *(open-ended)*
The horizon, not the plan. Pick from:
- **Real-time Rubin alert ingestion** — triage the nightly firehose; flag newly-discovered metal-rich/accessible outliers for follow-up.
- **Return-trip & multi-target tour modeling** (mining missions come back; tours visit several).
- **Active-learning loop** — the model recommends which objects most deserve scarce telescope time.
- **Public deployment + open-source release** (be the Rubin-era Asterank).

---

## 9. Risks & honest limits

| Risk | Why it bites | Mitigation |
|---|---|---|
| **Data sparsity** | Most NEAs have no measured composition; rankings rest on inference | ML layer + uncertainty-as-first-class-output |
| **Composition uncertainty** | Spectral type → category, not precise ore grade | Confidence intervals on every value estimate; never imply measurement |
| **Meteorite-analog imperfection** | Space weathering & grain size bias the training signal | Acknowledge in model docs; validate on real held-out asteroids |
| **Trajectory model fidelity** | Patched-conic Lambert ≠ full n-body reality | Be explicit it's screening-grade, not flight-grade (see §1) |
| **Scope creep** | "Just one more feature" toward actual mission planning | The §1 fence + the litmus test |
| **"Impressive glue" critique** | Most layers orchestrate powerful libraries | Go genuinely deep in ≥1 layer — ideally the ML (§6) |

---

## 10. Success criteria

What "good" looks like at each altitude:

- **MVP success (Phase 1):** a stranger can use it to produce a defensible asteroid shortlist in under a minute, and understands the value-vs-access tradeoff from the sliders alone.
- **Technical-credibility success (Phase 2–3):** porkchop plots and Δv values that a domain person checks and nods at; a cost model that connects to physical reality.
- **Novelty success (Phase 4):** the ML characterization meaningfully expands how many objects can be ranked at all, *with* honest error bars — something the incumbent tools don't do.
- **Portfolio/impact success:** it's deployed, open, explainable end-to-end by you, and at least one other person finds it useful.

---

## 11. Glossary

- **Δv (delta-v)** — the total change in velocity a spacecraft must produce; the fundamental "cost" of any maneuver or mission. Lower = more accessible.
- **Lambert's problem** — given two positions and a time of flight, solve for the orbit connecting them. The engine behind launch-window and transfer computation.
- **Porkchop plot** — a contour plot of mission Δv over a grid of departure × arrival dates. Its minima are the ideal launch windows and flight times.
- **C3 / v-infinity** — measures of departure energy / hyperbolic excess velocity; how hard the booster has to throw the spacecraft.
- **Synodic period** — how often a launch window to a given target recurs (typically every couple of years). Why "ideal times" repeat.
- **Taxonomic class (Bus–DeMeo)** — asteroid categories from spectra: **C-type** (carbonaceous; water/volatiles), **S-type** (silicaceous; stony), **M-type** (metallic; iron-nickel + platinum-group metals), and more.
- **PGMs** — platinum-group metals; the high-value target (platinum, palladium, iridium, etc.), used in electronics, catalysis, pharma, and chips.
- **Reflectance spectrum** — how much light an object reflects across wavelengths; absorption bands (≈1.0 & 2.0 µm) diagnose minerals like pyroxene and olivine.
- **Rendezvous vs intercept** — *intercept* reaches the position; *rendezvous* also matches velocity (required to actually mine). Rendezvous costs more Δv.
- **Space weathering** — surface alteration that changes an asteroid's spectrum over time, biasing composition inference.

---

## 12. References & resources

**Tools & libraries**
- Asterank (open data, model for the UI): https://www.asterank.com/ · code: https://github.com/typpo/asterank
- hapsira (maintained poliastro fork): https://github.com/pleiszenburg/hapsira · docs: https://hapsira.readthedocs.io/
- pykep (ESA trajectory optimization): https://esa.github.io/pykep/
- astroquery (JPL Horizons access): https://astroquery.readthedocs.io/

**Data**
- JPL Small-Body Database: https://ssd.jpl.nasa.gov/tools/sbdb_query.html
- JPL Horizons: https://ssd.jpl.nasa.gov/horizons/
- Rubin / LSST Asteroid Discoveries Dashboard: https://rubinobservatory.org/

**Domain & method (for the ML layer)**
- Neural network for asteroid mineral composition from reflectance spectra (A&A, 2023): https://www.aanda.org/articles/aa/full_html/2023/01/aa43886-22/aa43886-22.html
- Machine-learning classification of meteorite spectra applied to asteroids (Icarus / ScienceDirect): https://www.sciencedirect.com/science/article/abs/pii/S0019103523002956
- ECOCEL asteroid mission-planning database (related prior art): https://www.sciencedirect.com/science/article/abs/pii/S0032063322000496

**Real-world context**
- AstroForge (leading private asteroid miner; target-selection use case): https://www.astroforge.com/
- Rubin Observatory — early asteroid discoveries (the data-scale shift): https://rubinobservatory.org/news/11000-new-asteroids

---

## Appendix — MVP quick-start checklist

A literal to-do list to get from zero to Phase 1.

- [ ] Create repo from the §7 scaffold; set up `uv`/`poetry`, `ruff`, `pytest`.
- [ ] `ingest/asterank.py`: pull Asterank data → `data/processed/asteroids.parquet`.
- [ ] `ingest/sbdb.py`: enrich with SBDB orbital elements (join on designation).
- [ ] Notebook: sanity-check the data — distributions of value, Δv, spectral type.
- [ ] `ranking/score.py`: implement weighted composite over value + accessibility (use Asterank's Δv for now).
- [ ] `api/main.py`: FastAPI endpoint returning the ranked, filterable list.
- [ ] `frontend`: RankingTable + WeightControls (sliders) + FilterPanel (spectral type).
- [ ] Wire frontend → API; verify live re-ranking on slider change.
- [ ] Ship it. Demo it. *Then* start Phase 2.

---

*Lodestar PAC v1.1 — built to be the fixed point you navigate the build by. Update it as reality teaches you things.*
