import logging
import json
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


# =========================================================
# PATHS AND LOGGING
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

LOG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("mediresq.qpiai")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    file_handler = logging.FileHandler(
        LOG_DIR / "qpiai_usage.log",
        encoding="utf-8"
    )
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s"
        )
    )
    logger.addHandler(file_handler)


def log_event(event, details=None):
    """Write a timestamped event to the project log."""
    message = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "details": details or {}
    }

    logger.info(json.dumps(message, default=str))


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(title="MediResQ AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Local development only
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# =========================================================
# DISPATCH REQUEST MODEL
# =========================================================

class DispatchRequest(BaseModel):
    medicine: str = Field(min_length=1, max_length=100)
    quantity: int = Field(gt=0)
    source: str = Field(min_length=1, max_length=100)
    destination: str = Field(min_length=1, max_length=100)
    storage_requirement: str = Field(
        default="NORMAL",
        max_length=50
    )
    expiry_date: str | None = None


# =========================================================
# BASIC ENDPOINT
# =========================================================

@app.get("/")
def home():
    log_event("health_check", {"endpoint": "/"})

    return {
        "project": "MediResQ AI",
        "status": "API is running"
    }


@app.get("/api/health")
def health():
    log_event("health_check", {"endpoint": "/api/health"})

    return {
        "status": "healthy",
        "project": "MediResQ AI",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# =========================================================
# INVENTORY ENDPOINT
# =========================================================

@app.get("/api/inventory")
def get_inventory():
    file_path = DATA_DIR / "inventory_batches.csv"

    if not file_path.exists():
        log_event("inventory_file_missing", {
            "expected_file": str(file_path)
        })

        raise HTTPException(
            status_code=404,
            detail="Inventory file not found"
        )

    df = pd.read_csv(file_path).fillna("")

    log_event("inventory_loaded", {
        "record_count": len(df)
    })

    return {
        "count": len(df),
        "inventory": df.to_dict(orient="records")
    }


# =========================================================
# HOSPITALS ENDPOINT
# =========================================================

@app.get("/api/hospitals")
def get_hospitals():
    file_path = DATA_DIR / "hospitals.csv"

    if not file_path.exists():
        log_event("hospitals_file_missing", {
            "expected_file": str(file_path)
        })

        raise HTTPException(
            status_code=404,
            detail="Hospitals file not found"
        )

    df = pd.read_csv(file_path).fillna("")

    log_event("hospitals_loaded", {
        "record_count": len(df)
    })

    return {
        "count": len(df),
        "hospitals": df.to_dict(orient="records")
    }


# =========================================================
# REDISTRIBUTION PLAN ENDPOINT
# =========================================================

@app.get("/api/redistribution-plan")
def get_redistribution_plan():
    file_path = DATA_DIR / "redistribution_plan.csv"

    if not file_path.exists():
        log_event("redistribution_plan_missing", {})

        return {
            "count": 0,
            "plan": [],
            "message": "Redistribution plan has not been generated"
        }

    df = pd.read_csv(file_path).fillna("")

    log_event("redistribution_plan_loaded", {
        "record_count": len(df),
        "source": "redistribution_plan.csv",
        "status": "candidate_plan_not_automatically_approved"
    })

    return {
        "count": len(df),
        "plan": df.to_dict(orient="records"),
        "status": "candidate_plan_not_automatically_approved"
    }


# =========================================================
# DISPATCH ENDPOINT — LOGGING AND VALIDATION ONLY
# =========================================================

@app.post("/api/qubo/dispatch")
def dispatch(request: DispatchRequest):
    """
    Records a dispatch test request.

    IMPORTANT:
    This endpoint does NOT call QpiAI or run a QUBO solver.
    It must not be presented as a real optimization result.
    """

    request_data = request.model_dump()

    log_event("dispatch_request_received", {
        "input": request_data
    })

    log_event("dispatch_validation", {
        "result": "request_format_valid",
        "note": "This does not prove inventory feasibility or safety."
    })

    log_event("optimization_not_run", {
        "solver": "QpiAI",
        "status": "NOT_EXECUTED",
        "reason": (
            "This endpoint currently records the request only. "
            "No QpiAI solver call is implemented here."
        )
    })

    return {
        "project": "MediResQ AI",
        "request_received": True,
        "request": request_data,
        "optimization_status": "NOT_EXECUTED",
        "solver": "QpiAI",
        "message": (
            "Request logged successfully. "
            "No QpiAI optimization was performed."
        ),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }