"""The DataSource protocol — the single biggest schedule-risk mitigation in
this build. EarthEngineSource and SyntheticSource emit the identical
dataframe schema so the rest of the pipeline never knows or cares which one
produced the data. Swapping is a one-line config change (`source.kind` in
config.yaml).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd

OBSERVATION_COLUMNS = {
    "h3_index": "object",
    "year": "int64",
    "built_frac_soft": "float64",
    "built_frac_hard": "float64",
    "n_pixels": "int64",
    "n_scenes": "int64",
}


@runtime_checkable
class DataSource(Protocol):
    """Anything that can produce per-hexagon annual built-up observations."""

    provenance: str  # e.g. "SIMULATED DATA" or "LIVE: Dynamic World 2016-2025"

    def load_observations(self) -> pd.DataFrame:
        """Returns a long-format dataframe matching OBSERVATION_COLUMNS,
        one row per (h3_index, year)."""
        ...


def validate_observations_schema(df: pd.DataFrame) -> None:
    missing = set(OBSERVATION_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"observations dataframe is missing required columns: {sorted(missing)}")

    if df["built_frac_soft"].lt(0).any() or df["built_frac_soft"].gt(1).any():
        raise ValueError("built_frac_soft must be in [0, 1]")
    if df["built_frac_hard"].lt(0).any() or df["built_frac_hard"].gt(1).any():
        raise ValueError("built_frac_hard must be in [0, 1]")
    if df["year"].isna().any() or df["h3_index"].isna().any():
        raise ValueError("h3_index and year must not contain nulls")
