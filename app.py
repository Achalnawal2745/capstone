from fastapi import FastAPI, Query, HTTPException, Path
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import io
import warnings
import base64

warnings.filterwarnings("ignore", category=RuntimeWarning)   # suppress rio_tiler cast warnings

try:
    from rio_tiler.io import Reader
except ImportError:
    raise RuntimeError("Install rio-tiler: pip install rio-tiler")

# 1x1 transparent PNG — returned for tiles outside GeoTIFF bounds
TRANSPARENT_TILE = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)

app = FastAPI(title="TerraTime API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GEOTIFF_DIR = r"e:\capstone\data\geotiffs"

# ── Serve frontend ─────────────────────────────────────────────────────────────
@app.get("/")
async def read_index():
    return FileResponse('index.html')


# ── Helper: check if a local GeoTIFF exists ────────────────────────────────────
def geotiff_path(city: str, dataset: str, year: int) -> str:
    """Returns path to a complete local GeoTIFF, or None if not found/still downloading."""
    filename = f"{city}_{dataset}_{year}.tif"
    path = os.path.join(GEOTIFF_DIR, filename)
    # Ignore partially downloaded files
    crdownload = path.replace('.tif', '.crdownload')
    if os.path.exists(crdownload):
        return None
    return path if os.path.exists(path) else None


# ── Local tile endpoint (reads pre-stored GeoTIFFs) ────────────────────────────
@app.get("/api/tiles/{city}/{dataset}/{year}/{z}/{x}/{y}.png")
def serve_local_tile(
    city:    str  = Path(..., description="e.g. delhi, mumbai"),
    dataset: str  = Path(..., description="s2 or dw"),
    year:    int  = Path(...),
    z:       int  = Path(...),
    x:       int  = Path(...),
    y:       int  = Path(...),
):
    """
    Serves XYZ map tiles from pre-stored local GeoTIFF files.
    dataset: 's2' = Sentinel-2 RGB  |  'dw' = Dynamic World classified
    """
    # Validate dataset name
    if dataset not in ('s2', 'dw'):
        raise HTTPException(400, "dataset must be 's2' or 'dw'")

    path = geotiff_path(city, dataset, year)

    if path is None:
        # File not downloaded yet — return a transparent tile
        raise HTTPException(404, f"GeoTIFF not found: {city}_{dataset}_{year}.tif — run gee_export.py first")

    try:
        with Reader(path) as cog:
            if dataset == 's2':
                img = cog.tile(x, y, z, indexes=[1, 2, 3])
                # Fixed global stretch — same for every tile = no seams, consistent color
                # GEE Natural Color uses ~0–3000 for Sentinel-2 SR (0–10000 scale)
                img.rescale(in_range=((0, 3000),))
                png_bytes = img.render(img_format="PNG")
            else:
                # Dynamic World: coloured classification tile
                img = cog.tile(x, y, z, indexes=[1])
                data = img.data[0]

                # Colour map: DW class → RGBA
                # 0=water(blue) 1=trees(green) 2=grass(lime) 3=flooded(teal)
                # 4=crops(yellow) 5=shrub(olive) 6=built-up(red) 7=bare(tan) 8=snow(white)
                DW_COLORS = {
                    0: (65,  105, 225, 200),   # Water        - royal blue
                    1: (34,  139, 34,  200),   # Trees        - forest green
                    2: (144, 238, 144, 200),   # Grass        - light green
                    3: (0,   128, 128, 200),   # Flooded veg  - teal
                    4: (255, 215, 0,   200),   # Crops        - gold
                    5: (107, 142, 35,  200),   # Shrub        - olive
                    6: (220, 50,  50,  220),   # Built-up     - red
                    7: (210, 180, 140, 200),   # Bare ground  - tan
                    8: (255, 255, 255, 200),   # Snow         - white
                }
                import numpy as np
                from PIL import Image as PILImage

                h, w = data.shape
                rgba = np.zeros((h, w, 4), dtype=np.uint8)
                for cls, color in DW_COLORS.items():
                    mask = data == cls
                    rgba[mask] = color
                # Transparent where no data
                rgba[data == 255] = (0, 0, 0, 0)


                pil_img = PILImage.fromarray(rgba, 'RGBA')
                buf = io.BytesIO()
                pil_img.save(buf, format='PNG')
                png_bytes = buf.getvalue()

        return Response(content=png_bytes, media_type="image/png", headers={
            "Cache-Control": "public, max-age=86400",
            "Access-Control-Allow-Origin": "*"
        })

    except HTTPException:
        raise
    except Exception as e:
        err = str(e)
        # Tile is outside the GeoTIFF bounds — return transparent (not an error)
        if "outside bounds" in err or "TileOutsideBounds" in err:
            return Response(content=TRANSPARENT_TILE, media_type="image/png", headers={
                "Cache-Control": "public, max-age=86400"
            })
        print(f"[Tile Error] {dataset}/{year}/{z}/{x}/{y}: {e}")
        raise HTTPException(500, err)


# ── Status endpoint: which files are available ────────────────────────────────
@app.get("/api/available")
async def get_available():
    """Returns which city/dataset/year combinations have local GeoTIFFs ready."""
    available = {}
    if not os.path.exists(GEOTIFF_DIR):
        return available
        
    for filename in os.listdir(GEOTIFF_DIR):
        if not filename.endswith('.tif') or filename.endswith('.crdownload'):
            continue
        # Expected format: city_dataset_year.tif (e.g. delhi_s2_2022.tif)
        parts = filename.replace('.tif', '').split('_')
        if len(parts) == 3:
            city, dataset, year = parts[0], parts[1], int(parts[2])
            if city not in available:
                available[city] = {"s2": [], "dw": []}
            if dataset in ('s2', 'dw') and year not in available[city][dataset]:
                available[city][dataset].append(year)
                
    for city in available:
        available[city]['s2'].sort()
        available[city]['dw'].sort()
        
    return available


# ── Legacy live-GEE endpoint (kept as fallback) ───────────────────────────────
tile_cache = {}

@app.get("/api/tile-url")
async def get_tile_url(
    west: float = Query(...), south: float = Query(...),
    east: float = Query(...), north: float = Query(...),
    year: int   = Query(2023)
):
    r_west, r_south = round(west, 1), round(south, 1)
    r_east, r_north = round(east, 1), round(north, 1)
    cache_key = f"{r_west}_{r_south}_{r_east}_{r_north}_{year}"

    if cache_key in tile_cache:
        return {"url": tile_cache[cache_key], "source": "cache"}

    try:
        from gee_engine import get_engine   # lazy import — only used as fallback
        engine = get_engine()
        url = engine.get_sentinel2_tile(west, south, east, north, year)
        tile_cache[cache_key] = url
        return {"url": url, "source": "live_gee"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    print("\n  TerraTime API starting...")
    print(f"  GeoTIFF directory: {GEOTIFF_DIR}")

    # Audit files — separate complete from in-progress
    complete, downloading = [], []
    if os.path.exists(GEOTIFF_DIR):
        for f in sorted(os.listdir(GEOTIFF_DIR)):
            if f.endswith('.tif'):
                complete.append(f)
            elif f.endswith('.crdownload'):
                downloading.append(f)

    if complete:
        print(f"  [OK] {len(complete)} complete GeoTIFFs:")
        for f in complete:
            print(f"    + {f}")
    else:
        print("  [WARN] No complete GeoTIFFs found.")

    if downloading:
        print(f"  [..] {len(downloading)} still downloading (will be available after completion):")
        for f in downloading:
            print(f"    ~ {f}")

    print("\n  Open: http://localhost:5000\n")
    uvicorn.run(app, host="0.0.0.0", port=5000)
