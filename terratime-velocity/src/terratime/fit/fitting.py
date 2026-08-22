"""Bounded logistic curve fitting + tiering (§5.3-5.4 of the spec).

`fit_hexagon` is the per-hexagon entry point: it runs the undeveloped /
saturated_static short-circuits, the optional isotonic correction, the bounded
curve_fit, and tier classification, returning a single FitResult.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.optimize import curve_fit

from terratime.config import FittingConfig, TieringConfig
from terratime.fit.models import logistic
from terratime.fit.preprocess import apply_isotonic
from terratime.fit.robust import theil_sen_slope

TIER_UNDEVELOPED = "undeveloped"
TIER_SATURATED_STATIC = "saturated_static"
TIER_1 = "tier1"
TIER_2 = "tier2"
TIER_3 = "tier3"


@dataclass
class FitResult:
    tier: str
    K: float = float("nan")
    r: float = float("nan")
    t0: float = float("nan")
    K_stderr: float = float("nan")
    r_stderr: float = float("nan")
    t0_stderr: float = float("nan")
    r_squared: float = float("nan")
    rmse: float = float("nan")
    sen_slope: float = float("nan")
    isotonic_adjustment: float = 0.0
    converged: bool = False
    bad_covariance: bool = False


def _initial_guess(years: np.ndarray, F_obs: np.ndarray, r_lower: float, r_upper: float):
    max_F = float(np.max(F_obs))
    K0 = min(1.0, max(max_F * 1.05, 1e-3))

    diffs = np.diff(F_obs)
    if len(diffs) > 0:
        max_diff_idx = int(np.argmax(diffs))
        max_diff = float(diffs[max_diff_idx])
        t0_0 = float(years[max_diff_idx + 1])
    else:
        max_diff = 1e-3
        t0_0 = float(years[len(years) // 2])

    r0 = 4.0 * max(max_diff, 1e-3) / K0
    r0 = float(np.clip(r0, r_lower, r_upper))
    return K0, r0, t0_0


def fit_logistic(years, F_obs, fitting_cfg: FittingConfig) -> FitResult:
    """Bounded curve_fit for a single hexagon's series. Does NOT classify
    tier — call classify_tier separately once you also have the tiering
    thresholds and the short-circuit checks resolved."""
    years = np.asarray(years, dtype=float)
    F_obs = np.asarray(F_obs, dtype=float)
    t_start, t_end = float(years.min()), float(years.max())

    max_F = float(np.max(F_obs))
    K0, r0, t0_0 = _initial_guess(years, F_obs, fitting_cfg.r_lower, fitting_cfg.r_upper)

    lower = [max_F, fitting_cfg.r_lower, t_start - fitting_cfg.t0_window_pad_years]
    upper = [1.0, fitting_cfg.r_upper, t_end + fitting_cfg.t0_window_pad_years]
    # Guard against a degenerate lower==upper bound on K (curve_fit rejects it).
    if lower[0] >= upper[0]:
        lower[0] = upper[0] - 1e-6

    p0 = [
        float(np.clip(K0, lower[0], upper[0])),
        float(np.clip(r0, lower[1], upper[1])),
        float(np.clip(t0_0, lower[2], upper[2])),
    ]

    sen_slope = theil_sen_slope(years, F_obs)

    try:
        popt, pcov = curve_fit(
            logistic, years, F_obs, p0=p0, bounds=(lower, upper), method="trf", maxfev=10000
        )
    except (RuntimeError, ValueError):
        return FitResult(tier=TIER_3, sen_slope=sen_slope, converged=False)

    K, r, t0 = (float(x) for x in popt)

    bad_covariance = not np.all(np.isfinite(pcov))
    if not bad_covariance:
        diag = np.diag(pcov)
        if np.any(diag < 0):
            bad_covariance = True

    if bad_covariance:
        K_se = r_se = t0_se = float("nan")
    else:
        K_se, r_se, t0_se = (float(x) for x in np.sqrt(np.diag(pcov)))

    F_pred = logistic(years, K, r, t0)
    residuals = F_obs - F_pred
    ss_res = float(np.sum(residuals ** 2))
    ss_tot = float(np.sum((F_obs - np.mean(F_obs)) ** 2))
    if ss_tot > 0:
        # When ss_tot is tiny (a nearly-flat series that still failed the
        # undeveloped/saturated_static short-circuit), 1 - ss_res/ss_tot can
        # blow up to an astronomically large negative number. It's already
        # unambiguously below every tiering threshold at that point, so clamp
        # it to a sane floor rather than reporting a physically meaningless
        # magnitude downstream (it has broken GeoJSON/vector-tile encoding).
        r_squared = max(1.0 - ss_res / ss_tot, -1.0)
    else:
        r_squared = 1.0 if ss_res < 1e-12 else 0.0
    rmse = float(np.sqrt(np.mean(residuals ** 2)))

    return FitResult(
        tier="pending",
        K=K, r=r, t0=t0,
        K_stderr=K_se, r_stderr=r_se, t0_stderr=t0_se,
        r_squared=r_squared, rmse=rmse,
        sen_slope=sen_slope, converged=True, bad_covariance=bad_covariance,
    )


def classify_tier(fit: FitResult, t_start: float, t_end: float, tiering_cfg: TieringConfig) -> str:
    if not fit.converged:
        return TIER_3
    if fit.r_squared < tiering_cfg.tier2_r2:
        return TIER_3

    t0_window_ok = (t_start - tiering_cfg.tier1_t0_pre_years) <= fit.t0 <= (t_end + tiering_cfg.tier1_t0_post_years)
    rel_stderr_ok = (
        not fit.bad_covariance
        and fit.r > 0
        and np.isfinite(fit.r_stderr)
        and (fit.r_stderr / fit.r) < tiering_cfg.tier1_max_rel_stderr_r
    )

    if fit.r_squared >= tiering_cfg.tier1_r2 and t0_window_ok and rel_stderr_ok:
        return TIER_1
    return TIER_2


def fit_hexagon(
    years,
    F_raw,
    fitting_cfg: FittingConfig,
    tiering_cfg: TieringConfig,
    use_isotonic: Optional[bool] = None,
) -> FitResult:
    """Full per-hexagon pipeline: short-circuits, optional isotonic
    correction, bounded fit, tier classification."""
    years = np.asarray(years, dtype=float)
    F_raw = np.asarray(F_raw, dtype=float)
    use_isotonic = fitting_cfg.isotonic if use_isotonic is None else use_isotonic

    max_F = float(np.max(F_raw))
    if max_F < tiering_cfg.undeveloped_max_f:
        return FitResult(tier=TIER_UNDEVELOPED, sen_slope=0.0, converged=False)

    first_F = float(F_raw[0])
    spread = float(np.max(F_raw) - np.min(F_raw))
    if first_F > tiering_cfg.saturated_first_f and spread < tiering_cfg.saturated_range:
        return FitResult(tier=TIER_SATURATED_STATIC, sen_slope=0.0, converged=False)

    if use_isotonic:
        F_fit, isotonic_adjustment = apply_isotonic(years, F_raw)
    else:
        F_fit, isotonic_adjustment = F_raw, 0.0

    result = fit_logistic(years, F_fit, fitting_cfg)
    result.isotonic_adjustment = isotonic_adjustment
    result.tier = classify_tier(result, float(years.min()), float(years.max()), tiering_cfg)
    return result
