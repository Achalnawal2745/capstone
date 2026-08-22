"""Optional monotonic correction (PAVA / isotonic regression).

Built-up fraction at 0.1 km^2 scale is near-monotonic in reality; large
year-on-year decreases are almost always classifier noise, not demolition.
This step is flagged and optional (--no-isotonic) so both corrected and raw
results can be shown side by side.
"""

from __future__ import annotations

import numpy as np
from sklearn.isotonic import IsotonicRegression


def apply_isotonic(years, F_obs) -> tuple[np.ndarray, float]:
    """Returns (F_corrected, isotonic_adjustment) where isotonic_adjustment
    is mean(|F_corrected - F_raw|) — how much correction the series needed."""
    years = np.asarray(years, dtype=float)
    F_obs = np.asarray(F_obs, dtype=float)

    ir = IsotonicRegression(increasing=True, y_min=0.0, y_max=1.0)
    F_corrected = ir.fit_transform(years, F_obs)
    adjustment = float(np.mean(np.abs(F_corrected - F_obs)))
    return F_corrected, adjustment
