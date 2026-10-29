import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_FOLDER = PROJECT_ROOT / "data"

INVENTORY_FILE = DATA_FOLDER / "inventory_batches.csv"
DEMAND_FILE = DATA_FOLDER / "hospital_demand.csv"
BASELINE_FILE = DATA_FOLDER / "redistribution_plan.csv"
DISTANCE_FILE = DATA_FOLDER / "distance_redistribution_plan.csv"


def load_csv(file_path):
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    return pd.read_csv(file_path)


def prepare_initial_data(inventory, demand):
    inventory = inventory.copy()
    demand = demand.copy()

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

    eligible = inventory[
        (inventory["expiry_date"] >= today)
        & (inventory["quantity_in_stock"] > 0)
    ].copy()

    stock = (
        eligible.groupby(
            ["hospital_id", "drug_id", "drug_name"],
            as_index=False
        )["quantity_in_stock"]
        .sum()
        .rename(columns={"quantity_in_stock": "available_stock"})
    )

    demand_summary = (
        demand.groupby(
            ["hospital_id", "drug_id", "drug_name"],
            as_index=False
        )["simulated_7_day_demand"]
        .sum()
        .rename(
            columns={
                "simulated_7_day_demand": "demand_for_7_days"
            }
        )
    )

    summary = demand_summary.merge(
        stock,
        on=["hospital_id", "drug_id", "drug_name"],
        how="left"
    )

    summary["available_stock"] = summary["available_stock"].fillna(0)

    return summary


def evaluate_algorithm(initial_data, plan, algorithm_name):
    result = initial_data.copy()
    result["stock_after_transfers"] = result["available_stock"]

    if not plan.empty:
        required_columns = {
            "drug_id",
            "from_hospital",
            "to_hospital",
            "transfer_quantity"
        }

        missing = required_columns - set(plan.columns)

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

            result.loc[
                donor_mask, "stock_after_transfers"
            ] -= quantity

            result.loc[
                recipient_mask, "stock_after_transfers"
            ] += quantity

    result["remaining_shortage"] = (
        result["demand_for_7_days"]
        - result["stock_after_transfers"]
    ).clip(lower=0)

    hospital_results = (
        result.groupby("hospital_id", as_index=False)
        .agg(
            Total_Demand=("demand_for_7_days", "sum"),
            Remaining_Shortage=("remaining_shortage", "sum")
        )
    )

    hospital_results["Shortage_Rate_Percent"] = (
        hospital_results["Remaining_Shortage"]
        / hospital_results["Total_Demand"].replace(0, float("nan"))
        * 100
    ).fillna(0)

    hospital_results["Algorithm"] = algorithm_name

    return hospital_results


def calculate_fairness_metrics(hospital_results, algorithm_name):
    rates = hospital_results["Shortage_Rate_Percent"]

    highest_index = rates.idxmax()
    lowest_index = rates.idxmin()

    return {
        "Algorithm": algorithm_name,
        "Hospitals Evaluated": len(hospital_results),
        "Average Shortage Rate (%)": round(rates.mean(), 2),
        "Highest Shortage Rate (%)": round(rates.max(), 2),
        "Highest Shortage Hospital": hospital_results.loc[
            highest_index, "hospital_id"
        ],
        "Lowest Shortage Rate (%)": round(rates.min(), 2),
        "Lowest Shortage Hospital": hospital_results.loc[
            lowest_index, "hospital_id"
        ],
        "Shortage Rate Std Dev": round(rates.std(ddof=0), 2)
    }


if __name__ == "__main__":
    print("\n===== MediResQ AI: Demand-Based Fairness Evaluation =====")

    inventory = load_csv(INVENTORY_FILE)
    demand = load_csv(DEMAND_FILE)
    baseline_plan = load_csv(BASELINE_FILE)
    distance_plan = load_csv(DISTANCE_FILE)

    initial_data = prepare_initial_data(inventory, demand)

    baseline_results = evaluate_algorithm(
        initial_data, baseline_plan, "Baseline"
    )

    distance_results = evaluate_algorithm(
        initial_data, distance_plan, "Distance-Aware"
    )

    comparison = pd.DataFrame([
        calculate_fairness_metrics(baseline_results, "Baseline"),
        calculate_fairness_metrics(distance_results, "Distance-Aware")
    ])

    all_hospital_results = pd.concat(
        [baseline_results, distance_results],
        ignore_index=True
    )

    print("\n===== Fairness Comparison =====")
    print(comparison.to_string(index=False))

    print("\n===== Baseline: Demand-Based Shortage Rates =====")
    print(baseline_results.round(2).to_string(index=False))

    print("\n===== Distance-Aware: Demand-Based Shortage Rates =====")
    print(distance_results.round(2).to_string(index=False))

    comparison.to_csv(
        DATA_FOLDER / "demand_fairness_comparison.csv",
        index=False
    )

    all_hospital_results.to_csv(
        DATA_FOLDER / "hospital_demand_fairness.csv",
        index=False
    )

    print("\n===== Evaluation Complete =====")
    print("Saved: data/demand_fairness_comparison.csv")
    print("Saved: data/hospital_demand_fairness.csv")

    print(
        "\nNOTE: Hospital data and demand are simulated. "
        "These results do not establish real-world clinical fairness."
    )