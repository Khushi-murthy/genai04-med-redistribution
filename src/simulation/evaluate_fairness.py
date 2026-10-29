import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_FOLDER = PROJECT_ROOT / "data"

INVENTORY_FILE = DATA_FOLDER / "inventory_batches.csv"
DEMAND_FILE = DATA_FOLDER / "hospital_demand.csv"
BASELINE_FILE = DATA_FOLDER / "redistribution_plan.csv"
DISTANCE_FILE = DATA_FOLDER / "distance_redistribution_plan.csv"


def load_csv(file_path):
    """Load a CSV file and report a clear error if it is missing."""
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    return pd.read_csv(file_path)


def prepare_initial_shortages(inventory, demand):
    """Calculate initial stock and shortage for each hospital and medicine."""

    inventory = inventory.copy()
    demand = demand.copy()

    required_inventory_columns = {
        "hospital_id",
        "drug_id",
        "drug_name",
        "quantity_in_stock",
        "expiry_date",
    }

    required_demand_columns = {
        "hospital_id",
        "drug_id",
        "drug_name",
        "simulated_7_day_demand",
    }

    missing_inventory = required_inventory_columns - set(inventory.columns)
    missing_demand = required_demand_columns - set(demand.columns)

    if missing_inventory:
        raise ValueError(
            f"Inventory file is missing columns: {sorted(missing_inventory)}"
        )

    if missing_demand:
        raise ValueError(
            f"Demand file is missing columns: {sorted(missing_demand)}"
        )

    # Convert values to the correct data types.
    inventory["expiry_date"] = pd.to_datetime(
        inventory["expiry_date"], errors="coerce"
    )

    inventory["quantity_in_stock"] = pd.to_numeric(
        inventory["quantity_in_stock"], errors="coerce"
    ).fillna(0)

    demand["simulated_7_day_demand"] = pd.to_numeric(
        demand["simulated_7_day_demand"], errors="coerce"
    ).fillna(0)

    today = pd.Timestamp.today().normalize()

    # Exclude expired stock and records with invalid expiry dates.
    eligible_inventory = inventory[
        (inventory["expiry_date"] >= today)
        & (inventory["quantity_in_stock"] > 0)
    ].copy()

    # Aggregate eligible stock by hospital and medicine.
    stock_summary = (
        eligible_inventory.groupby(
            ["hospital_id", "drug_id", "drug_name"],
            as_index=False,
        )["quantity_in_stock"]
        .sum()
        .rename(columns={"quantity_in_stock": "available_stock"})
    )

    # Aggregate the actual column used in hospital_demand.csv.
    demand_summary = (
        demand.groupby(
            ["hospital_id", "drug_id", "drug_name"],
            as_index=False,
        )["simulated_7_day_demand"]
        .sum()
        .rename(
            columns={
                "simulated_7_day_demand": "demand_for_7_days"
            }
        )
    )

    # Combine stock and demand information.
    summary = demand_summary.merge(
        stock_summary,
        on=["hospital_id", "drug_id", "drug_name"],
        how="left",
    )

    summary["available_stock"] = summary["available_stock"].fillna(0)

    summary["initial_shortage"] = (
        summary["demand_for_7_days"] - summary["available_stock"]
    ).clip(lower=0)

    return summary


