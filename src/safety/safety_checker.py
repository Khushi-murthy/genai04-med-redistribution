class SafetyChecker:
    def __init__(self, max_allowable_quantity: int = 5000):
        self.max_allowable_quantity = max_allowable_quantity

    def audit_transfer_plan(self, final_plan: dict) -> dict:
        """
        Performs a final safety audit on the optimized transfer plan before execution.
        """
        violations = []
        is_approved = True

        transfers = final_plan.get("selected_transfers", [])

        if not transfers:
            return {
                "is_approved": False,
                "violations": ["No transfers selected in the final plan."]
            }

        for idx, item in enumerate(transfers):
            # Rule 1: Check quantity limits
            qty = item.get("quantity", 0)
            if qty <= 0:
                is_safe = False
                violations.append(f"Transfer #{idx}: Quantity must be greater than zero.")
            elif qty > self.max_allowable_quantity:
                violations.append(f"Transfer #{idx}: Exceeds maximum single-batch transfer limit ({self.max_allowable_quantity}).")
                is_approved = False

            # Rule 2: Verify safety status flag from earlier constraints
            if not item.get("is_safe", True):
                violations.append(f"Transfer #{idx} contains an unsafe batch flag.")
                is_approved = False

        return {
            "is_approved": is_approved,
            "violations": violations,
            "total_audited": len(transfers)
        }