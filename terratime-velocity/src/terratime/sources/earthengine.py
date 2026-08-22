"""EarthEngineSource — loads real Dynamic World-derived per-hexagon time
series from an already-exported observations.parquet (produced by
gee/export_dynamic_world.py's raster-export + local zonal-stats path; see §8).

This adapter never talks to the Earth Engine API itself — by the time this
class runs, the GEE round-trip is done and its output is just a parquet file
on disk. That's what keeps the engine from ever depending on GEE auth/export
being available at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from terratime.sources.base import validate_observations_schema


@dataclass
class EarthEngineSource:
    observations_file: Path
    provenance: str = "LIVE: Dynamic World 2016-2025"

    def load_observations(self) -> pd.DataFrame:
        path = Path(self.observations_file)
        if not path.exists():
            raise FileNotFoundError(
                f"EarthEngineSource: {path} not found. Run gee/export_dynamic_world.py "
                "first, or switch source.kind to 'synthetic' in config.yaml."
            )
        df = pd.read_parquet(path)
        validate_observations_schema(df)
        return df
