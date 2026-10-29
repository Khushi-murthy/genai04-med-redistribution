from src.optimizer.clash_finder import ClashFinder
finder = ClashFinder()
mock_options = [
    {"batch_id": "B1", "source": "H1", "destination": "C1"},
    {"batch_id": "B1", "source": "H1", "destination": "C2"}, # Clashes with index 0
    {"batch_id": "B2", "source": "H1", "destination": "C3"}
]
print("Clash Analysis:", finder.find_clashes(mock_options))