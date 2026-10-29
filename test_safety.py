from src.safety.safety_checker import SafetyChecker

def test_safety_audit():
    checker = SafetyChecker()

    # Test Case 1: A valid plan
    valid_plan = {
        "selected_transfers": [
            {"batch_id": "BATCH_001", "quantity": 100, "is_safe": True}
        ]
    }
    
    result_valid = checker.audit_transfer_plan(valid_plan)
    print("Valid Plan Audit Result:", result_valid)

    # Test Case 2: An unsafe plan (violating safety flags or limits)
    invalid_plan = {
        "selected_transfers": [
            {"batch_id": "BATCH_999", "quantity": 6000, "is_safe": False}
        ]
    }
    
    result_invalid = checker.audit_transfer_plan(invalid_plan)
    print("Invalid Plan Audit Result:", result_invalid)

if __name__ == "__main__":
    test_safety_audit()