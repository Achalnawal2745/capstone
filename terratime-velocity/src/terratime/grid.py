"""H3 resolution-9 grid over the NCT Delhi boundary.

The polygon below is a simplified approximation of the NCT Delhi boundary
(traced from well-known reference points — Narela/Bawana in the north,
the Yamuna floodplain on the east, Badarpur/Chhatarpur in the south, and
Najafgarh in the west). It is accurate enough for hex-grid generation and
demo purposes at H3 res-9 (~0.105 km^2 / cell); it is NOT a survey-grade
boundary. Swap in an authoritative polygon (e.g. an OSM relation export)
before using this for anything beyond the Pillar-1 demo.

h3-py v4 API only — see module docstring warnings in the build spec:
latlng_to_cell, cell_to_latlng, cell_to_boundary, h3shape_to_cells,
LatLngPoly, cell_area, grid_disk. Never v3-style geo_to_h3 / h3_to_geo*.
"""

from __future__ import annotations

import h3
import pandas as pd

# (lat, lng) pairs, traced clockwise from the northern tip near Narela.
NCT_DELHI_BOUNDARY_LATLNG: list[tuple[float, float]] = [
    (28.8826, 77.0703),  # Narela, north tip
    (28.8586, 77.2020),  # NE, near Loni border
    (28.8253, 77.2965),  # East, Yamuna north
    (28.7300, 77.3480),  # East, Yamuna
    (28.6700, 77.3350),  # East, Yamuna
    (28.6000, 77.3050),  # SE, near Noida border
    (28.5300, 77.2900),  # South, near Badarpur
    (28.4550, 77.2100),  # South, near Faridabad border
    (28.4050, 77.1200),  # South, Chhatarpur area
    (28.4300, 77.0200),  # SW, near Gurgaon border
    (28.4600, 76.8700),  # West, near Najafgarh
    (28.5500, 76.8380),  # West, Najafgarh drain
    (28.6400, 76.8450),  # West
    (28.7200, 76.8850),  # NW
    (28.7900, 76.9500),  # North, near Bawana
    (28.8400, 77.0100),  # North
]


def get_nct_delhi_boundary() -> list[tuple[float, float]]:
    """Returns the boundary as a list of (lat, lng) tuples."""
    return list(NCT_DELHI_BOUNDARY_LATLNG)


def generate_hex_grid(resolution: int = 9) -> pd.DataFrame:
    """Generates the H3 grid covering NCT Delhi at the given resolution.

    Returns a dataframe with columns: h3_index, centroid_lat, centroid_lon, area_m2.
    """
    boundary = get_nct_delhi_boundary()
    shape = h3.LatLngPoly(boundary)
    cells = h3.h3shape_to_cells(shape, resolution)

    rows = []
    for cell in cells:
        lat, lng = h3.cell_to_latlng(cell)
        area_km2 = h3.cell_area(cell, unit="km^2")
        rows.append(dict(h3_index=cell, centroid_lat=lat, centroid_lon=lng, area_m2=area_km2 * 1e6))

    return pd.DataFrame(rows)
