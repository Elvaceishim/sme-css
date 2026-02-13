import os
import json
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

class TransactionProcessor:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("API Key not found! Ensure OPENROUTER_API_KEY is set in your .env file.")
        
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key
        )
        self.model = "google/gemini-2.0-flash-001"

    def _get_system_prompt(self):
        return """
        You are a financial underwriter for a Nigerian SME lender.
        Categorize transactions into: 'Business Income', 'Operational Expense', 'Personal', or 'High Risk'.
        Provide a short reasoning for each.
        Return ONLY a JSON object with a 'results' key containing the list of categorized transactions.
        """

    def process_batch(self, batch_df):
        """Processes a single chunk of data using the LLM."""
        data_json = batch_df.to_dict(orient="records")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": f"Categorize these: {json.dumps(data_json)}"}
                ],
                response_format={"type": "json_object"}
            )
            # Parse the AI's JSON response
            return json.loads(response.choices[0].message.content).get("results", [])
        except Exception as e:
            print(f"Error processing batch: {e}")
            return []

    def run_pipeline(self, input_csv, output_csv, batch_size=10):
        """Reads large CSV in chunks to avoid memory crashes."""
        print(f"Starting pipeline: {input_csv} -> {output_csv}")
        
        for i, chunk in enumerate(pd.read_csv(input_csv, chunksize=batch_size)):
            print(f"Processing batch {i+1}...")
            categorized_data = self.process_batch(chunk)
            
            result_df = pd.DataFrame(categorized_data)
            mode = 'w' if i == 0 else 'a'
            header = True if i == 0 else False
            result_df.to_csv(output_csv, mode=mode, index=False, header=header)

if __name__ == "__main__":
    processor = TransactionProcessor()
    
    processor.run_pipeline("transactions.csv", "analyzed_transactions.csv")