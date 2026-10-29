from datetime import datetime, timedelta

class SafeOptionBuilder:
    def __init__(self, transport_buffer_days: int = 2):
        self.transport_buffer_days = transport_buffer_days

    def validate_transfer(self, source_facility: dict, dest_facility: dict, batch: dict) -> dict:
        """
        Validates whether a specific medicine batch can be safely transferred 
        from a source facility to a destination facility based on GENAI-04 rules.
        """
        reasons = []
        is_safe = True

        # 1. Drug Identity Match Check
        if batch["drug_name"] not in dest_facility.get("requested_drugs", []):
            is_safe = False
            reasons.append("Drug identity mismatch or not requested by destination.")

        # 2. Minimum Stock Reserve Check at Source
        current_source_qty = source_facility["inventory"].get(batch["drug_name"], 0)
        min_reserve = source_facility.get("min_stock_reserve", 0)
        transfer_qty = batch["quantity"]

        if (current_source_qty - transfer_qty) < min_reserve:
            is_safe = False
            reasons.append(f"Transfer violates source minimum stock reserve ({min_reserve}).")

        # 3. Expiry & Shelf-Life Check
        expiry_date = datetime.strptime(batch["expiry_date"], "%Y-%m-%d")
        min_allowable_expiry = datetime.now() + timedelta(days=self.transport_buffer_days)

        if expiry_date <= min_allowable_expiry:
            is_safe = False
            reasons.append("Batch is too close to expiry or already expired for safe transport.")

        # 4. Cold-Chain & Temperature Compatibility Check
        batch_temp = batch.get("storage_temp", "ambient")
        dest_temp_support = dest_facility.get("supported_temperatures", ["ambient"])
        
        if batch_temp not in dest_temp_support:
            is_safe = False
            reasons.append(f"Cold-chain mismatch: Destination does not support required storage ({batch_temp}).")

        return {
            "batch_id": batch["batch_id"],
            "drug_name": batch["drug_name"],
            "source": source_facility["id"],
            "destination": dest_facility["id"],
            "quantity": transfer_qty,
            "is_safe": is_safe,
            "reasons": reasons
        }

    def filter_safe_options(self, sources: list, destinations: list, batches: list) -> list:
        """
        Filters all possible batch transfer combinations and returns only valid, safe options.
        """
        safe_options = []
        
        # Quick lookup dictionaries
        source_map = {s["id"]: s for s in sources}
        dest_map = {d["id"]: d for d in destinations}

        for batch in batches:
            source_fac = source_map.get(batch["current_location"])
            if not source_fac:
                continue

            for dest_fac in destinations:
                # Don't transfer to itself
                if source_fac["id"] == dest_fac["id"]:
                    continue

                validation = self.validate_transfer(source_fac, dest_fac, batch)
                if validation["is_safe"]:
                    safe_options.append(validation)

        return safe_options