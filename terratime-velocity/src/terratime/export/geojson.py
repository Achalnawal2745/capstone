"""Writes data/processed/hexes.geojson for the offline viewer.

Coordinates are rounded to 5 decimal places (~1.1 m) to keep the file small
enough for a single-file, double-click-to-open demo, per §7 M3 / §9 (plain
GeoJSON, no PMTiles/tippecanoe at this scale).
"""

from __future__ import annotations

import json
from pathlib import Path

import h3
import numpy as np
import pandas as pd

# Keep the properties payload to what the viewer actually reads (choropleth
# layers + the click-through side panel), not every internal fitting column.
VIEWER_PROPERTIES = [
    "h3_index", "tier", "K", "r", "t0",
    "r_squared", "rmse",
    "velocity_2026", "velocity_m2_per_year", "acceleration_2026",
    "lifecycle", "years_to_inflection", "years_to_saturation", "peak_velocity",
    "confidence", "velocity_pctile", "acceleration_pctile",
    "sen_slope", "isotonic_adjustment",
    "first_year_obs", "last_year_obs", "n_obs", "mean_n_scenes",
    "centroid_lat", "centroid_lon", "area_m2",
]


def _clean(value):
    if value is None:
        return None
    if isinstance(value, (float, np.floating)):
        if not np.isfinite(value):
            return None
        return round(float(value), 5)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, str):
        return value
    return value


def hex_metrics_to_geojson(hex_metrics: pd.DataFrame, precision: int = 5) -> dict:
    features = []
    for row in hex_metrics.itertuples(index=False):
        row_dict = row._asdict()
        h3_index = row_dict["h3_index"]
        boundary = h3.cell_to_boundary(h3_index)  # tuple of (lat, lng)
        ring = [[round(lng, precision), round(lat, precision)] for lat, lng in boundary]
        ring.append(ring[0])  # GeoJSON polygons must be closed rings

        properties = {col: _clean(row_dict.get(col)) for col in VIEWER_PROPERTIES if col in row_dict}

        features.append({
            "type": "Feature",
            "properties": properties,
            "geometry": {"type": "Polygon", "coordinates": [ring]},
        })

    return {"type": "FeatureCollection", "features": features}


def write_hexes_geojson(hex_metrics: pd.DataFrame, out_path: Path, precision: int = 5) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    geojson = hex_metrics_to_geojson(hex_metrics, precision=precision)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, separators=(",", ":"))
    return out_path


def _observations_lookup(observations: pd.DataFrame, precision: int = 4) -> dict:
    """h3_index -> [[year, built_frac_soft], ...] — the raw points the click-
    through side panel overlays the fitted S-curve on top of."""
    lookup = {}
    for h3_index, g in observations.sort_values("year").groupby("h3_index"):
        lookup[h3_index] = [
            [int(y), round(float(f), precision)]
            for y, f in zip(g["year"], g["built_frac_soft"])
        ]
    return lookup


def write_hexes_geojson_js(
    hex_metrics: pd.DataFrame, out_path: Path, provenance: str,
    observations: pd.DataFrame | None = None, precision: int = 5,
) -> Path:
    """Wraps the same GeoJSON (plus, if given, per-hex raw observed points)
    as a `<script src=...>`-loadable JS file.

    The viewer opens via double-click (file:// protocol), where `fetch()` of
    a sibling file is blocked by CORS in most browsers. A plain <script src>
    local file load is not subject to that restriction, so this is what the
    viewer actually loads — data/processed/hexes.geojson remains the
    canonical, tool-agnostic artifact.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    geojson = hex_metrics_to_geojson(hex_metrics, precision=precision)
    payload = {"provenance": provenance, "geojson": geojson}
    if observations is not None:
        payload["observations"] = _observations_lookup(observations)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("window.TERRATIME_DATA = ")
        f.write(json.dumps(payload, separators=(",", ":")))
        f.write(";\n")
    return out_path
