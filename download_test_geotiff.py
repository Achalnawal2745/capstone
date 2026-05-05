"""
TerraTime — Quick Test GeoTIFF Downloader
==========================================
Downloads small test patches of Delhi directly from GEE
(not an export task — instant download to disk).

Used for testing the rio-tiler tile-serving pipeline
before the full-resolution exports finish.

Run: python download_test_geotiff.py
"""

import ee
import requests
import os
import sys

GCP_PROJECT = 'chatty-qp3qx'
OUTPUT_DIR  = r'e:\capstone\data\geotiffs'

# Small Delhi region for quick download (central area)
# [west, south, east, north]
DELHI_TEST = [76.9, 28.4, 77.5, 28.85]

YEARS = [2016, 2018, 2020, 2022, 2024]   # Test with 5 years first

print("Initialising GEE...")
ee.Initialize(project=GCP_PROJECT)
print("  [OK]\n")

os.makedirs(OUTPUT_DIR, exist_ok=True)

region = ee.Geometry.Rectangle(DELHI_TEST)


def download_geotiff(url, filepath):
    """Downloads a GeoTIFF from a GEE download URL."""
    print(f"  Downloading -> {os.path.basename(filepath)}")
    response = requests.get(url, stream=True, timeout=300)
    response.raise_for_status()
    with open(filepath, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    print(f"  [OK] {size_mb:.1f} MB saved")


def get_s2_download_url(year):
    """Generates a direct download URL for a Sentinel-2 composite."""
    collection = (
        ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
        .filterDate(f'{year}-01-01', f'{year}-12-31')
        .filterBounds(region)
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
    )
    # Take the clearest image (sorted ascending = least cloudy first)
    composite = collection.sort('CLOUDY_PIXEL_PERCENTAGE').mosaic()
    image = composite.select(['B4', 'B3', 'B2']).clip(region)

    url = image.getDownloadURL({
        'scale': 100,           # 100m resolution for quick download
        'crs': 'EPSG:4326',
        'region': region,
        'format': 'GeoTIFF',
        'filePerBand': False,   # All bands in one file
    })
    return url


def get_dw_download_url(year):
    """Generates a direct download URL for a Dynamic World composite."""
    collection = (
        ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1')
        .filterDate(f'{year}-01-01', f'{year}-12-31')
        .filterBounds(region)
        .select('label')
    )
    composite = collection.mode().clip(region)

    url = composite.getDownloadURL({
        'scale': 100,
        'crs': 'EPSG:4326',
        'region': region,
        'format': 'GeoTIFF',
    })
    return url


print(f"Downloading test GeoTIFFs for {len(YEARS)} years...\n")
print("NOTE: These are 100m resolution patches for testing.")
print("Full 10m exports are running separately in GEE Tasks.\n")
print("=" * 55)

success = 0
for year in YEARS:
    print(f"\n[Year {year}]")

    # Sentinel-2
    s2_path = os.path.join(OUTPUT_DIR, f'delhi_s2_{year}.tif')
    if os.path.exists(s2_path):
        print(f"  [SKIP] {os.path.basename(s2_path)} already exists")
    else:
        try:
            url = get_s2_download_url(year)
            download_geotiff(url, s2_path)
            success += 1
        except Exception as e:
            print(f"  [ERROR] S2 {year}: {e}")

    # Dynamic World
    dw_path = os.path.join(OUTPUT_DIR, f'delhi_dw_{year}.tif')
    if os.path.exists(dw_path):
        print(f"  [SKIP] {os.path.basename(dw_path)} already exists")
    else:
        try:
            url = get_dw_download_url(year)
            download_geotiff(url, dw_path)
            success += 1
        except Exception as e:
            print(f"  [ERROR] DW {year}: {e}")

print("\n" + "=" * 55)
print(f"\n[DONE] {success} files downloaded to:")
print(f"  {OUTPUT_DIR}")
print("\nNow run:  python app.py")
print("Then open: http://localhost:5000")
