import pandas as pd
from pathlib import Path

# ==========================================
# 1. PROJECT PATHS
# ==========================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_FOLDER = PROJECT_ROOT / "data"

INVENTORY_FILE = DATA_FOLDER / "inventory_batches.csv"
DEMAND_FILE = DATA_FOLDER / "hospital_demand.csv"
HOSPITAL_FILE = DATA_FOLDER / "hospitals.csv"

OUTPUT_FILE = DATA_FOLDER / "redistribution_plan.csv"


# ==========================================
# 2. LOAD AND VALIDATE DATA
# ==========================================

def load_data():
    """Load the inventory, demand, and hospital datasets."""

    print("\n===== MediResQ AI: Redistribution System =====\n")

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

    inventory_columns = [
        "hospital_id",
        "drug_id",
        "drug_name",
        "quantity_in_stock",
        "expiry_date",
    ]

    demand_columns = [
        "hospital_id",
        "drug_id",
        "simulated_daily_demand",
        "simulated_7_day_demand",
    ]

    for column in inventory_columns:
        if column not in inventory.columns:
            raise ValueError(
                f"Inventory file is missing column: {column}"
            )

    for column in demand_columns:
        if column not in demand.columns:
            raise ValueError(
                f"Demand file is missing column: {column}"
            )

    if "hospital_id" not in hospitals.columns:
        raise ValueError(
            "Hospital file is missing column: hospital_id"
        )

    print(f"Inventory records: {len(inventory)}")
    print(f"Demand records: {len(demand)}")
    print(f"Hospital records: {len(hospitals)}")

    print("\nAll required files and columns are available.")

    return inventory, demand, hospitals


# ==========================================
# 3. CALCULATE SURPLUS AND SHORTAGE
# ==========================================

def calculate_surplus_shortage(inventory, demand):
    """
    Calculate potential surplus and shortage for each
    hospital and medicine.

    Expired stock is excluded from available inventory.
    """

    inventory = inventory.copy()
    demand = demand.copy()

    # Convert values to appropriate data types
    inventory["expiry_date"] = pd.to_datetime(
        inventory["expiry_date"],
        errors="coerce",
    )

    inventory["quantity_in_stock"] = pd.to_numeric(
        inventory["quantity_in_stock"],
        errors="coerce",
    )

    demand["simulated_7_day_demand"] = pd.to_numeric(
        demand["simulated_7_day_demand"],
        errors="coerce",
    )

    # Use the current date to exclude expired inventory
    today = pd.Timestamp.today().normalize()

    # Keep only stock with valid future expiry dates
    # and positive quantities
    eligible_inventory = inventory[
        (inventory["expiry_date"] >= today)
        & (inventory["quantity_in_stock"] > 0)
    ].copy()

    # Summarize eligible stock by hospital and medicine
    stock_summary = (
        eligible_inventory
        .groupby(
            ["hospital_id", "drug_id", "drug_name"],
            as_index=False,
        )["quantity_in_stock"]
        .sum()
    )

    # Summarize demand by hospital and medicine
    demand_summary = (
        demand
        .groupby(
            ["hospital_id", "drug_id"],
            as_index=False,
        )["simulated_7_day_demand"]
        .sum()
    )

    # Combine stock and demand
    summary = pd.merge(
        stock_summary,
        demand_summary,
        on=["hospital_id", "drug_id"],
        how="outer",
    )

    # Fill missing medicine names using the inventory catalogue
    medicine_names = (
        inventory[["drug_id", "drug_name"]]
        .dropna(subset=["drug_id", "drug_name"])
        .drop_duplicates(subset=["drug_id"])
        .set_index("drug_id")["drug_name"]
    )

    summary["drug_name"] = summary["drug_name"].fillna(
        summary["drug_id"].map(medicine_names)
    )

    # Replace missing stock or demand values with zero
    summary["quantity_in_stock"] = (
        summary["quantity_in_stock"].fillna(0)
    )

    summary["simulated_7_day_demand"] = (
        summary["simulated_7_day_demand"].fillna(0)
    )

    # Calculate potential surplus
    summary["surplus"] = (
        summary["quantity_in_stock"]
        - summary["simulated_7_day_demand"]
    ).clip(lower=0)

    # Calculate shortage
    summary["shortage"] = (
        summary["simulated_7_day_demand"]
        - summary["quantity_in_stock"]
    ).clip(lower=0)

    # Display the results
    print("\n===== Surplus and Shortage Summary =====")

    print(
        "Eligible inventory records:",
        len(eligible_inventory),
    )

    print(
        "Hospital-medicine combinations:",
        len(summary),
    )

    print(
        "Total potential surplus:",
        f"{summary['surplus'].sum():.0f}",
    )

    print(
        "Total potential shortage:",
        f"{summary['shortage'].sum():.0f}",
    )

    print("\nSample results:")

    print(
        summary.head(10).to_string(index=False)
    )

    return summary, eligible_inventory

