# 🇳🇬 SME AI Credit Scoring System

An AI-powered credit scoring dashboard built for Nigerian SME lenders. Upload a bank statement CSV and get an instant credit risk assessment — powered by LLM-based transaction analysis, a multi-signal scoring engine, and an AI-generated underwriter's memo.

![Dashboard Preview](docs/dashboard_preview.png)

## Features

- **AI Transaction Categorization** — Uses Google Gemini (via OpenRouter) to classify each transaction as *Business Income*, *Operational Expense*, *Personal*, or *High Risk*
- **Multi-Signal Credit Scoring** — Generates a 0–100 risk score based on 7 weighted factors:
  - Expense ratio
  - Income volatility & frequency
  - Revenue diversification
  - Co-mingling detection (personal spending on business accounts)
  - High-risk behavioral flags (e.g. betting platforms)
  - Data sufficiency
- **AI Credit Memo** — A Senior Credit Analyst–style narrative tailored to the Nigerian SME lending context
- **PDF Report Generation** — Downloadable credit analysis report with executive summary and underwriter notes
- **Interactive Dashboard** — Streamlit-based UI with a risk gauge, transaction breakdown table, and one-click PDF download

## Tech Stack

| Component | Technology |
|---|---|
| Frontend | Streamlit |
| AI/LLM | Google Gemini 2.0 Flash (via OpenRouter) |
| Data Processing | Pandas |
| Visualization | Plotly |
| PDF Generation | fpdf2 |

## Getting Started

### Prerequisites

- Python 3.10+
- An [OpenRouter](https://openrouter.ai/) API key

### Installation

```bash
# Clone the repo
git clone https://github.com/Elvaceishim/sme-css.git
cd sme-css

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root (see `.env.example`):

```
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

### Run

```bash
streamlit run app.py
```

Then open [http://localhost:8501](http://localhost:8501) in your browser.

### Sample Input

Upload a CSV with this format:

| date | description | amount | type |
|---|---|---|---|
| 2026-01-01 | Transfer from CHIDIMA OKORO | 50000 | Credit |
| 2026-01-02 | POS PURCHASE - JOSSY VENTURES | -12000 | Debit |
| 2026-01-05 | BET9JA WALLET TOPUP | -5000 | Debit |

## Project Structure

```
sme-css/
├── app.py                    # Streamlit dashboard (entry point)
├── transaction_processor.py  # LLM-powered transaction categorizer
├── scorer.py                 # Multi-signal credit scoring engine
├── memo_generator.py         # AI credit memo generator
├── report_gen.py             # PDF report builder
├── requirements.txt
├── .env.example
└── docs/
    └── dashboard_preview.png
```

## License

This project is for educational and demonstration purposes.
