"""
TerraTime — Delhi Metro Network & Track Line Generator
======================================================
Builds continuous connected metro track lines linking all stations in order
with official DMRC color coding (Red, Yellow, Blue, Green, Violet, Pink, Magenta,
Airport Express, Rapid Metro, Aqua Line) and saves as `data/infrastructure/delhi_metro_lines.geojson`.
"""

import os
import json

STATIONS_FILE = r"e:\capstone\data\infrastructure\delhi_metro_stations.geojson"
OUTPUT_FILE   = r"e:\capstone\data\infrastructure\delhi_metro_lines.geojson"

# Official DMRC Line Definitions (ordered station sequence & color codes)
METRO_NETWORK_ROUTES = [
    {
        "line_name": "Yellow Line",
        "color": "#ffcc00",
        "description": "Samaypur Badli ↔ Millennium City Centre Gurugram",
        "stations": [
            "Samaypur Badli", "Rohini Sector 18, 19", "Haiderpur Badli Mor", "Jahangirpuri", "Adarsh Nagar",
            "Azadpur", "Model Town", "Guru Tegh Bahadur Nagar", "Vishwavidyalaya", "Vidhan Sabha",
            "Civil Lines", "Kashmere Gate", "Chandni Chowk", "Chawri Bazar", "New Delhi",
            "Rajiv Chowk", "Patel Chowk", "Central Secretariat", "Udyog Bhawan", "Lok Kalyan Marg",
            "Jor Bagh", "Dilli Haat - INA", "AIIMS", "Green Park", "Hauz Khas",
            "Malviya Nagar", "Saket", "Qutab Minar", "Chhatarpur", "Sultanpur",
            "Ghitorni", "Arjan Garh", "Guru Dronacharya", "Sikanderpur", "MG Road",
            "IFFCO Chowk", "Millennium City Centre Gurugram"
        ]
    },
    {
        "line_name": "Blue Line (Main)",
        "color": "#0070c0",
        "description": "Dwarka Sector 21 ↔ Noida Electronic City",
        "stations": [
            "Dwarka Sector 21", "Dwarka Sector 8", "Dwarka Sector 9", "Dwarka Sector 10", "Dwarka Sector 11",
            "Dwarka Sector 12", "Dwarka Sector 13", "Dwarka Sector 14", "Dwarka", "Dwarka Mor",
            "Nawada", "Uttam Nagar West", "Uttam Nagar East", "Janakpuri West", "Janakpuri East",
            "Tilak Nagar", "Subhash Nagar", "Tagore Garden", "Rajouri Garden", "Ramesh Nagar",
            "Moti Nagar", "Kirti Nagar", "Shadipur", "Patel Nagar", "Rajendra Place",
            "Karol Bagh", "Jhandewalan", "RK Ashram Marg", "Rajiv Chowk", "Barakhamba Road",
            "Mandi House", "Supreme Court", "Indraprastha", "Yamuna Bank", "Akshardham",
            "Mayur Vihar-I", "Mayur Vihar Extension", "New Ashok Nagar", "Noida Sector 15", "Noida Sector 16",
            "Noida Sector 18", "Botanical Garden", "Golf Course", "Noida City Centre", "Noida Sector 34",
            "Noida Sector 52", "Noida Sector 61", "Noida Sector 59", "Noida Sector 62", "Noida Electronic City"
        ]
    },
    {
        "line_name": "Blue Line (Vaishali Branch)",
        "color": "#0070c0",
        "description": "Yamuna Bank ↔ Vaishali",
        "stations": [
            "Yamuna Bank", "Laxmi Nagar", "Nirman Vihar", "Preet Vihar", "Karkarduma",
            "Anand Vihar ISBT", "Kaushambi", "Vaishali"
        ]
    },
    {
        "line_name": "Red Line",
        "color": "#e61919",
        "description": "Rithala ↔ Shaheed Sthal (New Bus Adda Ghaziabad)",
        "stations": [
            "Rithala", "Rohini West", "Rohini East", "Pitampura", "Kohat Enclave",
            "Netaji Subhash Place", "Keshav Puram", "Kanhaiya Nagar", "Inderlok", "Shastri Nagar",
            "Pratap Nagar", "Pul Bangash", "Tis Hazari", "Kashmere Gate", "Shastri Park",
            "Seelampur", "Welcome", "Shahdara", "Mansarovar Park", "Jhilmil",
            "Dilshad Garden", "Shahid Nagar", "Raj Bagh", "Major Mohit Sharma", "Shyam Park",
            "Mohan Nagar", "Arthala", "Hindon River", "Shaheed Sthal"
        ]
    },
    {
        "line_name": "Magenta Line",
        "color": "#c00060",
        "description": "Janakpuri West ↔ Botanical Garden",
        "stations": [
            "Janakpuri West", "Dabri Mor - Janakpuri South", "Dashrath Puri", "Palam", "Sadar Bazar Cantonment",
            "Terminal 1-IGI Airport", "Shankar Vihar", "Vasant Vihar", "Munirka", "RK Puram",
            "IIT Delhi", "Hauz Khas", "Panchsheel Park", "Chirag Delhi", "Greater Kailash",
            "Nehru Enclave", "Kalkaji Mandir", "Okhla NSIC", "Sukhdev Vihar", "Jamia Millia Islamia",
            "Okhla Vihar", "Jasola Vihar Shaheen Bagh", "Kalindi Kunj", "Okhla Bird Sanctuary", "Botanical Garden"
        ]
    },
    {
        "line_name": "Pink Line (Ring Road)",
        "color": "#ff66cc",
        "description": "Majlis Park ↔ Shiv Vihar",
        "stations": [
            "Majlis Park", "Azadpur", "Shalimar Bagh", "Netaji Subhash Place", "Shakurpur",
            "Punjabi Bagh West", "ESI - Basaidarapur", "Rajouri Garden", "Maya Puri", "Naraina Vihar",
            "Delhi Cantonment", "Durgabai Deshmukh South Campus", "Sir M. Vishweshwaraiah Moti Bagh", "Bhikaji Cama Place", "Sarojini Nagar",
            "Dilli Haat - INA", "South Extension", "Lajpat Nagar", "Vinobapuri", "Ashram",
            "Sarai Kale Khan - Nizamuddin", "Mayur Vihar-I", "Mayur Vihar Pocket 1", "Trilokpuri Sanjay Lake", "East Vinod Nagar - Mayur Vihar-II",
            "Mandawali - West Vinod Nagar", "IP Extension", "Anand Vihar ISBT", "Karkarduma", "Karkarduma Court",
            "Krishna Nagar", "East Azad Nagar", "Welcome", "Jaffrabad", "Maujpur - Babarpur",
            "Gokulpuri", "Johri Enclave", "Shiv Vihar"
        ]
    },
    {
        "line_name": "Violet Line",
        "color": "#7030a0",
        "description": "Kashmere Gate ↔ Raja Nahar Singh (Ballabhgarh)",
        "stations": [
            "Kashmere Gate", "Lal Quila", "Jama Masjid", "Delhi Gate", "ITO",
            "Mandi House", "Janpath", "Central Secretariat", "Khan Market", "Jawaharlal Nehru Stadium",
            "Jangpura", "Lajpat Nagar", "Moolchand", "Kailash Colony", "Nehru Place",
            "Kalkaji Mandir", "Govind Puri", "Harkesh Nagar Okhla", "Jasola Apollo", "Sarita Vihar",
            "Mohan Estate", "Tughlakabad Station", "Badarpur Border", "Sarai", "NHPC Chowk",
            "Mewala Maharajpur", "Sector 28", "Badkal Mor", "Old Faridabad", "Neelam Chowk Ajronda",
            "Bata Chowk", "Escorts Mujesar", "Sant Surdas (Sihi)", "Raja Nahar Singh"
        ]
    },
    {
        "line_name": "Green Line",
        "color": "#00b050",
        "description": "Kirti Nagar/Inderlok ↔ Brig. Hoshiar Singh (Bahadurgarh)",
        "stations": [
            "Inderlok", "Ashok Park Main", "Punjabi Bagh", "Shivaji Park", "Madipur",
            "Paschim Vihar East", "Paschim Vihar West", "Peeragarhi", "Udyog Nagar", "Surajmal Stadium",
            "Nangloi", "Nangloi Railway Station", "Rajdhani Park", "Mundka", "Mundka Industrial Area",
            "Ghevra Metro Station", "Tikri Kalan", "Tikri Border", "Pandit Shree Ram Sharma", "Bahadurgarh City", "Brigadier Hoshiar Singh"
        ]
    },
    {
        "line_name": "Airport Express (Orange Line)",
        "color": "#ff6600",
        "description": "New Delhi ↔ Yashobhoomi Dwarka Sector 25",
        "stations": [
            "New Delhi", "Shivaji Stadium", "Dhaula Kuan", "Delhi Aerocity", "Airport (T-3)",
            "Dwarka Sector 21", "Yashobhoomi Dwarka Sector 25"
        ]
    },
    {
        "line_name": "Rapid Metro Gurugram",
        "color": "#003399",
        "description": "Cyber City Loop ↔ Sector 55-56",
        "stations": [
            "Sector 55-56", "Sector 54 Chowk", "Sector 53-54", "Sector 42-43", "Phase 1",
            "Sikanderpur", "Phase 2", "Belvedere Towers", "Cyber City", "Moulsari Avenue", "Phase 3"
        ]
    },
    {
        "line_name": "Aqua Line (Noida Metro)",
        "color": "#00cccc",
        "description": "Noida Sector 51 ↔ Depot (Greater Noida)",
        "stations": [
            "Noida Sector 51", "Noida Sector 50", "Noida Sector 76", "Noida Sector 101", "Noida Sector 81",
            "NSEZ", "Noida Sector 83", "Noida Sector 137", "Noida Sector 142", "Noida Sector 143",
            "Noida Sector 144", "Noida Sector 145", "Noida Sector 146", "Noida Sector 147", "Noida Sector 148",
            "Knowledge Park II", "Pari Chowk", "Alpha 1", "Delta 1", "GNIDA Office", "Depot"
        ]
    }
]


