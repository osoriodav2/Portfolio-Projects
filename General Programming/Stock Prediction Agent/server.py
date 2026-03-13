"""
server.py
─────────
Flask web server for the Stock Prediction Agent UI.
Serves three modes:
  • Predict  – single-day prediction + paper trade decision
  • Backtest – walk-forward replay over historical data
  • Live     – persistent daily paper trading (state saved to disk)

Run:  python server.py
Open: http://localhost:5000
"""

import json
import os
import threading
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory

from data_fetcher import fetch_stock_data, add_technical_indicators
from predictor import train_xgboost, predict_next_day
from simulator import PaperTrader
from backtester import run_backtest
from live_trader import run_live_session, _load_state, SAVE_FILE

app = Flask(__name__, static_folder="ui", static_url_path="")
os.makedirs("results", exist_ok=True)


# ── Shared helpers ─────────────────────────────────────────────────────────────

def make_state():
    return dict(running=False, log=[], predictions={}, trades=[],
                portfolio={}, error=None)

def log_to(state, msg):
    ts = datetime.now().strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    state["log"].append(entry)
    print(entry)


# ── Per-mode state objects ─────────────────────────────────────────────────────
predict_state  = make_state()
backtest_state = make_state()
backtest_state["result"] = {}
live_state     = make_state()
live_state["portfolio"] = {}

predict_trader = PaperTrader(start_cash=10_000)


# ════════════════════════════════════════════════════════════════════════════════
#  Static
# ════════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return send_from_directory("ui", "index.html")


# ════════════════════════════════════════════════════════════════════════════════
#  PREDICT
# ════════════════════════════════════════════════════════════════════════════════

@app.route("/api/run", methods=["POST"])
def run_predict():
    if predict_state["running"]:
        return jsonify({"error": "Already running"}), 400

    body       = request.json or {}
    tickers    = body.get("tickers", ["AAPL", "TSLA"])
    start_cash = float(body.get("startCash", 10_000))
    period     = body.get("period", "2y")

    predict_state.update(running=True, log=[], predictions={}, trades=[], error=None)
    global predict_trader
    predict_trader = PaperTrader(start_cash=start_cash)

    def run():
        try:
            for ticker in tickers:
                log_to(predict_state, f"── {ticker} ──────────────────────────")
                log_to(predict_state, f"Fetching {period} of history …")
                df = fetch_stock_data(ticker, period=period)
                df = add_technical_indicators(df)
                log_to(predict_state, f"✓ {len(df)} trading days loaded")

                log_to(predict_state, "Training XGBoost model …")
                model, scaler, feature_cols = train_xgboost(df)
                log_to(predict_state, "✓ Model trained")

                log_to(predict_state, "Predicting next trading day …")
                pred_price, confidence, last_price = predict_next_day(
                    df, model, scaler, feature_cols, "xgboost"
                )
                change_pct = (pred_price - last_price) / last_price * 100
                predict_state["predictions"][ticker] = {
                    "last_price": round(last_price, 2),
                    "pred_price": round(pred_price, 2),
                    "change_pct": round(change_pct, 2),
                    "confidence": round(confidence, 1),
                }
                arrow = "▲" if change_pct > 0 else "▼"
                log_to(predict_state, f"Prediction: ${pred_price:.2f}  {arrow} {change_pct:+.2f}%  (conf {confidence:.0f}%)")

                log_to(predict_state, "Deciding trade …")
                action = predict_trader.decide_and_trade(ticker, last_price, pred_price, confidence)
                if predict_trader.trades:
                    t = predict_trader.trades[-1]
                    predict_state["trades"].append({
                        "ticker": t.ticker, "action": t.action,
                        "shares": round(t.shares, 4), "price": round(t.price, 2),
                        "value":  round(t.value, 2),  "reason": t.reason,
                        "cash_after": round(t.cash_after, 2),
                        "realized_pnl": round(t.realized_pnl, 2),
                    })
                    log_to(predict_state, f"→ {t.action} {t.shares:.4f} sh @ ${t.price:.2f}  |  cash: ${t.cash_after:,.2f}")

            current_prices = {
                t: predict_state["predictions"][t]["last_price"]
                for t in predict_state["predictions"]
            }
            predict_state["portfolio"] = predict_trader.portfolio_summary(current_prices)
            pf = predict_state["portfolio"]
            log_to(predict_state, f"✓ Run complete!  Portfolio: ${pf['total']:,.2f}  (P&L: ${pf['total_pnl']:+.2f})")

        except Exception as e:
            predict_state["error"] = str(e)
            log_to(predict_state, f"ERROR: {e}")
        finally:
            predict_state["running"] = False

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"status": "started"})


@app.route("/api/status")
def predict_status():
    return jsonify(predict_state)


