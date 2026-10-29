import json
import math
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


# =========================================================
# 1. PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="MediResQ AI - Hospital Map",
    page_icon="🏥",
    layout="wide",
)

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent.parent

HOSPITALS_FILE = BASE_DIR / "hospital_locations.csv"
ROUTES_FILE = BASE_DIR / "map_routes.json"
ANIMATION_FILE = BASE_DIR / "vehicle_animation.json"

INVENTORY_FILE = PROJECT_DIR / "data" / "inventory_batches.csv"

REDISTRIBUTION_FILE = (
    PROJECT_DIR / "data" / "distance_redistribution_plan.csv"
)

ANIMATION_DURATION = 30


# =========================================================
# 2. PAGE HEADER
# =========================================================

st.title("🏥 MediResQ AI")
st.subheader("Hospital Medicine Redistribution & Vehicle Simulation")

st.caption(
    "Interactive demonstration of hospital locations, medicine "
    "stock balances, proposed transfers, and simulated vehicle movement."
)


# =========================================================
# 3. LOAD DATA
# =========================================================

@st.cache_data
def load_json(path):
    if not path.exists():
        return []

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


@st.cache_data
def load_csv(path):
    if not path.exists():
        return pd.DataFrame()

    return pd.read_csv(path)


hospitals_df = load_csv(HOSPITALS_FILE)
routes_data = load_json(ROUTES_FILE)
animation_data = load_json(ANIMATION_FILE)

inventory_df = load_csv(INVENTORY_FILE)
transfers_df = load_csv(REDISTRIBUTION_FILE)


if hospitals_df.empty:
    st.error(f"No hospital records found: {HOSPITALS_FILE}")
    st.stop()


# =========================================================
# 4. NORMALIZE COLUMN NAMES
# =========================================================

def normalize_columns(dataframe):
    dataframe = dataframe.copy()
    dataframe.columns = [
        str(column).strip().lower()
        for column in dataframe.columns
    ]
    return dataframe


hospitals_df = normalize_columns(hospitals_df)

if not inventory_df.empty:
    inventory_df = normalize_columns(inventory_df)

if not transfers_df.empty:
    transfers_df = normalize_columns(transfers_df)


def find_column(dataframe, possible_names):
    for name in possible_names:
        if name.lower() in dataframe.columns:
            return name.lower()
    return None


id_column = find_column(
    hospitals_df,
    ["hospital_id", "id", "hospitalid"],
)

name_column = find_column(
    hospitals_df,
    ["hospital_name", "name", "hospital"],
)

latitude_column = find_column(
    hospitals_df,
    ["latitude", "lat", "location_lat", "hospital_latitude"],
)

longitude_column = find_column(
    hospitals_df,
    [
        "longitude",
        "lon",
        "lng",
        "location_lon",
        "location_lng",
        "hospital_longitude",
    ],
)


# =========================================================
# 5. CALCULATE HOSPITAL STOCK BALANCES
# =========================================================

required_inventory_columns = {
    "hospital_id",
    "quantity_in_stock",
    "expiry_date",
}

if inventory_df.empty:
    stock_summary = pd.DataFrame(
        columns=["total_stock", "usable_stock"]
    )

    st.warning(
        f"Inventory data could not be loaded from {INVENTORY_FILE}"
    )

elif not required_inventory_columns.issubset(inventory_df.columns):
    stock_summary = pd.DataFrame(
        columns=["total_stock", "usable_stock"]
    )

    missing_columns = (
        required_inventory_columns - set(inventory_df.columns)
    )

    st.error(
        "Inventory CSV is missing required columns: "
        + ", ".join(sorted(missing_columns))
    )

else:
    inventory_df["hospital_id"] = (
        inventory_df["hospital_id"]
        .astype(str)
        .str.strip()
    )

    inventory_df["quantity_in_stock"] = pd.to_numeric(
        inventory_df["quantity_in_stock"],
        errors="coerce",
    ).fillna(0)

    inventory_df["expiry_date"] = pd.to_datetime(
        inventory_df["expiry_date"],
        errors="coerce",
    )

    today = pd.Timestamp.now().normalize()

    # Expiry date must be today or later to count as unexpired.
    inventory_df["usable_stock"] = inventory_df.apply(
        lambda row: (
            row["quantity_in_stock"]
            if (
                pd.notna(row["expiry_date"])
                and row["expiry_date"] >= today
            )
            else 0
        ),
        axis=1,
    )

    stock_summary = (
        inventory_df.groupby("hospital_id")
        .agg(
            total_stock=("quantity_in_stock", "sum"),
            usable_stock=("usable_stock", "sum"),
        )
    )


