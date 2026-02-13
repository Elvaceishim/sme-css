import pdfplumber
import pandas as pd
import io


def extract_transactions_from_pdf(pdf_file):
    """
    Extract transaction data from a bank statement PDF.
    
    Tries two strategies:
    1. Table extraction — uses pdfplumber's built-in table detection
    2. Text extraction — falls back to parsing raw text line by line
    
    Args:
        pdf_file: A file-like object (e.g., from st.file_uploader)
    
    Returns:
        tuple: (DataFrame, extraction_method) or (None, error_message)
    """
    try:
        pdf = pdfplumber.open(pdf_file)
    except Exception as e:
        return None, f"Could not open PDF: {e}"
    
    # Strategy 1: Table extraction
    df = _extract_from_tables(pdf)
    if df is not None and len(df) > 0:
        df = _clean_extracted_df(df)
        if df is not None and len(df) > 0:
            pdf.close()
            return df, "table_extraction"
    
    # Strategy 2: Text-based extraction
    df = _extract_from_text(pdf)
    if df is not None and len(df) > 0:
        df = _clean_extracted_df(df)
        if df is not None and len(df) > 0:
            pdf.close()
            return df, "text_extraction"
    
    pdf.close()
    return None, "Could not extract transaction data from this PDF. Please try exporting as CSV from your online banking portal."


def _extract_from_tables(pdf):
    """Extract transactions using pdfplumber's table detection."""
    all_rows = []
    header = None
    
    for page in pdf.pages:
        tables = page.extract_tables()
        for table in tables:
            if not table:
                continue
            
            for i, row in enumerate(table):
                # Clean cells
                cleaned = [_clean_cell(cell) for cell in row]
                
                # Detect header row
                if header is None and _is_header_row(cleaned):
                    header = cleaned
                    continue
                
                # Skip empty rows
                if all(c == "" for c in cleaned):
                    continue
                
                all_rows.append(cleaned)
    
    if not all_rows:
        return None
    
    # Determine target width and normalize all rows to that width
    if header:
        target_width = len(header)
    else:
        # Use the most common row length
        from collections import Counter
        widths = Counter(len(r) for r in all_rows)
        target_width = widths.most_common(1)[0][0]
    
    def _normalize_row(row, width):
        if len(row) < width:
            return row + [""] * (width - len(row))
        elif len(row) > width:
            return row[:width]
        return row
    
    all_rows = [_normalize_row(r, target_width) for r in all_rows]
    
    # Build DataFrame
    if header:
        header = _normalize_row(header, target_width)
        df = pd.DataFrame(all_rows, columns=header)
    else:
        df = pd.DataFrame(all_rows)
        # Try to infer column names from first row
        if len(df) > 0 and _is_header_row(df.iloc[0].tolist()):
            df.columns = df.iloc[0]
            df = df.iloc[1:]
    
    # Drop fully empty columns
    df = df.dropna(axis=1, how="all")
    df = df.loc[:, (df != "").any()]
    
    return df if len(df) > 0 else None


def _extract_from_text(pdf):
    """
    Fallback: extract transactions by parsing raw text.
    Looks for lines that start with a date pattern.
    """
    import re
    
    date_patterns = [
        r'\d{2}/\d{2}/\d{4}',   # DD/MM/YYYY
        r'\d{2}-\d{2}-\d{4}',   # DD-MM-YYYY
        r'\d{4}-\d{2}-\d{2}',   # YYYY-MM-DD
        r'\d{2}\s\w{3}\s\d{4}', # DD MMM YYYY
        r'\d{2}-\w{3}-\d{4}',   # DD-MMM-YYYY
    ]
    combined_pattern = "|".join(f"({p})" for p in date_patterns)
    
    rows = []
    for page in pdf.pages:
        text = page.extract_text()
        if not text:
            continue
        
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            
            # Check if line starts with a date
            match = re.match(combined_pattern, line)
            if match:
                date = match.group(0)
                rest = line[match.end():].strip()
                
                # Try to extract amounts (numbers with commas/decimals)
                amounts = re.findall(r'[\d,]+\.\d{2}', rest)
                
                # Remove amounts from description
                description = rest
                for amt in amounts:
                    description = description.replace(amt, "").strip()
                description = re.sub(r'\s+', ' ', description).strip(" -|")
                
                if amounts:
                    rows.append({
                        "date": date,
                        "description": description,
                        "amount_1": amounts[0] if len(amounts) > 0 else "",
                        "amount_2": amounts[1] if len(amounts) > 1 else "",
                        "amount_3": amounts[2] if len(amounts) > 2 else "",
                    })
    
    if not rows:
        return None
    
    df = pd.DataFrame(rows)
    
    # Try to figure out which amount columns are debit/credit/balance
    df = _resolve_amount_columns(df)
    
    return df


