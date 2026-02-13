import pandas as pd

class CreditScorer:
    def __init__(self, filepath):
        self.df = pd.read_csv(filepath)
        
    def calculate_metrics(self):
        # 1. Total Income vs Total Expenses
        income = self.df[self.df['category'] == 'Business Income']['amount'].sum()
        expenses = self.df[self.df['category'].isin(['Operational Expense', 'Personal'])]['amount'].abs().sum()
        
        # 2. Expense Ratio (Lower is better)
        # If income is 0, ratio is 1 (bad)
        expense_ratio = min(expenses / income, 1.0) if income > 0 else 1.0
        
        # 3. High Risk Flags
        high_risk_count = len(self.df[self.df['category'] == 'High Risk'])
        
        return {
            "total_income": income,
            "total_expenses": expenses,
            "expense_ratio": expense_ratio,
            "high_risk_count": high_risk_count
        }

    def generate_score(self):
        metrics = self.calculate_metrics()
        
        # Simple Scoring Logic (0 to 100)
        # Higher income consistency and lower expense ratio = Higher Score
        base_score = 100
        
        # Deduct for high expense ratio
        base_score -= (metrics['expense_ratio'] * 50)
        
        # Deduct for each high risk transaction
        base_score -= (metrics['high_risk_count'] * 10)
        
        return max(min(base_score, 100), 0) # Keep score between 0 and 100

if __name__ == "__main__":
    scorer = CreditScorer("analyzed_transactions.csv")
    final_score = scorer.generate_score()
    print(f"Final SME Credit Score: {final_score}/100")