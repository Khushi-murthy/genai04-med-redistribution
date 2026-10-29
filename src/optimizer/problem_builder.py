class ProblemBuilder:
    def __init__(self, problem_name: str = "medicine_redistribution_genai04"):
        self.problem_name = problem_name

    def build_payload(self, safe_options: list, optimization_goal: str = "maximize_demand_fulfillment") -> dict:
        """
        Translates safe transfer options into the structured JSON payload 
        required by the QpiAl solver API.
        """
        if not safe_options:
            raise ValueError("No safe options provided to build the optimization problem.")

        # Define decision variables based on safe options
        variables = []
        for idx, option in enumerate(safe_options):
            var_id = f"transfer_{idx}_{option['batch_id']}_{option['source']}_to_{option['destination']}"
            variables.append({
                "variable_id": var_id,
                "type": "BINARY",  # 1 to execute transfer, 0 otherwise
                "cost_coefficient": -float(option["quantity"]),  # Negative if maximizing fulfilled quantity
                "metadata": option
            })

        # Define constraints (e.g., source stock limits, destination demand caps)
        constraints = [
            {
                "constraint_id": "max_one_transfer_per_batch",
                "description": "Ensure a single specific batch is not over-allocated across multiple conflicting paths.",
                "type": "CARDINALITY_LIMIT",
                "limit": 1
            }
        ]

        # Construct final payload matching solver schema
        payload = {
            "problem_name": self.problem_name,
            "objective": {
                "sense": "MAXIMIZE" if "maximize" in optimization_goal else "MINIMIZE",
                "primary_goal": optimization_goal
            },
            "variables": variables,
            "constraints": constraints,
            "metadata": {
                "total_candidate_options": len(safe_options)
            }
        }

        return payload