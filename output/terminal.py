"""
Terminal output formatting for screener results.

The screener engine returns raw numerics; this module is responsible for
turning them into user-facing strings (percentages, "Xd" durations, etc.).
"""
import os

import pandas as pd


# ANSI color codes for tier-based coloring
_TIER_COLORS = {
    'S': '\033[38;5;208m',  # Orange
    'A': '\033[35m',        # Purple
    'B': '\033[94m',        # Blue
    'C': '\033[92m',        # Green
}
_RESET = '\033[0m'


def _format_display_row(row: pd.Series) -> dict:
    """Convert the numeric result row into the strings shown in the table."""
    lps_len = int(row['LPS Length'])
    return {
        'Ticker': row['Ticker'],
        'Tier': row['Tier'],
        'Setup': row['Setup'],
        'Score': row['Score'],
        'Price': f"${row['Current Price']:.2f}",
        'Base Len': f"{int(row['Base Len'])}d",
        'Box Width': f"{row['Box Width'] * 100:.1f}%",
        'Touches': f"{int(row['Touches'])}",
        'ATR Ratio': f"{row['ATR Ratio'] * 100:.1f}%",
        'LPS Length': f"{lps_len}d" if lps_len > 0 else "-",
    }


def print_results(results_df: pd.DataFrame) -> None:
    """Print a formatted, color-coded results table to the terminal."""
    print("\n" + "=" * 87)
    print(" [ WYCKOFF VCP/LPS SCREENER RESULTS (V2 RANKED) ] ".center(87))
    print("=" * 87 + "\n")

    headers = ['TICKER', 'TIER', 'SETUP', 'SCORE', 'PRICE', 'BASE', 'BOX W', 'TCHS', 'ATR SQZ', 'LPS LEN']
    print(f"{headers[0]:<8} | {headers[1]:<4} | {headers[2]:<8} | {headers[3]:<5} | {headers[4]:<6} | {headers[5]:<5} | {headers[6]:<6} | {headers[7]:<4} | {headers[8]:<7} | {headers[9]:<7}")
    print("-" * 87)

    for _, row in results_df.iterrows():
        display = _format_display_row(row)
        color = _TIER_COLORS.get(display['Tier'], '')
        row_str = (
            f"{display['Ticker']:<8} | {display['Tier']:<4} | {display['Setup']:<8} | "
            f"{display['Score']:<5} | {display['Price']:<6} | "
            f"{display['Base Len']:<5} | {display['Box Width']:<6} | {display['Touches']:<4} | "
            f"{display['ATR Ratio']:<7} | {display['LPS Length']:<7}"
        )
        print(f"{color}{row_str}{_RESET}")

    print("\n" + "=" * 87)


def save_csv(results_df: pd.DataFrame, output_dir: str) -> None:
    """Save results to CSV, excluding internal columns."""
    output_csv = os.path.join(output_dir, "lps_watchlist_v2.csv")
    public_cols = [c for c in results_df.columns if not c.startswith('_')]
    results_df[public_cols].to_csv(output_csv, index=False)
    print(f"\nResults saved to {output_csv}!")


def print_finviz_url(results_df: pd.DataFrame) -> None:
    """Print a Finviz link for quick visual verification."""
    passed_tickers = results_df['Ticker'].tolist()
    finviz_url = f"https://finviz.com/screener.ashx?v=211&t={','.join(passed_tickers)}"
    print("\nOpen these exact charts instantly in Finviz (Ctrl+Click):")
    print(finviz_url)
    print("-" * 50)
