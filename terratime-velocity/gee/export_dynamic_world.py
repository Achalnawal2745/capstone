"""§8 — Dynamic World export for NCT Delhi, raster-export + local zonal-stats.

This is a *standalone* script, run manually and occasionally (once your GEE
auth works), not part of the `terratime` package and not imported by it.
Its only job is to eventually produce a local observations.parquet matching
the schema in sources/base.py — after that, EarthEngineSource just reads a
file. The engine never calls the Earth Engine API itself, which is the
whole point of the DataSource split in §1.

Two-phase design (do NOT use reduceRegions over 15,000 features in one call
-- it will time out or hit memory limits):

  Phase 1 (this script, `export` command): for each year 2016-2025, build an
    annual Dynamic World composite over the NCT Delhi bbox and export two
    10 m GeoTIFF bands (mean `built` probability, hard argmax==built
    fraction) plus a scene-count band, to Google Drive.

  Phase 2 (this script, `zonal-stats` command): after downloading the
    GeoTIFFs locally, compute per-hexagon zonal statistics *vectorized*
    (build an H3-index-per-pixel array once, then groupby) and write
    data/interim/observations.parquet.

Usage:
    python gee/export_dynamic_world.py export        # requires `earthengine authenticate`
    python gee/export_dynamic_world.py zonal-stats --raster-dir data/raw
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import typer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from terratime.grid import get_nct_delhi_boundary  # noqa: E402

app = typer.Typer(add_completion=False)

YEAR_START, YEAR_END = 2016, 2025
DW_BUILT_BAND_INDEX = 6  # Dynamic World label classes: 0 water ... 6 built ...
CLOUDY_PIXEL_PERCENTAGE_MAX = 35


@app.command()
def export(
    year_start: int = YEAR_START,
    year_end: int = YEAR_END,
    drive_folder: str = "terratime_dynamic_world",
):
    """Builds annual Dynamic World composites and exports them to Drive.

    Requires `pip install earthengine-api` and a working `earthengine
    authenticate`. If this stalls for more than ~45 minutes, per the build
    spec: abandon this branch and keep going on synthetic data — nothing
    else in the pipeline depends on it.
    """
    import ee

    ee.Initialize()

    boundary_latlng = get_nct_delhi_boundary()
    region = ee.Geometry.Polygon([[[lng, lat] for lat, lng in boundary_latlng]])

    dw = ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")

    for year in range(year_start, year_end + 1):
        start = ee.Date.fromYMD(year, 1, 1)
        end = ee.Date.fromYMD(year, 12, 31)

        year_collection = (
            dw.filterDate(start, end)
            .filterBounds(region)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", CLOUDY_PIXEL_PERCENTAGE_MAX))
        )

        built_prob = year_collection.select("built").mean().rename("built_prob")
        is_built_argmax = year_collection.map(
            lambda img: img.select("label").eq(DW_BUILT_BAND_INDEX).rename("is_built")
        )
        built_hard = is_built_argmax.mean().rename("built_hard")
        scene_count = year_collection.select("built").count().rename("scene_count")

        composite = ee.Image.cat([built_prob, built_hard, scene_count]).clip(region)

        task = ee.batch.Export.image.toDrive(
            image=composite,
            description=f"terratime_dw_{year}",
            folder=drive_folder,
            fileNamePrefix=f"dynamic_world_{year}",
            region=region,
            scale=10,
            maxPixels=1e13,
        )
        task.start()
        typer.echo(f"Started export task for {year}: {task.id}")

    typer.echo(
        "\nAll export tasks submitted. Monitor progress at "
        "https://code.earthengine.google.com/tasks , then download the "
        f"GeoTIFFs from the Drive folder '{drive_folder}' into data/raw/ "
        "before running `zonal-stats`."
    )


@app.command("zonal-stats")
def zonal_stats(
    raster_dir: Path = PROJECT_ROOT / "data" / "raw",
    out_path: Path = PROJECT_ROOT / "data" / "interim" / "observations.parquet",
    h3_resolution: int = 9,
):
    """Vectorized per-hexagon zonal statistics over the downloaded GeoTIFFs.

    Builds one H3-index-per-pixel array per raster (via each pixel's
    lat/lon centroid -> h3.latlng_to_cell), then groups by H3 index — this
    is what keeps a 15,000-hex x 10-year job from being a slow Python loop.
    """
    import h3
    import rasterio

    rows = []
    for year in range(YEAR_START, YEAR_END + 1):
        path = raster_dir / f"dynamic_world_{year}.tif"
        if not path.exists():
            typer.echo(f"skipping {year}: {path} not found", err=True)
            continue

        with rasterio.open(path) as src:
            built_prob = src.read(1).astype("float64")
            built_hard = src.read(2).astype("float64")
            scene_count = src.read(3).astype("float64")
            transform = src.transform
            height, width = built_prob.shape

            rows_idx, cols_idx = np.meshgrid(np.arange(height), np.arange(width), indexing="ij")
            xs, ys = rasterio.transform.xy(transform, rows_idx.ravel(), cols_idx.ravel())
            lngs = np.asarray(xs)
            lats = np.asarray(ys)

            valid = np.isfinite(built_prob.ravel()) & (scene_count.ravel() > 0)

            h3_indices = np.array([
                h3.latlng_to_cell(lat, lng, h3_resolution)
                for lat, lng, ok in zip(lats, lngs, valid) if ok
            ])

            df = pd.DataFrame({
                "h3_index": h3_indices,
                "built_frac_soft": built_prob.ravel()[valid],
                "built_frac_hard": built_hard.ravel()[valid],
                "n_scenes": scene_count.ravel()[valid],
            })

            agg = df.groupby("h3_index").agg(
                built_frac_soft=("built_frac_soft", "mean"),
                built_frac_hard=("built_frac_hard", "mean"),
                n_pixels=("built_frac_soft", "size"),
                n_scenes=("n_scenes", "mean"),
            ).reset_index()
            agg["year"] = year
            rows.append(agg)

        typer.echo(f"{year}: {len(agg)} hexagons")

    if not rows:
        typer.echo("No rasters found — nothing to write.", err=True)
        raise typer.Exit(1)

    observations = pd.concat(rows, ignore_index=True)
    observations = observations[["h3_index", "year", "built_frac_soft", "built_frac_hard", "n_pixels", "n_scenes"]]
    observations["year"] = observations["year"].astype(int)
    observations["n_pixels"] = observations["n_pixels"].astype(int)
    observations["n_scenes"] = observations["n_scenes"].round().astype(int)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    observations.to_parquet(out_path, index=False)
    typer.echo(f"Wrote {len(observations)} rows -> {out_path}")


if __name__ == "__main__":
    app()
