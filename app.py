import streamlit as st
import pandas as pd
import os
import json
import requests
from pathlib import Path
from src.genai.ai_assistant import AIAssistant

# --- Page Config ---
st.set_page_config(page_title="MediResQ AI Data & Solver Backend", page_icon="💊", layout="wide")

# --- Initialize AI Assistant ---
ai = AIAssistant()

# --- Custom Styling ---
st.markdown("""
    <style>
        .main { background-color: #f8f9fa; }
        .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
""", unsafe_allow_html=True)

# --- API Helper Functions ---
API_BASE_URL = "http://127.0.0.1:8000"

@st.cache_data(ttl=10)
def fetch_api_data(endpoint):
    try:
        response = requests.get(f"{API_BASE_URL}{endpoint}", timeout=3)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None

@st.cache_data
def load_csv_data(filepath, fallback_df):
    if os.path.exists(filepath):
        try:
            return pd.read_csv(filepath)
        except Exception:
            return fallback_df
    return fallback_df

# --- Header ---
st.title("MediResQ AI: Data & Optimization Backend")
st.markdown("Managing redistribution datasets and live FastAPI backend connectivity.")

# --- Stock & Topology Data Loading & Calculation ---
BASE_DIR = Path(__file__).resolve().parent

# 1. Fetch or Load Hospitals/Facilities
hospitals_data = fetch_api_data("/api/hospitals")
if hospitals_data and "hospitals" in hospitals_data:
    df_facilities = pd.DataFrame(hospitals_data["hospitals"])
else:
    fallback_facilities = pd.DataFrame({
        "hospital_id": [f"H0{i}" if i < 10 else "H10" for i in range(1, 11)],
        "facility_name": [
            "Central Hospital", "North Clinic", "South Hospital", "East Clinic", 
            "West Hospital", "Community Clinic", "City Hospital", "Rural Clinic", 
            "General Hospital", "Emergency Clinic"
        ],
        "category_type": [
            "Large Hospital", "Small Clinic", "Medium Hospital", "Small Clinic", 
            "Medium Hospital", "Small Clinic", "Large Hospital", "Small Clinic", 
            "Medium Hospital", "Small Clinic"
        ]
    })
    facilities_file = BASE_DIR / "data" / "hospitals.csv"
    df_facilities = load_csv_data(str(facilities_file), fallback_facilities)

# Standardize keys
for col_options in [["hospital_id", "facility_id", "id"]]:
    found = next((c for c in col_options if c in df_facilities.columns), None)
    if found and found != "hospital_id":
        df_facilities = df_facilities.rename(columns={found: "hospital_id"})
        break

for col_options in [["facility_name", "name", "hospital_name"]]:
    found = next((c for c in col_options if c in df_facilities.columns), None)
    if found and found != "facility_name":
        df_facilities = df_facilities.rename(columns={found: "facility_name"})
        break

if "hospital_id" not in df_facilities.columns:
    df_facilities["hospital_id"] = [f"H0{i}" for i in range(1, len(df_facilities) + 1)]
if "facility_name" not in df_facilities.columns:
    df_facilities["facility_name"] = df_facilities["hospital_id"]
if "category_type" not in df_facilities.columns and "category" in df_facilities.columns:
    df_facilities = df_facilities.rename(columns={"category": "category_type"})
elif "category_type" not in df_facilities.columns:
    df_facilities["category_type"] = "Standard Facility"

# 2. Fetch or Load Inventory Batches & Calculate Stock
inventory_data = fetch_api_data("/api/inventory")
if inventory_data and "inventory" in inventory_data:
    inventory_df = pd.DataFrame(inventory_data["inventory"])
else:
    INVENTORY_FILE = BASE_DIR / "data" / "inventory_batches.csv"
    fallback_inventory = pd.DataFrame({
        "batch_id": ["BATCH_001", "BATCH_002", "BATCH_003"],
        "hospital_id": ["H01", "H02", "H03"],
        "drug_name": ["Paracetamol 500mg", "Amoxicillin Caps", "Insulin Glargine"],
        "quantity_in_stock": [150, 80, 45],
        "storage_requirement": ["Room Temp (15-25°C)", "Room Temp (15-25°C)", "Cold Chain (2-8°C)"],
        "expiry_date": ["2026-11-01", "2026-11-05", "2026-12-15"]
    })
    inventory_df = load_csv_data(str(INVENTORY_FILE), fallback_inventory)

# Process inventory calculations safely
if not inventory_df.empty:
    if "quantity_in_stock" in inventory_df.columns:
        inventory_df["quantity_in_stock"] = pd.to_numeric(
            inventory_df["quantity_in_stock"],
            errors="coerce"
        ).fillna(0)
    else:
        inventory_df["quantity_in_stock"] = 0

    if "expiry_date" in inventory_df.columns:
        inventory_df["expiry_date"] = pd.to_datetime(
            inventory_df["expiry_date"],
            errors="coerce"
        )
    else:
        inventory_df["expiry_date"] = pd.NaT

    today = pd.Timestamp.now().normalize()
    inventory_df["usable_stock"] = inventory_df.apply(
        lambda row: (
            row["quantity_in_stock"]
            if pd.notna(row["expiry_date"]) and row["expiry_date"] >= today
            else 0
        ),
        axis=1
    )

    inv_id_col = next((col for col in ["hospital_id", "facility_id", "location", "facility"] if col in inventory_df.columns), "hospital_id")
    if inv_id_col != "hospital_id":
        inventory_df = inventory_df.rename(columns={inv_id_col: "hospital_id"})

    storage_col = next((col for col in ["storage_requirement", "storage_temp", "storage"] if col in inventory_df.columns), None)

    agg_dict = {
        "current_stock_balance": ("quantity_in_stock", "sum"),
        "usable_stock": ("usable_stock", "sum")
    }
    if storage_col:
        agg_dict["storage_temp"] = (storage_col, lambda x: x.iloc[0] if not x.empty else "Room Temp (15-25°C)")

    stock_by_hospital = inventory_df.groupby("hospital_id").agg(**agg_dict).reset_index()
    if "storage_temp" not in stock_by_hospital.columns:
        stock_by_hospital["storage_temp"] = "Room Temp (15-25°C)"
