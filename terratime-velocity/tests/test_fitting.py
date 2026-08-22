"""Noise-free parameter recovery (<1% error, per acceptance criteria) and
tiering short-circuit behavior."""

import numpy as np
import pytest

from terratime.config import FittingConfig, TieringConfig
from terratime.fit.fitting import fit_hexagon, TIER_1, TIER_UNDEVELOPED, TIER_SATURATED_STATIC
from terratime.fit.models import logistic

FITTING = FittingConfig()
TIERING = TieringConfig()

YEARS = np.arange(2016, 2026, dtype=float)


@pytest.mark.parametrize("K,r,t0", [
    (0.8, 0.4, 2020.0),
    (0.9, 0.25, 2019.0),
    (0.6, 0.6, 2021.0),
])
def test_noise_free_recovery_under_one_percent(K, r, t0):
    F_obs = logistic(YEARS, K, r, t0)
    fit = fit_hexagon(YEARS, F_obs, FITTING, TIERING, use_isotonic=False)

    assert fit.tier == TIER_1
    assert fit.K == pytest.approx(K, rel=0.01)
    assert fit.r == pytest.approx(r, rel=0.01)
    assert fit.t0 == pytest.approx(t0, rel=0.01)
    assert fit.r_squared > 0.999


def test_undeveloped_short_circuit():
    F_obs = np.full(len(YEARS), 0.005) + np.array([0, 0.001, -0.001, 0, 0.002, 0, 0, -0.002, 0.001, 0])
    fit = fit_hexagon(YEARS, F_obs, FITTING, TIERING)
    assert fit.tier == TIER_UNDEVELOPED
    assert not fit.converged


def test_saturated_static_short_circuit():
    F_obs = np.full(len(YEARS), 0.92) + np.array([0, 0.005, -0.004, 0.002, 0, -0.003, 0.001, 0, 0.004, -0.002])
    fit = fit_hexagon(YEARS, F_obs, FITTING, TIERING)
    assert fit.tier == TIER_SATURATED_STATIC
    assert not fit.converged


def test_noisy_series_falls_back_gracefully():
    rng = np.random.default_rng(0)
    F_obs = np.clip(rng.uniform(0.1, 0.9, size=len(YEARS)), 0, 1)  # pure noise, no logistic structure
    fit = fit_hexagon(YEARS, F_obs, FITTING, TIERING)
    assert fit.tier in ("tier2", "tier3")
    assert np.isfinite(fit.sen_slope)


def test_r_squared_is_clamped_for_near_zero_variance_series():
    # A near-flat series (tiny variance -> ss_tot near 0) that still clears
    # both short-circuits can otherwise blow 1 - ss_res/ss_tot up to an
    # astronomically large negative number, which broke GeoJSON/vector-tile
    # encoding downstream in the viewer (real bug caught via headless-browser
    # testing: MapLibre threw "Given varint doesn't fit into 10 bytes").
    rng = np.random.default_rng(1)
    F_obs = 0.3 + rng.normal(0, 1e-7, size=len(YEARS))
    fit = fit_hexagon(YEARS, F_obs, FITTING, TIERING)
    assert fit.r_squared >= -1.0
    assert np.isfinite(fit.r_squared)
