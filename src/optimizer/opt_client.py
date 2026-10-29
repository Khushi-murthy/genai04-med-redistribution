import os
import json
from datetime import datetime
import requests
from dotenv import load_dotenv

load_dotenv()

class QpiAlClient:
    def __init__(self, token: str = None):
        # Fixed os.getenv usage: first argument is the env key, second is the fallback URL
        self.api_url = os.getenv("QPIAI_API_URL", "https://opt-server.qpiai.tech/api/")
        
        # Pull token securely from environment variables, fallback to argument if passed
        self.secret_token = token or os.getenv("QPIAI_SECRET_TOKEN")
        
        if not self.secret_token:
            raise ValueError("QpiAI secret token is missing. Set QPIAI_SECRET_TOKEN in your .env file.")
            
        os.makedirs("proofs", exist_ok=True)

    def send_problem(self, payload: dict) -> dict:
        headers = {
            "X-Secret-Token": self.secret_token,
            "Content-Type": "application/json"
        }

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save request proof
        request_proof_path = os.path.join("proofs", f"request_{timestamp}.json")
        with open(request_proof_path, "w") as f:
            json.dump(payload, f, indent=4)

        status_code = 500
        response_data = {}

        try:
            response = requests.post(self.api_url, json=payload, headers=headers, timeout=5)
            status_code = response.status_code
            try:
                response_data = response.json()
            except Exception:
                response_data = {"raw_text": response.text}
        except requests.exceptions.RequestException as e:
            response_data = {"error": str(e)}
            status_code = 503

        # Save response proof
        response_proof_path = os.path.join("proofs", f"response_{timestamp}.json")
        with open(response_proof_path, "w") as f:
            json.dump({
                "status_code": status_code,
                "response": response_data
            }, f, indent=4)

        if status_code != 200:
            raise Exception(f"QpiAl API Error [{status_code}]: {response_data}")

        return response_data