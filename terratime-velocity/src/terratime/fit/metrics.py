"""Turns a FitResult into the output metrics of §3.2: velocity, acceleration,
lifecycle stage, confidence, and the closed-form timing metrics.
"""

from __future__ import annotations

import numpy as np

from terratime.config import TieringConfig
from terratime.fit.fitting import (
    FitResult, TIER_UNDEVELOPED, TIER_SATURATED_STATIC, TIER_1, TIER_2, TIER_3,
)
from terratime.fit.models import (
    logistic, velocity_from_F, acceleration_from_F, peak_velocity, time_to_fraction_of_K,
)

NAN = float("nan")


def classify_lifecycle_tier1(t_eval: float, K: float, r: float, t0: float, F_eval: float) -> str:
    """§5.5. Emerging/Accelerating split on whether we're before or after the
    inflection point t0; Saturated once F reaches 90% of carrying capacity K."""
    if t_eval < t0 - 1.0 / r:
        return "Emerging"
    if t_eval < t0:
        return "Accelerating"
    if F_eval >= 0.9 * K:
        return "Saturated"
    return "Maturing"


def classify_lifecycle_tier2(sen_slope: float, F_last: float, undeveloped_max_f: float) -> str:
    """Tier 2 has no (K, r, t0) — only a Theil-Sen slope — so lifecycle here
    is a coarse heuristic bucket onto the same 5-category scale, not a fit to
    the S-curve shape. Documented explicitly since the spec doesn't pin this
    case down: a flat, near-zero slope is either untouched land or already
    built out (split on the observed level); a rising slope is split on
    whether the hex is still mostly below or above half built-up."""
    flat = abs(sen_slope) < 1e-3
    if flat:
        return "Undeveloped" if F_last < undeveloped_max_f else "Saturated"
    if F_last < 0.5:
        return "Emerging"
    return "Maturing"


def compute_confidence(fit: FitResult, n_obs: int, mean_n_scenes: float, t_start: float, t_end: float,
                        tiering_cfg: TieringConfig) -> float:
    """0-1 composite: R^2 (0.4) + inverse relative stderr on r & t0 (0.3)
    + data completeness (0.2) + t0-within-observation-window (0.1).

    score_r  = 1 / (1 + rel_stderr(r))          -> 1 as stderr -> 0
    score_t0 = 1 / (1 + t0_stderr / 5 years)    -> 0.5 at a 5-year stderr
    """
    if fit.tier in (TIER_UNDEVELOPED, TIER_SATURATED_STATIC):
        return 1.0
    if fit.tier == TIER_3:
        return 0.0

    r2_component = float(np.clip(fit.r_squared, 0.0, 1.0)) * 0.4

    if fit.tier == TIER_1 and not fit.bad_covariance and fit.r > 0 and np.isfinite(fit.t0_stderr):
        score_r = 1.0 / (1.0 + fit.r_stderr / fit.r)
        score_t0 = 1.0 / (1.0 + fit.t0_stderr / 5.0)
        stderr_component = 0.5 * (score_r + score_t0) * 0.3
    else:
        stderr_component = 0.0

    completeness = 0.5 * float(np.clip(n_obs / 10.0, 0.0, 1.0)) + 0.5 * float(np.clip(mean_n_scenes / 20.0, 0.0, 1.0))
    completeness_component = completeness * 0.2

    if fit.tier == TIER_1:
        window_component = 0.1
    elif np.isfinite(fit.t0):
        in_window = (t_start - tiering_cfg.tier1_t0_pre_years) <= fit.t0 <= (t_end + tiering_cfg.tier1_t0_post_years)
        window_component = 0.1 if in_window else 0.0
    else:
        window_component = 0.0

    return float(np.clip(r2_component + stderr_component + completeness_component + window_component, 0.0, 1.0))


def compute_metrics(
    fit: FitResult,
    F_last: float,
    t_eval: float,
    area_m2: float,
    n_obs: int,
    mean_n_scenes: float,
    t_start: float,
    t_end: float,
    tiering_cfg: TieringConfig,
) -> dict:
    base = dict(
        velocity_2026=NAN, velocity_m2_per_year=NAN, acceleration_2026=NAN,
        lifecycle=NAN, years_to_inflection=NAN, years_to_saturation=NAN,
        peak_velocity=NAN, confidence=NAN,
    )

    if fit.tier == TIER_UNDEVELOPED:
        base.update(velocity_2026=0.0, velocity_m2_per_year=0.0, acceleration_2026=0.0,
                     lifecycle="Undeveloped", confidence=1.0)
        return base

    if fit.tier == TIER_SATURATED_STATIC:
        base.update(velocity_2026=0.0, velocity_m2_per_year=0.0, acceleration_2026=0.0,
                     lifecycle="Saturated", confidence=1.0)
        return base

    confidence = compute_confidence(fit, n_obs, mean_n_scenes, t_start, t_end, tiering_cfg)

    if fit.tier == TIER_1:
        K, r, t0 = fit.K, fit.r, fit.t0
        F_eval = float(logistic(t_eval, K, r, t0))
        v = float(velocity_from_F(F_eval, K, r))
        a = float(acceleration_from_F(F_eval, K, r))
        base.update(
            velocity_2026=v,
            velocity_m2_per_year=v * area_m2,
            acceleration_2026=a,
            lifecycle=classify_lifecycle_tier1(t_eval, K, r, t0, F_eval),
            years_to_inflection=t0 - t_eval,
            years_to_saturation=float(time_to_fraction_of_K(t0, r, 0.9)) - t_eval,
            peak_velocity=float(peak_velocity(K, r)),
            confidence=confidence,
        )
        return base

    if fit.tier == TIER_2:
        v = fit.sen_slope if np.isfinite(fit.sen_slope) else NAN
        base.update(
            velocity_2026=v,
            velocity_m2_per_year=(v * area_m2 if np.isfinite(v) else NAN),
            lifecycle=classify_lifecycle_tier2(fit.sen_slope, F_last, tiering_cfg.undeveloped_max_f),
            confidence=confidence,
        )
        return base

    # TIER_3 — insufficient_signal, all metrics stay null per spec §5.4.
    base.update(lifecycle="insufficient_signal", confidence=0.0)
    return base
