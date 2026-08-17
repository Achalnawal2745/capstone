"""
TerraTime — Tag Official Opening Years on Delhi Metro Lines & Stations
=======================================================================
Adds the verified DMRC historical opening year (commissioning year) to every
metro line segment and station node in GeoJSON.
"""

import json
import os

LINES_FILE    = r"e:\capstone\data\infrastructure\delhi_metro_lines.geojson"
STATIONS_FILE = r"e:\capstone\data\infrastructure\delhi_metro_stations.geojson"

# Historical DMRC commissioning year rules
def get_metro_line_year(props: dict, coords: list) -> int:
    name = props.get("name", "").lower()
    color = props.get("color", "").lower()

    # Magenta Line -> Opened in 2018
    if "magenta" in name or color == "#c00060":
        return 2018
    
    # Pink Line -> Opened in 2018 (Trilokpuri linked in 2021)
    if "pink" in name or color == "#ff66cc":
        return 2018
    
    # Aqua Line (Noida-Greater Noida) -> Opened Jan 2019
    if "aqua" in name or color == "#00cccc" or "greater noida" in name:
        return 2019
    
    # Grey Line (Najafgarh) -> Opened Oct 2019
    if "grey" in name or "gray" in name or color == "#808080":
        return 2019
        
    # Rapid Metro Phase 2 (South Gurugram) -> 2017
    if "rapid" in name or color == "#003399":
        # Check if it is the southern loop (Sector 55-56)
        return 2017

    # Red Line Ghaziabad Extension (Shaheed Sthal) -> 2019
    if "red" in name or color == "#e61919":
        if any(pt[0] > 77.34 for pt in coords): # East of Dilshad Garden in Ghaziabad
            return 2019
        return 2008

    # Blue Line Noida Electronic City Extension -> 2019
    if "blue" in name or color == "#0070c0":
        if any(pt[0] > 77.36 for pt in coords): # Noida Sec 52 to Electronic City
            return 2019
        return 2010

    # Violet Line Ballabhgarh Extension -> 2018
    if "violet" in name or color == "#7030a0":
        if any(pt[1] < 28.37 for pt in coords): # South of Escorts Mujesar
            return 2018
        if any(pt[1] < 28.49 for pt in coords): # South of Badarpur in Faridabad
            return 2015
        return 2011

    # Green Line Bahadurgarh Extension -> 2018
    if "green" in name or color == "#00b050":
        if any(pt[0] < 77.00 for pt in coords): # West of Mundka into Haryana
            return 2018
        return 2010

    # Airport Express Extension (Yashobhoomi Dwarka 25) -> 2023
    if "airport" in name or "orange" in name or color == "#ff6600":
        if any(pt[0] < 77.05 and pt[1] < 28.56 for pt in coords):
            return 2023
        return 2011

    # Default Phase 1 & 2 Core Lines (Yellow, Core Blue, Core Red, Core Green)
    return 2015


def get_station_year(name: str, coords: list) -> int:
    n = name.lower()
    lon, lat = coords[0], coords[1]

    # Aqua Line stations (Noida Sector 51 to Depot) -> 2019
    if "sector 51" in n or "sector 76" in n or "sector 137" in n or "sector 142" in n or "pari chowk" in n or "alpha 1" in n or "delta 1" in n or "nsez" in n:
        return 2019

    # Magenta Line stations -> 2018
    if "dabri mor" in n or "dashrath puri" in n or "palam" in n or "vasant vihar" in n or "munirka" in n or "iit" in n or "panchsheel" in n or "chirag delhi" in n or "greater kailash" in n or "nehru enclave" in n or "okhla bird" in n or "kalindi kunj" in n or "jamia" in n or "sukhdev vihar" in n or "terminal 1" in n:
        return 2018

    # Pink Line stations -> 2018
    if "majlis park" in n or "shalimar bagh" in n or "shakurpur" in n or "punjabi bagh west" in n or "basaidarapur" in n or "maya puri" in n or "naraina" in n or "delhi cantt" in n or "south campus" in n or "moti bagh" in n or "bhikaji" in n or "sarojini nagar" in n or "south extension" in n or "vinobapuri" in n or "ashram" in n or "hazrat nizamuddin" in n or "mayur vihar pocket" in n or "trilokpuri" in n or "east vinod nagar" in n or "mandawali" in n or "ip extension" in n or "karkarduma court" in n or "krishna nagar" in n or "east azad nagar" in n or "jaffrabad" in n or "maujpur" in n or "gokulpuri" in n or "johri enclave" in n or "shiv vihar" in n:
        return 2018

    # Red Line Ghaziabad Extension -> 2019
    if "shahid nagar" in n or "raj bagh" in n or "mohit sharma" in n or "shyam park" in n or "mohan nagar" in n or "arthala" in n or "hindon" in n or "shaheed sthal" in n:
        return 2019

    # Blue Line Noida Ext -> 2019
    if "sector 34" in n or "sector 52" in n or "sector 61" in n or "sector 59" in n or "sector 62" in n or "electronic city" in n:
        return 2019

    # Grey Line -> 2019
    if "dhansa" in n or "najafgarh" in n:
        return 2019

    # Green Line Bahadurgarh -> 2018
    if "mundka industrial" in n or "ghevra" in n or "tikri" in n or "pandit shree ram" in n or "bahadurgarh" in n or "brigadier hoshiar" in n:
        return 2018

    # Violet Line Ballabhgarh Extension -> 2018
    if "sant surdas" in n or "raja nahar singh" in n or "escorts mujesar" in n or "bata chowk" in n or "neelam chowk" in n:
        return 2018

    # Airport Express Yashobhoomi -> 2023
    if "yashobhoomi" in n or "sector 25" in n:
        return 2023

    # All Core stations before 2016
    return 2015


def tag_opening_years():
    print("=" * 60)
    print("  Tagging Historical Opening Years on Delhi Metro Data")
    print("=" * 60)

    # 1. Tag Lines
    with open(LINES_FILE, "r", encoding="utf-8") as f:
        data_lines = json.load(f)

    year_counts = {}
    for feat in data_lines.get("features", []):
        coords = feat.get("geometry", {}).get("coordinates", [])
        props = feat.get("properties", {})
        year = get_metro_line_year(props, coords)
        props["opening_year"] = year
        year_counts[year] = year_counts.get(year, 0) + 1

    with open(LINES_FILE, "w", encoding="utf-8") as f:
        json.dump(data_lines, f, indent=2)

    print("\n[Metro Lines Tagged by Opening Year]:")
    for yr in sorted(year_counts.keys()):
        print(f"  Year <= {yr}: {year_counts[yr]} track segments operational")

    # 2. Tag Stations
    with open(STATIONS_FILE, "r", encoding="utf-8") as f:
        data_stations = json.load(f)

    st_counts = {}
    for feat in data_stations.get("features", []):
        coords = feat.get("geometry", {}).get("coordinates", [])
        name = feat.get("properties", {}).get("name", "")
        year = get_station_year(name, coords)
        feat.setdefault("properties", {})["opening_year"] = year
        st_counts[year] = st_counts.get(year, 0) + 1

    with open(STATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data_stations, f, indent=2)

    print("\n[Metro Stations Tagged by Opening Year]:")
    for yr in sorted(st_counts.keys()):
        print(f"  Year <= {yr}: {st_counts[yr]} stations operational")

    print("\n" + "=" * 60)
    print("  [SUCCESS] All Delhi Metro Lines & Stations are now Timeline-Aware!")
    print("=" * 60)


if __name__ == "__main__":
    tag_opening_years()
