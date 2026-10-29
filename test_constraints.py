from src.optimizer.safe_option_builder import SafeOptionBuilder

def test_builder():
    builder = SafeOptionBuilder()

    # Mock Source Facility with surplus stock
    sources = [{
        "id": "Hospital_A",
        "min_stock_reserve": 50,
        "inventory": {"Paracetamol_500mg": 300},
        "supported_temperatures": ["ambient"]
    }]

    # Mock Destination Facility facing a shortage
    destinations = [{
        "id": "Clinic_B",
        "requested_drugs": ["Paracetamol_500mg"],
        "supported_temperatures": ["ambient"]
    }]

    # Mock Medicine Batches (One valid, one failing expiry)
    batches = [
        {
            "batch_id": "BATCH_001",
            "drug_name": "Paracetamol_500mg",
            "current_location": "Hospital_A",
            "quantity": 100,
            "expiry_date": "2026-12-31", # Safe future date
            "storage_temp": "ambient"
        },
        {
            "batch_id": "BATCH_002",
            "drug_name": "Paracetamol_500mg",
            "current_location": "Hospital_A",
            "quantity": 50,
            "expiry_date": "2026-10-29", # Too close/expired relative to current time
            "storage_temp": "ambient"
        }
    ]

    safe_options = builder.filter_safe_options(sources, destinations, batches)
    print(f"Total safe transfer options found: {len(safe_options)}")
    for option in safe_options:
        print(option)

if __name__ == "__main__":
    test_builder()
    