stock_data = {}

for hospital_id, row in stock_summary.iterrows():
    stock_data[str(hospital_id).strip()] = {
        "total_stock": int(round(row["total_stock"])),
        "usable_stock": int(round(row["usable_stock"])),
    }


# =========================================================
# 6. PREPARE HOSPITAL LOCATIONS
# =========================================================

hospital_points = []

if latitude_column and longitude_column:

    for index, row in hospitals_df.iterrows():
        try:
            latitude = float(row[latitude_column])
            longitude = float(row[longitude_column])
        except (ValueError, TypeError):
            continue

        if not (
            math.isfinite(latitude)
            and math.isfinite(longitude)
            and -90 <= latitude <= 90
            and -180 <= longitude <= 180
        ):
            continue

        hospital_id = (
            str(row[id_column]).strip()
            if id_column and pd.notna(row[id_column])
            else str(index + 1)
        )

        hospital_name = (
            str(row[name_column])
            if name_column and pd.notna(row[name_column])
            else f"Hospital {hospital_id}"
        )

        stock = stock_data.get(
            hospital_id,
            {
                "total_stock": 0,
                "usable_stock": 0,
            },
        )

        hospital_points.append(
            {
                "id": hospital_id,
                "name": hospital_name,
                "lat": latitude,
                "lon": longitude,
                "total_stock": stock["total_stock"],
                "usable_stock": stock["usable_stock"],
            }
        )


if not hospital_points:
    st.error(
        "Hospital markers could not be created. "
        "Check hospital_locations.csv for valid latitude "
        "and longitude columns."
    )

    st.write("Columns found:")
    st.code(", ".join(hospitals_df.columns))

    st.stop()


# =========================================================
# 7. NORMALIZE ROUTE DATA
# =========================================================

def extract_records(data, keys):
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in keys:
            if isinstance(data.get(key), list):
                return data[key]

    return []


route_records = extract_records(
    routes_data,
    ["routes", "features", "results"],
)

animation_records = extract_records(
    animation_data,
    ["animations", "vehicles", "routes", "results"],
)


def get_route_id(record, index):
    return str(
        record.get(
            "transfer_id",
            record.get("route_id", record.get("id", index + 1)),
        )
    )


def extract_coordinates(record):
    if not isinstance(record, dict):
        return []

    geometry = record.get("geometry")

    if isinstance(geometry, dict):
        if geometry.get("type") == "LineString":
            result = []

            for point in geometry.get("coordinates", []):
                if len(point) >= 2:
                    try:
                        result.append([
                            float(point[1]),
                            float(point[0]),
                        ])
                    except (ValueError, TypeError):
                        continue

            return result

    for key in [
        "route_coordinates",
        "path",
        "points",
        "coordinates",
    ]:
        value = record.get(key)

        if not isinstance(value, list) or not value:
            continue

        if all(
            isinstance(point, (list, tuple))
            and len(point) >= 2
            for point in value
        ):
            try:
                return [
                    [float(point[0]), float(point[1])]
                    for point in value
                ]
            except (ValueError, TypeError):
                continue

    return []


def route_name(record, index):
    source = (
        record.get("from_hospital_name")
        or record.get("source_hospital")
        or record.get("from_hospital")
        or record.get("origin")
        or "Source"
    )

    destination = (
        record.get("to_hospital_name")
        or record.get("destination_hospital")
        or record.get("to_hospital")
        or record.get("destination")
        or "Destination"
    )

    return f"Route {index + 1}: {source} → {destination}"


routes = []

