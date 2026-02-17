import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest

def detect_anomalies(df):
    """
    Detects anomalous financial transactions using Isolation Forest.
    
    Parameters:
        df (pd.DataFrame): DataFrame containing at least 'amount' and 'date'.
        
    Returns:
        pd.DataFrame: DataFrame of detected anomalies.
    """
    if df is None or len(df) < 5:
        # Not enough data for ML
        return pd.DataFrame()

    # Preprocessing
    data = df.copy()
    data['amount_abs'] = data['amount'].abs()
    
    # We use amount magnitude for anomaly detection
    # (Future: can add 'frequency' or 'time_of_month' features)
    X = data[['amount_abs']].values
    
    # Initialize Isolation Forest
    # contamination='auto' lets the model decide the threshold
    clf = IsolationForest(contamination=0.05, random_state=42)
    
    # Predict (-1 is anomaly, 1 is normal)
    data['anomaly_score'] = clf.fit_predict(X)
    
    # Filter for anomalies
    anomalies = data[data['anomaly_score'] == -1].copy()
    
    # Sort by amount (descending) to show biggest outliers first
    anomalies = anomalies.sort_values(by='amount_abs', ascending=False)
    
    # Return formatted anomalies
    return anomalies[['date', 'description', 'amount', 'category']]
