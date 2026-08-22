"""End-to-end pipeline test on a small synthetic grid (fast) — the same
code path `terratime run` exercises against the full ~17k-hex NCT Delhi grid."""

from terratime.config import load_config, DEFAULT_CONFIG_PATH
from terratime.pipeline import HEX_METRICS_COLUMNS, run_pipeline
from terratime.sources.synthetic import SyntheticSource


def test_run_pipeline_end_to_end_small_grid():
    cfg = load_config(DEFAULT_CONFIG_PATH)
    source = SyntheticSource(
        year_start=cfg.time.year_start, year_end=cfg.time.year_end, t_eval=cfg.time.t_eval,
        n_hexes=120, seed=3,
    )

    hex_metrics = run_pipeline(source, cfg, verbose=False)

    assert list(hex_metrics.columns) == HEX_METRICS_COLUMNS
    assert len(hex_metrics) == 120
    assert set(hex_metrics["tier"]).issubset({"tier1", "tier2", "tier3", "saturated_static", "undeveloped"})

    tier1 = hex_metrics[hex_metrics["tier"] == "tier1"]
    assert len(tier1) > 0, "expected at least some Tier-1 hexes in a 120-hex synthetic sample"
    assert tier1["K"].notna().all()
    assert tier1["r"].notna().all()
    assert tier1["t0"].notna().all()

    non_tier1 = hex_metrics[hex_metrics["tier"] != "tier1"]
    assert non_tier1["K"].isna().all(), "K/r/t0 must be null outside Tier 1 (§3.2)"
    assert non_tier1["r"].isna().all()
    assert non_tier1["t0"].isna().all()

    assert hex_metrics["confidence"].between(0, 1).all()
    assert hex_metrics["velocity_pctile"].dropna().between(0, 1).all()
