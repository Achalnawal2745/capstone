"""
TerraTime — Tag Historical Opening Years for All Infrastructure
================================================================
Tags verified commissioning/opening years on:
1. Delhi Metro Lines (delhi_metro_lines.geojson)
2. Delhi Metro Stations (delhi_metro_stations.geojson)
3. Delhi Major Highways (delhi_roads.geojson)
"""

import json
import os

OUTPUT_DIR = r"e:\capstone\data\infrastructure"
LINES_FILE    = os.path.join(OUTPUT_DIR, "delhi_metro_lines.geojson")
STATIONS_FILE = os.path.join(OUTPUT_DIR, "delhi_metro_stations.geojson")
ROADS_FILE    = os.path.join(OUTPUT_DIR, "delhi_roads.geojson")


def get_metro_line_year(props: dict, coords: list) -> int:
    name = props.get("name", "").lower()
    color = props.get("color", "").lower()

    # Magenta Line -> Opened 2018
    if "magenta" in name or color == "#c00060":
        return 2018
    
    # Pink Line -> Opened 2018 (Trilokpuri linked 2021)
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
        return 2017

    # Red Line Ghaziabad Extension -> 2019
    if "red" in name or color == "#e61919":
        if any(pt[0] > 77.33 for pt in coords): # Ghaziabad side
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
        if any(pt[1] < 28.49 for pt in coords): # Faridabad
            return 2015
        return 2011

    # Green Line Bahadurgarh Extension -> 2018
    if "green" in name or color == "#00b050":
        if any(pt[0] < 77.00 for pt in coords): # Haryana border extension
            return 2018
        return 2010

    # Airport Express Extension (Yashobhoomi Dwarka 25) -> 2023
    if "airport" in name or "orange" in name or color == "#ff6600":
        if any(pt[0] < 77.05 and pt[1] < 28.56 for pt in coords):
            return 2023
        return 2011

    # Core Lines before 2016
    return 2015


def get_station_year(name: str, coords: list) -> int:
    n = name.lower()

    # Aqua Line stations (Noida Sector 51 to Depot) -> 2019
    if any(k in n for k in ["sector 51", "sector 76", "sector 137", "sector 142", "pari chowk", "alpha 1", "delta 1", "nsez", "knowledge park"]):
        return 2019

    # Magenta Line stations -> 2018
    if any(k in n for k in ["dabri mor", "dashrath puri", "palam", "vasant vihar", "munirka", "iit", "panchsheel", "chirag delhi", "greater kailash", "nehru enclave", "okhla bird", "kalindi kunj", "jamia", "sukhdev vihar", "terminal 1"]):
        return 2018

    # Pink Line stations -> 2018
    if any(k in n for k in ["majlis park", "shalimar bagh", "shakurpur", "punjabi bagh west", "basaidarapur", "maya puri", "naraina", "delhi cantt", "south campus", "moti bagh", "bhikaji", "sarojini nagar", "south extension", "vinobapuri", "ashram", "nizamuddin", "mayur vihar pocket", "trilokpuri", "east vinod nagar", "mandawali", "ip extension", "karkarduma court", "krishna nagar", "east azad nagar", "jaffrabad", "maujpur", "gokulpuri", "johri enclave", "shiv vihar"]):
        return 2018

    # Red Line Ghaziabad Extension -> 2019
    if any(k in n for k in ["shahid nagar", "raj bagh", "mohit sharma", "shyam park", "mohan nagar", "arthala", "hindon", "shaheed sthal"]):
        return 2019

    # Blue Line Noida Ext -> 2019
    if any(k in n for k in ["sector 34", "sector 52", "sector 61", "sector 59", "sector 62", "electronic city"]):
        return 2019

    # Grey Line -> 2019
    if any(k in n for k in ["dhansa", "najafgarh"]):
        return 2019

    # Green Line Bahadurgarh -> 2018
    if any(k in n for k in ["mundka industrial", "ghevra", "tikri", "pandit shree ram", "bahadurgarh", "brigadier hoshiar"]):
        return 2018

    # Violet Line Ballabhgarh -> 2018
    if any(k in n for k in ["sant surdas", "raja nahar singh", "escorts mujesar", "bata chowk", "neelam chowk"]):
        return 2018

    # Airport Express Yashobhoomi -> 2023
    if "yashobhoomi" in n or "sector 25" in n:
        return 2023

    # All Core stations before 2016
    return 2015


def get_road_year(props: dict, coords: list) -> int:
    name = props.get("name", "").lower()

    # Dwarka Expressway -> 2024
    if "dwarka expressway" in name or "nh 248-bb" in name or "northern peripheral" in name:
        return 2024
    
    # Delhi-Meerut Expressway -> 2021
    if "delhi-meerut" in name or "meerut expressway" in name:
        return 2021
    
    # Eastern / Western Peripheral Expressway (KMP / KGP) -> 2018
    if "peripheral" in name or "kundli-manesar" in name or "eastern peripheral" in name or "western peripheral" in name:
        return 2018
    
    # Sohna Elevated Highway -> 2022
    if "sohna" in name or "rajiv chowk-sohna" in name:
        return 2022

    # Standard major roads exist before 2016
    return 2015


def main():
    print("=" * 65)
    print("  TerraTime: Tagging Opening Years for Timeline Slider Sync")
    print("=" * 65)

    # 1. Metro Lines
    with open(LINES_FILE, "r", encoding="utf-8") as f:
        d_lines = json.load(f)
    for feat in d_lines.get("features", []):
        feat.setdefault("properties", {})["opening_year"] = get_metro_line_year(feat["properties"], feat["geometry"]["coordinates"])
    with open(LINES_FILE, "w", encoding="utf-8") as f:
        json.dump(d_lines, f, indent=2)
    print("  [OK] Delhi Metro Lines tagged with opening years (2015-2023)")

    # 2. Metro Stations
    with open(STATIONS_FILE, "r", encoding="utf-8") as f:
        d_stations = json.load(f)
    for feat in d_stations.get("features", []):
        feat.setdefault("properties", {})["opening_year"] = get_station_year(feat.get("properties", {}).get("name", ""), feat["geometry"]["coordinates"])
    with open(STATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(d_stations, f, indent=2)
    print("  [OK] Delhi Metro Stations tagged with opening years (2015-2023)")

    # 3. Roads
    with open(ROADS_FILE, "r", encoding="utf-8") as f:
        d_roads = json.load(f)
    for feat in d_roads.get("features", []):
        feat.setdefault("properties", {})["opening_year"] = get_road_year(feat["properties"], feat["geometry"]["coordinates"])
    with open(ROADS_FILE, "w", encoding="utf-8") as f:
        json.dump(d_roads, f, indent=2)
    print("  [OK] Delhi Major Roads & Expressways tagged with opening years")

    print("\n" + "=" * 65)
    print("  [SUCCESS] All infrastructure is now Timeline-Synchronized!")
    print("=" * 65)


if __name__ == "__main__":
    main()
