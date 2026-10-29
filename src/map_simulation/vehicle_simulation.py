import json
import math
from pathlib import Path

MAP_DIR = Path(__file__).resolve().parent
ROUTES_FILE = MAP_DIR / "map_routes.json"
OUTPUT_FILE = MAP_DIR / "vehicle_animation.json"

# Generate one vehicle position every 5 simulated seconds.
FRAME_INTERVAL_SECONDS = 5


def haversine_km(point_a, point_b):
    """Calculate approximate distance between two [longitude, latitude] points."""
    lon1, lat1 = point_a
    lon2, lat2 = point_b

    earth_radius_km = 6371.0

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(delta_lon / 2) ** 2
    )

    return 2 * earth_radius_km * math.asin(math.sqrt(value))


def cumulative_distances(coordinates):
    """Calculate distance travelled along the route up to each coordinate."""
    distances = [0.0]

    for index in range(1, len(coordinates)):
        segment = haversine_km(
            coordinates[index - 1],
            coordinates[index],
        )
        distances.append(distances[-1] + segment)

    return distances


def position_at_distance(coordinates, distances, target_distance):
    """Find an interpolated vehicle position along the road geometry."""
    if target_distance <= 0:
        return coordinates[0]

    if target_distance >= distances[-1]:
        return coordinates[-1]

    for index in range(1, len(distances)):
        if distances[index] >= target_distance:
            segment_start = distances[index - 1]
            segment_end = distances[index]
            segment_length = segment_end - segment_start

            if segment_length == 0:
                return coordinates[index]

            fraction = (
                (target_distance - segment_start) / segment_length
            )

            lon1, lat1 = coordinates[index - 1]
            lon2, lat2 = coordinates[index]

            longitude = lon1 + fraction * (lon2 - lon1)
            latitude = lat1 + fraction * (lat2 - lat1)

            return [longitude, latitude]

    return coordinates[-1]


def build_animation(route):
    geometry = route.get("geometry", {})
    coordinates = geometry.get("coordinates", [])

    if len(coordinates) < 2:
        raise ValueError("Route must contain at least two coordinates.")

    distances = cumulative_distances(coordinates)
    total_geometry_distance = distances[-1]

    if total_geometry_distance <= 0:
        raise ValueError("Route geometry has zero length.")

    # Use the route service's estimated duration for animation timing.
    duration_minutes = float(
        route.get("estimated_duration_minutes") or 1
    )
    duration_seconds = max(1, round(duration_minutes * 60))

    frame_times = list(
        range(0, duration_seconds, FRAME_INTERVAL_SECONDS)
    )

    if not frame_times or frame_times[-1] != duration_seconds:
        frame_times.append(duration_seconds)

    frames = []

    for elapsed_seconds in frame_times:
        progress = min(elapsed_seconds / duration_seconds, 1.0)

        target_distance = progress * total_geometry_distance
        longitude, latitude = position_at_distance(
            coordinates,
            distances,
            target_distance,
        )

        frames.append({
            "elapsed_seconds": elapsed_seconds,
            "progress": round(progress, 4),
            "position": {
                "longitude": round(longitude, 7),
                "latitude": round(latitude, 7),
            },
        })

    return {
        "transfer_number": route.get("transfer_number"),
        "from_hospital": route.get("from_hospital"),
        "from_hospital_name": route.get("from_hospital_name"),
        "to_hospital": route.get("to_hospital"),
        "to_hospital_name": route.get("to_hospital_name"),
        "transfer_quantity": route.get("transfer_quantity"),
        "distance_km": route.get("distance_km"),
        "estimated_duration_minutes": duration_minutes,
        "frames": frames,
    }


def main():
    if not ROUTES_FILE.exists():
        raise FileNotFoundError(
            f"Route file not found: {ROUTES_FILE}\n"
            "Run route_simulation.py first."
        )

    with open(ROUTES_FILE, "r", encoding="utf-8") as file:
        route_data = json.load(file)

    animations = []
    failed = []

    for route in route_data.get("routes", []):
        try:
            animations.append(build_animation(route))
        except (ValueError, TypeError, KeyError) as error:
            failed.append({
                "transfer_number": route.get("transfer_number"),
                "reason": str(error),
            })

    output = {
        "description": (
            "Vehicle animation positions follow the road geometry. "
            "Medicine transfers are simulated; timing is illustrative, "
            "not live traffic or a real delivery schedule."
        ),
        "frame_interval_seconds": FRAME_INTERVAL_SECONDS,
        "route_count": len(route_data.get("routes", [])),
        "successful_animation_count": len(animations),
        "failed_animation_count": len(failed),
        "animations": animations,
        "failed_animations": failed,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(output, file, indent=2)

    print("Vehicle animation data generated.")
    print(f"Successful animations: {len(animations)}")
    print(f"Failed animations: {len(failed)}")
    print(f"Output saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()