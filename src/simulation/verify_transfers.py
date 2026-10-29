import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_FOLDER = PROJECT_ROOT / "data"

plan = pd.read_csv(DATA_FOLDER / "redistribution_plan.csv")
inventory = pd.read_csv(DATA_FOLDER / "inventory_batches.csv")
demand = pd.read_csv(DATA_FOLDER / "hospital_demand.csv")

inventory["expiry_date"] = pd.to_datetime(
    inventory["expiry_date"], errors="coerce"
)
inventory["quantity_in_stock"] = pd.to_numeric(
    inventory["quantity_in_stock"], errors="coerce"
).fillna(0)

today = pd.Timestamp.today().normalize()

eligible = inventory[
    (inventory["expiry_date"] >= today)
    & (inventory["quantity_in_stock"] > 0)
]

stock = eligible.groupby(
    ["hospital_id", "drug_id"]
)["quantity_in_stock"].sum()

demand_totals = demand.groupby(
    ["hospital_id", "drug_id"]
)["simulated_7_day_demand"].sum()

print("\n===== DONOR STOCK VERIFICATION =====")

violations = 0

for (hospital, drug), group in plan.groupby(
    ["from_hospital", "drug_id"]
):
    available = max(
        0,
        float(stock.get((hospital, drug), 0))
        - float(demand_totals.get((hospital, drug), 0))
    )

    sent = group["transfer_quantity"].sum()

    if sent > available:
        print(
            f"{hospital} | {drug} | "
            f"Sent: {sent:.0f} | "
            f"Available surplus: {available:.0f}"
        )
        violations += 1

print("\nDonor limit violations:", violations)

if violations == 0:
    print("All transfers passed the donor stock-limit check.")
else:
    print("Some transfers exceed the calculated surplus.")