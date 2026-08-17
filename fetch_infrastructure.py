"""
TerraTime — Delhi Infrastructure Data Fetcher (OpenStreetMap Overpass API)
==========================================================================
Fetches all Metro Stations and Major Highways/Expressways/Primary Roads for Delhi
and saves them as standard GeoJSON files in `data/infrastructure/`.
"""

import os
import json
import time
import requests

OUTPUT_DIR = r"e:\capstone\data\infrastructure"
os.makedirs(OUTPUT_DIR, exist_ok=True)

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
]

# Delhi NCR Bounding Box: [south, west, north, east]
DELHI_BBOX = (28.3, 76.8, 28.9, 77.5)


def query_overpass(query_str: str) -> dict:
    """Executes a query against the Overpass Cloud API with mirror fallback."""
    headers = {
        "User-Agent": "TerraTime-Capstone/1.0 (Delhi Infrastructure Fetcher)"
    }
    for url in OVERPASS_URLS:
        try:
            print(f"  [API] Querying {url} ...", flush=True)
            response = requests.post(url, data={"data": query_str}, headers=headers, timeout=60)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                print("  [WARN] Rate limited, trying mirror...", flush=True)
                time.sleep(3)
            else:
                print(f"  [WARN] Server returned HTTP {response.status_code}, trying mirror...", flush=True)
        except Exception as e:
            print(f"  [WARN] Mirror connection failed: {e}", flush=True)
    raise RuntimeError("All Overpass API mirrors failed. Please check internet connection.")


def fetch_delhi_metro():
    """Fetches all Delhi Metro and Rapid Metro stations."""
    south, west, north, east = DELHI_BBOX
    print("\n[1/2] Fetching Delhi Metro Stations...", flush=True)

    query = f"""
    [out:json][timeout:45];
    (
      node["railway"="station"]["station"="subway"]({south},{west},{north},{east});
      node["railway"="station"]["subway"="yes"]({south},{west},{north},{east});
      node["station"="subway"]({south},{west},{north},{east});
    );
    out body;
    """

    data = query_overpass(query)
    elements = data.get("elements", [])
    print(f"  Received {len(elements)} raw station nodes from cloud.", flush=True)

    features = []
    seen = set()

    for el in elements:
        lat = el.get("lat")
        lon = el.get("lon")
        if not lat or not lon:
            continue
        
        # Deduplicate coordinates rounded to 4 decimals (~10m)
        key = (round(lat, 4), round(lon, 4))
        if key in seen:
            continue
        seen.add(key)

        tags = el.get("tags", {})
        name = tags.get("name") or tags.get("name:en") or "Delhi Metro Station"
        line = tags.get("line") or tags.get("network") or "Delhi Metro"

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat]
            },
            "properties": {
                "id": el.get("id"),
                "name": name,
                "line": line,
                "city": "delhi"
            }
        })

    geojson = {
        "type": "FeatureCollection",
        "city": "delhi",
        "type_layer": "metro_stations",
        "total_count": len(features),
        "features": features
    }

    out_file = os.path.join(OUTPUT_DIR, "delhi_metro_stations.geojson")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2)

    print(f"  [SUCCESS] Saved {len(features)} unique Metro Stations to {os.path.basename(out_file)}!", flush=True)
    return len(features)


def fetch_delhi_roads():
    """Fetches major highways, expressways, and arterial roads in Delhi NCR."""
    south, west, north, east = DELHI_BBOX
    print("\n[2/2] Fetching Delhi Major Road Network (Expressways, Highways, Arterials)...", flush=True)

    # Filter for motorway, trunk, and primary (the major corridors used for expansion prediction)
    query = f"""
    [out:json][timeout:60];
    (
      way["highway"~"^(motorway|motorway_link|trunk|trunk_link|primary)$"]({south},{west},{north},{east});
    );
    out body geom;
    """

    data = query_overpass(query)
    elements = data.get("elements", [])
    print(f"  Received {len(elements)} major road segments from cloud.", flush=True)

    features = []
    for el in elements:
        geom = el.get("geometry", [])
        if len(geom) < 2:
            continue

        coordinates = [[pt["lon"], pt["lat"]] for pt in geom]
        tags = el.get("tags", {})

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coordinates
            },
            "properties": {
                "id": el.get("id"),
                "highway": tags.get("highway"),
                "name": tags.get("name") or tags.get("ref") or "Major Road",
                "lanes": tags.get("lanes", "unknown"),
                "maxspeed": tags.get("maxspeed", "unknown")
            }
        })

    geojson = {
        "type": "FeatureCollection",
        "city": "delhi",
        "type_layer": "major_roads",
        "total_count": len(features),
        "features": features
    }

    out_file = os.path.join(OUTPUT_DIR, "delhi_roads.geojson")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2)

    print(f"  [SUCCESS] Saved {len(features)} major road segments to {os.path.basename(out_file)}!", flush=True)
    return len(features)


def main():
    print("=" * 65, flush=True)
    print("  TerraTime: Fetching Delhi Infrastructure Data from OpenStreetMap", flush=True)
    print(f"  Destination: {OUTPUT_DIR}", flush=True)
    print("=" * 65, flush=True)

    stations = fetch_delhi_metro()
    time.sleep(2)
    roads = fetch_delhi_roads()

    print("\n" + "=" * 65, flush=True)
    print(f"  [COMPLETE] Downloaded {stations} Metro Stations & {roads} Major Roads!", flush=True)
    print(f"  All saved in: {OUTPUT_DIR}", flush=True)
    print("=" * 65, flush=True)


if __name__ == "__main__":
    main()