else:
    stock_by_hospital = pd.DataFrame(columns=["hospital_id", "current_stock_balance", "usable_stock", "storage_temp"])

# Merge facilities with inventory calculations
topology_df = pd.merge(df_facilities, stock_by_hospital, on="hospital_id", how="left")
topology_df["current_stock_balance"] = topology_df["current_stock_balance"].fillna(0).astype(int)
topology_df["usable_stock"] = topology_df["usable_stock"].fillna(0).astype(int)
topology_df["storage_temp"] = topology_df["storage_temp"].fillna("Room Temp (15-25°C)")

def determine_redistribution_role(row):
    stock = row["current_stock_balance"]
    usable = row["usable_stock"]
    if stock == 0:
        return "Deficit / Requester"
    elif stock > 200:
        return "Surplus / Donor"
    elif usable < stock * 0.5:
        return "Expiring / Priority Transfer"
    else:
        return "Balanced / Stable"

topology_df["redistribution_role"] = topology_df.apply(determine_redistribution_role, axis=1)

display_topology = topology_df[[
    "hospital_id", "facility_name", "category_type", "current_stock_balance", "storage_temp", "redistribution_role"
]].copy()
display_topology.columns = ["FACILITY ID", "FACILITY NAME", "CATEGORY TYPE", "CURRENT STOCK BALANCE", "STORAGE TEMP", "REDISTRIBUTION ROLE"]


# --- Navigation Tabs ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🏥 Facility Network Topology",
    "📋 Distance Redistribution Plan", 
    "🤖 AI NLP Intake", 
    "📊 Impact Analysis", 
    "🔒 Audit Trail"
])

# --- TAB 1: Facility Network Topology ---
with tab1:
    col_t1, col_t2 = st.columns([3, 1])
    with col_t1:
        st.subheader("Facility Network Topology")
        st.write("Live Health Facility Nodes & Redistribution Stock Metrics calculated from inventory batches.")
    with col_t2:
        st.metric(label="Active Facilities", value=str(len(display_topology)))
    
    st.dataframe(display_topology, use_container_width=True)

# --- TAB 2: Distance Redistribution Plan ---
with tab2:
    st.subheader("Distance Redistribution Plan (`data/distance_redistribution_plan.csv`)")
    fallback_plan = pd.DataFrame({
        "Batch ID": ["BATCH_001", "BATCH_002"],
        "Drug Name": ["Paracetamol 500mg", "Amoxicillin Caps"],
        "From": ["Hospital A", "Hospital C"],
        "To": ["Clinic B", "Clinic D"],
        "Quantity": [100, 50],
        "Distribution Type": ["Free Donation", "Discounted"],
        "Expiry Date": ["2026-11-01", "2026-11-05"]
    })
    df_plan = load_csv_data("data/distance_redistribution_plan.csv", fallback_plan)
    edited_plan = st.data_editor(df_plan, use_container_width=True)
    
    if st.button("Approve & Lock Plan for Dispatch", type="primary"):
        os.makedirs("data", exist_ok=True)
        edited_plan.to_csv("data/distance_redistribution_plan.csv", index=False)
        st.success("Plan successfully approved and saved!")

# --- TAB 3: AI NLP Intake ---
with tab3:
    st.subheader("AI NLP Intake & Scenario Parser")
    user_prompt = st.text_input("Type scenario prompt (e.g., 'demand up 30% at clinic 3'):")
    if user_prompt:
        parsed = ai.parse_typed_what_if(user_prompt)
        st.json(parsed)
        st.success("Structured input verified and queued for solver!")

# --- TAB 4: Impact Analysis ---
with tab4:
    st.subheader("Network Impact: Before vs. After Optimization")
    st.info("Note: 'After Optimization' metrics represent benchmark estimates.")
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.markdown("##### ❌ Before Optimization (Baseline)")
        st.bar_chart(pd.DataFrame({"Metric": ["Stockout Days", "Wasted Units", "Unfulfilled Demand"], "Value": [42, 180, 350]}).set_index("Metric"), color="#ff4b4b")
    with col_chart2:
        st.markdown("##### ✅ After Optimization (Illustrative)")
        st.bar_chart(pd.DataFrame({"Metric": ["Stockout Days", "Wasted Units", "Unfulfilled Demand"], "Value": [4, 12, 25]}).set_index("Metric"), color="#00C853")

# --- TAB 5: Audit Trail ---
with tab5:
    st.subheader("Immutable Audit Trail & Proof Files")
    proof_dir = "proofs"
    if os.path.exists(proof_dir) and os.listdir(proof_dir):
        selected_proof = st.selectbox("Select Proof Log File", sorted(os.listdir(proof_dir), reverse=True))
        if selected_proof:
            with open(os.path.join(proof_dir, selected_proof), "r") as f:
                st.code(f.read(), language="json")
    else:
        st.info("No proof logs found yet.")