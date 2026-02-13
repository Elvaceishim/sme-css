"""
Rule-based transaction categorizer for Nigerian bank statements.
Categorizes transactions instantly using keyword matching — no API calls needed.
"""
import pandas as pd
import re


# Category rules: (pattern, category, reason)
# Patterns are checked in order; first match wins.
CATEGORIZATION_RULES = [
    # ── High Risk ──
    (r'\b(sporty|bet9ja|betway|1xbet|nairabet|betking|betting|gambl)', 'High Risk', 'Gambling/betting activity'),
    (r'\b(loan shark|ponzi|fraud)', 'High Risk', 'Suspicious activity'),

    # ── Business Income (incoming transfers / credits) ──
    (r'^transfer from\b', 'Business Income', 'Incoming transfer'),
    (r'\binterest earned\b', 'Business Income', 'Interest income'),
    (r'\binward\b.*\btransfer\b', 'Business Income', 'Inward transfer'),
    (r'\bcredit alert\b', 'Business Income', 'Credit alert'),

    # ── Personal / Savings movements ──
    (r'\bowealth\b', 'Personal', 'OWealth savings movement'),
    (r'\bauto[- ]?save\b', 'Personal', 'Auto-save to savings'),
    (r'\bsavings?\b.*\b(withdrawal|deposit|transfer)\b', 'Personal', 'Savings movement'),
    (r'\bstamp duty\b', 'Operational Expense', 'Government levy'),
    (r'\belectronic money transfer levy\b', 'Operational Expense', 'Government levy'),
    (r'\bvat\b|\bwithholding tax\b', 'Operational Expense', 'Tax/levy'),

    # ── Operational Expense (outgoing transfers with business keywords) ──
    (r'transfer to\b.*\b(fuel|oil|gas|diesel|petrol|energy)', 'Operational Expense', 'Fuel/energy expense'),
    (r'transfer to\b.*\b(rent|landlord)', 'Operational Expense', 'Rent payment'),
    (r'transfer to\b.*\b(food|bread|drink|rice|plantain|fish|egg|buns|cafe)', 'Operational Expense', 'Food/provisions'),
    (r'transfer to\b.*\b(engine|brake|mechanic|spare|part|tyre|tire)', 'Operational Expense', 'Vehicle maintenance'),
    (r'transfer to\b.*\b(shoe|material|fabric|cloth|tailor)', 'Operational Expense', 'Materials/supplies'),
    (r'transfer to\b.*\b(phone|airtime|data)', 'Operational Expense', 'Communication expense'),
    (r'transfer to\b.*\b(waste|clean|sanit)', 'Operational Expense', 'Utility expense'),
    (r'\bmobile data\b|\bairtime\b', 'Operational Expense', 'Communication expense'),
    (r'\bthird[- ]?party merchant\b', 'Operational Expense', 'Merchant payment'),
    (r'\bvirtual card\b', 'Operational Expense', 'Card fee'),

    # ── General outgoing transfers (default to Personal if no business keyword) ──
    (r'^transfer to\b', 'Personal', 'Outgoing transfer'),

    # ── POS transactions ──
    (r'\bpos\b.*\btransfer\b', 'Operational Expense', 'POS/cash withdrawal'),

    # ── Catch-all for anything with a description ──
    (r'.+', 'Personal', 'Uncategorized transaction'),
]

# Compile patterns for speed
_COMPILED_RULES = [(re.compile(pat, re.IGNORECASE), cat, reason) for pat, cat, reason in CATEGORIZATION_RULES]


def categorize_transactions(df):
    """
    Categorize transactions using keyword-based rules.
    
    Args:
        df: DataFrame with at least 'description' and 'amount' columns.
    
    Returns:
        DataFrame with 'category' and 'reason' columns added.
    """
    df = df.copy()
    
    categories = []
    reasons = []
    
    for _, row in df.iterrows():
        desc = str(row.get("description", "")).strip()
        amount = row.get("amount", 0)
        
        if not desc:
            # No description — categorize by amount sign
            if amount > 0:
                categories.append("Business Income")
                reasons.append("Incoming amount (no description)")
            else:
                categories.append("Personal")
                reasons.append("Outgoing amount (no description)")
            continue
        
        # Try each rule in priority order
        matched = False
        for pattern, category, reason in _COMPILED_RULES:
            if pattern.search(desc):
                # Override: if it's flagged as Business Income but amount is negative,
                # it's likely an expense
                if category == "Business Income" and amount < 0:
                    categories.append("Operational Expense")
                    reasons.append(reason + " (debit)")
                else:
                    categories.append(category)
                    reasons.append(reason)
                matched = True
                break
        
        if not matched:
            categories.append("Personal")
            reasons.append("Could not categorize")
    
    df["category"] = categories
    df["reason"] = reasons
    
    return df
