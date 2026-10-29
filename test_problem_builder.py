from src.optimizer.safe_option_builder import SafeOptionBuilder
from src.optimizer.problem_builder import ProblemBuilder

def test_builder():
    # 1. Generate a safe option using our Task 2 logic
    builder_safety = SafeOptionBuilder()
    sources = [{
        "id": "Hospital_A",
        "min_stock_reserve": 50,
        "inventory": {"Paracetamol_500mg": 300},
        "supported_temperatures": ["ambient"]
    }]
    destinations = [{
        "id": "Clinic_B",
        "requested_drugs": ["Paracetamol_500mg"],
        "supported_temperatures": ["ambient"]
    }]
    batches = [{
        "batch_id": "BATCH_001",
        "drug_name": "Paracetamol_500mg",
        "current_location": "Hospital_A",
        "quantity": 100,
        "expiry_date": "2026-12-31",
        "storage_temp": "ambient"
    }]
    
    safe_options = builder_safety.filter_safe_options(sources, destinations, batches)

    # 2. Build the QpiAl solver payload using Task 3
    prob_builder = ProblemBuilder()
    payload = prob_builder.build_payload(safe_options)

    print("Successfully built QpiAl Solver Payload:")
    import json
    print(json.dumps(payload, indent=4))

if __name__ == "__main__":
    test_builder()