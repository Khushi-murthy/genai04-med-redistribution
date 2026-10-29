import pandas as pd
from pathlib import Path
from math import sqrt

# ==========================================
# 1. PROJECT PATHS
# ==========================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_FOLDER = PROJECT_ROOT / "data"

INVENTORY_FILE = DATA_FOLDER / "inventory_batches.csv"
DEMAND_FILE = DATA_FOLDER / "hospital_demand.csv"
HOSPITAL_FILE = DATA_FOLDER / "hospitals.csv"

OUTPUT_FILE = DATA_FOLDER / "distance_redistribution_plan.csv"


# ==========================================
# 2. LOAD DATA
# ==========================================

def load_data():
    """Load the inventory, demand, and hospital datasets."""

    required_files = [
        INVENTORY_FILE,
        DEMAND_FILE,
        HOSPITAL_FILE,
    ]

    for file_path in required_files:
        if not file_path.exists():
            raise FileNotFoundError(
                f"Required file not found: {file_path}"
            )

    inventory = pd.read_csv(INVENTORY_FILE)
    demand = pd.read_csv(DEMAND_FILE)
    hospitals = pd.read_csv(HOSPITAL_FILE)

    required_inventory_columns = [
        "hospital_id",
        "drug_id",
        "drug_name",
        "quantity_in_stock",
        "expiry_date",
    ]

    required_demand_columns = [
        "hospital_id",
        "drug_id",
        "simulated_7_day_demand",
    ]

    required_hospital_columns = [
        "hospital_id",
        "hospital_name",
        "hospital_type",
        "location_x",
        "location_y",
        "daily_patient_capacity",
    ]

    for column in required_inventory_columns:
        if column not in inventory.columns:
            raise ValueError(
                f"Inventory is missing column: {column}"
            )

    for column in required_demand_columns:
        if column not in demand.columns:
            raise ValueError(
                f"Demand is missing column: {column}"
            )

    for column in required_hospital_columns:
        if column not in hospitals.columns:
            raise ValueError(
                f"Hospital data is missing column: {column}"
            )

    print("\n===== MediResQ AI: Distance-Aware Redistribution =====")
    print("Inventory records:", len(inventory))
    print("Demand records:", len(demand))
    print("Hospitals loaded:", len(hospitals))

    return inventory, demand, hospitals


# ==========================================
# 3. CALCULATE DISTANCE
# ==========================================

def calculate_distance(hospital_a, hospital_b):
    """Calculate Euclidean distance between simulated coordinates."""

    dx = float(hospital_a["location_x"]) - float(
        hospital_b["location_x"]
    )

    dy = float(hospital_a["location_y"]) - float(
        hospital_b["location_y"]
    )

    return sqrt(dx**2 + dy**2)


# ==========================================
# 4. CALCULATE NEED PRIORITY
# ==========================================

def calculate_need_priority(shortage, hospital_type):
    """
    Calculate an experimental priority score.

    The shortage is the main factor. A configurable fairness
    multiplier gives small clinics additional consideration.
    This is a simulation score, not clinical triage.
    """

    shortage = max(0.0, float(shortage))

    fairness_bonus = {
        "Small Clinic": 1.20,
        "Medium Hospital": 1.10,
        "Large Hospital": 1.00,
    }

    bonus = fairness_bonus.get(hospital_type, 1.00)

    return shortage * bonus


# ==========================================
# 5. PREPARE AVAILABLE STOCK AND DEMAND
# ==========================================

def prepare_summary(inventory, demand):
    """Calculate eligible stock, shortages, and potential surplus."""

    inventory = inventory.copy()
    demand = demand.copy()

    inventory["expiry_date"] = pd.to_datetime(
        inventory["expiry_date"],
        errors="coerce",
    )

    inventory["quantity_in_stock"] = pd.to_numeric(
        inventory["quantity_in_stock"],
        errors="coerce",
    ).fillna(0)

    demand["simulated_7_day_demand"] = pd.to_numeric(
        demand["simulated_7_day_demand"],
        errors="coerce",
    ).fillna(0)

    today = pd.Timestamp.today().normalize()

    # Exclude expired, invalid-date, and non-positive stock.
    eligible = inventory[
        (inventory["expiry_date"] >= today)
        & (inventory["quantity_in_stock"] > 0)
    ].copy()

    stock_summary = (
        eligible.groupby(
            ["hospital_id", "drug_id", "drug_name"],
            as_index=False,
        )["quantity_in_stock"].sum()
    )

    demand_summary = (
        demand.groupby(
            ["hospital_id", "drug_id"],
            as_index=False,
        )["simulated_7_day_demand"].sum()
    )

    summary = pd.merge(
        stock_summary,
        demand_summary,
        on=["hospital_id", "drug_id"],
        how="outer",
    )

    # Restore medicine names for combinations with no eligible stock.
    medicine_names = (
        inventory[["drug_id", "drug_name"]]
        .dropna(subset=["drug_id", "drug_name"])
        .drop_duplicates(subset=["drug_id"])
        .set_index("drug_id")["drug_name"]
    )

    summary["drug_name"] = summary["drug_name"].fillna(
        summary["drug_id"].map(medicine_names)
    )

    summary["quantity_in_stock"] = (
        summary["quantity_in_stock"].fillna(0)
    )

    summary["simulated_7_day_demand"] = (
        summary["simulated_7_day_demand"].fillna(0)
    )

    summary["surplus"] = (
        summary["quantity_in_stock"]
        - summary["simulated_7_day_demand"]
    ).clip(lower=0)

    summary["shortage"] = (
        summary["simulated_7_day_demand"]
        - summary["quantity_in_stock"]
    ).clip(lower=0)

    return summary, eligible


