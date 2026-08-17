"""
TerraTime — Fast Delhi Metro Line & Track Fetcher
=================================================
Fetches subway & light rail tracks in Delhi NCR and tags them with their
official Delhi Metro line names and colors.
"""

import os
import json
import time
import requests

OUTPUT_DIR = r"e:\capstone\data\infrastructure"
os.makedirs(OUTPUT_DIR, exist_ok=True)

DELHI_BBOX = (28.3, 76.8, 28.9, 77.5)

METRO_COLORS = {
    "red": "#e61919",
    "yellow": "#ffcc00",
    "blue": "#0070c0",
    "green": "#00b050",
    "violet": "#7030a0",
    "pink": "#ff66cc",
    "magenta": "#c00060",
    "grey": "#808080",
    "orange": "#ff6600",
    "airport": "#ff6600",
    "aqua": "#00cccc",
    "rapid": "#003399"
}

def determine_color(tags: dict) -> str:
    raw = f"{tags.get('name', '')} {tags.get('ref', '')} {tags.get('colour', '')} {tags.get('color', '')} {tags.get('line', '')} {tags.get('network', '')}".lower()
    for key, hex_code in METRO_COLORS.items():
        if key in raw:
            return hex_code
    return "#ffcc00"  # Default golden yellow for metro tracks


def fetch_tracks():
    south, west, north, east = DELHI_BBOX
    print(">>> Querying Delhi Metro Tracks from Overpass API...", flush=True)

    query = f"""
    [out:json][timeout:35];
    (
      way["railway"~"^(subway|light_rail)$"]({south},{west},{north},{east});
    );
    out body geom;
    """

    url = "https://overpass-api.de/api/interpreter"
    headers = {"User-Agent": "TerraTime/1.0"}
    
    try:
        res = requests.post(url, data={"data": query}, headers=headers, timeout=40)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        print(f"Primary mirror failed: {e}, trying backup...", flush=True)
        url = "https://overpass.kumi.systems/api/interpreter"
        res = requests.post(url, data={"data": query}, headers=headers, timeout=40)
        res.raise_for_status()
        data = res.json()

    elements = data.get("elements", [])
    print(f"  Received {len(elements)} metro track segments.", flush=True)

    features = []
    for el in elements:
        geom = el.get("geometry", [])
        if len(geom) < 2:
            continue
        coords = [[pt["lon"], pt["lat"]] for pt in geom]
        tags = el.get("tags", {})
        color = determine_color(tags)
        name = tags.get("name") or tags.get("ref") or "Delhi Metro Track"

        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "id": el.get("id"),
                "name": name,
                "color": color,
                "line": tags.get("line") or tags.get("network") or "Delhi Metro"
            }
        })

    geojson = {
        "type": "FeatureCollection",
        "city": "delhi",
        "type_layer": "metro_lines",
        "total_count": len(features),
        "features": features
    }

    out_file = os.path.join(OUTPUT_DIR, "delhi_metro_lines.geojson")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2)

    print(f"  [SUCCESS] Saved {len(features)} Metro Track Segments to {os.path.basename(out_file)}!", flush=True)
    return len(features)


if __name__ == "__main__":
    fetch_tracks()