for index, record in enumerate(route_records):
    if not isinstance(record, dict):
        continue

    coordinates = extract_coordinates(record)

    if len(coordinates) < 2:
        continue

    routes.append(
        {
            "id": get_route_id(record, index),
            "name": route_name(record, index),
            "coordinates": coordinates,
            "source": str(
                record.get(
                    "from_hospital",
                    record.get("source_hospital_id", ""),
                )
            ),
            "destination": str(
                record.get(
                    "to_hospital",
                    record.get("destination_hospital_id", ""),
                )
            ),
        }
    )


# =========================================================
# 8. SUMMARY METRICS
# =========================================================

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Hospitals on Map", len(hospital_points))

with col2:
    st.metric("Available Routes", len(routes))

with col3:
    st.metric("Transfer Records", len(transfers_df))

with col4:
    st.metric(
        "Total Recorded Stock",
        f"{sum(item['total_stock'] for item in hospital_points):,}",
    )


st.caption(
    "Stock is calculated from inventory_batches.csv. "
    "Usable stock excludes batches with missing or past expiry dates. "
    "Quantities are summed across recorded medicine batches."
)


# =========================================================
# 9. SELECT ROUTE
# =========================================================

selected_route = None

if routes:
    selected_route_name = st.selectbox(
        "Select a redistribution route",
        [route["name"] for route in routes],
    )

    selected_route = next(
        route
        for route in routes
        if route["name"] == selected_route_name
    )

else:
    st.warning(
        "No valid route geometry was found. "
        "Hospitals will still be displayed on the map."
    )


# =========================================================
# 10. MATCH TRANSFERS
# =========================================================

matching_transfers = pd.DataFrame()

if selected_route is not None and not transfers_df.empty:

    source_column = find_column(
        transfers_df,
        ["from_hospital", "source_hospital", "source"],
    )

    destination_column = find_column(
        transfers_df,
        ["to_hospital", "destination_hospital", "destination"],
    )

    if source_column and destination_column:
        source_id = selected_route["source"]
        destination_id = selected_route["destination"]

        if source_id and destination_id:
            matching_transfers = transfers_df[
                (
                    transfers_df[source_column].astype(str)
                    == source_id
                )
                & (
                    transfers_df[destination_column].astype(str)
                    == destination_id
                )
            ].copy()


# =========================================================
# 11. HOSPITAL AND TRANSFER TABLES
# =========================================================

with st.expander("View hospital stock balances", expanded=True):
    stock_table = pd.DataFrame(hospital_points)[
        ["id", "name", "total_stock", "usable_stock"]
    ].rename(
        columns={
            "id": "Hospital ID",
            "name": "Hospital",
            "total_stock": "Total Recorded Stock",
            "usable_stock": "Usable Unexpired Stock",
        }
    )

    st.dataframe(
        stock_table,
        use_container_width=True,
        hide_index=True,
    )


with st.expander("View all hospital locations"):
    st.dataframe(
        pd.DataFrame(hospital_points),
        use_container_width=True,
        hide_index=True,
    )


with st.expander("View medicine inventory batches"):
    if inventory_df.empty:
        st.info("No inventory data was found.")
    else:
        st.dataframe(
            inventory_df,
            use_container_width=True,
            hide_index=True,
        )


with st.expander("View medicine redistribution records"):
    if transfers_df.empty:
        st.info(
            "No redistribution CSV was found or it contains no rows."
        )
    else:
        st.dataframe(
            transfers_df,
            use_container_width=True,
            hide_index=True,
        )


if selected_route is not None:
    st.markdown("### Selected Route")

    if matching_transfers.empty:
        st.info(
            "No transfer records matched this route. "
            "This does not mean that the route has been approved."
        )
    else:
        st.dataframe(
            matching_transfers,
            use_container_width=True,
            hide_index=True,
        )


# =========================================================
# 12. PREPARE MAP DATA
# =========================================================

hospitals_json = json.dumps(hospital_points)
routes_json = json.dumps(routes)

selected_route_json = json.dumps(
    selected_route if selected_route else {}
)


# =========================================================
# 13. INTERACTIVE LEAFLET MAP
# =========================================================

map_html = r"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<link
    rel="stylesheet"
    href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<style>
html, body {
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    font-family: Arial, sans-serif;
}

#map {
    width: 100%;
    height: 100%;
}

.hospital-marker {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 38px;
    height: 38px;
    background: white;
    border: 2px solid #9caf88;
    border-radius: 50%;
    font-size: 24px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
}

