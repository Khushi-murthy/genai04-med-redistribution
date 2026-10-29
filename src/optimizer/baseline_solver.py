class BaselineSolver:
    def solve_baseline(self, safe_options: list) -> dict:
        """
        Performs a greedy optimal baseline solve to compare against QpiAl solver.
        """
        sorted_options = sorted(safe_options, key=lambda x: x["quantity"], reverse=True)
        
        selected = []
        used_batches = set()
        total_qty = 0

        for opt in sorted_options:
            if opt["batch_id"] not in used_batches:
                selected.append(opt)
                used_batches.add(opt["batch_id"])
                total_qty += opt["quantity"]

        return {
            "solver_name": "Greedy-Exact Baseline",
            "selected_transfers": selected,
            "total_quantity_transferred": total_qty,
            "optimality_gap_percentage": 0.0
        }

if __name__ == "__main__":
    solver = BaselineSolver()
    mock_safe_options = [
        {"batch_id": "BATCH_001", "quantity": 100, "source": "H1", "destination": "C1"},
        {"batch_id": "BATCH_002", "quantity": 250, "source": "H1", "destination": "C2"}
    ]
    print("Running Baseline Solver...")
    result = solver.solve_baseline(mock_safe_options)
    import json
    print(json.dumps(result, indent=4))