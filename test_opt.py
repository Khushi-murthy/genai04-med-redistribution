import os

from dotenv import load_dotenv
from src.optimizer.opt_client import QpiAlClient

load_dotenv()


def test_qpiai_configuration():
    """Check that QpiAI configuration is available locally."""

    assert os.getenv("QPIAI_API_URL"), (
        "QPIAI_API_URL is missing from .env"
    )

    assert os.getenv("QPIAI_SECRET_TOKEN"), (
        "QPIAI_SECRET_TOKEN is missing from .env"
    )

    client = QpiAlClient()

    assert client.api_url.startswith(("https://", "http://"))
    assert client.secret_token

    print("QpiAI configuration loaded successfully.")
