"""
Financial Statement Analyzer
-----------------------------
Pulls a public company's financial data directly from SEC EDGAR (XBRL
"company facts" API), computes key ratios across the last several fiscal
years, and flags potential red flags an auditor or analyst would look for
(e.g. receivables growing faster than revenue).

Data source: SEC EDGAR XBRL Frames/Company Facts API (free, no API key).
Docs: https://www.sec.gov/edgar/sec-api-documentation

Usage:
    python financial_analyzer.py AAPL
    python financial_analyzer.py MSFT --export report.xlsx
    python financial_analyzer.py --demo          (uses bundled sample data, no internet needed)

Author: you. Built with Claude.
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import requests

# --------------------------------------------------------------------------
# SEC requires a descriptive User-Agent identifying you or your app on every
# request, or it will rate-limit / block you. Replace the email below with
# your own contact info before you rely on this for real use.
# --------------------------------------------------------------------------
SEC_HEADERS = {
    "User-Agent": "Student Resume Project contact@example.com",
    "Accept-Encoding": "gzip, deflate",
}

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

# Each "concept" we care about, with a list of XBRL tags to try in order
# (companies don't always use the exact same GAAP tag from year to year).
CONCEPT_TAGS = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ],
    "net_income": ["NetIncomeLoss"],
    "total_assets": ["Assets"],
    "total_liabilities": ["Liabilities"],
    "stockholders_equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "current_assets": ["AssetsCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
    "receivables": [
        "AccountsReceivableNetCurrent",
        "ReceivablesNetCurrent",
    ],
    "inventory": ["InventoryNet"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
}


def get_cik_for_ticker(ticker: str) -> tuple[int, str]:
    """Look up a company's 10-digit CIK number from its ticker symbol."""
    resp = requests.get(TICKER_MAP_URL, headers=SEC_HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    ticker = ticker.upper()
    for entry in data.values():
        if entry["ticker"].upper() == ticker:
            return entry["cik_str"], entry["title"]
    raise ValueError(f"Ticker '{ticker}' not found in SEC's ticker list.")


def get_company_facts(cik: int) -> dict:
    """Download the full XBRL company-facts JSON for a given CIK."""
    url = COMPANY_FACTS_URL.format(cik=cik)
    resp = requests.get(url, headers=SEC_HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _best_annual_values(fact_entry: dict) -> dict:
    """
    Given one XBRL fact entry (e.g. facts['us-gaap']['Revenues']), return
    {fiscal_year: value} using only annual (form 10-K, fp='FY') data points,
    keeping the most recently *filed* value if a year appears more than once.
    """
    out = {}
    filed_at = {}
    units = fact_entry.get("units", {})
    values = units.get("USD", [])
    for v in values:
        if v.get("form") != "10-K" or v.get("fp") != "FY":
            continue
        fy = v.get("fy")
        filed = v.get("filed", "")
        if fy is None:
            continue
        if fy not in out or filed > filed_at.get(fy, ""):
            out[fy] = v.get("val")
            filed_at[fy] = filed
    return out


def extract_metrics(facts: dict) -> pd.DataFrame:
    """Turn raw company-facts JSON into a tidy DataFrame: rows=fiscal year, cols=metric."""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    series = {}
    for concept, tags in CONCEPT_TAGS.items():
        for tag in tags:
            if tag in gaap:
                annual = _best_annual_values(gaap[tag])
                if annual:
                    series[concept] = annual
                    break
    if not series:
        raise ValueError("No usable financial data found for this company.")

    df = pd.DataFrame(series).sort_index()
    df.index.name = "fiscal_year"
    return df


def compute_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """Add standard financial ratios as new columns."""
    out = df.copy()

    if {"current_assets", "current_liabilities"}.issubset(out.columns):
        out["current_ratio"] = out["current_assets"] / out["current_liabilities"]

    if {"current_assets", "inventory", "current_liabilities"}.issubset(out.columns):
        out["quick_ratio"] = (out["current_assets"] - out["inventory"].fillna(0)) / out["current_liabilities"]

    if {"total_liabilities", "stockholders_equity"}.issubset(out.columns):
        out["debt_to_equity"] = out["total_liabilities"] / out["stockholders_equity"]

    if {"net_income", "revenue"}.issubset(out.columns):
        out["net_margin_pct"] = 100 * out["net_income"] / out["revenue"]

    if {"net_income", "stockholders_equity"}.issubset(out.columns):
        out["roe_pct"] = 100 * out["net_income"] / out["stockholders_equity"]

    if {"net_income", "total_assets"}.issubset(out.columns):
        out["roa_pct"] = 100 * out["net_income"] / out["total_assets"]

    if "revenue" in out.columns:
        out["revenue_growth_pct"] = 100 * out["revenue"].pct_change()

    if "receivables" in out.columns:
        out["receivables_growth_pct"] = 100 * out["receivables"].pct_change()

    if {"operating_cash_flow", "net_income"}.issubset(out.columns):
        out["cf_to_ni_ratio"] = out["operating_cash_flow"] / out["net_income"]

    return out


def flag_anomalies(df: pd.DataFrame) -> list[str]:
    """
    Simple rule-based checks for the kind of things an auditor/analyst
    scans for first. Not a substitute for real audit judgment -- this is
    meant to demonstrate the *type* of automated screening firms use.
    """
    flags = []

    if {"revenue_growth_pct", "receivables_growth_pct"}.issubset(df.columns):
        gap = df["receivables_growth_pct"] - df["revenue_growth_pct"]
        for fy, g in gap.items():
            if pd.notna(g) and g > 15:
                flags.append(
                    f"FY{fy}: Receivables grew {g:.1f} pts faster than revenue "
                    f"-> possible revenue recognition / collections risk."
                )

    if "cf_to_ni_ratio" in df.columns:
        for fy, ratio in df["cf_to_ni_ratio"].items():
            if pd.notna(ratio) and ratio < 0.6:
                flags.append(
                    f"FY{fy}: Operating cash flow is only {ratio:.2f}x net income "
                    f"-> earnings quality worth a closer look."
                )

    if "current_ratio" in df.columns:
        for fy, cr in df["current_ratio"].items():
            if pd.notna(cr) and cr < 1.0:
                flags.append(f"FY{fy}: Current ratio below 1.0 ({cr:.2f}) -> potential liquidity concern.")

    if "debt_to_equity" in df.columns:
        for fy, de in df["debt_to_equity"].items():
            if pd.notna(de) and de > 3.0:
                flags.append(f"FY{fy}: Debt-to-equity is high ({de:.2f}) -> elevated leverage risk.")

    return flags


def plot_trends(df: pd.DataFrame, ticker: str, outdir: Path) -> list[Path]:
    """Save a couple of trend charts as PNGs. Returns list of file paths."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    outdir.mkdir(parents=True, exist_ok=True)
    saved = []

    if {"revenue", "net_income"}.issubset(df.columns):
        fig, ax = plt.subplots(figsize=(7, 4))
        df["revenue"].plot(ax=ax, marker="o", label="Revenue")
        df["net_income"].plot(ax=ax, marker="o", label="Net Income")
        ax.set_title(f"{ticker}: Revenue vs Net Income")
        ax.set_ylabel("USD")
        ax.legend()
        fig.tight_layout()
        path = outdir / f"{ticker}_revenue_net_income.png"
        fig.savefig(path)
        plt.close(fig)
        saved.append(path)

    ratio_cols = [c for c in ["current_ratio", "debt_to_equity", "net_margin_pct", "roe_pct"] if c in df.columns]
    if ratio_cols:
        fig, ax = plt.subplots(figsize=(7, 4))
        df[ratio_cols].plot(ax=ax, marker="o")
        ax.set_title(f"{ticker}: Key Ratios Over Time")
        fig.tight_layout()
        path = outdir / f"{ticker}_ratios.png"
        fig.savefig(path)
        plt.close(fig)
        saved.append(path)

    return saved


def generate_report(ticker: str, company_name: str, df: pd.DataFrame, flags: list[str]) -> str:
    lines = []
    lines.append(f"# Financial Analysis: {company_name} ({ticker})\n")
    lines.append("## Key Figures by Fiscal Year\n")
    display_cols = [c for c in ["revenue", "net_income", "total_assets", "stockholders_equity"] if c in df.columns]
    if display_cols:
        lines.append(df[display_cols].round(0).to_markdown())
    lines.append("\n## Ratios\n")
    ratio_cols = [
        c
        for c in [
            "current_ratio",
            "quick_ratio",
            "debt_to_equity",
            "net_margin_pct",
            "roe_pct",
            "roa_pct",
            "revenue_growth_pct",
            "cf_to_ni_ratio",
        ]
        if c in df.columns
    ]
    if ratio_cols:
        lines.append(df[ratio_cols].round(2).to_markdown())
    lines.append("\n## Flags\n")
    if flags:
        for f in flags:
            lines.append(f"- {f}")
    else:
        lines.append("No automated flags triggered by the current rule set.")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Analyze a public company's financials from SEC EDGAR data.")
    parser.add_argument("ticker", nargs="?", help="Stock ticker, e.g. AAPL")
    parser.add_argument("--export", help="Optional path to export full data to .xlsx")
    parser.add_argument("--charts", action="store_true", help="Save trend charts as PNGs")
    parser.add_argument("--demo", action="store_true", help="Use bundled sample data instead of live SEC data")
    args = parser.parse_args()

    if args.demo:
        sample_path = Path(__file__).parent / "sample_data" / "DEMO_sample_facts.json"
        with open(sample_path) as f:
            facts = json.load(f)
        ticker = "DEMO"
        company_name = facts.get("entityName", "Demo Company")
    else:
        if not args.ticker:
            print("Provide a ticker, e.g.: python financial_analyzer.py AAPL")
            print("Or run with --demo to try it without a ticker / internet access.")
            sys.exit(1)
        ticker = args.ticker.upper()
        print(f"Looking up CIK for {ticker}...")
        cik, company_name = get_cik_for_ticker(ticker)
        print(f"Found {company_name} (CIK {cik}). Downloading filings data...")
        facts = get_company_facts(cik)

    df = extract_metrics(facts)
    df = compute_ratios(df)
    flags = flag_anomalies(df)

    report = generate_report(ticker, company_name, df, flags)
    print("\n" + report + "\n")

    outdir = Path("output") / ticker
    outdir.mkdir(parents=True, exist_ok=True)

    report_path = outdir / f"{ticker}_report.md"
    report_path.write_text(report)
    print(f"Report saved to {report_path}")

    if args.export:
        df.to_excel(args.export)
        print(f"Data exported to {args.export}")

    if args.charts:
        paths = plot_trends(df, ticker, outdir)
        for p in paths:
            print(f"Chart saved to {p}")


if __name__ == "__main__":
    main()
