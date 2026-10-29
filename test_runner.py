from src.optimizer.problem_runner import ProblemRunner

def test_pipeline():
    runner = ProblemRunner(token="mock_token_123")

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

    print("Running full optimization pipeline...")
    result = runner.run_optimization_pipeline(sources, destinations, batches)
    print("Pipeline Result:")
    import json
    print(json.dumps(result, indent=4))

if __name__ == "__main__":
    test_pipeline()