# 🚀 MediResQ AI (Quant-A-Maze 3.0 • GENAI-04)

**MediResQ AI** is an intelligent, full-stack medical supply chain and humanitarian platform designed to eliminate pharmaceutical waste, prevent facility stockouts, and provide free life-saving medicines to low-income populations through advanced mathematical optimization and generative AI.

---

## 🎨 Custom Visual Brand Identity
* **Sage Green:** `#9caf88` (Primary brand color, active states, badges)
* **Concrete Grey:** `#a7a7a7` (Neutral structural borders, subtext, secondary states)
* **Burnt Amber:** `#cc5500` (Urgent alerts, risk highlights, actions)

---

## 🏗️ Core Architecture & Tech Stack

MediResQ AI runs on a decoupled multi-part architecture:
1. **Frontend Landing & Dashboard (`index.html`):**
   * Fullscreen background video landing page with a glowing launch button.
   * Built with Tailwind CSS and styled with the custom Sage Green, Concrete Grey, and Burnt Amber palette.
   * Houses an interactive 9-tab workspace.
2. **Map Simulation Backend (Port `8501`):**
   * Powered by `src/map_simulation/map_preview.py` for geospatial and route simulations.
3. **Data & Solver Backend (Port `8502`):**
   * Powered by Streamlit (`app.py`), managing live CSV-backed data synchronization (`data/distance_redistribution_plan.csv`).
4. **Optimization & Security Layer:**
   * Uses `src/optimizer/opt_client.py` and `run_pipeline.py` to securely interface with the **QpiAI Optimization API** via environment variables (`.env`), writing cryptographic proof logs to the `proofs/` directory.

---

## ✨ Key Features & Humanitarian Differentiator (USP)

* **The Humanitarian Mandate:** Automatically flags sealed essential medicines nearing expiration ($\le 7$ days) and allocates them **100% FREE** to low-income, uninsured individuals under health officer authorization, while discounting longer-expiry surplus stock.
* **Role-Based Security Portal:**
  * **Citizen Mode:** Allows patients/citizens to submit direct allocation requests and track request statuses (read-only).
  * **Admin / Officer Mode:** Strictly locked behind an authorized health officer passcode (**`1305`**), granting exclusive permissions to review, authorize, or reject medicine release claims.
* **GenAI NLP Assistant (`src/genai/ai_assistant.py`):**
  * **AI NLP Intake:** Translates free-form human text prompts (e.g., *"demand up 30% at clinic 3"*) into validated structured dataset schemas.
  * **AI Plan Narrative Explainer:** Translates complex mathematical solver outputs into plain-English operational reasoning for hospital administrators.
* **Interactive What-If Simulator & Risk Forecasts:**
  * Test regional demand surges, vehicle shortages, and temperature threshold shifts with live backend recalculations.

---

## 🚀 Getting Started & Local Execution

### 1. Clone the Repository & Configure Environment
```bash
git clone [https://github.com/your-username/genai04-med-redistribution.git](https://github.com/your-username/genai04-med-redistribution.git)
cd genai04-med-redistribution