# ==========================================
# 6. DISTANCE-AWARE REDISTRIBUTION
# ==========================================

def create_distance_redistribution_plan(
    summary,
    eligible_inventory,
    hospitals,
):
    """
    Propose transfers to shortage hospitals.

    Recipients are ranked by need priority and then distance.
    Donor surplus and recipient shortage are reduced after
    each proposed transfer to prevent double allocation.

    This is a simulation, not a real-world medical dispatch system.
    """

    transfers = []

    # Make independent working copies.
    working = summary.copy()

    # Build a lookup table for hospital details.
    hospital_lookup = hospitals.set_index("hospital_id")

    # Process each medicine independently.
    for drug_id in working["drug_id"].dropna().unique():

        medicine_data = working[
            working["drug_id"] == drug_id
        ].copy()

        donors = medicine_data[
            medicine_data["surplus"] > 0
        ].copy()

        recipients = medicine_data[
            medicine_data["shortage"] > 0
        ].copy()

        # Process each donor separately.
        for donor_index, donor in donors.iterrows():

            donor_id = donor["hospital_id"]

            if donor_id not in hospital_lookup.index:
                continue

            available_surplus = float(donor["surplus"])

            donor_hospital = hospital_lookup.loc[donor_id]

            # Rank recipients by need priority, then distance.
            recipient_candidates = []

            for recipient_index, recipient in recipients.iterrows():

                recipient_id = recipient["hospital_id"]

                if recipient_id == donor_id:
                    continue

                if float(recipient["shortage"]) <= 0:
                    continue

                if recipient_id not in hospital_lookup.index:
                    continue

                recipient_hospital = hospital_lookup.loc[
                    recipient_id
                ]

                distance = calculate_distance(
                    donor_hospital,
                    recipient_hospital,
                )

                priority = calculate_need_priority(
                    recipient["shortage"],
                    recipient_hospital["hospital_type"],
                )

                recipient_candidates.append({
                    "recipient_index": recipient_index,
                    "recipient_id": recipient_id,
                    "distance": distance,
                    "priority": priority,
                })

            # Higher priority first; closer hospital wins ties.
            recipient_candidates.sort(
                key=lambda item: (
                    -item["priority"],
                    item["distance"],
                    item["recipient_id"],
                )
            )

            for candidate in recipient_candidates:

                if available_surplus <= 0:
                    break

                recipient_index = candidate["recipient_index"]

                remaining_shortage = float(
                    recipients.loc[
                        recipient_index, "shortage"
                    ]
                )

                if remaining_shortage <= 0:
                    continue

                transfer_quantity = min(
                    available_surplus,
                    remaining_shortage,
                )

                if transfer_quantity <= 0:
                    continue

                recipient_id = candidate["recipient_id"]

                transfers.append({
                    "drug_id": drug_id,
                    "drug_name": donor["drug_name"],
                    "from_hospital": donor_id,
                    "to_hospital": recipient_id,
                    "transfer_quantity": transfer_quantity,
                    "simulated_distance": candidate["distance"],
                    "recipient_priority": candidate["priority"],
                    "transfer_status": "PROPOSED",
                    "data_origin": "SIMULATED",
                })

                # Reduce available donor stock and recipient need.
                available_surplus -= transfer_quantity

                recipients.loc[
                    recipient_index, "shortage"
                ] -= transfer_quantity

    columns = [
        "drug_id",
        "drug_name",
        "from_hospital",
        "to_hospital",
        "transfer_quantity",
        "simulated_distance",
        "recipient_priority",
        "transfer_status",
        "data_origin",
    ]

    plan = pd.DataFrame(transfers, columns=columns)

    plan.to_csv(OUTPUT_FILE, index=False)

    print("\n===== Redistribution Results =====")
    print("Eligible inventory records:", len(eligible_inventory))
    print("Proposed transfer records:", len(plan))

    if not plan.empty:
        print(
            "Total proposed units:",
            f"{plan['transfer_quantity'].sum():.0f}",
        )

        print(
            "Average simulated distance:",
            f"{plan['simulated_distance'].mean():.2f}",
        )

        print("\nSample proposed transfers:")
        print(plan.head(10).to_string(index=False))
    else:
        print("No feasible transfers found.")

    print(f"\nPlan saved to: {OUTPUT_FILE}")

    return plan


# ==========================================
# 7. MAIN PROGRAM
# ==========================================

if __name__ == "__main__":

    inventory, demand, hospitals = load_data()

    summary, eligible_inventory = prepare_summary(
        inventory,
        demand,
    )

    print("\n===== Surplus and Shortage Summary =====")
    print("Hospital-medicine combinations:", len(summary))
    print(
        "Total potential surplus:",
        f"{summary['surplus'].sum():.0f}",
    )
    print(
        "Total potential shortage:",
        f"{summary['shortage'].sum():.0f}",
    )

    plan = create_distance_redistribution_plan(
        summary,
        eligible_inventory,
        hospitals,
    )

    print("\nDistance-aware simulation completed successfully!")