from src.optimizer.opt_client import QpiAlClient
from src.optimizer.safe_option_builder import SafeOptionBuilder
from src.optimizer.problem_builder import ProblemBuilder

class ProblemRunner:
    def __init__(self, token: str = "mock_token_123"):
        self.client = QpiAlClient(token=token)
        self.safe_builder = SafeOptionBuilder()
        self.prob_builder = ProblemBuilder()

    def run_optimization_pipeline(self, sources: list, destinations: list, batches: list) -> dict:
        """
        Runs the full end-to-end optimization pipeline:
        1. Filters safe options.
        2. Builds the solver payload.
        3. Sends it to QpiAl Opt and saves proof files.
        """
        # Step 1: Filter safe options
        safe_options = self.safe_builder.filter_safe_options(sources, destinations, batches)
        if not safe_options:
            return {"status": "failed", "message": "No safe transfer options available to optimize."}

        # Step 2: Build payload
        payload = self.prob_builder.build_payload(safe_options)

        # Step 3: Send via client (generates audit proof files automatically)
        try:
            response = self.client.send_problem(payload)
            return {
                "status": "success",
                "payload_sent": payload,
                "solver_response": response
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "payload_attempted": payload
            }