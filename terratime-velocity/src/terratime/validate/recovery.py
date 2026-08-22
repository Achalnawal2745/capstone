"""§6.1 — parameter recovery. Generates synthetic hexagons spanning realistic
(K, r, t0) ranges at several noise levels (plus a classifier-flip noise mode),
fits each with the real pipeline, and reports how well K/r/t0 come back out.

The headline number is the t0 recovery error distribution: "we recover the
inflection year to within +-X years at realistic noise."
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from terratime.config import Config
from terratime.fit.fitting import fit_hexagon, TIER_1

# Realistic ranges for a res-9 (~0.105 km^2) hexagon in an actively developing city.
K_RANGE = (0.3, 0.98)
R_RANGE = (0.1, 1.5)


def _sample_ground_truth(n: int, year_start: int, year_end: int, rng: np.random.Generator) -> pd.DataFrame:
    K = rng.uniform(*K_RANGE, size=n)
    r = rng.uniform(*R_RANGE, size=n)
    # t0 spans well before to well after the observation window, so some
    # hexes are genuinely hard to identify (t0 far outside [t_start-2, t_end+7])
    # -- that's deliberate: it's what lets us report Tier-1 recovery rate.
    t0 = rng.uniform(year_start - 5, year_end + 10, size=n)
    return pd.DataFrame({"K": K, "r": r, "t0": t0})


def _true_tier1(ground_truth: pd.DataFrame, year_start: int, year_end: int, tiering_cfg) -> np.ndarray:
    lo = year_start - tiering_cfg.tier1_t0_pre_years
    hi = year_end + tiering_cfg.tier1_t0_post_years
    return ((ground_truth["t0"] >= lo) & (ground_truth["t0"] <= hi)).to_numpy()


def _simulate(K, r, t0, years, noise_sigma, flip_mode, flip_magnitude, rng):
    from terratime.fit.models import logistic
    F_true = logistic(years, K, r, t0)
    F_obs = F_true + rng.normal(0.0, noise_sigma, size=years.shape)
    if flip_mode:
        n_flips = rng.integers(1, 3)
        idx = rng.choice(len(years), size=min(n_flips, len(years)), replace=False)
        F_obs[idx] += rng.choice([-1.0, 1.0], size=len(idx)) * flip_magnitude
    return np.clip(F_obs, 0.0, 1.0)


def run_recovery_validation(cfg: Config) -> dict:
    """Returns a dict keyed by noise-level label, each containing MAE/bias for
    K, r, t0, the Tier-1 recovery rate, and the raw t0 error array (for the
    figure and the headline ± number)."""
    vcfg = cfg.validation
    rng = np.random.default_rng(vcfg.recovery_seed)
    years = np.arange(cfg.time.year_start, cfg.time.year_end + 1, dtype=float)

    ground_truth = _sample_ground_truth(vcfg.recovery_n_hexes, cfg.time.year_start, cfg.time.year_end, rng)
    true_tier1_mask = _true_tier1(ground_truth, cfg.time.year_start, cfg.time.year_end, cfg.tiering)

    conditions = [(f"sigma={s}", s, False) for s in vcfg.recovery_noise_levels]
    # Classifier-flip mode layers 1-2 year spikes on top of a moderate baseline noise floor.
    conditions.append(("classifier_flip", 0.02, True))

    results = {}
    for label, noise_sigma, flip_mode in conditions:
        K_err, r_err, t0_err = [], [], []
        K_signed, r_signed, t0_signed = [], [], []
        recovered_tier1 = []

        for K_true, r_true, t0_true in ground_truth[["K", "r", "t0"]].itertuples(index=False):
            F_obs = _simulate(K_true, r_true, t0_true, years, noise_sigma, flip_mode, vcfg.recovery_flip_magnitude, rng)
            fit = fit_hexagon(years, F_obs, cfg.fitting, cfg.tiering)

            recovered_tier1.append(fit.tier == TIER_1)
            if fit.tier == TIER_1:
                K_signed.append(fit.K - K_true)
                r_signed.append(fit.r - r_true)
                t0_signed.append(fit.t0 - t0_true)
                K_err.append(abs(fit.K - K_true))
                r_err.append(abs(fit.r - r_true))
                t0_err.append(abs(fit.t0 - t0_true))

        recovered_tier1 = np.array(recovered_tier1)
        n_true_tier1 = int(true_tier1_mask.sum())
        n_correctly_recovered = int((recovered_tier1 & true_tier1_mask).sum())

        results[label] = dict(
            noise_sigma=noise_sigma, flip_mode=flip_mode,
            n=len(ground_truth),
            n_fit_tier1=int(recovered_tier1.sum()),
            n_true_tier1=n_true_tier1,
            pct_true_tier1_recovered=(100.0 * n_correctly_recovered / n_true_tier1) if n_true_tier1 else float("nan"),
            K_mae=float(np.mean(K_err)) if K_err else float("nan"),
            K_bias=float(np.mean(K_signed)) if K_signed else float("nan"),
            r_mae=float(np.mean(r_err)) if r_err else float("nan"),
            r_bias=float(np.mean(r_signed)) if r_signed else float("nan"),
            t0_mae=float(np.mean(t0_err)) if t0_err else float("nan"),
            t0_bias=float(np.mean(t0_signed)) if t0_signed else float("nan"),
            t0_median_abs_err=float(np.median(t0_err)) if t0_err else float("nan"),
            t0_p90_abs_err=float(np.percentile(t0_err, 90)) if t0_err else float("nan"),
            t0_errors=np.array(t0_err),
        )

    return results


def recovery_markdown(results: dict) -> str:
    lines = [
        "## Parameter recovery (synthetic ground truth)",
        "",
        "| Noise condition | n | Tier-1 fit | True Tier-1 recovered | K MAE | r MAE | t0 MAE (yrs) | t0 median abs err | t0 p90 abs err |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for label, r in results.items():
        lines.append(
            f"| {label} | {r['n']} | {r['n_fit_tier1']} | "
            f"{r['pct_true_tier1_recovered']:.1f}% ({r['n_true_tier1']} true) | "
            f"{r['K_mae']:.4f} | {r['r_mae']:.4f} | {r['t0_mae']:.2f} | "
            f"{r['t0_median_abs_err']:.2f} | {r['t0_p90_abs_err']:.2f} |"
        )

    headline_sigma = "sigma=0.02"
    if headline_sigma in results and np.isfinite(results[headline_sigma]["t0_mae"]):
        r = results[headline_sigma]
        lines += [
            "",
            f"**Headline: at realistic noise ({headline_sigma}), the engine recovers the inflection "
            f"year to within +-{r['t0_median_abs_err']:.1f} years (median), "
            f"+-{r['t0_p90_abs_err']:.1f} years (90th percentile).**",
        ]
    return "\n".join(lines)