.vehicle-marker {
    font-size: 30px;
    text-align: center;
    width: 36px;
    height: 36px;
}

.control-panel {
    position: absolute;
    top: 12px;
    left: 60px;
    z-index: 1000;
    background: white;
    padding: 12px;
    border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.25);
    max-width: 280px;
}

button {
    margin-top: 8px;
    margin-right: 4px;
    padding: 7px 12px;
    border: none;
    border-radius: 5px;
    background: #9caf88;
    color: #172313;
    cursor: pointer;
    font-weight: bold;
}

#status {
    margin-top: 8px;
    font-size: 13px;
}

.legend {
    background: white;
    padding: 8px;
    border-radius: 6px;
    line-height: 1.8;
    box-shadow: 0 1px 5px rgba(0,0,0,0.2);
}
</style>
</head>

<body>

<div id="map"></div>

<div class="control-panel">
    <strong>🚑 Vehicle Simulation</strong>

    <div id="route-name" style="margin-top:5px;font-size:12px;"></div>

    <button onclick="startAnimation()">▶ Start</button>
    <button onclick="pauseAnimation()">⏸ Pause</button>
    <button onclick="resetAnimation()">↺ Reset</button>

    <div id="status">Ready</div>

    <div style="font-size:11px;color:#555;margin-top:6px;">
        Demonstration simulation — not live tracking.
    </div>
</div>

<script>
const hospitals = HOSPITAL_DATA;
const routes = ROUTE_DATA;
const selectedRoute = SELECTED_DATA;

function escapeHTML(value) {
    return String(value).replace(/[&<>"']/g, function(c) {
        return {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#039;"
        }[c];
    });
}

const map = L.map("map");

L.tileLayer(
    "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    {
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap contributors"
    }
).addTo(map);


// ---------------------------------------------------------
// HOSPITAL MARKERS WITH STOCK BALANCE
// ---------------------------------------------------------

const hospitalIcon = L.divIcon({
    className: "",
    html: '<div class="hospital-marker">🏥</div>',
    iconSize: [42, 42],
    iconAnchor: [21, 21]
});

const hospitalBounds = [];

hospitals.forEach(function(hospital) {
    const position = [
        Number(hospital.lat),
        Number(hospital.lon)
    ];

    if (
        !Number.isFinite(position[0]) ||
        !Number.isFinite(position[1])
    ) {
        return;
    }

    hospitalBounds.push(position);

    const totalStock = Number(hospital.total_stock || 0);
    const usableStock = Number(hospital.usable_stock || 0);

    L.marker(position, {
        icon: hospitalIcon
    })
    .addTo(map)
    .bindPopup(
        "<strong>" + escapeHTML(hospital.name) + "</strong><br>" +
        "Hospital ID: " + escapeHTML(hospital.id) + "<br>" +
        "Total recorded stock: " + totalStock.toLocaleString() +
        " units<br>" +
        "Usable, unexpired stock: " + usableStock.toLocaleString() +
        " units<br>" +
        "Location: " +
        position[0].toFixed(5) + ", " +
        position[1].toFixed(5)
    );
});


// ---------------------------------------------------------
// ROUTES
// ---------------------------------------------------------

routes.forEach(function(route) {
    const isSelected =
        selectedRoute &&
        String(route.id) === String(selectedRoute.id);

    L.polyline(route.coordinates, {
        color: isSelected ? "#cc5500" : "#2474d2",
        weight: isSelected ? 5 : 3,
        opacity: isSelected ? 0.95 : 0.45
    })
    .addTo(map)
    .bindPopup(escapeHTML(route.name));
});


// ---------------------------------------------------------
// MAP BOUNDS
// ---------------------------------------------------------

let bounds = [...hospitalBounds];

routes.forEach(function(route) {
    if (Array.isArray(route.coordinates)) {
        bounds = bounds.concat(route.coordinates);
    }
});

if (bounds.length > 0) {
    map.fitBounds(bounds, {
        padding: [35, 35],
        maxZoom: 14
    });
} else {
    map.setView([20.5937, 78.9629], 5);
}


// ---------------------------------------------------------
// VEHICLE ANIMATION
// ---------------------------------------------------------

