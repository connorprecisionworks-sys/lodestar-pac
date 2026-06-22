# Dataset improvement runbook (run on your Mac, open internet)

Goal: add infrared + colour features and more spectral labels, then retrain and
see the lift. The Cowork sandbox cannot reach these archives, so you run these.
None need an account or API key.

## One-time
```
cd path/to/lodestar
```
Everything below is run from the repo root with `uv run`.

## 1. Pull the three external catalogues
Run each. They download a public catalogue and write a small file to `data/raw/`.
Each prints how many objects it cross-matched to our 41,884.

```
uv run python -m backend.ingest.neowise
uv run python -m backend.ingest.sdss_moc
uv run python -m backend.ingest.spectra
```

If any prints a 0 / low match count or a 404, the source moved. Download the file
by hand and re-run with `--file`, for example:
```
uv run python -m backend.ingest.sdss_moc --file ~/Downloads/ADR4.dat
uv run python -m backend.ingest.neowise --file ~/Downloads/neowise_albedos.csv
uv run python -m backend.ingest.spectra --file ~/Downloads/demeo2009.csv --source bus-demeo
```
Then paste me the run output (and, if a parser failed, the first line of the file)
and I will fix the column mapping in one edit.

Where to download by hand if needed:
- SDSS MOC4 (ADR4): https://faculty.washington.edu/ivezic/sdssmoc/sdssmoc.html
- NEOWISE diameters/albedos: NASA PDS Small Bodies Node (search "NEOWISE diameters albedos")
- Bus-DeMeo / SMASS / MITHNEOS classifications: https://smass.mit.edu  and the PDS taxonomy bundles

## 2. Merge into the store
```
uv run python -m backend.ingest.enrich_features
```
Prints albedo coverage before/after and how many new measured labels were added.

## 3. Retrain and read the lift
```
uv run python -m backend.ml.taxonomy_enriched
```
Prints `LOO accuracy  albedo-only X%  ->  enriched Y%` and per-class recall. The
number to watch is metallic (M) recall: today it is 0%, and infrared/colour is the
feature set that can move it.

## 4. (optional) Re-rank + re-export so the app shows the new predictions
```
uv run python -m backend.ranking.enrich
uv run python -m backend.export_dataset   # if that is the export entrypoint name
```
Then commit `data/` and push; the live console + research pages pick it up.

## Notes
- Re-running `normalize` overwrites the store, so always run it BEFORE the
  neowise/sdss/spectra/enrich_features steps, never after.
- Everything is provenance-tagged: NEOWISE-filled albedos and added labels keep
  their source, and predictions stay separate from measurements.
