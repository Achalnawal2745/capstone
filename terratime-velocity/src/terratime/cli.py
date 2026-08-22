"""TerraTime Pillar 1 CLI.

    python -m terratime.cli run --source synthetic
    python -m terratime.cli validate
    python -m terratime.cli export-figures
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd
import typer

from terratime.config import Config, DEFAULT_CONFIG_PATH, load_config
from terratime.pipeline import run_pipeline
from terratime.sources import build_source
from terratime.export.geojson import write_hexes_geojson, write_hexes_geojson_js
from terratime.export.report import generate_validation_report
from terratime.validate.facevalidity import get_anchor_overrides

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="TerraTime Pillar 1 — Growth Velocity & Acceleration Engine",
)


def _load_cfg(config: Path) -> Config:
    return load_config(config)


@app.command()
def run(
    source: str = typer.Option(None, help="synthetic | earthengine (overrides config.yaml source.kind)"),
    isotonic: bool = typer.Option(True, help="Apply isotonic (monotonic) correction before fitting."),
    config: Path = typer.Option(DEFAULT_CONFIG_PATH, help="Path to config.yaml"),
):
    """Loads observations (synthetic or real), fits every hexagon, writes
    hex_metrics.parquet and hexes.geojson. Prints tier population counts."""
    cfg = _load_cfg(config)
    if source:
        cfg.source.kind = source

    anchor_hexes = get_anchor_overrides(cfg.time.t_eval, cfg.grid.h3_resolution) if cfg.source.kind == "synthetic" else None
    data_source = build_source(cfg, anchor_hexes=anchor_hexes)

    typer.echo(f"Loading observations from source: {cfg.source.kind} ({data_source.provenance})")
    observations = data_source.load_observations()

    cfg.data.interim_dir.mkdir(parents=True, exist_ok=True)
    observations.to_parquet(cfg.data.observations_file, index=False)
    typer.echo(f"Wrote {len(observations)} observation rows -> {cfg.data.observations_file}")

    typer.echo(f"Fitting {observations['h3_index'].nunique()} hexagons (isotonic={isotonic})...")
    hex_metrics = run_pipeline(data_source, cfg, isotonic=isotonic, verbose=True)

    cfg.data.processed_dir.mkdir(parents=True, exist_ok=True)
    hex_metrics.to_parquet(cfg.data.hex_metrics_file, index=False)
    typer.echo(f"Wrote hex_metrics -> {cfg.data.hex_metrics_file}")

    write_hexes_geojson(hex_metrics, cfg.data.hexes_geojson_file)
    typer.echo(f"Wrote hexes.geojson -> {cfg.data.hexes_geojson_file}")

    viewer_data_file = cfg.root / "viewer" / "data" / "hexes.js"
    write_hexes_geojson_js(hex_metrics, viewer_data_file, data_source.provenance, observations=observations)
    typer.echo(f"Wrote viewer data -> {viewer_data_file}")

    _write_provenance(cfg, data_source.provenance)
    typer.echo(f"\nData provenance: {data_source.provenance}")


def _write_provenance(cfg: Config, provenance: str) -> None:
    (cfg.data.processed_dir / "provenance.json").write_text(
        json.dumps({"provenance": provenance}), encoding="utf-8"
    )


@app.command()
def validate(
    config: Path = typer.Option(DEFAULT_CONFIG_PATH, help="Path to config.yaml"),
    out_dir: Path = typer.Option(None, help="Directory for VALIDATION.md + figures (default: <root>/reports)"),
):
    """Runs the full validation suite (recovery, LOYO, face-validity) and
    writes reports/VALIDATION.md. Requires `run` to have been executed first."""
    cfg = _load_cfg(config)
    out_dir = out_dir or (cfg.root / "reports")

    if not cfg.data.hex_metrics_file.exists() or not cfg.data.observations_file.exists():
        typer.echo("hex_metrics.parquet / observations.parquet not found — run `terratime run` first.", err=True)
        raise typer.Exit(1)

    hex_metrics = pd.read_parquet(cfg.data.hex_metrics_file)
    observations = pd.read_parquet(cfg.data.observations_file)

    provenance_file = cfg.data.processed_dir / "provenance.json"
    provenance = "SIMULATED DATA"
    if provenance_file.exists():
        provenance = json.loads(provenance_file.read_text(encoding="utf-8")).get("provenance", provenance)

    typer.echo("Running validation suite...")
    out_path = generate_validation_report(cfg, hex_metrics, observations, provenance, out_dir)
    typer.echo(f"Wrote validation report -> {out_path}")


@app.command("export-figures")
def export_figures(
    config: Path = typer.Option(DEFAULT_CONFIG_PATH, help="Path to config.yaml"),
    out_dir: Path = typer.Option(None, help="Directory for deck figures (default: <root>/reports/figures)"),
):
    """Extra polished figures for a slide deck: top-10 accelerating cells and
    a static city-wide velocity map."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cfg = _load_cfg(config)
    out_dir = out_dir or (cfg.root / "reports" / "figures")
    out_dir.mkdir(parents=True, exist_ok=True)

    if not cfg.data.hex_metrics_file.exists():
        typer.echo("hex_metrics.parquet not found — run `terratime run` first.", err=True)
        raise typer.Exit(1)

    hex_metrics = pd.read_parquet(cfg.data.hex_metrics_file)

    top10 = hex_metrics[hex_metrics["tier"] == "tier1"].nlargest(10, "acceleration_2026")
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.barh(top10["h3_index"].str[-6:][::-1], top10["acceleration_2026"][::-1], color="#e67e22")
    ax.set_xlabel("Acceleration (d2F/dt2, frac/yr2)")
    ax.set_title("Top 10 fastest-accelerating cells")
    fig.tight_layout()
    fig.savefig(out_dir / "top10_accelerating.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 7))
    plottable = hex_metrics.dropna(subset=["velocity_2026"])
    sc = ax.scatter(
        plottable["centroid_lon"], plottable["centroid_lat"],
        c=plottable["velocity_2026"], cmap="magma", s=4, marker="h",
    )
    fig.colorbar(sc, ax=ax, label="velocity_2026 (frac/yr)")
    ax.set_title("NCT Delhi — built-up growth velocity")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(out_dir / "velocity_map.png", dpi=150)
    plt.close(fig)

    typer.echo(f"Wrote deck figures -> {out_dir}")


if __name__ == "__main__":
    app()
