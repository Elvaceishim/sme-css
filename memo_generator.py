import os
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

def generate_credit_memo(score, transactions_path):
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.getenv("OPENROUTER_API_KEY"))
    df = pd.read_csv(transactions_path)
    
    available_cols = [c for c in ['description', 'category', 'reasoning', 'amount'] if c in df.columns]
    summary_data = df[available_cols].to_string()

    prompt = f"""
    You are a Senior Credit Analyst specializing in the Nigerian SME market. 
    Analyze the loan application for a business operating in the current Nigerian economic climate.
    
    Score: {score}/100.
    Data: {summary_data}
    
    Specific Instructions:
    - Identify if spending on fuel/power is stable (operational health).
    - Look for 'Co-mingling': Are they paying school fees or family transfers from a business account?
    - Consider the 'Bet9ja/SportyBet' factor as a high-risk behavioral red flag.
    - Provide a recommendation based on typical Nigerian interest rates (e.g., 5-10% monthly for high risk, lower for low risk).
    """

    response = client.chat.completions.create(
        model="google/gemini-2.0-flash-001",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

if __name__ == "__main__":
    test_score = 72.5 
    print("Generating Credit Memo...\n")
    memo = generate_credit_memo(test_score, "analyzed_transactions.csv")
    print(memo)