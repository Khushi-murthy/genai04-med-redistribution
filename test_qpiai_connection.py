from src.optimizer.opt_client import QpiAlClient
from src.optimizer.qubo_builder import QUBOBuilder

try:
    client = QpiAlClient()
    payload = QUBOBuilder().build_payload()
    response = client.send_problem(payload)

    print("\nQpiAI problem creation successful!")
    print("Actual response:", response)
    print("\nCheck the proofs folder for request and response JSON files.")

except Exception as e:
    print("QpiAI request failed:", e)