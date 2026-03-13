"""
live_trader.py
──────────────
Persistent daily paper-trading tracker with full P&L.

State saved to results/live_portfolio.json between sessions.
Each session:
  1. Fetches live prices
  2. Retrains model on fresh data
  3. Makes BUY/SELL/HOLD decision
  4. Records realized P&L on sells, unrealized on open positions
  5. Saves daily equity snapshot
"""

import json
import os
from datetime import datetime

from data_fetcher import fetch_stock_data, add_technical_indicators
from predictor import train_xgboost, predict_next_day

SAVE_FILE      = "results/live_portfolio.json"
BUY_THRESHOLD  =  1.5
SELL_THRESHOLD = -1.5
MIN_CONFIDENCE = 55.0


def _load_state(start_cash: float) -> dict:
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE) as f:
            return json.load(f)
    return {
        "start_cash":    start_cash,
        "cash":          start_cash,
        "positions":     {},   # ticker → {shares, avg_cost}
        "history":       [],   # daily equity snapshots
        "trades":        [],   # all-time trade log
        "realized_pnl":  0.0,
    }


def _save_state(state: dict):
    os.makedirs("results", exist_ok=True)
    with open(SAVE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def run_live_session(tickers: list, start_cash: float = 10_000, log_fn=None) -> dict:
    def _log(msg):
        if log_fn:
            log_fn(msg)

    state = _load_state(start_cash)
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    _log(f"Live session: {today}")
    _log(f"Cash: ${state['cash']:,.2f}  |  Realized P&L so far: ${state.get('realized_pnl', 0):+.2f}")

    current_prices = {}   # collect latest price per ticker for mark-to-market

    for ticker in tickers:
        _log(f"── {ticker} ──────────────────────")
        _log("Fetching latest data …")
        df = fetch_stock_data(ticker, period="1y")
        df = add_technical_indicators(df)
        last_price = float(df["Close"].iloc[-1])
        current_prices[ticker] = last_price
        _log(f"✓ {len(df)} days  |  Last close: ${last_price:.2f}")

        _log("Training model …")
        model, scaler, feature_cols = train_xgboost(df)

        _log("Predicting …")
        pred_price, confidence, _ = predict_next_day(
            df, model, scaler, feature_cols, "xgboost"
        )
        change_pct = (pred_price - last_price) / last_price * 100
        arrow = "▲" if change_pct > 0 else "▼"
        _log(f"Pred: ${pred_price:.2f}  {arrow} {change_pct:+.2f}%  (conf {confidence:.0f}%)")

        pos    = state["positions"].get(ticker, {"shares": 0.0, "avg_cost": 0.0})
        action = "HOLD"

        # ── BUY ───────────────────────────────────────────────────────────────
        if change_pct > BUY_THRESHOLD and confidence > MIN_CONFIDENCE and state["cash"] >= last_price:
            pos_pct    = 0.20 + (confidence - 55) / (95 - 55) * 0.20
            invest_amt = state["cash"] * min(pos_pct, 0.40)
            new_shares = invest_amt / last_price
            cost       = new_shares * last_price

            old_shares = pos["shares"]
            old_avg    = pos["avg_cost"]
            total_sh   = old_shares + new_shares
            new_avg    = (old_avg * old_shares + cost) / total_sh if total_sh > 0 else last_price

            pos = {"shares": round(total_sh, 6), "avg_cost": round(new_avg, 4)}
            state["cash"] -= cost
            action = "BUY"

            trade = {
                "date": today, "ticker": ticker, "action": "BUY",
                "shares": round(new_shares, 4), "price": round(last_price, 2),
                "value": round(cost, 2),
                "cash_after": round(state["cash"], 2),
                "pred_change": round(change_pct, 2),
                "confidence": round(confidence, 1),
                "realized_pnl": 0.0,
            }
            state["trades"].append(trade)
            _log(f"→ BUY  {new_shares:.4f} sh @ ${last_price:.2f} = ${cost:.2f}  |  cash: ${state['cash']:,.2f}")

        # ── SELL ──────────────────────────────────────────────────────────────
        elif change_pct < SELL_THRESHOLD and confidence > MIN_CONFIDENCE and pos["shares"] > 0:
            proceeds   = pos["shares"] * last_price
            cost_basis = pos["shares"] * pos["avg_cost"]
            realized   = proceeds - cost_basis
            real_pct   = realized / cost_basis * 100 if cost_basis else 0

            state["cash"]         += proceeds
            state["realized_pnl"] = round(state.get("realized_pnl", 0) + realized, 4)
            action = "SELL"

            trade = {
                "date": today, "ticker": ticker, "action": "SELL",
                "shares": round(pos["shares"], 4), "price": round(last_price, 2),
                "value": round(proceeds, 2),
                "cash_after": round(state["cash"], 2),
                "pred_change": round(change_pct, 2),
                "confidence": round(confidence, 1),
                "realized_pnl": round(realized, 2),
                "realized_pct": round(real_pct, 2),
            }
            state["trades"].append(trade)
            _log(f"→ SELL {pos['shares']:.4f} sh @ ${last_price:.2f} = ${proceeds:.2f}  |  P&L: ${realized:+.2f} ({real_pct:+.1f}%)")
            pos = {"shares": 0.0, "avg_cost": 0.0}

        else:
            _log(f"→ HOLD")

        state["positions"][ticker] = pos

    # ── Mark-to-market snapshot ────────────────────────────────────────────────
    invested     = 0.0
    unrealized   = 0.0
    positions_snap = []

    for ticker, pos in state["positions"].items():
        if pos["shares"] <= 0:
            continue
        price     = current_prices.get(ticker, pos["avg_cost"])
        mkt_val   = pos["shares"] * price
        cost_b    = pos["shares"] * pos["avg_cost"]
        unreal    = mkt_val - cost_b
        unreal_pct = unreal / cost_b * 100 if cost_b else 0
        invested  += mkt_val
        unrealized += unreal
        positions_snap.append({
            "ticker":         ticker,
            "shares":         round(pos["shares"], 6),
            "avg_cost":       round(pos["avg_cost"], 4),
            "current_price":  round(price, 2),
            "market_value":   round(mkt_val, 2),
            "cost_basis":     round(cost_b, 2),
            "unrealized_pnl": round(unreal, 2),
            "unrealized_pct": round(unreal_pct, 2),
        })

    total        = state["cash"] + invested
    realized_pnl = state.get("realized_pnl", 0.0)
    total_pnl    = realized_pnl + unrealized
    total_pnl_pct = total_pnl / state["start_cash"] * 100 if state["start_cash"] else 0

    snapshot = {
        "date":          datetime.now().strftime("%Y-%m-%d"),
        "value":         round(total, 2),
        "cash":          round(state["cash"], 2),
        "invested":      round(invested, 2),
        "unrealized_pnl": round(unrealized, 2),
        "realized_pnl":  round(realized_pnl, 2),
        "total_pnl":     round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
    }
    state["history"].append(snapshot)

    # Attach computed fields to state for UI
    state["positions_snap"] = positions_snap
    state["current_snapshot"] = snapshot
    state["total_pnl"]      = round(total_pnl, 2)
    state["total_pnl_pct"]  = round(total_pnl_pct, 2)
    state["unrealized_pnl"] = round(unrealized, 2)

    _log(f"✓ Total: ${total:,.2f}  |  Realized: ${realized_pnl:+.2f}  |  Unrealized: ${unrealized:+.2f}")

    _save_state(state)
    _log(f"State saved → {SAVE_FILE}")

    return state
