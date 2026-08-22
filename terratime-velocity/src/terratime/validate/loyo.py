"""§6.2 — leave-one-year-out. For each Tier-1 hexagon, refit holding out one
year at a time and predict the held-out value; this proves the curve is
capturing real structure rather than just interpolating noise.

Refitting uses the same isotonic setting as the run being validated; the
held-out target is always the raw observed built_frac_soft (the actual
measurement), not the isotonic-corrected value.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from terratime.config import Config
from terratime.fit.fitting import fit_logistic, TIER_1
from terratime.fit.models import logistic
from terratime.fit.preprocess import apply_isotonic


def run_loyo_validation(observations: pd.DataFrame, hex_metrics: pd.DataFrame, cfg: Config,
                         isotonic: bool | None = None) -> dict:
    isotonic = cfg.fitting.isotonic if isotonic is None else isotonic

    tier1_hexes = hex_metrics.loc[hex_metrics["tier"] == TIER_1, "h3_index"]
    max_hexes = cfg.validation.loyo_max_hexes
    if max_hexes is not None and max_hexes < len(tier1_hexes):
        tier1_hexes = tier1_hexes.sample(n=max_hexes, random_state=cfg.validation.recovery_seed)

    obs_by_hex = {h: g.sort_values("year") for h, g in observations.groupby("h3_index") if h in set(tier1_hexes)}

    abs_errors = []
    per_hex_mae = []

    for h3_index, g in obs_by_hex.items():
        years = g["year"].to_numpy(dtype=float)
        F_raw = g["built_frac_soft"].to_numpy(dtype=float)
        if len(years) < 4:
            continue  # need enough points left after holding one out

        hex_errors = []
        for holdout_i in range(len(years)):
            train_years = np.delete(years, holdout_i)
            train_F = np.delete(F_raw, holdout_i)

            fit_input_F = apply_isotonic(train_years, train_F)[0] if isotonic else train_F
            fit = fit_logistic(train_years, fit_input_F, cfg.fitting)
            if not fit.converged:
                continue

            predicted = float(logistic(years[holdout_i], fit.K, fit.r, fit.t0))
            actual = F_raw[holdout_i]
            err = abs(predicted - actual)
            abs_errors.append(err)
            hex_errors.append(err)

        if hex_errors:
            per_hex_mae.append(float(np.mean(hex_errors)))

    abs_errors = np.array(abs_errors)
    return dict(
        n_hexes=len(obs_by_hex),
        n_predictions=len(abs_errors),
        mae=float(np.mean(abs_errors)) if len(abs_errors) else float("nan"),
        median_abs_err=float(np.median(abs_errors)) if len(abs_errors) else float("nan"),
        p90_abs_err=float(np.percentile(abs_errors, 90)) if len(abs_errors) else float("nan"),
        per_hex_mae=np.array(per_hex_mae),
    )


def loyo_markdown(results: dict) -> str:
    return "\n".join([
        "## Leave-one-year-out validation",
        "",
        f"Refit {results['n_hexes']} Tier-1 hexagons, holding out each observed year in turn "
        f"({results['n_predictions']} total held-out predictions).",
        "",
        f"- **MAE (built-up fraction): {results['mae']:.4f}**",
        f"- Median absolute error: {results['median_abs_err']:.4f}",
        f"- 90th percentile absolute error: {results['p90_abs_err']:.4f}",
    ])