@app.route("/api/reset", methods=["POST"])
def predict_reset():
    global predict_trader
    if predict_state["running"]:
        return jsonify({"error": "Cannot reset while running"}), 400
    predict_trader = PaperTrader(start_cash=10_000)
    predict_state.update(running=False, log=[], predictions={}, trades=[], portfolio={}, error=None)
    return jsonify({"status": "reset"})


# ════════════════════════════════════════════════════════════════════════════════
#  BACKTEST
# ════════════════════════════════════════════════════════════════════════════════

@app.route("/api/backtest/run", methods=["POST"])
def backtest_run():
    if backtest_state["running"]:
        return jsonify({"error": "Backtest already running"}), 400

    body       = request.json or {}
    tickers    = body.get("tickers", ["AAPL"])
    if isinstance(tickers, str):
        tickers = [tickers]
    start_cash = float(body.get("startCash", 10_000))
    period     = body.get("period", "3y")

    backtest_state.update(running=True, log=[], result={}, error=None)

    def run():
        try:
            log_to(backtest_state, f"Backtest: {', '.join(tickers)}  |  {period}  |  ${start_cash:,.0f}")
            dfs = {}
            for ticker in tickers:
                log_to(backtest_state, f"Fetching {ticker} …")
                df = fetch_stock_data(ticker, period=period)
                df = add_technical_indicators(df)
                dfs[ticker] = df
                log_to(backtest_state, f"✓ {ticker}: {len(df)} days")

            result = run_backtest(
                dfs,
                start_cash=start_cash,
                log_fn=lambda m: log_to(backtest_state, m),
            )

            backtest_state["result"] = result
            s = result["stats"]
            log_to(backtest_state, f"━━ Results ━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            log_to(backtest_state, f"Strategy return : {s['strat_return']:+.2f}%")
            log_to(backtest_state, f"Buy & hold      : {s['bh_return']:+.2f}%")
            log_to(backtest_state, f"Alpha           : {s['alpha']:+.2f}%")
            log_to(backtest_state, f"Realized P&L    : ${s['realized_pnl']:+.2f}")
            log_to(backtest_state, f"Total trades    : {s['total_trades']}")
            log_to(backtest_state, f"Win rate        : {s['win_rate']:.1f}%")
            log_to(backtest_state, f"Max drawdown    : {s['max_drawdown']:.2f}%")

            label = "_".join(tickers)
            fname = f"results/backtest_{label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(fname, "w") as f:
                json.dump(result, f, indent=2, default=str)
            log_to(backtest_state, f"Saved → {fname}")

        except Exception as e:
            backtest_state["error"] = str(e)
            log_to(backtest_state, f"ERROR: {e}")
        finally:
            backtest_state["running"] = False

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"status": "started"})


@app.route("/api/backtest/status")
def backtest_status():
    return jsonify(backtest_state)


@app.route("/api/backtest/reset", methods=["POST"])
def backtest_reset():
    if backtest_state["running"]:
        return jsonify({"error": "Cannot reset while running"}), 400
    backtest_state.update(running=False, log=[], result={}, error=None)
    return jsonify({"status": "reset"})


# ════════════════════════════════════════════════════════════════════════════════
#  LIVE PAPER TRADING
# ════════════════════════════════════════════════════════════════════════════════

@app.route("/api/live/run", methods=["POST"])
def live_run():
    if live_state["running"]:
        return jsonify({"error": "Live session already running"}), 400

    body       = request.json or {}
    tickers    = body.get("tickers", ["AAPL", "TSLA"])
    start_cash = float(body.get("startCash", 10_000))

    live_state.update(running=True, log=[], error=None)

    def run():
        try:
            pf = run_live_session(
                tickers,
                start_cash=start_cash,
                log_fn=lambda m: log_to(live_state, m),
            )
            live_state["portfolio"] = pf
        except Exception as e:
            live_state["error"] = str(e)
            log_to(live_state, f"ERROR: {e}")
        finally:
            live_state["running"] = False

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"status": "started"})


@app.route("/api/live/status")
def live_status():
    pf = live_state.get("portfolio") or {}
    if not pf and os.path.exists(SAVE_FILE):
        with open(SAVE_FILE) as f:
            pf = json.load(f)
    return jsonify({
        "running":   live_state["running"],
        "log":       live_state["log"],
        "error":     live_state["error"],
        "portfolio": pf,
    })


@app.route("/api/live/reset", methods=["POST"])
def live_reset():
    if live_state["running"]:
        return jsonify({"error": "Cannot reset while running"}), 400
    if os.path.exists(SAVE_FILE):
        os.remove(SAVE_FILE)
    live_state.update(running=False, log=[], portfolio={}, error=None)
    return jsonify({"status": "reset"})


# ════════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    os.makedirs("ui", exist_ok=True)
    print("\n  🚀  Stock Agent UI  →  http://localhost:5000\n")
    app.run(debug=False, port=5000)
