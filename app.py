from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from gee_engine import get_engine
import uvicorn
import os

app = FastAPI(title="TerraTime API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (for index.html)
# We can serve index.html at the root
@app.get("/")
async def read_index():
    return FileResponse('index.html')

# Simple in-memory cache for tile URLs
tile_cache = {}

@app.get("/api/tile-url")
async def get_tile_url(
    west: float = Query(...),
    south: float = Query(...),
    east: float = Query(...),
    north: float = Query(...),
    year: int = Query(2023)
):
    # Round to 0.1 degree (~10km) to allow for caching nearby requests
    r_west, r_south = round(west, 1), round(south, 1)
    r_east, r_north = round(east, 1), round(north, 1)
    
    cache_key = f"{r_west}_{r_south}_{r_east}_{r_north}_{year}"
    
    if cache_key in tile_cache:
        print(f"  [Cache] Hit for {cache_key}")
        return {"url": tile_cache[cache_key]}

    print(f"[API] Request: Bounds({west}, {south}, {east}, {north}), Year={year}")
    try:
        engine = get_engine()
        url = engine.get_sentinel2_tile(west, south, east, north, year)
        tile_cache[cache_key] = url
        return {"url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Auto-initialize GEE
    try:
        get_engine()
    except:
        pass
    uvicorn.run(app, host="0.0.0.0", port=5000)
