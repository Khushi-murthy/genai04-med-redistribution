import pandas as pd
from pathlib import Path

# ==========================================
# 1. PROJECT PATHS
# ==========================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_FOLDER = PROJECT_ROOT / "data"

BASELINE_FILE = DATA_FOLDER / "redistribution_plan.csv"
DISTANCE_FILE = DATA_FOLDER / "distance_redistribution_plan.csv"


# ==========================================
# 2. LOAD BOTH PLANS
# ==========================================

def load_plan(file_path):

    if not file_path.exists():
        raise FileNotFoundError(
            f"Plan file not found: {file_path}"
        )

    plan = pd.read_csv(file_path)

    if not plan.empty:
        plan["transfer_quantity"] = pd.to_numeric(
            plan["transfer_quantity"],
            errors="coerce",
        ).fillna(0)

    return plan


# ==========================================
# 3. CALCULATE COMPARISON METRICS
# ==========================================

def calculate_metrics(plan, algorithm_name):

    total_units = (
        plan["transfer_quantity"].sum()
        if not plan.empty else 0
    )

    transfer_count = len(plan)

    if (
        not plan.empty
        and "simulated_distance" in plan.columns
    ):
        average_distance = plan[
            "simulated_distance"
        ].mean()
    else:
        average_distance = None

    return {
        "Algorithm": algorithm_name,
        "Transfer Records": transfer_count,
        "Total Units Proposed": round(total_units, 2),
        "Average Simulated Distance": (
            round(average_distance, 2)
            if pd.notna(average_distance)
            else "Not recorded"
        ),
    }


# ==========================================
# 4. COMPARE RESULTS
# ==========================================

if __name__ == "__main__":

    baseline_plan = load_plan(BASELINE_FILE)
    distance_plan = load_plan(DISTANCE_FILE)

    results = [
        calculate_metrics(
            baseline_plan,
            "Baseline",
        ),
        calculate_metrics(
            distance_plan,
            "Distance-Aware",
        ),
    ]

    comparison = pd.DataFrame(results)

    print("\n===== MediResQ AI: Algorithm Comparison =====\n")

    print(comparison.to_string(index=False))

    print("\n===== Difference in Results =====")

    print(
        "Difference in transfer records:",
        len(distance_plan) - len(baseline_plan),
    )

    print(
        "Difference in proposed units:",
        round(
            distance_plan["transfer_quantity"].sum()
            - baseline_plan["transfer_quantity"].sum(),
            2,
        ),
    )

    output_file = DATA_FOLDER / "algorithm_comparison.csv"

    comparison.to_csv(output_file, index=False)

    print(f"\nComparison saved to: {output_file}")

    print(
        "\nNote: The baseline does not record distance, "
        "so its average distance cannot be compared here."
    )