# Financial Statement Analyzer

Pulls a public company's financial statements directly from **SEC EDGAR**
(the same source auditors and analysts use), computes standard financial
ratios across the last several fiscal years, and automatically flags
patterns that would catch an auditor's or analyst's eye — like receivables
growing faster than revenue, or cash flow lagging behind net income.

Built as a resume/portfolio project for accounting & analytics students —
it mirrors real audit/advisory analytical procedures (ratio analysis,
trend analysis, anomaly flagging) rather than being a generic finance app.

## What it does

1. Takes a stock ticker (e.g. `AAPL`, `MSFT`, `KO`)
2. Looks up the company's SEC CIK number and downloads its XBRL filings data
3. Extracts key line items (revenue, net income, assets, liabilities,
   receivables, inventory, operating cash flow, etc.) for each fiscal year
4. Computes ratios: current ratio, quick ratio, debt-to-equity, net margin,
   ROE, ROA, revenue growth, and cash-flow-to-net-income
5. Flags anomalies using simple audit-style heuristics
6. Outputs a Markdown report, optional Excel export, and optional trend charts

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Analyze a real company (needs internet access)
python financial_analyzer.py AAPL

# Also export the full dataset to Excel and save trend charts
python financial_analyzer.py MSFT --export msft_analysis.xlsx --charts

# Try it instantly with no internet / no ticker, using bundled sample data
python financial_analyzer.py --demo --charts
```

Reports are saved to `output/<TICKER>/`.

## A note on SEC's rules

SEC EDGAR requires every request to include a descriptive `User-Agent`
header (your name/app + contact email). This is set in
`SEC_HEADERS` at the top of `financial_analyzer.py` — update it with your
own info before relying on this for anything beyond a demo. SEC also rate
limits requests, so avoid hammering the API in a loop.

## Why this is a good resume project

- Uses a **real, primary data source** (SEC XBRL filings) — not a toy dataset
- Mirrors actual audit/advisory analytical procedures: ratio analysis,
  trend analysis, and rule-based anomaly detection
- Demonstrates Python, working with REST APIs, pandas, and data visualization
- Directly relevant to Big 4 audit/advisory roles, where "read financials,
  compute ratios, and flag anomalies" is core entry-level work

**Suggested resume bullet:**
> Built a Python tool that pulls public companies' financial statements
> from SEC EDGAR's XBRL API, computes liquidity/profitability/leverage
> ratios across multiple fiscal years, and flags audit-relevant anomalies
> (e.g. receivables outpacing revenue growth, weak cash-flow-to-earnings
> conversion).

## Ideas to extend it (good "what would you add next" interview answer)

- Add more red-flag rules (e.g. gross margin volatility, unusual SG&A trends)
- Compare a company against its industry peers
- Add a simple web front-end (Streamlit) so it's demo-able without a terminal
- Cache downloaded filings so repeat runs don't re-hit the SEC API