def _resolve_amount_columns(df):
    """Convert extracted amount columns into a single signed amount."""
    amount_cols = [c for c in df.columns if c.startswith("amount_")]
    
    for col in amount_cols:
        df[col] = df[col].apply(lambda x: _parse_amount(x) if x else 0)
    
    if "amount_1" in df.columns and "amount_2" in df.columns and "amount_3" in df.columns:
        # Pattern: debit, credit, balance (common in Nigerian bank statements)
        df["amount"] = df.apply(
            lambda r: r["amount_2"] if r["amount_2"] > 0 else -r["amount_1"], axis=1
        )
        df["type"] = df["amount"].apply(lambda x: "Credit" if x >= 0 else "Debit")
        df = df.drop(columns=amount_cols)
    elif "amount_1" in df.columns and "amount_2" in df.columns:
        # Pattern: debit, credit OR amount, balance
        df["amount"] = df.apply(
            lambda r: r["amount_2"] if r["amount_2"] > 0 else -r["amount_1"], axis=1
        )
        df["type"] = df["amount"].apply(lambda x: "Credit" if x >= 0 else "Debit")
        df = df.drop(columns=amount_cols)
    elif "amount_1" in df.columns:
        df = df.rename(columns={"amount_1": "amount"})
        df = df.drop(columns=[c for c in amount_cols if c != "amount_1"], errors="ignore")
    
    return df


def _parse_amount(value):
    """Parse a string amount like '1,500.00' into a float."""
    if not value or value == "":
        return 0.0
    try:
        return float(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return 0.0


def _clean_cell(cell):
    """Clean a table cell value."""
    if cell is None:
        return ""
    return str(cell).strip().replace("\n", " ")


def _is_header_row(row):
    """Check if a row looks like a header (contains keywords)."""
    header_keywords = [
        "date", "narration", "description", "particulars", "details",
        "debit", "credit", "amount", "withdrawal", "deposit", "balance",
        "value date", "trans date", "reference", "remarks", "type"
    ]
    row_text = " ".join(str(cell).lower() for cell in row)
    matches = sum(1 for kw in header_keywords if kw in row_text)
    return matches >= 2


def _clean_extracted_df(df):
    """
    Post-process extracted DataFrame to remove junk rows.
    - Drops rows with empty/null dates
    - Removes header artifact rows
    - Strips whitespace from text columns
    """
    import re
    
    # Normalize column names
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    # Drop rows where date is empty/null
    if "date" in df.columns:
        df = df[df["date"].astype(str).str.strip().ne("")]
        df = df[df["date"].astype(str).str.strip().ne("nan")]
        df = df[df["date"].astype(str).str.strip().ne("None")]
    
    # Drop rows that look like repeated headers
    junk_patterns = [
        r'^(date|description|narration|trans\.?\s*time|channel|balance|s/n|no\.)$',
    ]
    if "description" in df.columns:
        for pat in junk_patterns:
            mask = df["description"].astype(str).str.strip().str.match(pat, case=False, na=False)
            df = df[~mask]
    
    # Strip whitespace from all string columns
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].apply(lambda x: re.sub(r'\s+', ' ', x))
    
    # Drop fully empty rows
    df = df.replace("", pd.NA).dropna(how="all").fillna("")
    
    return df.reset_index(drop=True) if len(df) > 0 else None