def load_station_lookup():
    """Loads stations GeoJSON and indexes by normalized name and coordinate."""
    if not os.path.exists(STATIONS_FILE):
        raise FileNotFoundError(f"Missing stations file: {STATIONS_FILE}")

    with open(STATIONS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    lookup = {}
    all_stations = []

    for feat in data.get("features", []):
        props = feat.get("properties", {})
        coords = feat.get("geometry", {}).get("coordinates", [])
        name = props.get("name", "").strip()
        if not name or len(coords) < 2:
            continue
        
        all_stations.append({"name": name, "coords": coords})
        clean_name = name.lower().replace("metro station", "").replace("station", "").replace("-", " ").replace("  ", " ").strip()
        lookup[clean_name] = coords

    return lookup, all_stations


def find_best_station_coords(target_name: str, lookup: dict, all_stations: list):
    """Fuzzy-matches a target station name to its exact GPS coordinates."""
    clean = target_name.lower().replace("metro station", "").replace("station", "").replace("-", " ").replace("  ", " ").strip()
    if clean in lookup:
        return lookup[clean]

    # Substring match
    for name, coords in lookup.items():
        if clean in name or name in clean:
            return coords

    # Word intersection
    target_words = set(clean.split())
    best_match = None
    max_overlap = 0

    for item in all_stations:
        cand_words = set(item["name"].lower().split())
        overlap = len(target_words & cand_words)
        if overlap > max_overlap:
            max_overlap = overlap
            best_match = item["coords"]

    return best_match if max_overlap >= 1 else None


def build_metro_lines_geojson():
    print("=" * 65)
    print("  Building Official Connected Delhi Metro Lines GeoJSON")
    print("=" * 65)

    lookup, all_stations = load_station_lookup()
    print(f"  Loaded {len(all_stations)} station coordinates for track routing.")

    line_features = []

    for route in METRO_NETWORK_ROUTES:
        line_name = route["line_name"]
        color = route["color"]
        desc = route["description"]
        station_list = route["stations"]

        line_coords = []
        matched_count = 0

        for st_name in station_list:
            coords = find_best_station_coords(st_name, lookup, all_stations)
            if coords:
                line_coords.append(coords)
                matched_count += 1

        if len(line_coords) >= 2:
            line_features.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": line_coords
                },
                "properties": {
                    "line_name": line_name,
                    "color": color,
                    "description": desc,
                    "total_stations": len(line_coords),
                    "network": "Delhi Metro Rail Corporation (DMRC)"
                }
            })
            print(f"  [OK] {line_name:<30} -> {matched_count}/{len(station_list)} stations connected ({color})")
        else:
            print(f"  [WARN] {line_name} had insufficient station matches ({len(line_coords)})")

    geojson = {
        "type": "FeatureCollection",
        "city": "delhi",
        "type_layer": "metro_lines",
        "total_lines": len(line_features),
        "features": line_features
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2)

    print("\n" + "=" * 65)
    print(f"  [SUCCESS] Created {len(line_features)} Complete Connected Delhi Metro Lines!")
    print(f"  Saved to: {OUTPUT_FILE}")
    print("=" * 65)


if __name__ == "__main__":
    build_metro_lines_geojson()
