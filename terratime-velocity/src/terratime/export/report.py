"""Writes reports/VALIDATION.md — the combined output of all three
validators (§6) plus the tier population summary and supporting figures.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from terratime.config import Config
from terratime.fit.models import logistic, logistic_velocity
from terratime.validate.facevalidity import run_facevalidity
from terratime.validate.loyo import loyo_markdown, run_loyo_validation
from terratime.validate.recovery import recovery_markdown, run_recovery_validation


def _plot_recovery_t0_errors(results: dict, out_path: Path) -> None:
    conditions = list(results.keys())
    fig, axes = plt.subplots(1, len(conditions), figsize=(4 * len(conditions), 3.5), sharey=True)
    if len(conditions) == 1:
        axes = [axes]
    for ax, label in zip(axes, conditions):
        errs = results[label]["t0_errors"]
        if len(errs) > 0:
            ax.hist(errs, bins=25, color="#3b7dd8", edgecolor="white")
        ax.set_title(label)
        ax.set_xlabel("|t0 error| (years)")
    axes[0].set_ylabel("Tier-1 hexagons")
    fig.suptitle("Parameter recovery: t0 error distribution by noise condition")
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def _plot_loyo_mae_hist(results: dict, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(5, 3.5))
    if len(results["per_hex_mae"]) > 0:
        ax.hist(results["per_hex_mae"], bins=30, color="#2f9e6f", edgecolor="white")
    ax.set_xlabel("Per-hexagon MAE (built-up fraction)")
    ax.set_ylabel("Hexagons")
    ax.set_title("Leave-one-year-out: per-hexagon MAE")
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def _plot_tier_population(hex_metrics: pd.DataFrame, out_path: Path) -> None:
    order = ["tier1", "tier2", "tier3", "saturated_static", "undeveloped"]
    counts = hex_metrics["tier"].value_counts().reindex(order, fill_value=0)
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.bar(order, counts.values, color="#c0392b")
    ax.set_ylabel("Hexagon count")
    ax.set_title("Tier population")
    for i, v in enumerate(counts.values):
        ax.text(i, v, str(int(v)), ha="center", va="bottom")
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def _plot_example_fit(observations: pd.DataFrame, hex_metrics: pd.DataFrame, out_path: Path) -> None:
    tier1 = hex_metrics[hex_metrics["tier"] == "tier1"]
    if tier1.empty:
        return
    row = tier1.sample(n=1, random_state=0).iloc[0]
    h3_index = row["h3_index"]
    g = observations[observations["h3_index"] == h3_index].sort_values("year")

    years_fine = np.linspace(g["year"].min() - 1, g["year"].max() + 3, 200)
    F_fit = logistic(years_fine, row["K"], row["r"], row["t0"])
    v_fit = logistic_velocity(years_fine, row["K"], row["r"], row["t0"])

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(6, 6), sharex=True)
    ax1.scatter(g["year"], g["built_frac_soft"], color="#333", label="observed", zorder=3)
    ax1.plot(years_fine, F_fit, color="#3b7dd8", label="fitted S-curve")
    ax1.axvline(row["t0"], color="#999", linestyle="--", linewidth=1, label="t0")
    ax1.set_ylabel("Built-up fraction")
    ax1.set_title(f"Example Tier-1 fit — {h3_index}\nK={row['K']:.2f} r={row['r']:.2f} t0={row['t0']:.1f} R2={row['r_squared']:.3f}")
    ax1.legend(fontsize=8)

    ax2.plot(years_fine, v_fit, color="#c0392b")
    ax2.axhline(0, color="#ccc", linewidth=1)
    ax2.set_ylabel("dF/dt (velocity)")
    ax2.set_xlabel("Year")

    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def generate_validation_report(
    cfg: Config,
    hex_metrics: pd.DataFrame,
    observations: pd.DataFrame,
    provenance: str,
    out_dir: Path,
) -> Path:
    out_dir = Path(out_dir)
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    print("  running parameter recovery validation...")
    recovery_results = run_recovery_validation(cfg)
    print("  running leave-one-year-out validation...")
    loyo_results = run_loyo_validation(observations, hex_metrics, cfg)
    print("  running face validity checks...")
    face_results, face_md = run_facevalidity(hex_metrics, cfg.grid.h3_resolution)

    _plot_recovery_t0_errors(recovery_results, fig_dir / "recovery_t0_errors.png")
    _plot_loyo_mae_hist(loyo_results, fig_dir / "loyo_mae_hist.png")
    _plot_tier_population(hex_metrics, fig_dir / "tier_population.png")
    _plot_example_fit(observations, hex_metrics, fig_dir / "example_fit.png")

    tier_counts = hex_metrics["tier"].value_counts()
    total = len(hex_metrics)

    lines = [
        "# TerraTime Pillar 1 — Validation Report",
        "",
        f"**Data provenance: {provenance}**",
        "",
        "## Tier population",
        "",
        "| Tier | Count | % |",
        "|---|---|---|",
    ]
    for tier in ["tier1", "tier2", "tier3", "saturated_static", "undeveloped"]:
        n = int(tier_counts.get(tier, 0))
        pct = 100.0 * n / total if total else 0.0
        lines.append(f"| {tier} | {n} | {pct:.1f}% |")
    lines += [
        f"| **TOTAL** | **{total}** | 100.0% |",
        "",
        "![Tier population](figures/tier_population.png)",
        "",
        recovery_markdown(recovery_results),
        "",
        "![t0 recovery error](figures/recovery_t0_errors.png)",
        "",
        loyo_markdown(loyo_results),
        "",
        "![LOYO MAE histogram](figures/loyo_mae_hist.png)",
        "",
        face_md,
        "",
        "## Example Tier-1 fit",
        "",
        "![Example fit](figures/example_fit.png)",
        "",
    ]

    out_path = out_dir / "VALIDATION.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
