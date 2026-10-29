from datetime import datetime
import json
import os

class DonationMatcher:
    def __init__(self, tickets_file_path: str = "data/public_tickets.json"):
        self.tickets_file_path = tickets_file_path

    def load_live_tickets(self) -> list:
        """
        Loads tickets dynamically raised by users from the shared file/database 
        where the webpage stores them.
        """
        if os.path.exists(self.tickets_file_path):
            with open(self.tickets_file_path, "r") as f:
                return json.load(f)
        return []

    def process_donation_queue(self, expiring_batches: list, public_tickets: list = None) -> list:
        """
        Matches near-expiry surplus medicines with public patient/charity tickets.
        If no tickets are passed explicitly, it automatically fetches live tickets from the frontend storage.
        """
        if public_tickets is None:
            public_tickets = self.load_live_tickets()

        donation_allocations = []
        current_date = datetime.now()

        for ticket in public_tickets:
            drug_needed = ticket["drug_name"]
            requested_qty = ticket["quantity"]
            
            for batch in expiring_batches:
                if batch["drug_name"] == drug_needed and batch["quantity"] >= requested_qty:
                    expiry_date = datetime.strptime(batch["expiry_date"], "%Y-%m-%d")
                    days_to_expiry = (expiry_date - current_date).days

                    if days_to_expiry <= 3:
                        distribution_type = "free_donation"
                    elif days_to_expiry <= 7:
                        distribution_type = "discounted_distribution"
                    else:
                        continue

                    donation_allocations.append({
                        "ticket_id": ticket["ticket_id"],
                        "batch_id": batch["batch_id"],
                        "drug_name": drug_needed,
                        "allocated_quantity": requested_qty,
                        "days_to_expiry": days_to_expiry,
                        "distribution_type": distribution_type,
                        "status": "matched"
                    })
                    batch["quantity"] -= requested_qty
                    break
                    
        return donation_allocations