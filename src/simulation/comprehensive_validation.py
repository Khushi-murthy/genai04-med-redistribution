from pathlib import Path

import pandas as pd


# --------------------------------------------------
# MediResQ AI - Comprehensive Transfer Validation
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"

INVENTORY_FILE = DATA_DIR / "inventory_batches.csv"
HOSPITALS_FILE = DATA_DIR / "hospitals.csv"
BASELINE_PLAN_FILE = DATA_DIR / "redistribution_plan.csv"
DISTANCE_PLAN_FILE = DATA_DIR / "distance_redistribution_plan.csv"

REQUIRED_INVENTORY_COLUMNS = {
    "hospital_id",
    "drug_id",
    "quantity_in_stock",
    "expiry_date",
}

REQUIRED_HOSPITAL_COLUMNS = {"hospital_id"}

REQUIRED_PLAN_COLUMNS = {
    "drug_id",
    "from_hospital",
    "to_hospital",
    "transfer_quantity",
}


def load_csv(file_path):
    """Load a CSV file and report a clear error if it is unavailable."""
    if not file_path.exists():
        raise FileNotFoundError(f"Required file not found: {file_path}")

    return pd.read_csv(file_path)


def check_required_columns(dataframe, required_columns, file_name):
    """Check whether a CSV contains all required columns."""
    missing = required_columns - set(dataframe.columns)

    if missing:
        raise ValueError(
            f"{file_name} is missing required columns: {sorted(missing)}"
        )


def prepare_eligible_inventory(inventory):
    """
    Keep inventory with valid expiry dates, positive stock,
    and an expiry date that has not passed.
    """
    inventory = inventory.copy()

    inventory["expiry_date"] = pd.to_datetime(
        inventory["expiry_date"],
        errors="coerce"
    )

    inventory["quantity_in_stock"] = pd.to_numeric(
        inventory["quantity_in_stock"],
        errors="coerce"
    )

    today = pd.Timestamp.today().normalize()

    eligible = inventory[
        inventory["expiry_date"].notna()
        & (inventory["expiry_date"] >= today)
        & (inventory["quantity_in_stock"] > 0)
    ].copy()

    return eligible


