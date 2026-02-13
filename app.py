import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from transaction_processor import TransactionProcessor
from scorer import CreditScorer
from statement_validator import validate_statement, get_monthly_trends
from pdf_extractor import extract_transactions_from_pdf

# Page Configuration
st.set_page_config(page_title="SME Credit Scorer", layout="wide")
st.title("SME AI Credit Scoring Dashboard")

# 1. Sidebar for Uploads
st.sidebar.header("Upload Data")
st.sidebar.markdown(
    "Upload an SME bank statement in **CSV** or **PDF** format.\n\n"
    "**Minimum 3 months** of transaction history is recommended for accurate scoring."
)
uploaded_file = st.sidebar.file_uploader("Upload Bank Statement (CSV or PDF)", type=["csv", "pdf"])

if uploaded_file:
    # Determine file type and load accordingly
    file_name = uploaded_file.name.lower()
    
    if file_name.endswith(".pdf"):
        with st.spinner("Extracting transactions from PDF..."):
            raw_df, method = extract_transactions_from_pdf(uploaded_file)
            if raw_df is None:
                st.error(method)  # method contains the error message
                st.stop()
            st.success(f"Extracted {len(raw_df)} rows from PDF (method: {method})")
    else:
        raw_df = pd.read_csv(uploaded_file)
    
    cleaned_df, summary, warnings = validate_statement(raw_df)

    if cleaned_df is None:
        for w in warnings:
            st.error(w)
        st.stop()

    # Show warnings (e.g., < 3 months)
    for w in warnings:
        st.warning(w)

    # ── Statement Overview ──
    st.subheader("Statement Overview")
    overview_cols = st.columns(4)
    with overview_cols[0]:
        st.metric("Transactions", summary.get("total_transactions", 0))
    with overview_cols[1]:
        months = summary.get("months_covered", "N/A")
        st.metric("Months Covered", months)
    with overview_cols[2]:
        st.metric("Period Start", summary.get("start_date", "N/A"))
    with overview_cols[3]:
        st.metric("Period End", summary.get("end_date", "N/A"))

    # ── Monthly Trends Chart ──
    monthly_trends = get_monthly_trends(cleaned_df)
    if not monthly_trends.empty:
        st.subheader("📊 Monthly Trends")
        fig_trends = go.Figure()
        fig_trends.add_trace(go.Bar(
            x=monthly_trends["month"], y=monthly_trends["income"],
            name="Income", marker_color="#2ecc71"
        ))
        fig_trends.add_trace(go.Bar(
            x=monthly_trends["month"], y=monthly_trends["expenses"],
            name="Expenses", marker_color="#e74c3c"
        ))
        fig_trends.add_trace(go.Scatter(
            x=monthly_trends["month"], y=monthly_trends["net"],
            name="Net", mode="lines+markers", marker_color="#3498db"
        ))
        fig_trends.update_layout(
            barmode="group", xaxis_title="Month", yaxis_title="Amount (₦)",
            height=350, margin=dict(t=10, b=40)
        )
        st.plotly_chart(fig_trends, use_container_width=True)

    st.divider()

    # Save cleaned data for the AI pipeline
    cleaned_df.to_csv("temp_transactions.csv", index=False)

    # ── AI Processing ──
    with st.spinner("AI is analyzing transactions..."):
        processor = TransactionProcessor()
        processor.run_pipeline("temp_transactions.csv", "analyzed_transactions.csv")
        
        scorer = CreditScorer("analyzed_transactions.csv")
        score = scorer.generate_score()
        metrics = scorer.calculate_metrics()

    # ── Results Row ──
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Credit Risk Score")
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=score,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Risk Level"},
            gauge={
                'axis': {'range': [None, 100]},
                'bar': {'color': "black"},
                'steps': [
                    {'range': [0, 40], 'color': "red"},
                    {'range': [40, 70], 'color': "orange"},
                    {'range': [70, 100], 'color': "green"}
                ]
            }
        ))
        st.plotly_chart(fig, use_container_width=True)

        # Key metrics summary
        st.caption("**Key Signals**")
        trend = metrics.get("income_trend", 0)
        trend_icon = "📈" if trend > 0.05 else ("📉" if trend < -0.05 else "➡️")
        st.markdown(f"- Income Trend: {trend_icon} {trend:+.0%}")
        st.markdown(f"- Expense Ratio: {metrics['expense_ratio']:.0%}")
        st.markdown(f"- Co-mingling: {metrics['comingling_ratio']:.0%}")
        st.markdown(f"- High-Risk Flags: {metrics['high_risk_count']}")

    with col2:
        st.subheader("Transaction Breakdown")
        df = pd.read_csv("analyzed_transactions.csv")
        display_cols = [c for c in ['date', 'description', 'category', 'amount', 'reason'] if c in df.columns]
        st.dataframe(df[display_cols], use_container_width=True, height=400)

    st.divider()
    st.subheader("AI Underwriter's Credit Memo")

    memo = None
    with st.spinner("Writing detailed credit analysis..."):
        try:
            from memo_generator import generate_credit_memo
            memo = generate_credit_memo(score, "analyzed_transactions.csv")
            st.info(memo)
        except Exception as e:
            st.error(f"The Memo Generator failed: {e}")

    if memo:
        from report_gen import generate_pdf_report
        pdf_path = generate_pdf_report(score, memo)

        with open(pdf_path, "rb") as f:
            st.download_button(
                label="Download PDF Report",
                data=f,
                file_name="SME_Credit_Report.pdf",
                mime="application/pdf"
            )

else:
    st.info("Please upload a CSV or PDF bank statement to begin the credit assessment.")
    
    with st.expander("What formats are supported?"):
        st.markdown("""
        ### CSV Files
        Your CSV should contain transaction data with columns like:
        
        | Column | Description |
        |--------|-------------|
        | `date` | Transaction date |
        | `description` / `narration` | Transaction details |
        | `amount` | Transaction amount (positive = credit, negative = debit) |
        | `type` | Credit or Debit *(optional — auto-detected from amount)* |
        
        **Or** separate credit/debit columns:
        
        | `date` | `narration` | `credit` | `debit` |
        |--------|-------------|----------|---------|
        
        Most Nigerian bank CSV exports are supported automatically.
        
        ### PDF Files
        Upload your bank statement PDF directly — the system will attempt to 
        extract transaction tables automatically. Works best with digitally 
        generated PDFs (not scanned images).
        """)