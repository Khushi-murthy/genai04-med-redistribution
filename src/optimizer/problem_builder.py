class ProblemBuilder:
    def __init__(self, problem_name: str = "medicine_redistribution_genai04"):
        self.problem_name = problem_name

    def build_payload(
        self,
        safe_options: list,
        optimization_goal: str = "maximize_demand_fulfillment"
    ) -> dict:
        """
        Builds a redistribution optimization payload from validated
        candidate transfers.

        Each candidate transfer becomes a binary decision variable.
        Constraints describe limits that the solver must enforce.
        """
        if not safe_options:
            raise ValueError(
                "No safe options provided to build the optimization problem."
            )

        variables = []
        batch_groups = {}
        source_groups = {}
        destination_groups = {}

        for idx, option in enumerate(safe_options):
            required_fields = [
                "batch_id",
                "source",
                "destination",
                "quantity",
            ]

            missing = [
                field for field in required_fields
                if field not in option
            ]

            if missing:
                raise ValueError(
                    f"Option {idx} is missing fields: {missing}"
                )

            quantity = float(option["quantity"])

            if quantity <= 0:
                raise ValueError(
                    f"Option {idx} must have a positive quantity."
                )

            if option["source"] == option["destination"]:
                raise ValueError(
                    f"Option {idx} has identical source and destination."
                )

            var_id = f"transfer_{idx}"

            variables.append({
                "variable_id": var_id,
                "type": "BINARY",
                "metadata": {
                    **option,
                    "quantity": quantity,
                },
            })

            # Group candidate transfers for constraint construction.
            batch_groups.setdefault(
                str(option["batch_id"]), []
            ).append(var_id)

            source_groups.setdefault(
                str(option["source"]), []
            ).append({
                "variable_id": var_id,
                "quantity": quantity,
            })

            destination_groups.setdefault(
                str(option["destination"]), []
            ).append({
                "variable_id": var_id,
                "quantity": quantity,
            })

        constraints = []

        # A batch may be assigned to at most one candidate transfer.
        for batch_id, variable_ids in batch_groups.items():
            constraints.append({
                "constraint_id": f"batch_{batch_id}_at_most_one",
                "type": "CARDINALITY_LIMIT",
                "variable_ids": variable_ids,
                "limit": 1,
            })

        # Explicitly report grouped quantities for validation.
        # Actual stock and demand constraints require their respective
        # available-stock and demand-cap values from your dataset.
        source_totals = {
            source: sum(item["quantity"] for item in transfers)
            for source, transfers in source_groups.items()
        }

        destination_totals = {
            destination: sum(item["quantity"] for item in transfers)
            for destination, transfers in destination_groups.items()
        }

        payload = {
            "problem_name": self.problem_name,
            "objective": {
                "sense": (
                    "MAXIMIZE"
                    if optimization_goal == "maximize_demand_fulfillment"
                    else "MINIMIZE"
                ),
                "primary_goal": optimization_goal,
            },
            "variables": variables,
            "constraints": constraints,
            "metadata": {
                "total_candidate_options": len(safe_options),
                "candidate_quantity_by_source": source_totals,
                "candidate_quantity_by_destination": destination_totals,
                "requires_stock_and_demand_validation": True,
            },
        }

        return payload