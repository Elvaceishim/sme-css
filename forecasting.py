import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from datetime import timedelta

def forecast_balance(df, days_ahead=30):
    """
    Forecasts End-of-Day balance for the next N days using Linear Regression.
    
    Returns:
        hist_df (pd.DataFrame): Historical daily balances containing 'date' and 'balance'.
        pred_df (pd.DataFrame): Predicted future balances containing 'date' and 'balance'.
    """
    if df.empty or 'date' not in df.columns or 'amount' not in df.columns:
        return pd.DataFrame(), pd.DataFrame()

    # 1. Prepare Daily Balance History
    df['date'] = pd.to_datetime(df['date'])
    daily_flow = df.groupby('date')['amount'].sum().reset_index()
    daily_flow = daily_flow.sort_values('date')
    
    # Create a full date range to handle missing days (balance implies carrying forward)
    # But wait, we only know the *change* (transaction amount), not the absolute balance strictly speaking?
    # Actually, pdf_extractor extracts 'balance' column if available!
    # Let's check if 'balance' column exists in input df.
    
    # Strategy: 
    # If 'balance' column exists and is populated, use it.
    # If not, assume starting balance = 0 (or cumulative sum of amounts).
    # Since credit scoring usually cares about trends, cumulative sum is a decent proxy for "Net Position".
    
    # We will use Cumulative Sum of extracted amounts as the "Balance Proxy" if actual balance is missing.
    # However, for specific bank statements (like OPay), we might have extracted 'balance'.
    # Let's assume we use Cumulative Sum for robustness (works for any CSV).
    
    daily_flow['cumulative_balance'] = daily_flow['amount'].cumsum()
    
    # Resample to daily to fill gaps (forward fill last known balance)
    daily_flow.set_index('date', inplace=True)
    daily_balance = daily_flow['cumulative_balance'].resample('D').last().ffill().reset_index()
    
    # 2. Prepare Training Data
    # X = Days since start (integer)
    # y = Balance
    daily_balance['days_from_start'] = (daily_balance['date'] - daily_balance['date'].min()).dt.days
    
    X = daily_balance[['days_from_start']].values
    y = daily_balance['cumulative_balance'].values
    
    if len(X) < 2:
        return daily_balance, pd.DataFrame() # Not enough data
        
    # 3. Fit Linear Regression
    model = LinearRegression()
    model.fit(X, y)
    
    # 4. Predict Next N Days
    last_day = daily_balance['days_from_start'].max()
    future_days = np.arange(last_day + 1, last_day + 1 + days_ahead).reshape(-1, 1)
    future_dates = [daily_balance['date'].max() + timedelta(days=int(i)) for i in range(1, days_ahead + 1)]
    
    future_pred = model.predict(future_days)
    
    pred_df = pd.DataFrame({
        'date': future_dates,
        'cumulative_balance': future_pred,
        'type': 'Forecast'
    })
    
    daily_balance['type'] = 'History'
    
    return daily_balance[['date', 'cumulative_balance', 'type']], pred_df[['date', 'cumulative_balance', 'type']]