let vehicle = null;
let animationFrame = null;
let running = false;
let startTime = null;
let elapsed = 0;

const duration = 30000;

const statusElement = document.getElementById("status");

if (
    selectedRoute &&
    selectedRoute.coordinates &&
    selectedRoute.coordinates.length >= 2
) {
    const coordinates = selectedRoute.coordinates;

    const vehicleIcon = L.divIcon({
        className: "",
        html: '<div class="vehicle-marker">🚑</div>',
        iconSize: [36, 36],
        iconAnchor: [18, 18]
    });

    vehicle = L.marker(coordinates[0], {
        icon: vehicleIcon,
        zIndexOffset: 1000
    }).addTo(map);

    vehicle.bindPopup("Simulated redistribution vehicle");

    document.getElementById("route-name").textContent =
        selectedRoute.name;

    function positionAt(progress) {
        const scaled = progress * (coordinates.length - 1);

        const index = Math.min(
            Math.floor(scaled),
            coordinates.length - 2
        );

        const fraction = scaled - index;

        const start = coordinates[index];
        const end = coordinates[index + 1];

        return [
            start[0] + (end[0] - start[0]) * fraction,
            start[1] + (end[1] - start[1]) * fraction
        ];
    }

    function animate(timestamp) {
        if (!running) {
            return;
        }

        if (startTime === null) {
            startTime = timestamp;
        }

        const currentElapsed = elapsed + timestamp - startTime;

        const progress = Math.min(
            currentElapsed / duration,
            1
        );

        vehicle.setLatLng(positionAt(progress));

        statusElement.textContent =
            "Simulation progress: " +
            Math.round(progress * 100) + "%";

        if (progress >= 1) {
            running = false;
            elapsed = 0;
            startTime = null;

            statusElement.textContent =
                "Journey simulation completed";

            return;
        }

        animationFrame = requestAnimationFrame(animate);
    }

    window.startAnimation = function() {
        if (running) {
            return;
        }

        if (elapsed >= duration) {
            elapsed = 0;
        }

        running = true;
        startTime = null;

        animationFrame = requestAnimationFrame(animate);
    };

    window.pauseAnimation = function() {
        if (!running) {
            return;
        }

        running = false;

        if (startTime !== null) {
            elapsed += performance.now() - startTime;
        }

        startTime = null;

        if (animationFrame !== null) {
            cancelAnimationFrame(animationFrame);
        }

        statusElement.textContent = "Simulation paused";
    };

    window.resetAnimation = function() {
        running = false;

        if (animationFrame !== null) {
            cancelAnimationFrame(animationFrame);
        }

        elapsed = 0;
        startTime = null;

        vehicle.setLatLng(coordinates[0]);

        statusElement.textContent = "Ready to start";
    };

} else {
    document.getElementById("route-name").textContent =
        "No valid route selected";

    statusElement.textContent =
        "Hospital map ready; vehicle route unavailable";

    window.startAnimation = function() {};
    window.pauseAnimation = function() {};
    window.resetAnimation = function() {};
}


// ---------------------------------------------------------
// LEGEND
// ---------------------------------------------------------

const legend = L.control({position: "bottomright"});

legend.onAdd = function() {
    const div = L.DomUtil.create("div", "legend");

    div.innerHTML =
        "<strong>Map Legend</strong><br>" +
        "🏥 Hospital location<br>" +
        "🚑 Simulated vehicle<br>" +
        '<span style="color:#cc5500;">━━</span> Selected route<br>' +
        '<span style="color:#2474d2;">━━</span> Other routes';

    return div;
};

legend.addTo(map);

</script>

</body>
</html>
"""

map_html = (
    map_html
    .replace("HOSPITAL_DATA", hospitals_json)
    .replace("ROUTE_DATA", routes_json)
    .replace("SELECTED_DATA", selected_route_json)
)


# =========================================================
# 14. DISPLAY MAP
# =========================================================

st.markdown("### Interactive Hospital Network")

st.caption(
    "Click a hospital marker to view its name, ID, and stock balance. "
    "Select a route above to view its simulated vehicle journey."
)

components.html(
    map_html,
    height=650,
    scrolling=False,
)