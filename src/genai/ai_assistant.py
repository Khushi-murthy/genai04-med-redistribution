import os

class AIAssistant:
    def __init__(self):
        # Fallback text in case AI API fails or is unavailable
        self.fallback_explanation = "This transfer was automatically selected to clear near-expiry stock while meeting the minimum regional shortage requirement safely."

    def explain_transfer(self, transfer_record: dict) -> str:
        """
        Explains an individual transfer order in plain English.
        Includes a fixed-text fallback mechanism.
        """
        try:
            # Placeholder for actual LLM call (e.g., Gemini API)
            drug = transfer_record.get("drug_name", "Medicine")
            qty = transfer_record.get("quantity", 0)
            src = transfer_record.get("from", "Source")
            dest = transfer_record.get("to", "Destination")
            
            return f"The system prioritized moving {qty} units of {drug} from {src} to {dest} to prevent an imminent stockout and mitigate expiry loss."
        except Exception:
            return self.fallback_explanation

    def parse_typed_what_if(self, text_input: str) -> dict:
        """
        Parses natural language what-if commands (e.g., 'demand up 30% at clinic 3') 
        into structured parameters.
        """
        text_lower = text_input.lower()
        parsed_result = {"target": "general", "metric": "demand", "value": 10, "raw_text": text_input}
        
        if "clinic" in text_lower or "hospital" in text_lower:
            # Simple keyword extraction mock
            words = text_lower.split()
            for i, w in enumerate(words):
                if w in ["clinic", "hospital"] and i + 1 < len(words):
                    parsed_result["target"] = f"{w}_{words[i+1]}"
                    
        if "up" in text_lower or "increase" in text_lower:
            for word in text_lower.split():
                if "%" in word or word.isdigit():
                    parsed_result["value"] = int(''.filter(str.isdigit, word) or 20)
                    
        return parsed_result