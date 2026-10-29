from src.optimizer.donation_matcher import DonationMatcher
from datetime import datetime, timedelta

def test_expiry_tiers():
    matcher = DonationMatcher()
    
    # Generate dynamic dates relative to today
    today = datetime.now()
    date_3_days = (today + timedelta(days=2)).strftime("%Y-%m-%d")  # Should trigger donation
    date_7_days = (today + timedelta(days=6)).strftime("%Y-%m-%d")  # Should trigger discount

    expiring_batches = [
        {"batch_id": "BATCH_A", "drug_name": "Amoxicillin", "quantity": 50, "expiry_date": date_3_days},
        {"batch_id": "BATCH_B", "drug_name": "Paracetamol", "quantity": 100, "expiry_date": date_7_days}
    ]

    public_tickets = [
        {"ticket_id": "TICKET_1", "drug_name": "Amoxicillin", "quantity": 10},
        {"ticket_id": "TICKET_2", "drug_name": "Paracetamol", "quantity": 30}
    ]

    results = matcher.process_donation_queue(expiring_batches, public_tickets)
    import json
    print("Donation/Discount Match Results:")
    print(json.dumps(results, indent=4))

if __name__ == "__main__":
    test_expiry_tiers()