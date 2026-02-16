import pdfplumber
import pandas as pd
import io


def extract_transactions_from_pdf(pdf_file):
    """
    Extract transaction data from a bank statement PDF.
    
    Tries both Table and Text strategies and picks the one with more valid rows.
    """
    try:
        pdf = pdfplumber.open(pdf_file)
    except Exception as e:
        return None, f"Could not open PDF: {e}"
    
    # Helper to count valid dates
    import re
    date_pat = r'(?:\d{2}[-/]\d{2}[-/]\d{4}|\d{2}\s(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s\d{4})'
    
    def count_valid_dates(df):
        if df is None or len(df) == 0 or "date" not in df.columns:
            return 0
        # Count rows where 'date' column matches the date pattern
        valid_mask = df["date"].astype(str).str.contains(date_pat, regex=True, case=False, na=False)
        return valid_mask.sum()

    # Strategy 1: Table extraction
    df_tables = _extract_from_tables(pdf)
    df_tables_clean = _clean_extracted_df(df_tables) if df_tables is not None else None
    score_tables = count_valid_dates(df_tables_clean)
    
    # Strategy 2: Text-based extraction (Regex)
    df_text = _extract_from_text(pdf)
    df_text_clean = _clean_extracted_df(df_text) if df_text is not None else None
    score_text = count_valid_dates(df_text_clean)
    
    # Choose the winner based on VALID dates, not just total rows
    pdf.close()
    
    if score_tables == 0 and score_text == 0:
        # Fallback: if neither produced valid dates, return the one with rows?
        # Or just fail.
        if df_tables_clean is not None and len(df_tables_clean) > 0:
             return df_tables_clean, f"table_extraction (fallback, {len(df_tables_clean)} rows)"
        return None, "Could not extract any valid transactions. Please try CSV export."
        
    if score_text >= score_tables:  # Prefer text if tie or better
        return df_text_clean, f"text_extraction ({score_text} valid rows)"
    else:
        return df_tables_clean, f"table_extraction ({score_tables} valid rows)"


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
    Robust regex-based extraction to handle merged columns.
    Finds lines with: [Date] ... [Amount] or [Description] ... [Date] ... [Amount]
    """
    import re
    
    # Regex patterns
    # Match dates like 15 Nov 2025, 15-11-2025, 15/11/2025
    date_pat = r'(?:\d{2}[-/]\d{2}[-/]\d{4}|\d{2}\s(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s\d{4})'
    # Match amounts OR placeholders (-- or -). 
    # capturing group for the amount itself to distinguish from placeholder
    amount_pat = r'(?:[\d,]+\.\d{2}|--|(?<=\s)-(?=\s))'
    
    rows = []
    
    for page in pdf.pages:
        text = page.extract_text()
        if not text:
            continue
        
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            
            # fast check: must have at least one digit
            if not any(c.isdigit() for c in line):
                continue

            # Find all dates in the line
            dates = re.findall(date_pat, line, re.IGNORECASE)
            # Find all amounts/placeholders in the line
            amounts = re.findall(amount_pat, line)
            
            # Filter matches that are just isolated hyphens if they aren't likely columns
            # (Valid placeholders usually appear after the date)
            
            if dates and len(amounts) >= 2:
                # It's a candidate transaction line!
                primary_date = dates[0]
                
                # Extract Description by removing dates and amounts
                desc = line
                for d in dates:
                    desc = desc.replace(d, " ")
                for a in amounts:
                    desc = desc.replace(a, " ")
                
                # Clean up description
                desc = re.sub(r'[^a-zA-Z0-9\s.,-]', '', desc) 
                desc = re.sub(r'\s+', ' ', desc).strip()
                
                # Skip if description is too short or looks like a header
                if len(desc) < 3 or "Opening Balance" in desc:
                    continue

                # Store raw string values (including placeholders)
                row = {
                    "date": primary_date,
                    "description": desc,
                    "amount_1": amounts[0],
                    "amount_2": amounts[1],
                    "amount_3": amounts[2] if len(amounts) > 2 else "",
                }
                rows.append(row)
    
    if not rows:
        return None
        
    df = pd.DataFrame(rows)
    return _resolve_amount_columns(df)


def _resolve_amount_columns(df):
    """Convert extracted amount columns into a single signed amount using Positional Logic."""
    # Helper to parse "2,000.00" -> 2000.0, "--" -> 0.0
    def parse(x):
        x = str(x).strip()
        if x in ["--", "-", ""]:
            return 0.0
        try:
            return float(x.replace(",", ""))
        except:
            return 0.0

    # Parse all amount columns
    for col in ["amount_1", "amount_2", "amount_3"]:
        if col in df.columns:
            df[col + "_val"] = df[col].apply(parse)
    
    # Infer credit/debit based on POSITION (Debit | Credit | Balance)
    final_amounts = []
    
    for _, row in df.iterrows():
        desc = row["description"].lower()
        a1 = row.get("amount_1_val", 0)
        a2 = row.get("amount_2_val", 0)
        
        # Logic: 
        # Col 1 (a1) = Debit
        # Col 2 (a2) = Credit
        # Col 3 = Balance (ignored)
        
        if a1 > 0 and a2 == 0:
            # Explicit Debit (Col 1 present, Col 2 empty/placeholder)
            final_amounts.append(-abs(a1))
        elif a2 > 0 and a1 == 0:
            # Explicit Credit (Col 1 empty/placeholder, Col 2 present)
            final_amounts.append(abs(a2))
        else:
            # Ambiguous (e.g. missing placeholders, so we have 2 numbers: [Transaction, Balance])
            # Strategy: Trust the FIRST number (a1) as the transaction amount.
            # (Because Balance is usually the last number).
            # Previous logic used max(a1, a2) which caused Inflation by picking Balance.
            
            val = a1 
            
            # Keyword inference fallback
            credit_keywords = [
                "transfer from", "deposit", "credit", "inward", "nip from", "trf from", 
                "fip", "ut", "dividend", "interest", "refund", "reversal", "topup", 
                "received", "fbn mobile", "uba mobile", "access mobile", "gtb mobile",
                "zenith mobile", "firstmobile", "alat", "opay", "loan", "disbursement"
            ]
            
            is_credit = any(k in desc for k in credit_keywords)
            
            if is_credit:
                final_amounts.append(abs(val))
            else:
                # Default to Expense if ambiguous
                final_amounts.append(-abs(val))
             
    df["amount"] = final_amounts
    df["type"] = df["amount"].apply(lambda x: "Credit" if x >= 0 else "Debit")
    
    # Drop temp cols
    df = df.drop(columns=[c for c in df.columns if c.startswith("amount_")], errors="ignore")
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
