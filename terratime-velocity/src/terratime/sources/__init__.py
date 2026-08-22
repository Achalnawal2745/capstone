"""Source factory — the one place `source.kind` in config.yaml is switched
on. Everything downstream only ever sees the DataSource protocol."""

from __future__ import annotations

from terratime.config import Config
from terratime.sources.base import DataSource
from terratime.sources.earthengine import EarthEngineSource
from terratime.sources.synthetic import SyntheticSource


def build_source(cfg: Config, anchor_hexes: dict | None = None) -> DataSource:
    if cfg.source.kind == "synthetic":
        sc = cfg.source.synthetic
        return SyntheticSource(
            year_start=cfg.time.year_start,
            year_end=cfg.time.year_end,
            t_eval=cfg.time.t_eval,
            n_hexes=sc.n_hexes,
            seed=sc.seed,
            noise_sigma=sc.noise_sigma,
            classifier_flip_prob=sc.classifier_flip_prob,
            classifier_flip_magnitude=sc.classifier_flip_magnitude,
            h3_resolution=cfg.grid.h3_resolution,
            anchor_hexes=anchor_hexes or {},
        )
    if cfg.source.kind == "earthengine":
        return EarthEngineSource(observations_file=cfg.source.earthengine.observations_file)
    raise ValueError(f"unknown source.kind: {cfg.source.kind!r} (expected 'synthetic' or 'earthengine')")
