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
    "deposit": "_credit",
    "credit(₦)": "_credit",
    "credit (₦)": "_credit",
    "credit(ngn)": "_credit",
    "debit": "_debit",
    "debit amount": "_debit",
    "withdrawals": "_debit",
    "withdrawal": "_debit",
    "debit(₦)": "_debit",
    "debit (₦)": "_debit",
    "debit(ngn)": "_debit",
    
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


def _parse_numeric_column(series):
    """Parse a column with amounts like '₦9,850.00', '9,850.00', '--', etc."""
    import re
    def _clean_amount(val):
        val = str(val).strip()
        # Remove currency symbols and letters
        val = re.sub(r'[₦$NGN]', '', val, flags=re.IGNORECASE)
        # Remove commas
        val = val.replace(',', '')
        # Handle dashes ("--" or "-" meaning zero/empty)
        val = val.strip()
        if val in ('', '-', '--', '---', 'None', 'nan', 'N/A', 'nil'):
            return 0.0
        try:
            return float(val)
        except (ValueError, TypeError):
            return None  # Truly unparseable
    
    result = series.apply(_clean_amount)
    return pd.to_numeric(result, errors='coerce').fillna(0)


def _normalize_columns(df):
    """Map bank-specific column names to our standard schema."""
    import re
    df.columns = [col.strip().lower() for col in df.columns]
    
    rename_map = {}
    for original_col in df.columns:
        # Direct match first
        mapped = COLUMN_MAPPINGS.get(original_col)
        if mapped:
            rename_map[original_col] = mapped
            continue
        
        # Fuzzy match: strip parenthesized content like (₦) or (NGN)
        stripped = re.sub(r'\s*\(.*?\)\s*', '', original_col).strip()
        mapped = COLUMN_MAPPINGS.get(stripped)
        if mapped:
            rename_map[original_col] = mapped
    
    df = df.rename(columns=rename_map)
    
    # Handle split credit/debit columns → single amount column
    if "_credit" in df.columns and "_debit" in df.columns:
        df["_credit"] = _parse_numeric_column(df["_credit"])
        df["_debit"] = _parse_numeric_column(df["_debit"])
        df["amount"] = df["_credit"] - df["_debit"]
        df["type"] = df["amount"].apply(lambda x: "Credit" if x >= 0 else "Debit")
        df = df.drop(columns=["_credit", "_debit"])
    
    return df


def _parse_dates(df, warnings_list=None):
    """Try multiple date formats and parse the date column."""
    if "date" not in df.columns:
        return df, None
    
    # Store original values for debug
    original_dates = df["date"].copy()

    for fmt in DATE_FORMATS:
        try:
            parsed = pd.to_datetime(df["date"], format=fmt, dayfirst=True, errors='coerce')
            if parsed.notna().sum() > len(df) * 0.8:  # At least 80% parsed
                df["date"] = parsed
                return df, fmt
        except (ValueError, TypeError):
            continue
    
    # Fallback: let pandas infer
    try:
        df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
        
        # Debug: log sample bad dates if we have warnings list
        if warnings_list is not None:
            failed_mask = df["date"].isna()
            if failed_mask.any():
                bad_samples = original_dates[failed_mask].unique()[:10]
                warnings_list.append(f"DEBUG: Sample unparseable dates: {', '.join(map(str, bad_samples))}")
        
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
    df, date_format = _parse_dates(df, warnings)
    if date_format is None:
        warnings.append("Could not parse dates. Please ensure a 'date' column with a recognizable format.")
    
    # 2b. Drop rows where date could not be parsed (shows as 'None')
    if pd.api.types.is_datetime64_any_dtype(df["date"]):
        before_count = len(df)
        df = df.dropna(subset=["date"])
        dropped = before_count - len(df)
        if dropped > 0:
            warnings.append(f"Dropped {dropped} rows with unparseable dates.")
            # DEBUG: Show what the bad dates look like
            bad_dates = df[df["date"].isna()]["date"].astype(str).unique()[:20]
            warnings.append(f"Sample bad dates: {', '.join(bad_dates)}")
    
    # 3. Clean amount column (handle commas, currency symbols, dashes)
    df["amount"] = _parse_numeric_column(df["amount"])
    # Only drop rows where amount is completely empty/unparseable, NOT where it's genuinely 0
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
