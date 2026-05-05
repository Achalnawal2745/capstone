"""
TerraTime — GEE Export Script
==============================
Run this ONCE to export annual composites for Delhi to Google Drive.

After running:
  1. Go to Google Drive → folder 'TerraTime_Data'
  2. Download all .tif files
  3. Place them in e:/capstone/data/geotiffs/

You can monitor export progress at:
  https://code.earthengine.google.com/  → Tasks tab (top right)
"""

import ee
import sys
import time

# ── Config ────────────────────────────────────────────────────────────────────
GCP_PROJECT   = 'chatty-qp3qx'          # Your GEE project
DRIVE_FOLDER  = 'TerraTime_Data'         # Google Drive folder name
YEARS         = list(range(2016, 2025))  # 2016 to 2024 inclusive
SCALE         = 10                       # 10 metres/pixel (Sentinel-2 native)
SCALE_DW      = 10                       # 10 metres/pixel (Dynamic World native)

CITY = 'mumbai'

# ── Initialise Earth Engine ───────────────────────────────────────────────────
print("Initialising Google Earth Engine...")
try:
    ee.Initialize(project=GCP_PROJECT)
    print(f"  [OK] Connected to project: {GCP_PROJECT}\n")
except Exception as e:
    print(f"  [FAIL] {e}")
    print("  Run: earthengine authenticate   then retry.")
    sys.exit(1)

# City bounding box — defined AFTER ee.Initialize()
# Mumbai: approx [72.77, 18.88, 73.0, 19.3]
BBOX = ee.Geometry.Rectangle([72.77, 18.88, 73.0, 19.3])


# ── Helper: Cloud mask for Sentinel-2 SR ─────────────────────────────────────
def mask_s2_clouds(image):
    """Use the Scene Classification Layer (SCL) to mask clouds and shadows."""
    scl = image.select('SCL')
    # SCL classes to remove: 3=shadows, 8=med cloud, 9=high cloud, 10=cirrus
    mask = (scl.neq(3)
              .And(scl.neq(8))
              .And(scl.neq(9))
              .And(scl.neq(10)))
    return image.updateMask(mask)


# ── Helper: Build annual Sentinel-2 composite ─────────────────────────────────
def get_s2_composite(year, region):
    """
    Returns a cloud-free median composite of Sentinel-2 SR for one year.
    Uses only images with < 20% cloud cover then takes the median.
    """
    collection = (
        ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
        .filterDate(f'{year}-01-01', f'{year}-12-31')
        .filterBounds(region)
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
        .map(mask_s2_clouds)
    )
    count = collection.size().getInfo()
    print(f"    S2 {year}: {count} scenes found")

    composite = collection.median().select(['B4', 'B3', 'B2'])  # RGB bands only
    return composite.clip(region)


# ── Helper: Build annual Dynamic World composite ──────────────────────────────
def get_dw_composite(year, region):
    """
    Returns the mode (most common class) Dynamic World composite for one year.
    Pixel values: 0=water 1=trees 2=grass 3=flooded 4=crops
                  5=shrub  6=built-up  7=bare  8=snow
    """
    collection = (
        ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1')
        .filterDate(f'{year}-01-01', f'{year}-12-31')
        .filterBounds(region)
        .select('label')   # 'label' = the classified land cover class
    )
    count = collection.size().getInfo()
    print(f"    DW {year}: {count} scenes found")

    composite = collection.mode()  # Most frequent class across the year
    return composite.clip(region)


# ── Export function ───────────────────────────────────────────────────────────
def export_image(image, description, filename, region, scale):
    """
    Submits a GEE export task to Google Drive.
    Returns the task object (already started).
    """
    task = ee.batch.Export.image.toDrive(
        image       = image,
        description = description,
        folder      = DRIVE_FOLDER,
        fileNamePrefix = filename,
        region      = region,
        scale       = scale,
        crs         = 'EPSG:4326',          # Standard lat/lon projection
        fileFormat  = 'GeoTIFF',
        maxPixels   = 1e13,
        formatOptions = {'cloudOptimized': True}  # COG = fast tile serving
    )
    task.start()
    return task


# ── Main Export Loop ──────────────────────────────────────────────────────────
def main():
    tasks = []

    print(f"Starting exports for: {CITY.upper()} ({len(YEARS)} years × 2 datasets)\n")
    print("=" * 60)

    for year in YEARS:
        print(f"\n[Year {year}]")

        # ── Sentinel-2 Export ──────────────────────────────────────────────
        print(f"  Generating Sentinel-2 composite...")
        try:
            s2 = get_s2_composite(year, BBOX)
            s2_desc = f"TerraTime_{CITY}_s2_{year}"
            s2_file = f"{CITY}_s2_{year}"
            task = export_image(s2, s2_desc, s2_file, BBOX, SCALE)
            tasks.append((s2_desc, task))
            print(f"  [QUEUED] {s2_file}.tif -> Google Drive/{DRIVE_FOLDER}/")
        except Exception as e:
            print(f"  [ERROR] S2 {year}: {e}")

        # ── Dynamic World Export ───────────────────────────────────────────
        print(f"  Generating Dynamic World composite...")
        try:
            dw = get_dw_composite(year, BBOX)
            dw_desc = f"TerraTime_{CITY}_dw_{year}"
            dw_file = f"{CITY}_dw_{year}"
            task = export_image(dw, dw_desc, dw_file, BBOX, SCALE_DW)
            tasks.append((dw_desc, task))
            print(f"  [QUEUED] {dw_file}.tif -> Google Drive/{DRIVE_FOLDER}/")
        except Exception as e:
            print(f"  [ERROR] DW {year}: {e}")

        # Brief pause to avoid hitting GEE API rate limits
        time.sleep(1)

    # -- Summary --
    print("\n" + "=" * 60)
    print(f"\n[DONE] {len(tasks)} export tasks submitted to Google Earth Engine.")
    print("\nMonitor progress at:")
    print("  https://code.earthengine.google.com/  (Tasks tab, top-right)")
    print(f"\nFiles will appear in: Google Drive / {DRIVE_FOLDER}/")
    print("\nExpected files (18 total):")
    for year in YEARS:
        print(f"  {CITY}_s2_{year}.tif   (Sentinel-2 RGB)")
        print(f"  {CITY}_dw_{year}.tif   (Dynamic World classes)")
    print("\nAfter download, place all .tif files in:")
    print("  e:/capstone/data/geotiffs/")


if __name__ == "__main__":
    main()
