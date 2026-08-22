import numpy as np

from terratime.config import TieringConfig
from terratime.fit.fitting import FitResult, TIER_1
from terratime.fit.metrics import classify_lifecycle_tier1, compute_metrics
from terratime.fit.models import logistic

TIERING = TieringConfig()


def test_lifecycle_emerging_before_takeoff():
    K, r, t0 = 0.8, 0.3, 2035.0
    t_eval = 2026.0
    F_eval = logistic(np.array([t_eval]), K, r, t0)[0]
    assert classify_lifecycle_tier1(t_eval, K, r, t0, F_eval) == "Emerging"


def test_lifecycle_accelerating_near_inflection():
    K, r, t0 = 0.8, 0.3, 2027.0
    t_eval = 2026.0
    F_eval = logistic(np.array([t_eval]), K, r, t0)[0]
    assert classify_lifecycle_tier1(t_eval, K, r, t0, F_eval) == "Accelerating"


def test_lifecycle_maturing_past_inflection_not_yet_saturated():
    K, r, t0 = 0.8, 0.3, 2020.0
    t_eval = 2026.0
    F_eval = logistic(np.array([t_eval]), K, r, t0)[0]
    assert F_eval < 0.9 * K
    assert classify_lifecycle_tier1(t_eval, K, r, t0, F_eval) == "Maturing"


def test_lifecycle_saturated_past_90pct():
    K, r, t0 = 0.8, 0.5, 2005.0
    t_eval = 2026.0
    F_eval = logistic(np.array([t_eval]), K, r, t0)[0]
    assert F_eval >= 0.9 * K
    assert classify_lifecycle_tier1(t_eval, K, r, t0, F_eval) == "Saturated"


def test_compute_metrics_tier1_confidence_in_bounds():
    fit = FitResult(
        tier=TIER_1, K=0.8, r=0.4, t0=2020.0,
        K_stderr=0.01, r_stderr=0.02, t0_stderr=0.3,
        r_squared=0.97, rmse=0.01, sen_slope=0.05,
        converged=True, bad_covariance=False,
    )
    metrics = compute_metrics(
        fit, F_last=0.75, t_eval=2026.0, area_m2=105000.0,
        n_obs=10, mean_n_scenes=20.0, t_start=2016.0, t_end=2025.0,
        tiering_cfg=TIERING,
    )
    assert 0.0 <= metrics["confidence"] <= 1.0
    assert metrics["lifecycle"] in ("Emerging", "Accelerating", "Maturing", "Saturated")
    assert metrics["velocity_m2_per_year"] == metrics["velocity_2026"] * 105000.0
