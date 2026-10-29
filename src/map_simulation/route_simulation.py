import csv
import json
import time
from pathlib import Path

import requests

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
MAP_DIR = Path(__file__).resolve().parent

HOSPITAL_FILE = MAP_DIR / "hospital_locations.csv"
TRANSFER_FILE = DATA_DIR / "distance_redistribution_plan.csv"
OUTPUT_FILE = MAP_DIR / "map_routes.json"

OSRM_URL = "https://router.project-osrm.org/route/v1/driving/"


def load_csv(file_path):
    with open(file_path, "r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def main():
    if not HOSPITAL_FILE.exists():
        raise FileNotFoundError(f"Hospital location file not found: {HOSPITAL_FILE}")

    if not TRANSFER_FILE.exists():
        raise FileNotFoundError(f"Transfer plan not found: {TRANSFER_FILE}")

    hospitals = load_csv(HOSPITAL_FILE)
    transfers = load_csv(TRANSFER_FILE)

    hospital_lookup = {row["hospital_id"]: row for row in hospitals}
    routes = []
    failed_routes = []

    for index, transfer in enumerate(transfers, start=1):
        donor_id = transfer["from_hospital"]
        recipient_id = transfer["to_hospital"]

        if donor_id not in hospital_lookup or recipient_id not in hospital_lookup:
            failed_routes.append({
                "transfer_number": index,
                "reason": "Hospital ID is missing from hospital_locations.csv",
                "donor": donor_id,
                "recipient": recipient_id,
            })
            continue

        donor = hospital_lookup[donor_id]
        recipient = hospital_lookup[recipient_id]

        # OSRM expects longitude,latitude
        coordinates = (
            f'{donor["longitude"]},{donor["latitude"]};'
            f'{recipient["longitude"]},{recipient["latitude"]}'
        )

        try:
            response = requests.get(
                OSRM_URL + coordinates,
                params={"overview": "full", "geometries": "geojson"},
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()

            if result.get("code") != "Ok" or not result.get("routes"):
                failed_routes.append({
                    "transfer_number": index,
                    "reason": result.get("message", "No route returned"),
                    "donor": donor_id,
                    "recipient": recipient_id,
                })
                continue

            route = result["routes"][0]

            routes.append({
                "transfer_number": index,
                "from_hospital": donor_id,
                "from_hospital_name": donor["hospital_name"],
                "to_hospital": recipient_id,
                "to_hospital_name": recipient["hospital_name"],
                "transfer_quantity": transfer.get("transfer_quantity"),
                "distance_km": round(route["distance"] / 1000, 2),
                "estimated_duration_minutes": round(route["duration"] / 60, 1),
                "geometry": route["geometry"],
                "data_origin": "SIMULATED_TRANSFER_REAL_ROAD_ROUTE",
            })

            print(
                f"Route {index}/{len(transfers)}: "
                f"{donor_id} -> {recipient_id} "
                f"({route['distance'] / 1000:.2f} km)"
            )

            # Avoid sending requests too quickly to the public routing service.
            time.sleep(1)

        except (requests.RequestException, ValueError, KeyError) as error:
            failed_routes.append({
                "transfer_number": index,
                "reason": str(error),
                "donor": donor_id,
                "recipient": recipient_id,
            })
            print(f"Route {index} failed: {error}")

    output = {
        "description": (
            "Medicine transfers are simulated. Road routes are requested "
            "from OSRM using the supplied hospital coordinates."
        ),
        "hospital_count": len(hospitals),
        "transfer_count": len(transfers),
        "successful_route_count": len(routes),
        "failed_route_count": len(failed_routes),
        "routes": routes,
        "failed_routes": failed_routes,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(output, file, indent=2)

    print("\nRoute generation finished.")
    print(f"Successful routes: {len(routes)}")
    print(f"Failed routes: {len(failed_routes)}")
    print(f"Output saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()