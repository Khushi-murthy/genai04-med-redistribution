import os
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

PROOFS_DIR = BASE_DIR / "proofs"
PROOFS_DIR.mkdir(parents=True, exist_ok=True)


class QpiAlClient:
    def __init__(self, token: str = None):
        base_url = os.getenv(
            "QPIAI_API_URL",
            "https://opt-server.qpiai.tech/api/"
        ).strip().rstrip("/")

        self.api_url = f"{base_url}/problems/create"
        self.secret_token = token or os.getenv("QPIAI_SECRET_TOKEN")

        if not self.secret_token:
            raise ValueError(
                "QpiAI token is missing. Set QPIAI_SECRET_TOKEN in .env."
            )

        if not base_url.startswith(("https://", "http://")):
            raise ValueError("QPIAI_API_URL must be an HTTP(S) URL.")

    def send_problem(self, payload: dict) -> dict:
        if not isinstance(payload, dict) or not payload:
            raise ValueError("Payload must be a non-empty dictionary.")

        request_id = uuid.uuid4().hex
        timestamp = datetime.now(timezone.utc).isoformat()

        request_path = PROOFS_DIR / f"request_{request_id}.json"
        response_path = PROOFS_DIR / f"response_{request_id}.json"

        request_record = {
            "request_id": request_id,
            "timestamp_utc": timestamp,
            "endpoint": self.api_url,
            "payload": payload,
        }

        request_path.write_text(
            json.dumps(request_record, indent=2, default=str),
            encoding="utf-8",
        )

        result = {
            "request_id": request_id,
            "timestamp_utc": timestamp,
            "endpoint": self.api_url,
            "status_code": None,
            "success": False,
            "response": None,
        }

        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers={
                    "X-Secret-Token": self.secret_token,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=(5, 30),
            )

            result["status_code"] = response.status_code

            try:
                response_data = response.json()
            except ValueError:
                response_data = {"raw_text": response.text[:2000]}

            result["response"] = response_data

            if not response.ok:
                result["error"] = (
                    f"QpiAI returned HTTP {response.status_code}"
                )
                raise RuntimeError(result["error"])

            result["success"] = True
            return response_data

        except requests.exceptions.RequestException as exc:
            result["error"] = str(exc)
            raise

        finally:
            response_path.write_text(
                json.dumps(result, indent=2, default=str),
                encoding="utf-8",
            )