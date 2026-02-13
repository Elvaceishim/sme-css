import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from transaction_processor import TransactionProcessor
from scorer import CreditScorer

# Page Configuration
st.set_page_config(page_title="SME Credit Scorer", layout="wide")
st.title("🇳🇬 SME AI Credit Scoring Dashboard")

# 1. Sidebar for Uploads
st.sidebar.header("Upload Data")
uploaded_file = st.sidebar.file_uploader("Upload SME Bank Statement (CSV)", type="csv")

if uploaded_file:
    # Save the uploaded file locally
    with open("temp_transactions.csv", "wb") as f:
        f.write(uploaded_file.getbuffer())

    st.success("File Uploaded Successfully!")

    # 2. Process Data
    with st.spinner("AI is analyzing transactions..."):
        processor = TransactionProcessor()
        processor.run_pipeline("temp_transactions.csv", "analyzed_transactions.csv")
        
        scorer = CreditScorer("analyzed_transactions.csv")
        score = scorer.generate_score()

    # 3. Display Results (Top Row)
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Credit Risk Score")
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = score,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Risk Level"},
            gauge = {
                'axis': {'range': [None, 100]},
                'bar': {'color': "black"},
                'steps': [
                    {'range': [0, 40], 'color': "red"},
                    {'range': [40, 70], 'color': "orange"},
                    {'range': [70, 100], 'color': "green"}
                ]
            }
        ))
        st.plotly_chart(fig, width='stretch')

    with col2:
        st.subheader("Transaction Breakdown")
        df = pd.read_csv("analyzed_transactions.csv")
        st.dataframe(df[['description', 'category', 'amount']], width='stretch')

    st.divider()
    st.subheader("AI Underwriter's Credit Memo")
    
    # DEBUG PRINT 1
    print("DEBUG: Reached the Memo Section Start")

    with st.spinner("Writing detailed credit analysis..."):
        try:
            from memo_generator import generate_credit_memo
            
            # DEBUG PRINT 2
            print(f"DEBUG: Calling AI with score: {score}")
            
            memo = generate_credit_memo(score, "analyzed_transactions.csv")
            
            # DEBUG PRINT 3
            print("DEBUG: AI successfully returned a memo")
            
            st.info(memo)
            
        except Exception as e:
            st.error(f"The Memo Generator failed: {e}")
            print(f"DEBUG ERROR: {e}")

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
    # This shows only when no file is uploaded
    st.info("Please upload a CSV file to begin the credit assessment.")