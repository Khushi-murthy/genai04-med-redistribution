import pandas as pd
from pathlib import Path

# ==========================================
# 1. PROJECT PATHS
# ==========================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_FOLDER = PROJECT_ROOT / "data"

PLAN_FILE = DATA_FOLDER / "distance_redistribution_plan.csv"
INVENTORY_FILE = DATA_FOLDER / "inventory_batches.csv"
DEMAND_FILE = DATA_FOLDER / "hospital_demand.csv"


# ==========================================
# 2. LOAD DATA
# ==========================================

plan = pd.read_csv(PLAN_FILE)
inventory = pd.read_csv(INVENTORY_FILE)
demand = pd.read_csv(DEMAND_FILE)

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

plan["transfer_quantity"] = pd.to_numeric(
    plan["transfer_quantity"],
    errors="coerce",
).fillna(0)

today = pd.Timestamp.today().normalize()

eligible = inventory[
    (inventory["expiry_date"] >= today)
    & (inventory["quantity_in_stock"] > 0)
].copy()

stock = eligible.groupby(
    ["hospital_id", "drug_id"]
)["quantity_in_stock"].sum()

demand_totals = demand.groupby(
    ["hospital_id", "drug_id"]
)["simulated_7_day_demand"].sum()


# ==========================================
# 3. VERIFY TRANSFER QUANTITIES
# ==========================================

print("\n===== DISTANCE PLAN VERIFICATION =====")

donor_violations = 0
recipient_violations = 0
invalid_transfers = 0

if not plan.empty:

    # Check for invalid transfer quantities and self-transfers.
    invalid_mask = (
        plan["transfer_quantity"].isna()
        | (plan["transfer_quantity"] <= 0)
        | (plan["from_hospital"] == plan["to_hospital"])
    )

    invalid_transfers = int(invalid_mask.sum())

    # Check donor surplus limits.
    for (hospital, drug), group in plan.groupby(
        ["from_hospital", "drug_id"]
    ):
        available = max(
            0.0,
            float(stock.get((hospital, drug), 0))
            - float(demand_totals.get((hospital, drug), 0)),
        )

        sent = group["transfer_quantity"].sum()

        if sent > available + 1e-9:
            donor_violations += 1
            print(
                f"DONOR VIOLATION: {hospital}, {drug}: "
                f"sent {sent:.0f}, surplus {available:.0f}"
            )

    # Check recipient shortage limits.
    received = plan.groupby(
        ["to_hospital", "drug_id"]
    )["transfer_quantity"].sum()

    for (hospital, drug), quantity in received.items():

        required = max(
            0.0,
            float(demand_totals.get((hospital, drug), 0))
            - float(stock.get((hospital, drug), 0)),
        )

        if quantity > required + 1e-9:
            recipient_violations += 1
            print(
                f"RECIPIENT VIOLATION: {hospital}, {drug}: "
                f"receives {quantity:.0f}, shortage {required:.0f}"
            )


# ==========================================
# 4. CALCULATE REMAINING SHORTAGE
# ==========================================

total_shortage_before = 0.0
total_shortage_after = 0.0

for (hospital, drug), required_demand in demand_totals.items():

    available_stock = float(stock.get((hospital, drug), 0))

    shortage_before = max(
        0.0,
        float(required_demand) - available_stock,
    )

    received_quantity = 0.0
    sent_quantity = 0.0

    if not plan.empty:

        received_quantity = plan.loc[
            (plan["to_hospital"] == hospital)
            & (plan["drug_id"] == drug),
            "transfer_quantity",
        ].sum()

        sent_quantity = plan.loc[
            (plan["from_hospital"] == hospital)
            & (plan["drug_id"] == drug),
            "transfer_quantity",
        ].sum()

    # Only calculate a meaningful result if transfers
    # respect donor and recipient limits.
    remaining_stock = (
        available_stock - sent_quantity + received_quantity
    )

    shortage_after = max(
        0.0,
        float(required_demand) - remaining_stock,
    )

    total_shortage_before += shortage_before
    total_shortage_after += shortage_after


# ==========================================
# 5. PRINT RESULTS
# ==========================================

print("Proposed transfer records:", len(plan))
print(
    "Total proposed units:",
    f"{plan['transfer_quantity'].sum():.0f}" if not plan.empty else "0",
)

print("Donor limit violations:", donor_violations)
print("Recipient limit violations:", recipient_violations)
print("Invalid transfer records:", invalid_transfers)

print(
    "Total simulated shortage before transfers:",
    f"{total_shortage_before:.0f}",
)

print(
    "Total simulated shortage after transfers:",
    f"{total_shortage_after:.0f}",
)

if (
    donor_violations == 0
    and recipient_violations == 0
    and invalid_transfers == 0
):
    print("\nQUANTITY CHECK: PASSED")
else:
    print("\nQUANTITY CHECK: FAILED")

print(
    "\nNote: This verifies simulated quantities only, "
    "not clinical or transport safety."
)