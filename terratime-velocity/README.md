# TerraTime — Pillar 1: Growth Velocity & Acceleration Engine

Fits a logistic (S-curve) growth model to per-hexagon built-up fraction time
series across NCT Delhi, recovering interpretable parameters — carrying
capacity `K`, growth rate `r`, inflection year `t0` — and from them each
hexagon's **velocity** (dA/dt), **acceleration** (d²A/dt²), and **lifecycle
stage**.

This covers only Pillar 1. No ML forecasting, no LLM/RAG layer — see §9 of
the build spec for the full non-goals list.

## Quickstart

```bash
python -m venv .venv
.venv\Scripts\activate          # or: source .venv/bin/activate
pip install -e .

python -m terratime.cli run --source synthetic
python -m terratime.cli validate
python -m terratime.cli export-figures
```

Then open `viewer/index.html` directly in a browser (double-click — no
server needed; MapLibre GL and Chart.js are vendored in `viewer/vendor/`,
and the hex data is embedded in `viewer/data/hexes.js` rather than fetched,
so it works fully offline).

## The data adapter

The engine never depends on Google Earth Engine being reachable. Every run
goes through a `DataSource` (`src/terratime/sources/`):

- `SyntheticSource` — generates hexagon series from known `(K, r, t0)` plus
  configurable noise. This is the default, the unit-test fixture, and the
  demo fallback.
- `EarthEngineSource` — reads an already-exported `observations.parquet`
  (see `gee/export_dynamic_world.py` for the GEE-side raster export +
  zonal-stats script). The engine itself never calls the Earth Engine API.

Switch between them with `source.kind: synthetic | earthengine` in
`config.yaml`, or `--source` on the CLI. Both emit the identical schema
(`src/terratime/sources/base.py`), so nothing downstream changes.

## Commands

- `terratime run [--source synthetic|earthengine] [--isotonic/--no-isotonic]`
  — loads observations, fits every hexagon, writes `hex_metrics.parquet`,
  `hexes.geojson`, and the viewer's data file. Prints tier population
  counts (a primary output, not just a diagnostic).
- `terratime validate` — runs parameter recovery, leave-one-year-out, and
  face-validity (named Delhi landmarks), writing `reports/VALIDATION.md`.
- `terratime export-figures` — extra deck-ready figures (top-10
  accelerating cells, a static velocity map) into `reports/figures/`.

## Repository layout

See the build spec (§4) — this mirrors it: `src/terratime/{grid,sources,
fit,validate,export,cli,pipeline}.py`, `gee/`, `viewer/`, `tests/`.

## Known limitation: the NCT Delhi boundary

`src/terratime/grid.py` uses a simplified, hand-traced approximation of the
NCT Delhi boundary (~1,900 km² vs. the real ~1,483 km² — an artifact of
straight-line simplification of a jagged real border, not a bug). It's
accurate enough to place the H3 grid and contains every named location used
in face-validity. Swap in a survey-grade boundary (e.g. an OSM relation
export) before using this for anything beyond this demo.

## Math reference

`F(t) = K / (1 + exp(-r*(t - t0)))`, with analytic (not numerical)
derivatives for velocity and acceleration — see `src/terratime/fit/models.py`
and `tests/test_models.py` for the derivation and verification against
finite differences.
