from src.optimizer.opt_client import QpiAlClient

def test_connection():
    client = QpiAlClient(token="36d305c4fde61888137be5e6cb4dcf3005804b93077b747f35edcf9f00ab68a1")
    
    test_payload = {
        "problem_type": "medicine_redistribution",
        "test_mode": True,
        "data": {
            "hospitals": ["H1", "H2"],
            "batches": [{"id": "B1", "qty": 100}]
        }
    }
    
    print("Sending test request to QpiAl Opt...")
    try:
        result = client.send_problem(test_payload)
        print("Success! Response received:")
        print(result)
    except Exception as e:
        print(f"Test note: {e}")
        print("Check your local 'proofs/' folder to confirm proof files were generated.")

if __name__ == "__main__":
    test_connection()