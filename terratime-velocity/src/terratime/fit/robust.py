"""Theil-Sen robust slope — the non-parametric fallback used for Tier 2/3
hexagons where the logistic fit didn't converge cleanly, and recorded as
`sen_slope` alongside every Tier-1 fit for comparison."""

from __future__ import annotations

import numpy as np
from scipy.stats import theilslopes


def theil_sen_slope(years, F_obs) -> float:
    years = np.asarray(years, dtype=float)
    F_obs = np.asarray(F_obs, dtype=float)
    if len(np.unique(years)) < 2:
        return float("nan")
    slope, _intercept, _lo, _hi = theilslopes(F_obs, years)
    return float(slope)
