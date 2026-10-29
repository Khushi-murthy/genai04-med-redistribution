class ClashFinder:
    def find_clashes(self, safe_options: list) -> dict:
        """
        Builds a clash graph identifying mutually exclusive transfer options 
        competing for the same inventory batch.
        """
        clash_graph = {}
        batch_to_indices = {}

        # Map each batch to the safe option indices using it
        for idx, opt in enumerate(safe_options):
            b_id = opt["batch_id"]
            if b_id not in batch_to_indices:
                batch_to_indices[b_id] = []
            batch_to_indices[b_id].append(idx)

        clash_pairs = []
        for b_id, indices in batch_to_indices.items():
            clash_graph[b_id] = indices
            if len(indices) > 1:
                # Options sharing the same batch conflict with each other
                for i in range(len(indices)):
                    for j in range(i + 1, len(indices)):
                        clash_pairs.append((indices[i], indices[j]))

        return {
            "total_options": len(safe_options),
            "clash_pairs": clash_pairs,
            "clash_graph": clash_graph
        }