import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from src.optimizer.problem_builder import ProblemBuilder


DATA_DIR = Path("data")
PROOFS_DIR = Path("proofs")


def read_csv(path):
    """Read a CSV file and return its rows."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def required_value(row, field):
    """Return a required CSV value."""
    value = row.get(field)

    if value is None or not str(value).strip():
        raise ValueError(f"Missing required field: {field}")

    return str(value).strip()


def positive_number(value, field):
    """Convert a value to a positive number."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be numeric.")

    if number <= 0:
        raise ValueError(f"{field} must be greater than zero.")

    return number


def format_quantity(value):
    """Format whole quantities without decimal places."""
    if value == int(value):
        return int(value)

    return round(value, 3)


def run_optimization_pipeline():
    run_id = uuid4().hex
    timestamp = datetime.now(timezone.utc).isoformat()

    PROOFS_DIR.mkdir(parents=True, exist_ok=True)

    audit = {
        "run_id": run_id,
        "timestamp_utc": timestamp,
        "data_type": "SYNTHETIC_OR_PROVIDED_DATASET",
        "status": "FAILED",
        "method": "demand_informed_candidate_generation",
        "qpiai_solver_called": False,
        "approved_transfers": 0,
        "valid_batches": 0,
        "rejected_batches": 0,
        "candidate_transfers": 0,
        "rejected_demand_rows": 0,
        "errors": [],
        "limitations": [
            "Destination current stock is unavailable.",
            "Demand data is simulated and is not verified unmet demand.",
            "Source stock requirements are approximated using recorded demand.",
            "Reserving demand against individual batches does not guarantee "
            "that the source hospital retains sufficient total stock.",
            "Storage compatibility and medicine-specific safety checks "
            "are not fully implemented.",
            "Candidates are not approved transfers.",
            "QpiAI optimization has not been executed."
        ]
    }

    print("=" * 55)
    print("MediResQ AI - Redistribution Candidate Pipeline")
    print("=" * 55)

    try:
        # --------------------------------------------------
        # 1. Read input datasets
        # --------------------------------------------------
        inventory_rows = read_csv(
            DATA_DIR / "inventory_batches.csv"
        )
        hospital_rows = read_csv(
            DATA_DIR / "hospitals.csv"
        )
        demand_rows = read_csv(
            DATA_DIR / "hospital_demand.csv"
        )

        # --------------------------------------------------
        # 2. Validate hospital IDs
        # --------------------------------------------------
        hospitals = {}

        for row in hospital_rows:
            hospital_id = required_value(row, "hospital_id")

            if hospital_id in hospitals:
                raise ValueError(
                    f"Duplicate hospital ID: {hospital_id}"
                )

            hospitals[hospital_id] = row

        if len(hospitals) < 2:
            raise ValueError(
                "At least two hospitals are required."
            )

        # --------------------------------------------------
        # 3. Read demand by hospital and medicine
        # --------------------------------------------------
        demand_by_hospital_drug = {}
        rejected_demand_rows = 0

        for row in demand_rows:
            try:
                hospital_id = required_value(row, "hospital_id")
                drug_id = required_value(row, "drug_id")

                if hospital_id not in hospitals:
                    raise ValueError(
                        f"Unknown hospital ID: {hospital_id}"
                    )

                demand_text = required_value(
                    row, "simulated_7_day_demand"
                )

                demand = float(demand_text)

                if demand < 0:
                    raise ValueError(
                        "Demand cannot be negative."
                    )

                key = (hospital_id, drug_id)

                # If the same hospital and drug occur multiple
                # times, combine their demand.
                demand_by_hospital_drug[key] = (
                    demand_by_hospital_drug.get(key, 0) + demand
                )

            except (ValueError, TypeError) as error:
                rejected_demand_rows += 1
                print(f"Rejected demand row: {error}")

        # Preserve original demand for reporting.
        original_demand = dict(demand_by_hospital_drug)

        # Track how much demand remains after candidate allocation.
        remaining_demand = dict(original_demand)

        # --------------------------------------------------
        # 4. Validate inventory batches and expiry dates
        # --------------------------------------------------
        today = date.today()
        valid_batches = []
        rejected_batches = 0

        for row in inventory_rows:
            try:
                batch_id = required_value(row, "batch_id")
                drug_id = required_value(row, "drug_id")
                drug_name = required_value(row, "drug_name")
                source = required_value(row, "hospital_id")
                expiry_text = required_value(row, "expiry_date")

                quantity = positive_number(
                    required_value(row, "quantity_in_stock"),
                    "quantity_in_stock"
                )

                if source not in hospitals:
                    raise ValueError(
                        f"Unknown source hospital: {source}"
                    )

                expiry_date = datetime.strptime(
                    expiry_text, "%Y-%m-%d"
                ).date()

                # Reject expired batches and batches expiring today.
                if expiry_date <= today:
                    raise ValueError(
                        f"Batch expired or expires today: {expiry_text}"
                    )

                valid_batches.append({
                    "batch_id": batch_id,
                    "drug_id": drug_id,
                    "drug_name": drug_name,
                    "source": source,
                    "quantity": quantity,
                    "expiry_date": expiry_text,
                    "storage_requirement": str(
                        row.get("storage_requirement", "")
                    ).strip(),
                    "data_origin": str(
                        row.get("data_origin", "UNKNOWN")
                    ).strip(),
                })

            except (ValueError, TypeError) as error:
                rejected_batches += 1

                print(
                    f"Rejected batch "
                    f"{row.get('batch_id', 'UNKNOWN')}: {error}"
                )

        # --------------------------------------------------
        # 5. Generate demand-informed transfer candidates
        # --------------------------------------------------
        candidates = []

        # Sort for repeatable output.
        valid_batches.sort(
            key=lambda batch: (
                batch["drug_id"],
                batch["expiry_date"],
                batch["batch_id"]
            )
        )

        for batch in valid_batches:
            remaining_batch_quantity = batch["quantity"]

            drug_id = batch["drug_id"]
            source = batch["source"]

            # Reserve a quantity for the source hospital's
            # recorded demand before considering other hospitals.
            #
            # This is only a preliminary estimate. It does not
            # calculate the source hospital's actual surplus.
            source_demand_key = (source, drug_id)

            source_demand_remaining = remaining_demand.get(
                source_demand_key, 0
            )

            source_reserved_quantity = min(
                remaining_batch_quantity,
                source_demand_remaining
            )

            remaining_batch_quantity -= source_reserved_quantity

            # Consider destination hospitals in sorted order.
            for destination in sorted(hospitals):
                if destination == source:
                    continue

                if remaining_batch_quantity <= 0:
                    break

                demand_key = (destination, drug_id)

                destination_demand_remaining = remaining_demand.get(
                    demand_key, 0
                )

                if destination_demand_remaining <= 0:
                    continue

                proposed_quantity = min(
                    remaining_batch_quantity,
                    destination_demand_remaining
                )

                if proposed_quantity <= 0:
                    continue

                # Preserve original demand and demand remaining
                # before this candidate was generated.
                candidates.append({
                    "batch_id": batch["batch_id"],
                    "drug_id": drug_id,
                    "drug_name": batch["drug_name"],
                    "source": source,
                    "destination": destination,
                    "quantity": proposed_quantity,
                    "expiry_date": batch["expiry_date"],
                    "storage_requirement":
                        batch["storage_requirement"],
                    "source_data_origin": batch["data_origin"],
                    "destination_demand_7_day":
                        original_demand.get(demand_key, 0),
                    "destination_demand_remaining_before":
                        destination_demand_remaining,
                    "status": (
                        "Candidate - Stock, Unmet Demand and "
                        "Safety Validation Required"
                    ),
                })

                # Do not allocate more than this batch contains.
                remaining_batch_quantity -= proposed_quantity

                # Do not reuse the same destination demand allowance.
                remaining_demand[demand_key] = (
                    destination_demand_remaining - proposed_quantity
                )

        # --------------------------------------------------
        # 6. Save the candidate redistribution plan
        # --------------------------------------------------
        output_path = DATA_DIR / "redistribution_plan.csv"

        fieldnames = [
            "Batch ID",
            "Drug ID",
            "Drug Name",
            "Source Hospital",
            "Destination Hospital",
            "Proposed Quantity",
            "Expiry Date",
            "Storage Requirement",
            "Source Data Origin",
            "Destination 7-Day Demand",
            "Destination Demand Remaining Before",
            "Status",
        ]

        with output_path.open(
            "w", encoding="utf-8", newline=""
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames
            )

            writer.writeheader()

            for candidate in candidates:
                writer.writerow({
                    "Batch ID": candidate["batch_id"],
                    "Drug ID": candidate["drug_id"],
                    "Drug Name": candidate["drug_name"],
                    "Source Hospital": candidate["source"],
                    "Destination Hospital":
                        candidate["destination"],
                    "Proposed Quantity": format_quantity(
                        candidate["quantity"]
                    ),
                    "Expiry Date": candidate["expiry_date"],
                    "Storage Requirement":
                        candidate["storage_requirement"],
                    "Source Data Origin":
                        candidate["source_data_origin"],
                    "Destination 7-Day Demand": format_quantity(
                        candidate["destination_demand_7_day"]
                    ),
                    "Destination Demand Remaining Before":
                        format_quantity(
                            candidate[
                                "destination_demand_remaining_before"
                            ]
                        ),
                    "Status": candidate["status"],
                })

        # --------------------------------------------------
        # 7. Save audit record
        # --------------------------------------------------
        audit["valid_batches"] = len(valid_batches)
        audit["rejected_batches"] = rejected_batches
        audit["rejected_demand_rows"] = rejected_demand_rows
        audit["candidate_transfers"] = len(candidates)
        audit["status"] = "SUCCESS"
        audit["message"] = (
            "Demand-informed candidates generated successfully. "
            "No transfers were approved and QpiAI was not called."
        )

        print("\nPipeline completed.")
        print(f"Valid batches: {len(valid_batches)}")
        print(f"Rejected batches: {rejected_batches}")
        print(f"Rejected demand rows: {rejected_demand_rows}")
        print(f"Candidate transfers: {len(candidates)}")
        print(f"Plan saved to: {output_path}")
        print("QpiAI solver called: No")
        print("Approved transfers: 0")

    except Exception as error:
        audit["errors"].append(str(error))
        print(f"\nPipeline failed: {error}")

    finally:
        proof_path = (
            PROOFS_DIR / f"proof_log_{run_id}.json"
        )

        with proof_path.open("w", encoding="utf-8") as file:
            json.dump(audit, file, indent=2)

        print(f"Audit record saved to: {proof_path}")

    return audit


if __name__ == "__main__":
    run_optimization_pipeline()