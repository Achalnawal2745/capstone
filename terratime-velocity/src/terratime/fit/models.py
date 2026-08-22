"""The logistic growth model and its analytic derivatives.

F(t) = K / (1 + exp(-r * (t - t0)))

dF/dt   = r * F * (1 - F/K)
d2F/dt2 = r^2 * F * (1 - F/K) * (1 - 2F/K)

These are implemented analytically (never via numerical differentiation) so
that velocity/acceleration are exact given the fitted parameters. See
tests/test_models.py for verification against finite differences.
"""

from __future__ import annotations

import numpy as np


def logistic(t, K: float, r: float, t0: float):
    """F(t) — fitted with scipy.optimize.curve_fit, so keep this signature
    (t, K, r, t0) -> array, matching curve_fit's positional-params convention."""
    t = np.asarray(t, dtype=float)
    return K / (1.0 + np.exp(-r * (t - t0)))


def velocity_from_F(F, K: float, r: float):
    """dF/dt expressed directly in terms of F (avoids recomputing exp)."""
    F = np.asarray(F, dtype=float)
    return r * F * (1.0 - F / K)


def acceleration_from_F(F, K: float, r: float):
    """d2F/dt2 expressed directly in terms of F."""
    F = np.asarray(F, dtype=float)
    return (r ** 2) * F * (1.0 - F / K) * (1.0 - 2.0 * F / K)


def logistic_velocity(t, K: float, r: float, t0: float):
    """dF/dt at time t."""
    return velocity_from_F(logistic(t, K, r, t0), K, r)


def logistic_acceleration(t, K: float, r: float, t0: float):
    """d2F/dt2 at time t."""
    return acceleration_from_F(logistic(t, K, r, t0), K, r)


def peak_velocity(K: float, r: float) -> float:
    """Velocity is maximised at t = t0, where F = K/2; value is r*K/4."""
    return r * K / 4.0


def time_to_fraction_of_K(t0: float, r: float, frac: float = 0.9) -> float:
    """Solve K/(1+exp(-r(t-t0))) = frac*K for t.

    exp(-r(t-t0)) = 1/frac - 1  =>  t = t0 + ln(frac/(1-frac)) / r
    For frac=0.9 this is t0 + ln(9)/r, matching the spec's closed form.
    """
    return t0 + np.log(frac / (1.0 - frac)) / r
