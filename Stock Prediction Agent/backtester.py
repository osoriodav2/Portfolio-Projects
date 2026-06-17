"""
backtester.py
─────────────
Walk-forward backtest engine — supports multiple tickers in one shared portfolio.

For each trading day in the test window:
  1. For each ticker: train XGBoost on all data UP TO that day (no lookahead)
  2. Predict the NEXT day's close + confidence
  3. Apply BUY/SELL/HOLD rules — all tickers compete for the same cash pool
  4. Mark portfolio to market and record equity snapshot

Returns daily equity curve, per-trade log, and summary statistics.
"""

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from xgboost import XGBRegressor

from predictor import FEATURE_COLS

BUY_THRESHOLD  =  1.5
SELL_THRESHOLD = -1.5
MIN_CONFIDENCE = 55.0


# ── Model helpers ──────────────────────────────────────────────────────────────

def _train_and_predict(df_train: pd.DataFrame, feature_cols: list):
    """Train on df_train, predict next close. Returns (pred_price, confidence)."""
    X = df_train[feature_cols].values
    y = df_train["Target"].values

    scaler  = MinMaxScaler()
    X_s     = scaler.fit_transform(X)
    model   = XGBRegressor(
        n_estimators=200, max_depth=4, learning_rate=0.08,
        subsample=0.8, colsample_bytree=0.8, random_state=42, verbosity=0,
    )
    model.fit(X_s, y, verbose=False)

    X_last = scaler.transform(df_train[feature_cols].iloc[-1:].values)
    pred   = float(model.predict(X_last)[0])

    recent  = min(30, len(df_train))
    X_r     = scaler.transform(df_train[feature_cols].iloc[-recent:].values)
    preds_r = model.predict(X_r)
    actuals = df_train["Target"].iloc[-recent:].values
    last_p  = float(df_train["Close"].iloc[-1])
    mae_pct = np.mean(np.abs(preds_r - actuals)) / (last_p + 1e-9)
    conf    = float(np.clip((1 - mae_pct * 10) * 100, 10, 95))

    return pred, conf


# ── Main backtest ──────────────────────────────────────────────────────────────

