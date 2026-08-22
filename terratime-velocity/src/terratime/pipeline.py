"""Orchestrates: DataSource -> per-hexagon fit -> metrics -> hex_metrics dataframe.

This is the one place that ties sources, fit, and grid together, so CLI
commands and the validation scripts (which need the same per-hex fit/metric
logic without re-deriving it) both call into this module.
"""

from __future__ import annotations

import sys

import h3
import numpy as np
import pandas as pd
from scipy.stats import rankdata

from terratime.config import Config
from terratime.fit.fitting import fit_hexagon
from terratime.fit.metrics import compute_metrics
from terratime.sources.base import DataSource, validate_observations_schema

HEX_METRICS_COLUMNS = [
    "h3_index", "centroid_lat", "centroid_lon", "area_m2",
    "tier",
    "K", "r", "t0",
    "K_stderr", "r_stderr", "t0_stderr",
    "r_squared", "rmse",
    "velocity_2026", "velocity_m2_per_year",
    "acceleration_2026",
    "lifecycle",
    "years_to_inflection", "years_to_saturation",
    "peak_velocity",
    "confidence",
    "velocity_pctile", "acceleration_pctile",
    "sen_slope",
    "isotonic_adjustment",
    "first_year_obs", "last_year_obs", "n_obs", "mean_n_scenes",
]


def _hex_geometry(h3_index: str) -> tuple[float, float, float]:
    lat, lng = h3.cell_to_latlng(h3_index)
    area_m2 = h3.cell_area(h3_index, unit="km^2") * 1e6
    return lat, lng, area_m2


def run_pipeline(source: DataSource, cfg: Config, isotonic: bool | None = None, verbose: bool = True) -> pd.DataFrame:
    observations = source.load_observations()
    validate_observations_schema(observations)

    observations = observations.sort_values(["h3_index", "year"])
    grouped = observations.groupby("h3_index", sort=False)

    rows = []
    n_hexes = grouped.ngroups
    for i, (h3_index, g) in enumerate(grouped):
        years = g["year"].to_numpy(dtype=float)
        F_soft = g["built_frac_soft"].to_numpy(dtype=float)
        n_scenes = g["n_scenes"].to_numpy(dtype=float)

        lat, lng, area_m2 = _hex_geometry(h3_index)

        fit = fit_hexagon(years, F_soft, cfg.fitting, cfg.tiering, use_isotonic=isotonic)
        metrics = compute_metrics(
            fit,
            F_last=float(F_soft[-1]),
            t_eval=cfg.time.t_eval,
            area_m2=area_m2,
            n_obs=len(years),
            mean_n_scenes=float(np.mean(n_scenes)) if len(n_scenes) else float("nan"),
            t_start=float(years.min()),
            t_end=float(years.max()),
            tiering_cfg=cfg.tiering,
        )

        # Per §3.2: K/r/t0 (and their stderrs) are null outside Tier 1, even
        # though a Tier-2 fit technically converged to some (K, r, t0) —
        # those values didn't clear the Tier-1 reliability bar, so they don't
        # get reported as the hexagon's growth parameters.
        is_tier1 = fit.tier == "tier1"
        rows.append(dict(
            h3_index=h3_index, centroid_lat=lat, centroid_lon=lng, area_m2=area_m2,
            tier=fit.tier,
            K=fit.K if is_tier1 else float("nan"),
            r=fit.r if is_tier1 else float("nan"),
            t0=fit.t0 if is_tier1 else float("nan"),
            K_stderr=fit.K_stderr if is_tier1 else float("nan"),
            r_stderr=fit.r_stderr if is_tier1 else float("nan"),
            t0_stderr=fit.t0_stderr if is_tier1 else float("nan"),
            r_squared=fit.r_squared, rmse=fit.rmse,
            velocity_2026=metrics["velocity_2026"], velocity_m2_per_year=metrics["velocity_m2_per_year"],
            acceleration_2026=metrics["acceleration_2026"],
            lifecycle=metrics["lifecycle"],
            years_to_inflection=metrics["years_to_inflection"], years_to_saturation=metrics["years_to_saturation"],
            peak_velocity=metrics["peak_velocity"],
            confidence=metrics["confidence"],
            sen_slope=fit.sen_slope,
            isotonic_adjustment=fit.isotonic_adjustment,
            first_year_obs=int(years.min()), last_year_obs=int(years.max()),
            n_obs=len(years), mean_n_scenes=float(np.mean(n_scenes)) if len(n_scenes) else float("nan"),
        ))

        if verbose and n_hexes > 2000 and (i + 1) % 2000 == 0:
            print(f"  fit {i + 1}/{n_hexes} hexagons...", file=sys.stderr)

    df = pd.DataFrame(rows)
    df["velocity_pctile"] = _percentile_rank(df["velocity_2026"])
    df["acceleration_pctile"] = _percentile_rank(df["acceleration_2026"])
    df = df[HEX_METRICS_COLUMNS]

    if verbose:
        print_tier_summary(df)

    return df


def _percentile_rank(series: pd.Series) -> pd.Series:
    values = series.to_numpy(dtype=float)
    result = np.full(values.shape, np.nan)
    mask = np.isfinite(values)
    if mask.sum() > 0:
        result[mask] = rankdata(values[mask], method="average") / mask.sum()
    return pd.Series(result, index=series.index)


def print_tier_summary(df: pd.DataFrame) -> None:
    counts = df["tier"].value_counts()
    total = len(df)
    print("\n=== Tier population (primary output) ===")
    for tier in ["tier1", "tier2", "tier3", "saturated_static", "undeveloped"]:
        n = int(counts.get(tier, 0))
        pct = 100.0 * n / total if total else 0.0
        print(f"  {tier:<18} {n:>7}  ({pct:5.1f}%)")
    print(f"  {'TOTAL':<18} {total:>7}")
    print()
