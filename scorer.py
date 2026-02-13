import pandas as pd
import numpy as np

class CreditScorer:
    def __init__(self, filepath):
        self.df = pd.read_csv(filepath)
        
    def calculate_metrics(self):
        """Calculate comprehensive financial metrics from transaction data."""
        income_df = self.df[self.df['category'] == 'Business Income']
        expense_df = self.df[self.df['category'].isin(['Operational Expense', 'Personal'])]
        high_risk_df = self.df[self.df['category'] == 'High Risk']
        
        total_income = income_df['amount'].sum()
        total_expenses = expense_df['amount'].abs().sum()
        
        # Expense ratio (lower is better)
        expense_ratio = min(total_expenses / total_income, 1.0) if total_income > 0 else 1.0
        
        # Income consistency — standard deviation relative to mean (lower = more stable)
        income_values = income_df['amount']
        if len(income_values) > 1 and income_values.mean() != 0:
            income_volatility = income_values.std() / income_values.mean()
        else:
            income_volatility = 1.0  # High volatility if insufficient data
        
        # Transaction frequency
        total_transactions = len(self.df)
        income_frequency = len(income_df) / max(total_transactions, 1)
        
        # Diversification — how many unique income sources (descriptions)
        unique_income_sources = income_df['description'].nunique() if 'description' in income_df.columns else 1
        
        # Co-mingling ratio — personal spending mixed with business
        personal_count = len(self.df[self.df['category'] == 'Personal'])
        comingling_ratio = personal_count / max(total_transactions, 1)
        
        # High risk count
        high_risk_count = len(high_risk_df)
        
        return {
            "total_income": total_income,
            "total_expenses": total_expenses,
            "expense_ratio": expense_ratio,
            "income_volatility": income_volatility,
            "income_frequency": income_frequency,
            "unique_income_sources": unique_income_sources,
            "comingling_ratio": comingling_ratio,
            "high_risk_count": high_risk_count,
            "total_transactions": total_transactions,
        }

    def generate_score(self):
        """Generate a 0-100 credit score using weighted signals."""
        metrics = self.calculate_metrics()
        
        base_score = 100
        
        # 1. Expense ratio penalty (up to -30 pts)
        base_score -= metrics['expense_ratio'] * 30
        
        # 2. Income volatility penalty (up to -15 pts)
        volatility_penalty = min(metrics['income_volatility'], 1.0) * 15
        base_score -= volatility_penalty
        
        # 3. Low income frequency penalty (up to -10 pts)
        if metrics['income_frequency'] < 0.3:
            base_score -= 10
        elif metrics['income_frequency'] < 0.5:
            base_score -= 5
        
        # 4. Income diversification bonus (up to +5 pts)
        if metrics['unique_income_sources'] >= 3:
            base_score += 5
        elif metrics['unique_income_sources'] >= 2:
            base_score += 2
        
        # 5. Co-mingling penalty (up to -15 pts)
        base_score -= metrics['comingling_ratio'] * 15
        
        # 6. High-risk transaction penalty (-10 pts each)
        base_score -= metrics['high_risk_count'] * 10
        
        # 7. Insufficient data penalty
        if metrics['total_transactions'] < 5:
            base_score -= 10
        
        return round(max(min(base_score, 100), 0), 1)

if __name__ == "__main__":
    scorer = CreditScorer("analyzed_transactions.csv")
    final_score = scorer.generate_score()
    metrics = scorer.calculate_metrics()
    
    print(f"Final SME Credit Score: {final_score}/100")
    print(f"\nMetrics Breakdown:")
    for key, value in metrics.items():
        print(f"  {key}: {value}")