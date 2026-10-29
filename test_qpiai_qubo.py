import os
import requests
from dotenv import load_dotenv

load_dotenv(override=True)


def test_qpiai_qubo_request():
    api_url = os.getenv(
        "QPIAI_API_URL",
        "https://opt-server.qpiai.tech/api/"
    ).rstrip("/")

    token = os.getenv("QPIAI_SECRET_TOKEN")

    assert token, "QPIAI_SECRET_TOKEN is missing from .env"

    payload = {
        "name": "MediResQ QUBO Connection Test",
        "method": "QUBO",
        "num_variables": 2,
        "qubo_dict": {
            "0,0": -1.0,
            "1,1": -1.0,
            "0,1": 2.0
        },
        "max_evaluations": 100
    }

    # First try the primary authentication format from the docs.
    response = requests.post(
        f"{api_url}/problems/create",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=(5, 30)
    )

    print("Bearer authentication status:", response.status_code)

    if response.status_code == 401:
        # Try the alternative header mentioned in the docs.
        response = requests.post(
            f"{api_url}/problems/create",
            headers={
                "X-Secret-Token": token,
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=(5, 30)
        )

        print("X-Secret-Token authentication status:", response.status_code)

    try:
        result = response.json()
    except ValueError:
        result = {"response_text": response.text[:500]}

    print("API response:", result)

    assert response.status_code in (200, 201), (
        "Problem creation failed. Check the QpiAI authentication "
        "instructions and the API response above."
    )
