import pandas as pd
import numpy as np

class CreditScorer:
    def __init__(self, data):
        """Accept a DataFrame or a filepath string."""
        if isinstance(data, pd.DataFrame):
            self.df = data.copy()
        else:
            self.df = pd.read_csv(data)
        # Parse dates if available
        if "date" in self.df.columns:
            self.df["date"] = pd.to_datetime(self.df["date"], errors="coerce")
        
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
            income_volatility = 1.0
        
        # Transaction frequency
        total_transactions = len(self.df)
        income_frequency = len(income_df) / max(total_transactions, 1)
        
        # Diversification — unique income sources
        unique_income_sources = income_df['description'].nunique() if 'description' in income_df.columns else 1
        
        # Co-mingling ratio
        personal_count = len(self.df[self.df['category'] == 'Personal'])
        comingling_ratio = personal_count / max(total_transactions, 1)
        
        # High risk count
        high_risk_count = len(high_risk_df)
        
        # Monthly trend metrics
        trend_metrics = self._calculate_monthly_trends(income_df, expense_df)
        
        metrics = {
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
        metrics.update(trend_metrics)
        return metrics
    
    def _calculate_monthly_trends(self, income_df, expense_df):
        """Analyze monthly income/expense trends over time."""
        trends = {
            "income_trend": 0.0,       # positive = growing, negative = declining
            "expense_stability": 1.0,   # lower = more stable (coefficient of variation)
            "active_months": 0,
            "gap_months": 0,
        }
        
        if "date" not in self.df.columns or not pd.api.types.is_datetime64_any_dtype(self.df["date"]):
            return trends
        
        # Group all transactions by month
        self.df["_month"] = self.df["date"].dt.to_period("M")
        
        if self.df["_month"].nunique() < 2:
            self.df.drop(columns=["_month"], errors="ignore", inplace=True)
            return trends
        
        # Monthly income totals
        if len(income_df) > 0 and "date" in income_df.columns:
            inc = income_df.copy()
            inc["_month"] = inc["date"].dt.to_period("M")
            monthly_income = inc.groupby("_month")["amount"].sum().sort_index()
            
            if len(monthly_income) >= 2:
                # Income trend: percentage change from first to last month
                first_val = monthly_income.iloc[0]
                last_val = monthly_income.iloc[-1]
                if first_val > 0:
                    trends["income_trend"] = (last_val - first_val) / first_val
        
        # Monthly expense stability
        if len(expense_df) > 0 and "date" in expense_df.columns:
            exp = expense_df.copy()
            exp["_month"] = exp["date"].dt.to_period("M")
            monthly_expenses = exp.groupby("_month")["amount"].apply(lambda x: x.abs().sum()).sort_index()
            
            if len(monthly_expenses) >= 2 and monthly_expenses.mean() > 0:
                trends["expense_stability"] = monthly_expenses.std() / monthly_expenses.mean()
        
        # Active vs gap months
        all_months = self.df["_month"].sort_values()
        if len(all_months) > 0:
            month_range = pd.period_range(all_months.min(), all_months.max(), freq="M")
            active = self.df["_month"].nunique()
            trends["active_months"] = active
            trends["gap_months"] = len(month_range) - active
        
        self.df.drop(columns=["_month"], errors="ignore", inplace=True)
        return trends

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
        
        # 8. Income trend bonus/penalty (up to ±10 pts)
        trend = metrics.get("income_trend", 0)
        if trend > 0.1:
            base_score += min(trend * 20, 10)    # Growing income: bonus
        elif trend < -0.1:
            base_score += max(trend * 20, -10)   # Declining income: penalty
        
        # 9. Expense stability bonus (up to +5 pts)
        stability = metrics.get("expense_stability", 1.0)
        if stability < 0.3:
            base_score += 5   # Very stable expenses
        elif stability < 0.5:
            base_score += 2
        
        # 10. Gap months penalty (-5 pts per gap)
        base_score -= metrics.get("gap_months", 0) * 5
        
        return round(max(min(base_score, 100), 0), 1)

if __name__ == "__main__":
    scorer = CreditScorer("analyzed_transactions.csv")
    final_score = scorer.generate_score()
    metrics = scorer.calculate_metrics()
    
    print(f"Final SME Credit Score: {final_score}/100")
    print(f"\nMetrics Breakdown:")
    for key, value in metrics.items():
        print(f"  {key}: {value}")