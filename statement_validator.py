import pandas as pd
from datetime import datetime, timedelta

# Common column name mappings for Nigerian bank CSV exports
COLUMN_MAPPINGS = {
    # Date columns
    "date": "date",
    "trans date": "date",
    "transaction date": "date",
    "value date": "date",
    "posting date": "date",
    "txn date": "date",
    
    # Description columns
    "description": "description",
    "narration": "description",
    "remarks": "description",
    "details": "description",
    "transaction details": "description",
    "particulars": "description",
    "reference": "description",
    
    # Amount columns
    "amount": "amount",
    "transaction amount": "amount",
    "txn amount": "amount",
    
    # Credit/Debit split columns (handled separately)
    "credit": "_credit",
    "credit amount": "_credit",
    "deposits": "_credit",
    "debit": "_debit",
    "debit amount": "_debit",
    "withdrawals": "_debit",
    
    # Type columns
    "type": "type",
    "transaction type": "type",
    "txn type": "type",
    "dr/cr": "type",
}

DATE_FORMATS = [
    "%Y-%m-%d",      # 2026-01-15
    "%d/%m/%Y",      # 15/01/2026
    "%m/%d/%Y",      # 01/15/2026
    "%d-%m-%Y",      # 15-01-2026
    "%d-%b-%Y",      # 15-Jan-2026
    "%d-%B-%Y",      # 15-January-2026
    "%d %b %Y",      # 15 Jan 2026
    "%d %B %Y",      # 15 January 2026
    "%Y/%m/%d",      # 2026/01/15
]

MIN_MONTHS = 3


def _normalize_columns(df):
    """Map bank-specific column names to our standard schema."""
    df.columns = [col.strip().lower() for col in df.columns]
    
    rename_map = {}
    for original_col in df.columns:
        mapped = COLUMN_MAPPINGS.get(original_col)
        if mapped:
            rename_map[original_col] = mapped
    
    df = df.rename(columns=rename_map)
    
    # Handle split credit/debit columns → single amount column
    if "_credit" in df.columns and "_debit" in df.columns:
        df["_credit"] = pd.to_numeric(df["_credit"], errors="coerce").fillna(0)
        df["_debit"] = pd.to_numeric(df["_debit"], errors="coerce").fillna(0)
        df["amount"] = df["_credit"] - df["_debit"]
        df["type"] = df["amount"].apply(lambda x: "Credit" if x >= 0 else "Debit")
        df = df.drop(columns=["_credit", "_debit"])
    
    return df


def _parse_dates(df):
    """Try multiple date formats and parse the date column."""
    if "date" not in df.columns:
        return df, None
    
    for fmt in DATE_FORMATS:
        try:
            parsed = pd.to_datetime(df["date"], format=fmt, dayfirst=True)
            if parsed.notna().sum() > len(df) * 0.8:  # At least 80% parsed
                df["date"] = parsed
                return df, fmt
        except (ValueError, TypeError):
            continue
    
    # Fallback: let pandas infer
    try:
        df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
        return df, "inferred"
    except Exception:
        return df, None


def validate_statement(df):
    """
    Validate and normalize a bank statement DataFrame.
    
    Returns:
        tuple: (cleaned_df, summary_dict, warnings_list)
    """
    warnings = []
    
    # 1. Normalize column names
    df = _normalize_columns(df)
    
    # Check required columns
    required = ["date", "description", "amount"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        return None, None, [f"Missing required columns: {', '.join(missing)}. Found: {', '.join(df.columns)}"]
    
    # 2. Parse dates
    df, date_format = _parse_dates(df)
    if date_format is None:
        warnings.append("Could not parse dates. Please ensure a 'date' column with a recognizable format.")
    
    # 3. Clean amount column
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df = df.dropna(subset=["amount"])
    
    # 4. Infer type if missing
    if "type" not in df.columns:
        df["type"] = df["amount"].apply(lambda x: "Credit" if x >= 0 else "Debit")
    
    # 5. Sort by date
    if pd.api.types.is_datetime64_any_dtype(df["date"]):
        df = df.sort_values("date").reset_index(drop=True)
    
    # 6. Calculate statement period
    summary = _build_summary(df, date_format)
    
    # Clean up temp columns
    df = df.drop(columns=["_month"], errors="ignore")
    
    # 7. Validate minimum period
    if summary.get("months_covered", 0) < MIN_MONTHS:
        months = summary.get("months_covered", 0)
        warnings.append(
            f"Statement covers only {months} month(s). "
            f"A minimum of {MIN_MONTHS} months is recommended for reliable scoring."
        )
    
    return df, summary, warnings


def _build_summary(df, date_format):
    """Build a summary of the statement data."""
    summary = {
        "total_transactions": len(df),
        "date_format_detected": date_format or "unknown",
        "columns_found": list(df.columns),
    }
    
    if pd.api.types.is_datetime64_any_dtype(df["date"]):
        valid_dates = df["date"].dropna()
        if len(valid_dates) > 0:
            start = valid_dates.min()
            end = valid_dates.max()
            days = (end - start).days
            months = max(1, round(days / 30))
            
            summary.update({
                "start_date": start.strftime("%Y-%m-%d"),
                "end_date": end.strftime("%Y-%m-%d"),
                "days_covered": days,
                "months_covered": months,
            })
            
            # Monthly breakdown
            df["_month"] = df["date"].dt.to_period("M")
            monthly = df.groupby("_month")["amount"].agg(
                credits=lambda x: x[x > 0].sum(),
                debits=lambda x: x[x < 0].abs().sum(),
                count="count"
            ).reset_index()
            monthly["_month"] = monthly["_month"].astype(str)
            summary["monthly_breakdown"] = monthly.to_dict(orient="records")
            
            df = df.drop(columns=["_month"], errors="ignore")
    
    total_credits = df[df["amount"] > 0]["amount"].sum()
    total_debits = df[df["amount"] < 0]["amount"].abs().sum()
    summary["total_credits"] = total_credits
    summary["total_debits"] = total_debits
    
    return summary


def get_monthly_trends(df):
    """Extract monthly income vs expense trends for charting."""
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        return pd.DataFrame()
    
    df = df.copy()
    df["month"] = df["date"].dt.to_period("M").astype(str)
    
    monthly = df.groupby("month")["amount"].agg(
        income=lambda x: x[x > 0].sum(),
        expenses=lambda x: x[x < 0].abs().sum(),
    ).reset_index()
    
    monthly["net"] = monthly["income"] - monthly["expenses"]
    return monthly
