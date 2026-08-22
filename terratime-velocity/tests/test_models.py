"""Verifies the analytic derivatives against numerical (central) differentiation,
and the closed-form identities (peak velocity, zero acceleration at t0, t90)."""

import numpy as np
import pytest

from terratime.fit.models import (
    logistic, logistic_velocity, logistic_acceleration,
    peak_velocity, time_to_fraction_of_K,
)

PARAM_SETS = [
    (0.8, 0.4, 2020.0),
    (0.95, 0.15, 2018.0),
    (0.6, 1.2, 2022.5),
    (0.99, 0.05, 2010.0),
]


@pytest.mark.parametrize("K,r,t0", PARAM_SETS)
def test_velocity_matches_numerical_derivative(K, r, t0):
    t = np.linspace(t0 - 15, t0 + 15, 50)
    h = 1e-5
    numerical = (logistic(t + h, K, r, t0) - logistic(t - h, K, r, t0)) / (2 * h)
    analytic = logistic_velocity(t, K, r, t0)
    np.testing.assert_allclose(analytic, numerical, atol=1e-6, rtol=1e-5)


@pytest.mark.parametrize("K,r,t0", PARAM_SETS)
def test_acceleration_matches_numerical_second_derivative(K, r, t0):
    t = np.linspace(t0 - 15, t0 + 15, 50)
    h = 1e-3
    numerical = (logistic(t + h, K, r, t0) - 2 * logistic(t, K, r, t0) + logistic(t - h, K, r, t0)) / (h ** 2)
    analytic = logistic_acceleration(t, K, r, t0)
    np.testing.assert_allclose(analytic, numerical, atol=1e-4, rtol=1e-3)


@pytest.mark.parametrize("K,r,t0", PARAM_SETS)
def test_peak_velocity_occurs_at_t0(K, r, t0):
    v_at_t0 = logistic_velocity(np.array([t0]), K, r, t0)[0]
    assert v_at_t0 == pytest.approx(peak_velocity(K, r), rel=1e-9)

    # And it really is the max: nearby points should be no faster.
    t_nearby = np.linspace(t0 - 5, t0 + 5, 201)
    v_nearby = logistic_velocity(t_nearby, K, r, t0)
    assert v_nearby.max() == pytest.approx(v_at_t0, rel=1e-6)


@pytest.mark.parametrize("K,r,t0", PARAM_SETS)
def test_acceleration_is_zero_at_t0(K, r, t0):
    a_at_t0 = logistic_acceleration(np.array([t0]), K, r, t0)[0]
    assert a_at_t0 == pytest.approx(0.0, abs=1e-9)


@pytest.mark.parametrize("K,r,t0", PARAM_SETS)
def test_time_to_90pct_saturation(K, r, t0):
    t90 = time_to_fraction_of_K(t0, r, 0.9)
    F_at_t90 = logistic(np.array([t90]), K, r, t0)[0]
    assert F_at_t90 == pytest.approx(0.9 * K, rel=1e-9)
    # Matches the spec's closed form exactly: t0 + ln(9)/r.
    assert t90 == pytest.approx(t0 + np.log(9) / r, rel=1e-12)
