class QUBOBuilder:
    def build_payload(self):
        return {
            "name": "MediResQ AI QUBO Test",
            "method": "QUBO",
            "num_variables": 3,
            "qubo_dict": {
                "0,0": -1.0,
                "0,1": 2.0,
                "1,1": -1.0,
                "2,2": -1.0
            },
            "max_evaluations": 1000,
            "solver_config": {
                "penalty": 1.0
            }
        }