"""
Stock Prediction Agent
======================
Uses XGBoost + LSTM to predict stock prices and simulate paper trading.
Run:  python agent.py
"""

import os
import json
import argparse
from datetime import datetime

from data_fetcher import fetch_stock_data, add_technical_indicators
from predictor import train_xgboost, train_lstm, predict_next_day
from simulator import PaperTrader
from report import print_report

# ── Configuration ─────────────────────────────────────────────────────────────
TICKERS   = ["AAPL", "TSLA"]   # ← Add or change tickers here
PERIOD    = "2y"               # How much historical data to train on (e.g. "1y", "2y", "5y")
MODEL     = "xgboost"          # "xgboost" or "lstm"
START_CASH = 10_000            # Virtual starting cash in USD
# ──────────────────────────────────────────────────────────────────────────────


def run_agent(tickers=TICKERS, model_type=MODEL, start_cash=START_CASH):
    print("\n" + "═"*60)
    print("  📈  Stock Prediction Agent  📈")
    print("═"*60)
    print(f"  Tickers : {', '.join(tickers)}")
    print(f"  Model   : {model_type.upper()}")
    print(f"  Cash    : ${start_cash:,}")
    print("═"*60 + "\n")

    trader = PaperTrader(start_cash=start_cash)
    predictions = {}

    for ticker in tickers:
        print(f"\n{'─'*50}")
        print(f"  Processing {ticker} …")
        print(f"{'─'*50}")

        # 1. Fetch & prepare data
        print("  [1/4] Fetching historical data …")
        df = fetch_stock_data(ticker, period=PERIOD)
        df = add_technical_indicators(df)
        print(f"        ✓ {len(df)} trading days loaded")

        # 2. Train model
        print(f"  [2/4] Training {model_type.upper()} model …")
        if model_type == "xgboost":
            model, scaler, feature_cols = train_xgboost(df)
        else:
            model, scaler, feature_cols = train_lstm(df)
        print("        ✓ Model trained")

        # 3. Predict next trading day
        print("  [3/4] Predicting next trading day …")
        pred_price, confidence, last_price = predict_next_day(
            df, model, scaler, feature_cols, model_type
        )
        change_pct = (pred_price - last_price) / last_price * 100
        predictions[ticker] = {
            "last_price":  round(last_price, 2),
            "pred_price":  round(pred_price, 2),
            "change_pct":  round(change_pct, 2),
            "confidence":  round(confidence, 2),
        }
        direction = "▲" if change_pct > 0 else "▼"
        print(f"        Last close : ${last_price:.2f}")
        print(f"        Prediction : ${pred_price:.2f}  {direction} {change_pct:+.2f}%")
        print(f"        Confidence : {confidence:.0f}%")

        # 4. Simulate trade
        print("  [4/4] Simulating trade decision …")
        trader.decide_and_trade(ticker, last_price, pred_price, confidence)

    # Final report
    print_report(trader, predictions)

    # Save results
    os.makedirs("results", exist_ok=True)
    result_file = f"results/run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(result_file, "w") as f:
        json.dump({
            "tickers":     tickers,
            "model":       model_type,
            "predictions": predictions,
            "portfolio":   trader.get_summary(),
        }, f, indent=2)
    print(f"\n  💾  Results saved → {result_file}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stock Prediction Agent")
    parser.add_argument("--tickers", nargs="+", default=TICKERS)
    parser.add_argument("--model",   choices=["xgboost", "lstm"], default=MODEL)
    parser.add_argument("--cash",    type=float, default=START_CASH)
    args = parser.parse_args()

    run_agent(tickers=args.tickers, model_type=args.model, start_cash=args.cash)
