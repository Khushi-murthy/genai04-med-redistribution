import pandas as pd

from src.simulation.comprehensive_validation import validate_plan


def create_test_data():
    """Create small synthetic inventory and hospital datasets."""

    inventory = pd.DataFrame([
        {
            "hospital_id": "H001",
            "drug_id": "MED001",
            "quantity_in_stock": 10,
            "expiry_date": "2099-12-31",
        },
        {
            "hospital_id": "H002",
            "drug_id": "MED001",
            "quantity_in_stock": 5,
            "expiry_date": "2099-12-31",
        },
    ])

    hospitals = pd.DataFrame([
        {"hospital_id": "H001"},
        {"hospital_id": "H002"},
    ])

    return inventory, hospitals


def test_valid_transfer_passes():
    """A transfer within available stock should pass."""

    inventory, hospitals = create_test_data()

    plan = pd.DataFrame([
        {
            "drug_id": "MED001",
            "from_hospital": "H001",
            "to_hospital": "H002",
            "transfer_quantity": 5,
        }
    ])

    result = validate_plan("Test Valid Plan", plan, inventory, hospitals)

    assert result["result"] == "PASS"


def test_transfer_exceeding_stock_is_rejected():
    """A transfer exceeding the donor's eligible stock should be rejected."""

    inventory, hospitals = create_test_data()

    plan = pd.DataFrame([
        {
            "drug_id": "MED001",
            "from_hospital": "H001",
            "to_hospital": "H002",
            "transfer_quantity": 11,
        }
    ])

    result = validate_plan(
        "Test Excess Stock",
        plan,
        inventory,
        hospitals,
    )

    assert result["result"] == "REVIEW REQUIRED"
    assert result["donor_stock_limit_violations"] == 1


def test_self_transfer_is_rejected():
    """A hospital must not transfer medicine to itself."""

    inventory, hospitals = create_test_data()

    plan = pd.DataFrame([
        {
            "drug_id": "MED001",
            "from_hospital": "H001",
            "to_hospital": "H001",
            "transfer_quantity": 2,
        }
    ])

    result = validate_plan(
        "Test Self Transfer",
        plan,
        inventory,
        hospitals,
    )

    assert result["result"] == "REVIEW REQUIRED"
    assert result["self_transfer_rows"] == 1


def test_unknown_recipient_is_rejected():
    """A transfer to an unregistered hospital must be rejected."""

    inventory, hospitals = create_test_data()

    plan = pd.DataFrame([
        {
            "drug_id": "MED001",
            "from_hospital": "H001",
            "to_hospital": "H999",
            "transfer_quantity": 2,
        }
    ])

    result = validate_plan(
        "Test Unknown Recipient",
        plan,
        inventory,
        hospitals,
    )

    assert result["result"] == "REVIEW REQUIRED"
    assert result["unknown_recipient_rows"] == 1


def test_zero_quantity_is_rejected():
    """A transfer quantity of zero must be rejected."""

    inventory, hospitals = create_test_data()

    plan = pd.DataFrame([
        {
            "drug_id": "MED001",
            "from_hospital": "H001",
            "to_hospital": "H002",
            "transfer_quantity": 0,
        }
    ])

    result = validate_plan(
        "Test Zero Quantity",
        plan,
        inventory,
        hospitals,
    )

    assert result["result"] == "REVIEW REQUIRED"
    assert result["invalid_quantity_rows"] == 1