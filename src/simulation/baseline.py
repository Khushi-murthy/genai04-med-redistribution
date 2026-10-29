import pandas as pd
from pathlib import Path

# Locate the project and data folders
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_FOLDER = PROJECT_ROOT / "data"

INVENTORY_FILE = DATA_FOLDER / "inventory_batches.csv"


def main():
    print("\n===== MediResQ AI: Redistribution Baseline =====\n")

    if not INVENTORY_FILE.exists():
        print(f"ERROR: Inventory file not found: {INVENTORY_FILE}")
        return

    inventory = pd.read_csv(INVENTORY_FILE)

    # Convert expiry dates and stock quantities
    inventory["expiry_date"] = pd.to_datetime(
        inventory["expiry_date"], errors="coerce"
    )

    inventory["quantity_in_stock"] = pd.to_numeric(
        inventory["quantity_in_stock"], errors="coerce"
    )

    # Exclude expired, invalid, and unavailable stock
    today = pd.Timestamp.today().normalize()

    eligible = inventory[
        inventory["expiry_date"].notna()
        & (inventory["expiry_date"] >= today)
        & inventory["quantity_in_stock"].notna()
        & (inventory["quantity_in_stock"] > 0)
    ].copy()

    # First Expiry, First Out (FEFO)
    eligible = eligible.sort_values(
        by=["expiry_date", "drug_name"]
    )

    print(f"Total inventory records: {len(inventory)}")
    print(f"Eligible records: {len(eligible)}")
    print(f"Excluded records: {len(inventory) - len(eligible)}")

    print("\n===== Eligible Stock: Earliest Expiry First =====\n")

    columns = [
        "drug_name",
        "quantity_in_stock",
        "expiry_date",
        "hospital_id",
        "batch_id",
    ]

    print(eligible[columns].to_string(index=False))

    # Save eligible records without modifying the original dataset
    output_file = DATA_FOLDER / "eligible_inventory.csv"
    eligible.to_csv(output_file, index=False)

    print(f"\nEligible inventory saved to: {output_file}")
    print("\nBaseline inventory preparation completed.")


if __name__ == "__main__":
    main()