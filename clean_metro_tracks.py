"""
TerraTime — Clean Passenger Metro Lines (No Depot / Siding Clutter)
====================================================================
Filters out maintenance depots, train parking yards, and sidings so only
clean main passenger running tracks are displayed with official colors.
"""

import os
import json
import requests

OUTPUT_DIR = r"e:\capstone\data\infrastructure"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Delhi NCR Core Bounding Box
DELHI_BBOX = (28.38, 76.88, 28.88, 77.48)

# Official Line Color Map
METRO_COLORS = {
    "yellow": ("#ffcc00", "Yellow Line"),
    "blue": ("#0070c0", "Blue Line"),
    "red": ("#e61919", "Red Line"),
    "green": ("#00b050", "Green Line"),
    "violet": ("#7030a0", "Violet Line"),
    "pink": ("#ff66cc", "Pink Line"),
    "magenta": ("#c00060", "Magenta Line"),
    "grey": ("#808080", "Grey Line"),
    "orange": ("#ff6600", "Airport Express"),
    "airport": ("#ff6600", "Airport Express"),
    "aqua": ("#00cccc", "Aqua Line"),
    "rapid": ("#003399", "Rapid Metro")
}

MIRRORS = [
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter"
]


def send_query(query: str):
    headers = {"User-Agent": "TerraTime-CleanMetro/1.0"}
    for url in MIRRORS:
        try:
            print(f"  Querying: {url} ...", flush=True)
            res = requests.post(url, data={"data": query}, headers=headers, timeout=45)
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            print(f"  Mirror failed: {e}", flush=True)
    raise RuntimeError("All mirrors failed.")


def determine_line(tags: dict):
    raw = f"{tags.get('name', '')} {tags.get('ref', '')} {tags.get('colour', '')} {tags.get('color', '')} {tags.get('line', '')} {tags.get('network', '')}".lower()
    for key, (hex_code, name) in METRO_COLORS.items():
        if key in raw:
            return hex_code, name
    return "#00e5ff", "Delhi Metro Line"


def fetch_clean_metro_tracks():
    south, west, north, east = DELHI_BBOX
    print(">>> Fetching Clean Passenger Metro Tracks (Excluding Depots/Sidings)...", flush=True)

    # Exclude yard, siding, crossover, spur (parking and maintenance depot tracks)
    query = f"""
    [out:json][timeout:35];
    (
      way["railway"~"^(subway|light_rail)$"]["service"!~"^(yard|siding|crossover|spur)$"]({south},{west},{north},{east});
    );
    out body geom;
    """

    data = send_query(query)
    elements = data.get("elements", [])
    print(f"  Received {len(elements)} main running track segments.", flush=True)

    features = []
    seen = set()

    for el in elements:
        tags = el.get("tags", {})
        
        # Extra check to ensure no yard/depot tracks sneak in
        if tags.get("service") in ("yard", "siding", "crossover", "spur"):
            continue
        if "depot" in tags.get("name", "").lower() or "yard" in tags.get("name", "").lower():
            continue

        geom = el.get("geometry", [])
        if len(geom) < 2:
            continue

        coords = [[round(pt["lon"], 6), round(pt["lat"], 6)] for pt in geom]
        chash = (coords[0][0], coords[0][1], coords[-1][0], coords[-1][1], len(coords))
        if chash in seen:
            continue
        seen.add(chash)

        color, line_name = determine_line(tags)

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coords
            },
            "properties": {
                "id": el.get("id"),
                "name": tags.get("name") or line_name,
                "color": color,
                "total_points": len(coords)
            }
        })

    geojson = {
        "type": "FeatureCollection",
        "city": "delhi",
        "type_layer": "clean_metro_tracks",
        "total_segments": len(features),
        "features": features
    }

    out_file = os.path.join(OUTPUT_DIR, "delhi_metro_lines.geojson")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2)

    total_pts = sum(f["properties"]["total_points"] for f in features)
    print(f"  [SUCCESS] Cleaned tracks saved ({len(features)} main passenger segments, {total_pts} curve points) -> {os.path.basename(out_file)}!", flush=True)
    return len(features)


if __name__ == "__main__":
    fetch_clean_metro_tracks()