def evaluate_plan(initial_summary, plan, algorithm_name):
    """Evaluate shortage reduction and shortage distribution."""

    result = initial_summary.copy()

    result["stock_after_transfers"] = result["available_stock"]

    if not plan.empty:
        required_plan_columns = {
            "drug_id",
            "from_hospital",
            "to_hospital",
            "transfer_quantity",
        }

        missing = required_plan_columns - set(plan.columns)

        if missing:
            raise ValueError(
                f"{algorithm_name} plan is missing columns: "
                f"{sorted(missing)}"
            )

        plan = plan.copy()

        plan["transfer_quantity"] = pd.to_numeric(
            plan["transfer_quantity"], errors="coerce"
        ).fillna(0)

        for _, transfer in plan.iterrows():
            drug_id = transfer["drug_id"]
            donor = transfer["from_hospital"]
            recipient = transfer["to_hospital"]
            quantity = transfer["transfer_quantity"]

            donor_mask = (
                (result["hospital_id"] == donor)
                & (result["drug_id"] == drug_id)
            )

            recipient_mask = (
                (result["hospital_id"] == recipient)
                & (result["drug_id"] == drug_id)
            )

            # Apply each proposed transfer to the simulated stock.
            result.loc[
                donor_mask, "stock_after_transfers"
            ] -= quantity

            result.loc[
                recipient_mask, "stock_after_transfers"
            ] += quantity

    # Recalculate shortage after applying transfers.
    result["shortage_after_transfers"] = (
        result["demand_for_7_days"]
        - result["stock_after_transfers"]
    ).clip(lower=0)

    initial_total = result["initial_shortage"].sum()
    remaining_total = result["shortage_after_transfers"].sum()

    shortage_reduction = initial_total - remaining_total

    reduction_percentage = (
        shortage_reduction / initial_total * 100
        if initial_total > 0
        else 0
    )

    # Aggregate shortages by hospital.
    hospital_results = (
        result.groupby("hospital_id", as_index=False)
        .agg(
            Initial_Shortage=("initial_shortage", "sum"),
            Remaining_Shortage=("shortage_after_transfers", "sum"),
        )
    )

    # Compare the spread of remaining shortages across hospitals.
    # This measures absolute variation, not clinical fairness.
    shortage_std = hospital_results["Remaining_Shortage"].std(ddof=0)

    metrics = {
        "Algorithm": algorithm_name,
        "Initial Shortage": round(initial_total, 2),
        "Remaining Shortage": round(remaining_total, 2),
        "Shortage Reduction": round(shortage_reduction, 2),
        "Reduction Percentage": round(reduction_percentage, 2),
        "Hospital Shortage Std Dev": round(shortage_std, 2),
    }

    return metrics, hospital_results, result


if __name__ == "__main__":
    print("\n===== MediResQ AI: Fairness and Shortage Evaluation =====")

    # Load existing project data and proposed plans.
    inventory = load_csv(INVENTORY_FILE)
    demand = load_csv(DEMAND_FILE)
    baseline_plan = load_csv(BASELINE_FILE)
    distance_plan = load_csv(DISTANCE_FILE)

    print(f"Inventory records loaded: {len(inventory)}")
    print(f"Demand records loaded: {len(demand)}")
    print(f"Baseline transfer records: {len(baseline_plan)}")
    print(f"Distance-aware transfer records: {len(distance_plan)}")

    # Calculate stock and shortage before transfers.
    initial_summary = prepare_initial_shortages(inventory, demand)

    # Evaluate both algorithms using the same starting summary.
    baseline_metrics, baseline_hospitals, baseline_details = evaluate_plan(
        initial_summary,
        baseline_plan,
        "Baseline",
    )

    distance_metrics, distance_hospitals, distance_details = evaluate_plan(
        initial_summary,
        distance_plan,
        "Distance-Aware",
    )

    comparison = pd.DataFrame(
        [baseline_metrics, distance_metrics]
    )

    print("\n===== Algorithm Comparison =====")
    print(comparison.to_string(index=False))

    print("\n===== Baseline: Hospital Shortages =====")
    print(baseline_hospitals.to_string(index=False))

    print("\n===== Distance-Aware: Hospital Shortages =====")
    print(distance_hospitals.to_string(index=False))

    # Save the evaluation reports.
    comparison.to_csv(
        DATA_FOLDER / "fairness_comparison.csv",
        index=False,
    )

    baseline_hospitals.to_csv(
        DATA_FOLDER / "baseline_hospital_shortages.csv",
        index=False,
    )

    distance_hospitals.to_csv(
        DATA_FOLDER / "distance_hospital_shortages.csv",
        index=False,
    )

    baseline_details.to_csv(
        DATA_FOLDER / "baseline_fairness_details.csv",
        index=False,
    )

    distance_details.to_csv(
        DATA_FOLDER / "distance_fairness_details.csv",
        index=False,
    )

    print("\n===== Evaluation Complete =====")
    print("Reports saved in:", DATA_FOLDER)

    print(
        "\nNOTE: Demand and hospital information are simulated. "
        "These results evaluate proposed quantities only and do not "
        "establish clinical suitability, transport safety, or "
        "real-world fairness."
    )