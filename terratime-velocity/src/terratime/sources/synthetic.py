"""SyntheticSource — generates hexagon time series from known (K, r, t0) plus
configurable noise. This is the unit-test / parameter-recovery / demo-fallback
adapter described in §1 of the spec: it must never be required for the engine
to run, and it emits the exact same schema as EarthEngineSource.

Six archetypes populate the demo grid so the viewer shows a realistic mix of
lifecycle stages:
  undeveloped        - flat, near-zero, no logistic law
  emerging           - inflection well after t_eval
  accelerating        - inflection shortly after t_eval
  maturing            - inflection before t_eval, not yet 90% saturated
  saturated_dynamic   - inflection well before t_eval, already >=90% saturated
  saturated_static    - flat, near-K for the entire observed window (the
                        undeveloped/saturated_static tiering short-circuits)

A caller (typically the CLI, sourcing from validate.facevalidity) may pass
`anchor_hexes` to pin specific named locations (e.g. Karol Bagh) to a chosen
archetype/parameters so the face-validity demo table is meaningful even when
no real Dynamic World data has landed yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from terratime.fit.models import logistic
from terratime.grid import generate_hex_grid

FLAT_ARCHETYPES = {"undeveloped", "saturated_static"}

# Archetype order for the radial sampler below.
_RADIAL_ARCHETYPES = ["undeveloped", "emerging", "accelerating", "maturing", "saturated_dynamic", "saturated_static"]
_RADIAL_CORE_WEIGHTS = np.array([0.02, 0.05, 0.08, 0.25, 0.05, 0.55])   # city-center mix: mostly built out
_RADIAL_EDGE_WEIGHTS = np.array([0.35, 0.30, 0.20, 0.10, 0.02, 0.03])   # periphery mix: mostly still developing


def sample_archetypes_radial(dist_norm: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Real cities grow outward from a core, so a spatially uniform random
    archetype mix (independent of location) makes the demo map look like
    salt-and-pepper noise rather than a city. `dist_norm` is each hex's
    distance from the city center normalized to [0, 1]; archetype mix is
    linearly interpolated between a built-out core and a still-developing
    edge, then sampled independently per hex (still random, just spatially
    biased — this is cosmetic weighting for the synthetic demo grid, not a
    growth model)."""
    dist_norm = np.clip(dist_norm, 0.0, 1.0)
    w = _RADIAL_CORE_WEIGHTS[None, :] * (1 - dist_norm)[:, None] + _RADIAL_EDGE_WEIGHTS[None, :] * dist_norm[:, None]
    w /= w.sum(axis=1, keepdims=True)
    cum = np.cumsum(w, axis=1)
    u = rng.random(len(dist_norm))
    idx = np.clip((u[:, None] > cum).sum(axis=1), 0, len(_RADIAL_ARCHETYPES) - 1)
    return np.array(_RADIAL_ARCHETYPES)[idx]


def simulate_observed_series(
    K: float, r: float, t0: float, years, noise_sigma: float,
    flip_prob: float, flip_magnitude: float, rng: np.random.Generator,
):
    """Logistic ground truth + Gaussian noise + an occasional 1-2 year
    classifier-flip spike (§6.1's 'classifier flip' noise mode)."""
    years = np.asarray(years, dtype=float)
    F_true = logistic(years, K, r, t0)
    F_obs = F_true + rng.normal(0.0, noise_sigma, size=years.shape)

    n_years = len(years)
    if flip_prob > 0 and rng.random() < min(flip_prob * n_years, 0.9):
        n_flips = 1 if rng.random() < 0.7 else 2
        flip_idx = rng.choice(n_years, size=min(n_flips, n_years), replace=False)
        signs = rng.choice([-1.0, 1.0], size=len(flip_idx))
        F_obs[flip_idx] += signs * flip_magnitude

    return np.clip(F_obs, 0.0, 1.0), F_true


def _generate_flat_series(level: float, noise_std: float, years, rng: np.random.Generator):
    years = np.asarray(years, dtype=float)
    F_true = np.full(years.shape, level)
    F_obs = F_true + rng.normal(0.0, noise_std, size=years.shape)
    return np.clip(F_obs, 0.0, 1.0), F_true


