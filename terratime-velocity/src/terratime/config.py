"""Loads config.yaml into typed, dot-accessible config objects.

All relative paths in config.yaml are resolved against the project root
(the directory containing config.yaml), not the process's CWD, so the CLI
works the same regardless of where it's invoked from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"


@dataclass
class DataConfig:
    raw_dir: Path
    interim_dir: Path
    processed_dir: Path
    observations_file: Path
    hex_metrics_file: Path
    hexes_geojson_file: Path


@dataclass
class GridConfig:
    h3_resolution: int = 9


@dataclass
class TimeConfig:
    year_start: int = 2016
    year_end: int = 2025
    t_eval: float = 2026.0


@dataclass
class SyntheticSourceConfig:
    n_hexes: Optional[int] = None
    seed: int = 42
    noise_sigma: float = 0.02
    classifier_flip_prob: float = 0.12
    classifier_flip_magnitude: float = 0.08


@dataclass
class EarthEngineSourceConfig:
    observations_file: Path = Path("data/interim/observations.parquet")


@dataclass
class SourceConfig:
    kind: str = "synthetic"
    synthetic: SyntheticSourceConfig = field(default_factory=SyntheticSourceConfig)
    earthengine: EarthEngineSourceConfig = field(default_factory=EarthEngineSourceConfig)


@dataclass
class FittingConfig:
    isotonic: bool = True
    r_lower: float = 0.01
    r_upper: float = 3.0
    t0_window_pad_years: float = 15.0


@dataclass
class TieringConfig:
    undeveloped_max_f: float = 0.02
    saturated_first_f: float = 0.85
    saturated_range: float = 0.03
    tier1_r2: float = 0.85
    tier1_t0_pre_years: float = 2.0
    tier1_t0_post_years: float = 7.0
    tier1_max_rel_stderr_r: float = 0.5
    tier2_r2: float = 0.60


@dataclass
class ValidationConfig:
    recovery_n_hexes: int = 2000
    recovery_noise_levels: list = field(default_factory=lambda: [0.01, 0.02, 0.05])
    recovery_flip_prob: float = 0.15
    recovery_flip_magnitude: float = 0.08
    recovery_seed: int = 7
    loyo_max_hexes: Optional[int] = None


@dataclass
class Config:
    data: DataConfig
    grid: GridConfig
    time: TimeConfig
    source: SourceConfig
    fitting: FittingConfig
    tiering: TieringConfig
    validation: ValidationConfig
    root: Path = PROJECT_ROOT


def _resolve(root: Path, value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else (root / p)


def load_config(path: Path | str = DEFAULT_CONFIG_PATH) -> Config:
    path = Path(path)
    root = path.resolve().parent
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    data_raw = raw.get("data", {})
    data = DataConfig(
        raw_dir=_resolve(root, data_raw.get("raw_dir", "data/raw")),
        interim_dir=_resolve(root, data_raw.get("interim_dir", "data/interim")),
        processed_dir=_resolve(root, data_raw.get("processed_dir", "data/processed")),
        observations_file=_resolve(root, data_raw.get("observations_file", "data/interim/observations.parquet")),
        hex_metrics_file=_resolve(root, data_raw.get("hex_metrics_file", "data/processed/hex_metrics.parquet")),
        hexes_geojson_file=_resolve(root, data_raw.get("hexes_geojson_file", "data/processed/hexes.geojson")),
    )

    grid = GridConfig(**raw.get("grid", {}))
    time_cfg = TimeConfig(**raw.get("time", {}))

    source_raw = raw.get("source", {})
    synthetic = SyntheticSourceConfig(**source_raw.get("synthetic", {}))
    ee_raw = source_raw.get("earthengine", {})
    earthengine = EarthEngineSourceConfig(
        observations_file=_resolve(root, ee_raw.get("observations_file", "data/interim/observations.parquet"))
    )
    source = SourceConfig(kind=source_raw.get("kind", "synthetic"), synthetic=synthetic, earthengine=earthengine)

    fitting = FittingConfig(**raw.get("fitting", {}))
    tiering = TieringConfig(**raw.get("tiering", {}))
    validation = ValidationConfig(**raw.get("validation", {}))

    return Config(
        data=data,
        grid=grid,
        time=time_cfg,
        source=source,
        fitting=fitting,
        tiering=tiering,
        validation=validation,
        root=root,
    )
