"""
report.py
─────────
Pretty-prints the final agent run summary to the terminal.
"""

from simulator import PaperTrader


def print_report(trader: PaperTrader, predictions: dict):
    print("\n" + "═"*60)
    print("  📊  AGENT RUN SUMMARY")
    print("═"*60)

    # Predictions table
    print("\n  PREDICTIONS FOR NEXT TRADING DAY")
    print(f"  {'Ticker':<8} {'Last Close':>11} {'Predicted':>11} {'Change':>8}  {'Confidence':>10}")
    print("  " + "─"*54)
    for ticker, p in predictions.items():
        arrow = "▲" if p["change_pct"] > 0 else "▼"
        print(
            f"  {ticker:<8} "
            f"${p['last_price']:>10.2f} "
            f"${p['pred_price']:>10.2f} "
            f" {arrow}{abs(p['change_pct']):>6.2f}%"
            f"   {p['confidence']:>6.0f}%"
        )

    # Trade log
    print(f"\n  TRADES EXECUTED THIS RUN  ({len(trader.trades)} total)")
    if trader.trades:
        print(f"  {'Action':<6} {'Ticker':<8} {'Shares':>8} {'Price':>9} {'Value':>10}")
        print("  " + "─"*46)
        for t in trader.trades:
            print(
                f"  {t.action:<6} {t.ticker:<8} "
                f"{t.shares:>8.4f} "
                f"${t.price:>8.2f} "
                f"${t.value:>9.2f}"
            )
            print(f"         ↳ {t.reason}")
    else:
        print("  No trades executed (all positions HOLD).")

    # Portfolio state
    print(f"\n  PORTFOLIO")
    print(f"  Cash available : ${trader.cash:,.2f}")
    open_pos = {t: p for t, p in trader.positions.items() if p.shares > 0}
    if open_pos:
        print(f"  Open positions :")
        for ticker, pos in open_pos.items():
            mkt_val = pos.shares * pos.avg_cost   # using cost as placeholder
            print(f"    {ticker}: {pos.shares:.4f} shares  (avg cost ${pos.avg_cost:.2f}, ~${mkt_val:.2f})")
    else:
        print("  Open positions : None")

    total = trader.cash + sum(
        p.shares * p.avg_cost for p in trader.positions.values() if p.shares > 0
    )
    change = total - trader.start_cash
    pct    = change / trader.start_cash * 100
    arrow  = "▲" if change >= 0 else "▼"
    print(f"\n  Est. portfolio value : ${total:,.2f}  {arrow} {abs(pct):.2f}% vs start (${trader.start_cash:,.2f})")
    print("\n" + "═"*60)
    print("  ⚠️   This is a simulation. Not financial advice.")
    print("═"*60 + "\n")