def run_backtest(
    dfs: dict,           # {ticker: enriched DataFrame}
    start_cash: float = 10_000,
    train_window: int = 252,
    log_fn=None,
) -> dict:
    """
    Parameters
    ----------
    dfs          : dict of {ticker → enriched DataFrame from data_fetcher}
    start_cash   : Starting virtual cash (shared across all tickers)
    train_window : Rows required before first prediction (~1 trading year)
    log_fn       : Optional callable(str) for progress messages

    Returns
    -------
    dict with keys: equity_curve, trades, stats, ticker_stats
    """
    def _log(msg):
        if log_fn:
            log_fn(msg)

    tickers      = list(dfs.keys())
    feature_cols = {t: [c for c in FEATURE_COLS if c in dfs[t].columns] for t in tickers}

    # Align all DataFrames to a common date index
    common_dates = None
    for df in dfs.values():
        idx = pd.to_datetime(df.index.date, utc=False)
        common_dates = idx if common_dates is None else common_dates.intersection(idx)
    common_dates = sorted(common_dates)

    total_test = len(common_dates) - train_window
    if total_test <= 0:
        raise ValueError("Not enough data for the chosen period. Try a longer window.")
    _log(f"Tickers: {', '.join(tickers)}  |  Test days: {total_test}  |  Start cash: ${start_cash:,.0f}")

    # ── Portfolio state ────────────────────────────────────────────────────────
    cash          = start_cash
    positions     = {t: {"shares": 0.0, "avg_cost": 0.0} for t in tickers}
    realized_pnl  = 0.0
    equity_curve  = []
    trades        = []
    ticker_stats  = {t: {"buys": 0, "sells": 0, "realized": 0.0} for t in tickers}

    # ── Walk-forward loop ──────────────────────────────────────────────────────
    for day_idx, date in enumerate(common_dates[train_window:-1]):
        date_str    = str(date)
        next_date   = common_dates[train_window + day_idx + 1]

        # Mark-to-market at today's close
        invested = 0.0
        for t in tickers:
            df   = dfs[t]
            row  = df[pd.to_datetime(df.index.date, utc=False) == date]
            if row.empty:
                continue
            price     = float(row["Close"].iloc[0])
            pos       = positions[t]
            if pos["shares"] > 0:
                invested += pos["shares"] * price

        port_value = cash + invested
        equity_curve.append({
            "date":     date_str,
            "value":    round(port_value, 2),
            "cash":     round(cash, 2),
            "invested": round(invested, 2),
        })

        # Progress log every 20 days
        if day_idx % 20 == 0:
            pct = day_idx / total_test * 100
            _log(f"  {date_str}  |  ${port_value:,.0f}  |  cash ${cash:,.0f}  |  {pct:.0f}% done")

        # ── Per-ticker decisions ───────────────────────────────────────────────
        for ticker in tickers:
            df   = dfs[ticker]
            fcols = feature_cols[ticker]

            # Slice training data: everything up to (not including) today
            df_date = pd.to_datetime(df.index.date, utc=False)
            df_train = df[df_date < date]
            if len(df_train) < train_window:
                continue

            today_row = df[df_date == date]
            if today_row.empty:
                continue
            today_price = float(today_row["Close"].iloc[0])

            try:
                pred_price, confidence = _train_and_predict(df_train, fcols)
            except Exception:
                continue

            change_pct = (pred_price - today_price) / today_price * 100
            pos        = positions[ticker]

            # BUY
            if change_pct > BUY_THRESHOLD and confidence > MIN_CONFIDENCE and cash >= today_price:
                pos_pct      = 0.20 + (confidence - 55) / (95 - 55) * 0.20
                # Scale down allocation per ticker so we don't blow all cash on one
                per_ticker   = min(pos_pct, 0.40) / len(tickers) * 2
                invest_amt   = cash * min(per_ticker, 0.40)
                new_shares   = invest_amt / today_price
                cost         = new_shares * today_price

                old_sh  = pos["shares"]
                new_avg = (pos["avg_cost"] * old_sh + cost) / (old_sh + new_shares) if (old_sh + new_shares) > 0 else today_price
                pos["shares"]   += new_shares
                pos["avg_cost"]  = new_avg
                cash            -= cost

                ticker_stats[ticker]["buys"] += 1
                trades.append({
                    "date": date_str, "ticker": ticker, "action": "BUY",
                    "shares": round(new_shares, 4), "price": round(today_price, 2),
                    "value": round(cost, 2), "cash_after": round(cash, 2),
                    "pred_change": round(change_pct, 2), "confidence": round(confidence, 1),
                    "realized_pnl": 0.0,
                })

            # SELL
            elif change_pct < SELL_THRESHOLD and confidence > MIN_CONFIDENCE and pos["shares"] > 0:
                proceeds   = pos["shares"] * today_price
                cost_basis = pos["shares"] * pos["avg_cost"]
                realized   = proceeds - cost_basis
                gain_pct   = realized / cost_basis * 100 if cost_basis else 0

                cash         += proceeds
                realized_pnl += realized
                ticker_stats[ticker]["sells"]    += 1
                ticker_stats[ticker]["realized"] += realized

                trades.append({
                    "date": date_str, "ticker": ticker, "action": "SELL",
                    "shares": round(pos["shares"], 4), "price": round(today_price, 2),
                    "value": round(proceeds, 2), "cash_after": round(cash, 2),
                    "pred_change": round(change_pct, 2), "confidence": round(confidence, 1),
                    "realized_pnl": round(realized, 2), "gain_pct": round(gain_pct, 2),
                })

                pos["shares"]   = 0.0
                pos["avg_cost"] = 0.0

            positions[ticker] = pos

    # ── Final mark-to-market ───────────────────────────────────────────────────
    last_date  = common_dates[-1]
    last_prices = {}
    for t in tickers:
        df      = dfs[t]
        df_date = pd.to_datetime(df.index.date, utc=False)
        row     = df[df_date == last_date]
        if not row.empty:
            last_prices[t] = float(row["Close"].iloc[0])

    final_invested = sum(
        positions[t]["shares"] * last_prices.get(t, positions[t]["avg_cost"])
        for t in tickers if positions[t]["shares"] > 0
    )
    final_value    = cash + final_invested
    unrealized_pnl = sum(
        positions[t]["shares"] * (last_prices.get(t, positions[t]["avg_cost"]) - positions[t]["avg_cost"])
        for t in tickers if positions[t]["shares"] > 0
    )

    # ── Buy-and-hold benchmark (equal-weight across tickers) ──────────────────
    first_date = common_dates[train_window]
    bh_value   = 0.0
    per_ticker_cash = start_cash / len(tickers)
    for t in tickers:
        df      = dfs[t]
        df_date = pd.to_datetime(df.index.date, utc=False)
        first_row = df[df_date == first_date]
        last_row  = df[df_date == last_date]
        if first_row.empty or last_row.empty:
            bh_value += per_ticker_cash
            continue
        fp = float(first_row["Close"].iloc[0])
        lp = float(last_row["Close"].iloc[0])
        bh_shares = per_ticker_cash / fp
        bh_value += bh_shares * lp

    bh_return    = (bh_value - start_cash) / start_cash * 100
    strat_return = (final_value - start_cash) / start_cash * 100

    # Max drawdown
    values = [e["value"] for e in equity_curve]
    peak, max_dd = start_cash, 0.0
    for v in values:
        peak   = max(peak, v)
        max_dd = min(max_dd, (v - peak) / peak * 100)

    # Win rate across all sells
    sell_trades = [t for t in trades if t["action"] == "SELL"]
    wins        = sum(1 for t in sell_trades if t.get("realized_pnl", 0) > 0)
    win_rate    = wins / len(sell_trades) * 100 if sell_trades else 0.0

    stats = {
        "tickers":       tickers,
        "start_cash":    start_cash,
        "final_value":   round(final_value, 2),
        "strat_return":  round(strat_return, 2),
        "bh_return":     round(bh_return, 2),
        "alpha":         round(strat_return - bh_return, 2),
        "realized_pnl":  round(realized_pnl, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "total_pnl":     round(realized_pnl + unrealized_pnl, 2),
        "total_trades":  len(trades),
        "buy_trades":    sum(1 for t in trades if t["action"] == "BUY"),
        "sell_trades":   len(sell_trades),
        "win_rate":      round(win_rate, 1),
        "max_drawdown":  round(max_dd, 2),
        "test_days":     len(equity_curve),
    }

    _log(f"✓ Done!  Return: {strat_return:+.1f}%  |  B&H: {bh_return:+.1f}%  |  Alpha: {strat_return-bh_return:+.1f}%")

    return {
        "equity_curve":  equity_curve,
        "trades":        trades,
        "stats":         stats,
        "ticker_stats":  ticker_stats,
    }
