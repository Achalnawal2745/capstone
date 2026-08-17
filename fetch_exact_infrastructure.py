"""
TerraTime — Robust Physical Curve Fetcher with Multi-Mirror Fallback
=====================================================================
"""

import os
import json
import time
import requests

OUTPUT_DIR = r"e:\capstone\data\infrastructure"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Focused Delhi NCR Core bounding box: [south, west, north, east]
DELHI_BBOX = (28.40, 76.90, 28.85, 77.45)

MIRRORS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
    "https://overpass-api.de/api/interpreter"
]

METRO_COLOR_MAP = {
    "yellow": ("#ffcc00", "Yellow Line"),
    "blue": ("#0070c0", "Blue Line"),
    "red": ("#e61919", "Red Line"),
    "green": ("#00b050", "Green Line"),
    "violet": ("#7030a0", "Violet Line"),
    "pink": ("#ff66cc", "Pink Line"),
    "magenta": ("#c00060", "Magenta Line"),
    "grey": ("#808080", "Grey Line"),
    "orange": ("#ff6600", "Airport Express"),
    "aqua": ("#00cccc", "Aqua Line"),
    "rapid": ("#003399", "Rapid Metro")
}


def send_query(query: str):
    headers = {"User-Agent": "TerraTime-Capstone/1.0"}
    for url in MIRRORS:
        try:
            print(f"  Querying mirror: {url} ...", flush=True)
            res = requests.post(url, data={"data": query}, headers=headers, timeout=50)
            if res.status_code == 200:
                return res.json()
            print(f"  Mirror returned HTTP {res.status_code}, trying next...", flush=True)
        except Exception as e:
            print(f"  Mirror failed: {e}, trying next...", flush=True)
    raise RuntimeError("All mirrors failed. Please check internet connection.")


def match_color_and_name(tags: dict):
    raw = f"{tags.get('name', '')} {tags.get('ref', '')} {tags.get('colour', '')} {tags.get('color', '')} {tags.get('line', '')} {tags.get('network', '')}".lower()
    for key, (hex_code, name) in METRO_COLOR_MAP.items():
        if key in raw:
            return hex_code, name
    return "#ffcc00", "Delhi Metro Corridor"


def fetch_metro_tracks():
    south, west, north, east = DELHI_BBOX
    print(">>> [1/2] Fetching Exact Metro Track Curves...", flush=True)

    query = f"""
    [out:json][timeout:35];
    (
      way["railway"~"^(subway|light_rail)$"]({south},{west},{north},{east});
    );
    out body geom;
    """

    data = send_query(query)
    elements = data.get("elements", [])
    print(f"  Received {len(elements)} physical railway track ways.", flush=True)

    features = []
    seen = set()

    for el in elements:
        geom = el.get("geometry", [])
        if len(geom) < 2:
            continue

        coords = [[round(pt["lon"], 6), round(pt["lat"], 6)] for pt in geom]
        chash = (coords[0][0], coords[0][1], coords[-1][0], coords[-1][1], len(coords))
        if chash in seen:
            continue
        seen.add(chash)

        tags = el.get("tags", {})
        color, name = match_color_and_name(tags)

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coords
            },
            "properties": {
                "id": el.get("id"),
                "name": tags.get("name") or name,
                "color": color,
                "total_points": len(coords)
            }
        })

    geojson = {
        "type": "FeatureCollection",
        "city": "delhi",
        "type_layer": "exact_metro_tracks",
        "total_segments": len(features),
        "features": features
    }

    out_file = os.path.join(OUTPUT_DIR, "delhi_metro_lines.geojson")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2)

    total_pts = sum(f["properties"]["total_points"] for f in features)
    print(f"  [SUCCESS] Saved {len(features)} physical curved track segments ({total_pts} curve points) -> {os.path.basename(out_file)}!", flush=True)
    return len(features)


def fetch_road_curves():
    south, west, north, east = DELHI_BBOX
    print("\n>>> [2/2] Fetching Exact Highway Curves...", flush=True)

    query = f"""
    [out:json][timeout:35];
    (
      way["highway"~"^(motorway|motorway_link|trunk|trunk_link)$"]({south},{west},{north},{east});
    );
    out body geom;
    """

    data = send_query(query)
    elements = data.get("elements", [])
    print(f"  Received {len(elements)} major highway ways.", flush=True)

    features = []
    seen = set()

    for el in elements:
        geom = el.get("geometry", [])
        if len(geom) < 2:
            continue

        coords = [[round(pt["lon"], 6), round(pt["lat"], 6)] for pt in geom]
        chash = (coords[0][0], coords[0][1], coords[-1][0], coords[-1][1], len(coords))
        if chash in seen:
            continue
        seen.add(chash)

        tags = el.get("tags", {})
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coords
            },
            "properties": {
                "id": el.get("id"),
                "highway": tags.get("highway"),
                "name": tags.get("name") or tags.get("ref") or "Expressway / Highway",
                "total_points": len(coords)
            }
        })

    geojson = {
        "type": "FeatureCollection",
        "city": "delhi",
        "type_layer": "exact_highways",
        "total_roads": len(features),
        "features": features
    }

    out_file = os.path.join(OUTPUT_DIR, "delhi_roads.geojson")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2)

    total_pts = sum(f["properties"]["total_points"] for f in features)
    print(f"  [SUCCESS] Saved {len(features)} exact curved highway segments ({total_pts} curve points) -> {os.path.basename(out_file)}!", flush=True)
    return len(features)


def main():
    print("=" * 65, flush=True)
    print("  TerraTime: Downloading Exact Physical Curves", flush=True)
    print("=" * 65, flush=True)

    fetch_metro_tracks()
    time.sleep(2)
    fetch_road_curves()

    print("\n" + "=" * 65, flush=True)
    print("  [COMPLETE] Exact curve datasets saved successfully!", flush=True)
    print("=" * 65, flush=True)


if __name__ == "__main__":
    main()