# ==========================================
# 4. REDISTRIBUTION PLANNING
# ==========================================

def create_redistribution_plan(summary, eligible_inventory):
    """Match medicine surplus with shortages at other hospitals."""

    transfers = []

    # Work through one medicine at a time
    for drug_id in summary["drug_id"].dropna().unique():

        medicine_data = summary[
            summary["drug_id"] == drug_id
        ].copy()

        donors = medicine_data[
            medicine_data["surplus"] > 0
        ].copy()

        recipients = medicine_data[
            medicine_data["shortage"] > 0
        ].copy()

        # Match donor hospitals with needy hospitals
        for donor_index, donor in donors.iterrows():

            available_surplus = float(donor["surplus"])

            for recipient_index, recipient in recipients.iterrows():

                if donor["hospital_id"] == recipient["hospital_id"]:
                    continue

                if available_surplus <= 0:
                    break

                required_quantity = float(recipient["shortage"])

                if required_quantity <= 0:
                    continue

                transfer_quantity = min(
                    available_surplus,
                    required_quantity,
                )

                # Record the proposed transfer
                transfers.append({
                    "drug_id": drug_id,
                    "drug_name": donor["drug_name"],
                    "from_hospital": donor["hospital_id"],
                    "to_hospital": recipient["hospital_id"],
                    "transfer_quantity": transfer_quantity,
                    "transfer_status": "PROPOSED",
                    "data_origin": "SIMULATED",
                })

                # Reduce remaining quantities in this plan
                available_surplus -= transfer_quantity

                recipients.loc[
                    recipient_index, "shortage"
                ] -= transfer_quantity

    # Convert proposed transfers into a DataFrame
    plan_columns = [
        "drug_id",
        "drug_name",
        "from_hospital",
        "to_hospital",
        "transfer_quantity",
        "transfer_status",
        "data_origin",
    ]

    plan = pd.DataFrame(
        transfers,
        columns=plan_columns,
    )

    # Save the plan
    plan.to_csv(OUTPUT_FILE, index=False)

    print("\n===== Redistribution Plan =====")
    print(f"Proposed transfers: {len(plan)}")

    if not plan.empty:
        print(
            "Total proposed units to transfer:",
            f"{plan['transfer_quantity'].sum():.0f}",
        )

        print("\nSample proposed transfers:")
        print(plan.head(10).to_string(index=False))
    else:
        print("No feasible transfers were found.")

    print(f"\nPlan saved to: {OUTPUT_FILE}")

    return plan
# ==========================================
# 4. MAIN PROGRAM
# ==========================================

if __name__ == "__main__":

    inventory, demand, hospitals = load_data()

    summary, eligible_inventory = (
        calculate_surplus_shortage(inventory, demand)
    )

    plan = create_redistribution_plan(
        summary,
        eligible_inventory,
    )

    print(
        "\nMediResQ AI redistribution simulation "
        "completed successfully!"
    )