import os
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

def summarize_financials(df):
    """
    Creates a condensed summary of financial health from the transaction DataFrame.
    Avoids sending thousands of rows to the LLM.
    """
    if df.empty:
        return "No transactions available."
        
    # Basic Totals
    total_credit = df[df['amount'] > 0]['amount'].sum()
    total_debit = df[df['amount'] < 0]['amount'].sum()
    net_flow = total_credit + total_debit
    txn_count = len(df)
    
    # Date Range
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    start_date = df['date'].min().strftime('%Y-%m-%d')
    end_date = df['date'].max().strftime('%Y-%m-%d')
    
    # Categories (Top 5 Expenses)
    expenses = df[df['amount'] < 0].copy()
    if not expenses.empty:
        top_expenses = expenses.groupby('category')['amount'].sum().sort_values().head(5)
        top_expenses_str = top_expenses.to_string()
    else:
        top_expenses_str = "None"

    # Top 5 Largest Transactions (Context for anomalies)
    largest_txns = df.iloc[df['amount'].abs().argsort()].tail(5)
    largest_txns_str = largest_txns[['date', 'description', 'amount']].to_string(index=False)

    summary = f"""
    Financial Summary ({start_date} to {end_date}):
    - Total Income (Credits): ₦{total_credit:,.2f}
    - Total Expenses (Debits): ₦{total_debit:,.2f}
    - Net Cash Flow: ₦{net_flow:,.2f}
    - Transaction Count: {txn_count}
    
    Top 5 Expense Categories:
    {top_expenses_str}
    
    Top 5 Largest Transactions:
    {largest_txns_str}
    """
    return summary


def generate_credit_memo(score, transactions_path):
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.getenv("OPENROUTER_API_KEY"))
    df = pd.read_csv(transactions_path)
    
    # OPTIMIZATION: Summarize data instead of dumping raw rows
    financial_summary = summarize_financials(df)

    prompt = f"""
    You are a Senior Credit Analyst specializing in the Nigerian SME market. 
    Analyze the loan application for a business operating in the current Nigerian economic climate.
    
    Score: {score}/100.
    
    Financial Data Summary:
    {financial_summary}
    
    Specific Instructions:
    - Assess the Net Cash Flow: Is the business cash-positive?
    - Analyze the 'Top Expense Categories': Are they operational (good) or frivolous (bad)?
    - Review 'Largest Transactions': Do they look like normal business activity or capital flight?
    - Provide a specific credit recommendation (Approve/Decline) and a suggested credit limit based on the Total Income.
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