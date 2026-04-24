import ee
import sys
import io
import math

# Fix console encoding for Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

GCP_PROJECT = 'chatty-qp3qx'

class GEEEngine:
    def __init__(self, project_id=GCP_PROJECT):
        try:
            ee.Initialize(project=project_id)
            print(f"  [OK] Earth Engine initialized with project: {project_id}")
        except Exception as e:
            print(f"  [FAIL] GEE Initialization failed: {e}")
            raise e

    def mask_s2_clouds(self, image):
        # scene classification layer based masking
        scl = image.select('SCL')
        mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
        return image.updateMask(mask)

    def get_sentinel2_tile(self, west, south, east, north, year=2023):
        """High-Quality Sentinel-2 Engine that handles both Local and Global scales."""
        
        # Calculate viewport scale
        center_lat = (south + north) / 2
        lat_dist = abs(north - south) * 111000
        lng_dist = abs(east - west) * 111000 * math.cos(math.radians(center_lat))
        viewport_max_dim = max(lat_dist, lng_dist)

        # Decide on performance mode
        is_global = viewport_max_dim > 1500000
        
        # Performance Settings
        # If global, we use a tighter cloud filter to speed up the median calculation
        cloud_pct = 10 if is_global else 20
        
        collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterDate(f'{year}-01-01', f'{year}-12-31'))

        # Calculate buffer area
        if is_global:
            # Cap the global calculation area to ~3000km to prevent timeouts
            buffer_meters = min(3000000, viewport_max_dim * 1.2)
        else:
            # Minimum 1000km buffer. This matches the frontend's +/- 5 degree safe zone.
            # If this is smaller, the user will pan into black/transparent areas because the 
            # frontend won't request a new URL yet.
            buffer_meters = max(1000000, viewport_max_dim * 1.2)

        center_lng = (west + east) / 2
        point = ee.Geometry.Point([center_lng, center_lat])
        search_region = point.buffer(buffer_meters).bounds()
        collection = collection.filterBounds(search_region)
        
        # Mask and reduce
        if is_global:
            # ULTRA-FAST PATH: Use .mosaic() instead of .median() and skip pixel-level cloud masking.
            # We just take the cleanest images (<5% clouds) and layer them.
            composite = collection.filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 5)).mosaic()
        else:
            # HIGH-QUALITY PATH (Optimized for Speed): 
            # Median is too heavy and causes 429 errors. Instead, we sort by clouds (descending) 
            # so the absolute clearest image is layered on top.
            composite = (collection
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
                .sort('CLOUDY_PIXEL_PERCENTAGE', False)
                .mosaic())

        vis_params = {
            'bands': ['B4', 'B3', 'B2'],
            'min': 0,
            'max': 4000,
            'gamma': 1.4
        }

        map_id = composite.getMapId(vis_params)
        mode = "Global-Turbo" if is_global else "High-Res"
        print(f"  [GEE] Sentinel-2 ({mode}) for {year}")
        return map_id['tile_fetcher'].url_format

# Singleton instance
engine = None
def get_engine():
    global engine
    if engine is None:
        engine = GEEEngine()
    return engine
