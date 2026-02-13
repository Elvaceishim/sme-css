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
        Return ONLY a JSON object with a 'results' key containing a list.
        Each item must have: date, description, amount, type, category, reason.
        Keep the original date, description, amount, and type values exactly as provided.
        """

    def process_batch(self, batch_df):
        """Processes a single chunk of data using the LLM."""
        # Only send relevant columns to reduce token usage
        cols_to_send = [c for c in ['date', 'description', 'amount', 'type'] if c in batch_df.columns]
        data_json = batch_df[cols_to_send].to_dict(orient="records")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": f"Categorize these: {json.dumps(data_json)}"}
                ],
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            results = json.loads(content).get("results", [])
            return results
        except Exception as e:
            print(f"Error processing batch: {e}")
            # Return original rows with default category on failure
            fallback = batch_df[cols_to_send].to_dict(orient="records")
            for row in fallback:
                row["category"] = "Uncategorized"
                row["reason"] = "AI processing failed"
            return fallback

    def run_pipeline(self, input_csv, output_csv, batch_size=100):
        """Process CSV in batches with larger batch size for speed."""
        df = pd.read_csv(input_csv)
        total_rows = len(df)
        all_results = []
        
        for start in range(0, total_rows, batch_size):
            end = min(start + batch_size, total_rows)
            batch = df.iloc[start:end]
            
            categorized = self.process_batch(batch)
            all_results.extend(categorized)
        
        # Build result DataFrame and save safely
        if all_results:
            result_df = pd.DataFrame(all_results)
            # Ensure no stray commas/newlines corrupt the CSV
            for col in result_df.select_dtypes(include='object').columns:
                result_df[col] = result_df[col].astype(str).str.replace('\n', ' ').str.replace('\r', ' ')
            result_df.to_csv(output_csv, index=False, quoting=1)  # quoting=1 = QUOTE_ALL
        else:
            # Fallback: save original with default categories
            df["category"] = "Uncategorized"
            df["reason"] = "Processing failed"
            df.to_csv(output_csv, index=False, quoting=1)

if __name__ == "__main__":
    processor = TransactionProcessor()
    processor.run_pipeline("transactions.csv", "analyzed_transactions.csv")