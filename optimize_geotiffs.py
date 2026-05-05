"""
Convert GeoTIFFs to Cloud-Optimized format for fast tile serving.
Run once after downloading from Google Drive.
"""
import subprocess
import os
import sys

GEOTIFF_DIR = r"e:\capstone\data\geotiffs"

files = [f for f in os.listdir(GEOTIFF_DIR) if f.endswith('.tif')]
print(f"Found {len(files)} files to optimize\n")

for fname in sorted(files):
    src = os.path.join(GEOTIFF_DIR, fname)
    tmp = src.replace('.tif', '_cog_tmp.tif')

    size_mb = os.path.getsize(src) / (1024*1024)
    print(f"Optimizing {fname} ({size_mb:.0f} MB)...")

    try:
        # Use rio cogeo if available, else use gdal_translate
        result = subprocess.run([
            sys.executable, "-m", "rio", "cogeo", "create",
            src, tmp, "--overview-resampling", "average"
        ], capture_output=True, text=True)

        if result.returncode == 0:
            os.replace(tmp, src)
            print(f"  [OK] {fname} converted to COG")
        else:
            # Fallback: gdal_translate
            result2 = subprocess.run([
                "gdal_translate", src, tmp,
                "-of", "GTiff",
                "-co", "TILED=YES",
                "-co", "COMPRESS=DEFLATE",
                "-co", "COPY_SRC_OVERVIEWS=YES",
            ], capture_output=True, text=True)
            if result2.returncode == 0:
                os.replace(tmp, src)
                print(f"  [OK] {fname} tiled with gdal")
            else:
                if os.path.exists(tmp):
                    os.remove(tmp)
                print(f"  [SKIP] {fname} - could not optimize (will still work, just slower)")
    except Exception as e:
        if os.path.exists(tmp):
            os.remove(tmp)
        print(f"  [SKIP] {fname} - {e}")

print("\nDone. Restart app.py for faster tile serving.")