def validate_plan(plan_name, plan, inventory, hospitals):
    """Validate one redistribution plan and print its findings."""

    print("\n" + "=" * 65)
    print(f"VALIDATING: {plan_name}")
    print("=" * 65)

    plan = plan.copy()
    eligible_inventory = prepare_eligible_inventory(inventory)

    # Convert quantities to numeric values for checking.
    plan["transfer_quantity"] = pd.to_numeric(
        plan["transfer_quantity"],
        errors="coerce"
    )

    known_hospitals = set(hospitals["hospital_id"].dropna().astype(str))
    known_drugs = set(inventory["drug_id"].dropna().astype(str))

    plan["from_hospital"] = plan["from_hospital"].astype("string")
    plan["to_hospital"] = plan["to_hospital"].astype("string")
    plan["drug_id"] = plan["drug_id"].astype("string")

    eligible_inventory["hospital_id"] = (
        eligible_inventory["hospital_id"].astype("string")
    )
    eligible_inventory["drug_id"] = (
        eligible_inventory["drug_id"].astype("string")
    )

    # Check individual transfer rows.
    missing_values = plan[
        plan[
            [
                "drug_id",
                "from_hospital",
                "to_hospital",
                "transfer_quantity",
            ]
        ].isna().any(axis=1)
    ]

    invalid_quantity = plan[
        plan["transfer_quantity"].isna()
        | (plan["transfer_quantity"] <= 0)
        | (
            plan["transfer_quantity"].notna()
            & (
                plan["transfer_quantity"]
                != plan["transfer_quantity"].round()
            )
        )
    ]

    self_transfers = plan[
        plan["from_hospital"] == plan["to_hospital"]
    ]

    unknown_donors = plan[
        ~plan["from_hospital"].isin(known_hospitals)
    ]

    unknown_recipients = plan[
        ~plan["to_hospital"].isin(known_hospitals)
    ]

    unknown_drugs = plan[
        ~plan["drug_id"].isin(known_drugs)
    ]

    # Check whether each donor has eligible stock of the medicine.
    eligible_stock = (
        eligible_inventory
        .groupby(["hospital_id", "drug_id"], as_index=False)[
            "quantity_in_stock"
        ]
        .sum()
        .rename(columns={"quantity_in_stock": "eligible_stock"})
    )

    donor_totals = (
        plan.groupby(
            ["from_hospital", "drug_id"],
            dropna=False,
            as_index=False
        )["transfer_quantity"]
        .sum(min_count=1)
        .rename(
            columns={
                "from_hospital": "hospital_id",
                "transfer_quantity": "total_sent",
            }
        )
    )

    donor_check = donor_totals.merge(
        eligible_stock,
        on=["hospital_id", "drug_id"],
        how="left"
    )

    donor_check["eligible_stock"] = (
        donor_check["eligible_stock"].fillna(0)
    )

    donor_overages = donor_check[
        donor_check["total_sent"] > donor_check["eligible_stock"]
    ]

    # Check duplicate transfer rows.
    duplicate_rows = plan[
        plan.duplicated(
            subset=[
                "drug_id",
                "from_hospital",
                "to_hospital",
                "transfer_quantity",
            ],
            keep=False
        )
    ]

    # Check that the donor has eligible inventory for the medicine.
    eligible_pairs = set(
        zip(
            eligible_inventory["hospital_id"],
            eligible_inventory["drug_id"]
        )
    )

    no_eligible_stock_rows = plan[
        ~plan.apply(
            lambda row: (
                row["from_hospital"],
                row["drug_id"]
            ) in eligible_pairs,
            axis=1
        )
    ]

    # Check whether a medicine has any eligible stock at the donor.
    # This is separate from checking whether the proposed quantity
    # exceeds the donor's available eligible stock.
    total_units = plan["transfer_quantity"].sum(min_count=1)

    print(f"Transfer records: {len(plan)}")
    print(f"Total proposed units: {total_units}")
    print(f"Missing-value rows: {len(missing_values)}")
    print(f"Invalid quantity rows: {len(invalid_quantity)}")
    print(f"Self-transfer rows: {len(self_transfers)}")
    print(f"Unknown donor rows: {len(unknown_donors)}")
    print(f"Unknown recipient rows: {len(unknown_recipients)}")
    print(f"Unknown medicine rows: {len(unknown_drugs)}")
    print(f"Rows with no eligible donor stock: {len(no_eligible_stock_rows)}")
    print(f"Donor stock limit violations: {len(donor_overages)}")
    print(f"Duplicate transfer rows: {len(duplicate_rows)}")

    if not donor_overages.empty:
        print("\nDonor stock limit violations:")
        print(donor_overages.to_string(index=False))

    if not no_eligible_stock_rows.empty:
        print("\nTransfers without eligible donor stock:")
        print(
            no_eligible_stock_rows[
                [
                    "drug_id",
                    "from_hospital",
                    "to_hospital",
                    "transfer_quantity",
                ]
            ].to_string(index=False)
        )

    # Determine whether the plan passes the structural and stock checks.
    passed = all(
        [
            missing_values.empty,
            invalid_quantity.empty,
            self_transfers.empty,
            unknown_donors.empty,
            unknown_recipients.empty,
            unknown_drugs.empty,
            no_eligible_stock_rows.empty,
            donor_overages.empty,
            duplicate_rows.empty,
        ]
    )

    if passed:
        print("\nRESULT: PASS")
    else:
        print("\nRESULT: REVIEW REQUIRED")

    return {
        "algorithm": plan_name,
        "transfer_records": len(plan),
        "total_proposed_units": total_units,
        "missing_value_rows": len(missing_values),
        "invalid_quantity_rows": len(invalid_quantity),
        "self_transfer_rows": len(self_transfers),
        "unknown_donor_rows": len(unknown_donors),
        "unknown_recipient_rows": len(unknown_recipients),
        "unknown_medicine_rows": len(unknown_drugs),
        "no_eligible_stock_rows": len(no_eligible_stock_rows),
        "donor_stock_limit_violations": len(donor_overages),
        "duplicate_transfer_rows": len(duplicate_rows),
        "result": "PASS" if passed else "REVIEW REQUIRED",
    }


def main():
    print("=" * 65)
    print("MediResQ AI: COMPREHENSIVE TRANSFER VALIDATION")
    print("=" * 65)

    inventory = load_csv(INVENTORY_FILE)
    hospitals = load_csv(HOSPITALS_FILE)

    check_required_columns(
        inventory,
        REQUIRED_INVENTORY_COLUMNS,
        INVENTORY_FILE.name
    )

    check_required_columns(
        hospitals,
        REQUIRED_HOSPITAL_COLUMNS,
        HOSPITALS_FILE.name
    )

    print(f"\nInventory records loaded: {len(inventory)}")
    print(f"Hospitals loaded: {len(hospitals)}")

    results = []

    plan_files = [
        ("Baseline", BASELINE_PLAN_FILE),
        ("Distance-Aware", DISTANCE_PLAN_FILE),
    ]

    for plan_name, plan_file in plan_files:
        plan = load_csv(plan_file)

        check_required_columns(
            plan,
            REQUIRED_PLAN_COLUMNS,
            plan_file.name
        )

        result = validate_plan(
            plan_name,
            plan,
            inventory,
            hospitals
        )

        results.append(result)

    # Save the combined validation report.
    report = pd.DataFrame(results)
    report_path = DATA_DIR / "comprehensive_validation_report.csv"
    report.to_csv(report_path, index=False)

    print("\n" + "=" * 65)
    print("FINAL SUMMARY")
    print("=" * 65)
    print(
        report[
            [
                "algorithm",
                "transfer_records",
                "total_proposed_units",
                "donor_stock_limit_violations",
                "result",
            ]
        ].to_string(index=False)
    )

    print(f"\nValidation report saved to:\n{report_path}")
    print(
        "\nImportant: These checks validate simulated data consistency "
        "and quantities only. They do not verify clinical suitability, "
        "cold-chain compliance, transport safety, or real-world demand."
    )


if __name__ == "__main__":
    main()