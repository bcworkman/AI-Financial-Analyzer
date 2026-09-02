# Financial Statement Analyzer

Pulls a public company's financial statements directly from **SEC EDGAR**
(the same source auditors and analysts use), computes standard financial
ratios across the last several fiscal years, and automatically flags
patterns that would catch an auditor's or analyst's eye — like receivables
growing faster than revenue, or cash flow lagging behind net income.


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