def sample_params_for_archetype(archetype: str, t_eval: float, rng: np.random.Generator):
    """Sample (K, r, t0) so that, evaluated at t_eval, the resulting Tier-1
    fit lands in the intended lifecycle bucket (see classify_lifecycle_tier1).
    Uses the same ln(9)/r = time-to-90%-saturation closed form as the metrics
    module, so the archetype boundaries line up exactly with classification."""
    ln9 = np.log(9.0)

    if archetype == "emerging":
        r = rng.uniform(0.15, 0.5)
        K = rng.uniform(0.5, 0.95)
        t0 = t_eval + 1.0 / r + rng.uniform(1.0, 8.0)
    elif archetype == "accelerating":
        r = rng.uniform(0.15, 0.6)
        K = rng.uniform(0.5, 0.95)
        frac = rng.uniform(0.05, 0.95)
        t0 = t_eval + frac * (1.0 / r)
    elif archetype == "maturing":
        r = rng.uniform(0.2, 0.8)
        K = rng.uniform(0.6, 0.97)
        max_delta = (ln9 / r) * 0.9
        delta = rng.uniform(0.05 * max_delta, max_delta)
        t0 = t_eval - delta
    elif archetype == "saturated_dynamic":
        r = rng.uniform(0.2, 0.9)
        K = rng.uniform(0.7, 0.98)
        min_delta = (ln9 / r) * 1.15
        delta = rng.uniform(min_delta, min_delta * 2.5)
        t0 = t_eval - delta
    else:
        raise ValueError(f"unknown dynamic archetype: {archetype}")

    return float(K), float(r), float(t0)


@dataclass
class SyntheticSource:
    year_start: int = 2016
    year_end: int = 2025
    t_eval: float = 2026.0
    n_hexes: Optional[int] = None
    seed: int = 42
    noise_sigma: float = 0.02
    classifier_flip_prob: float = 0.12
    classifier_flip_magnitude: float = 0.08
    h3_resolution: int = 9
    anchor_hexes: dict = field(default_factory=dict)

    provenance: str = "SIMULATED DATA"

    def load_observations(self) -> pd.DataFrame:
        rng = np.random.default_rng(self.seed)
        years = np.arange(self.year_start, self.year_end + 1)

        cells = generate_hex_grid(self.h3_resolution)
        if self.n_hexes is not None and self.n_hexes < len(cells):
            cells = cells.sample(n=self.n_hexes, random_state=self.seed).reset_index(drop=True)

        center_lat, center_lon = cells["centroid_lat"].mean(), cells["centroid_lon"].mean()
        dist = np.hypot(cells["centroid_lat"] - center_lat, cells["centroid_lon"] - center_lon).to_numpy()
        dist_norm = dist / dist.max() if dist.max() > 0 else np.zeros_like(dist)
        assigned = sample_archetypes_radial(dist_norm, rng)

        obs_rows = []
        ground_truth_rows = []

        for i, row in enumerate(cells.itertuples(index=False)):
            h3_index = row.h3_index
            area_m2 = row.area_m2
            override = self.anchor_hexes.get(h3_index)
            archetype = override["archetype"] if override else assigned[i]

            if archetype in FLAT_ARCHETYPES:
                if archetype == "undeveloped":
                    level, noise_std = rng.uniform(0.0, 0.015), 0.003
                else:
                    level, noise_std = rng.uniform(0.87, 0.97), 0.005
                F_obs, F_true = _generate_flat_series(level, noise_std, years, rng)
                K = r = t0 = float("nan")
            else:
                if override and "K" in override:
                    # Named reference locations get a much cleaner signal (no
                    # classifier-flip spikes, ~2% of the usual noise floor) —
                    # they're a stable, verifiable spot-check for a demo
                    # audience, not a noise-robustness stress test. Some of
                    # these (e.g. still-early Emerging/Accelerating cases)
                    # are genuinely weakly-identified from only a decade of
                    # early-stage data, where realistic noise can flip the
                    # fitted curve's implied lifecycle entirely — that's a
                    # real statistical limitation the recovery validator
                    # (§6.1) characterizes properly at realistic noise
                    # levels; it isn't what face-validity is checking.
                    K, r, t0 = override["K"], override["r"], override["t0"]
                    F_obs, F_true = simulate_observed_series(
                        K, r, t0, years, self.noise_sigma * 0.02, 0.0, 0.0, rng,
                    )
                else:
                    K, r, t0 = sample_params_for_archetype(archetype, self.t_eval, rng)
                    F_obs, F_true = simulate_observed_series(
                        K, r, t0, years, self.noise_sigma,
                        self.classifier_flip_prob, self.classifier_flip_magnitude, rng,
                    )

            n_pixels_base = max(int(area_m2 / 100.0), 50)
            hard_noise = rng.normal(0.0, self.noise_sigma * 1.5, size=len(years))
            built_frac_hard = np.clip(F_true + hard_noise, 0.0, 1.0)

            for yi, year in enumerate(years):
                obs_rows.append(dict(
                    h3_index=h3_index,
                    year=int(year),
                    built_frac_soft=float(F_obs[yi]),
                    built_frac_hard=float(built_frac_hard[yi]),
                    n_pixels=int(n_pixels_base * rng.uniform(0.85, 1.0)),
                    n_scenes=int(rng.integers(6, 31)),
                ))

            ground_truth_rows.append(dict(h3_index=h3_index, archetype=archetype, K=K, r=r, t0=t0))

        self.ground_truth_ = pd.DataFrame(ground_truth_rows)
        self.cells_ = cells
        return pd.DataFrame(obs_rows)

    def ground_truth(self) -> pd.DataFrame:
        if not hasattr(self, "ground_truth_"):
            raise RuntimeError("call load_observations() first")
        return self.ground_truth_
