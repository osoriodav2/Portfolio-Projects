"""
simulator.py
────────────
Paper-trading simulator with full P&L tracking.

Tracks:
  - Cash balance after every trade
  - Shares held per ticker + avg cost basis
  - Realized P&L on each SELL
  - Unrealized P&L on open positions (marked to last price)
  - Running equity snapshots after each trade
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Trade:
    ticker:       str
    action:       str       # "BUY" | "SELL" | "HOLD"
    shares:       float
    price:        float
    value:        float     # cash moved (cost for BUY, proceeds for SELL)
    reason:       str
    cash_after:   float = 0.0
    realized_pnl: float = 0.0   # only set on SELL


@dataclass
class Position:
    ticker:   str
    shares:   float = 0.0
    avg_cost: float = 0.0

    def market_value(self, price: float) -> float:
        return self.shares * price

    def unrealized_pnl(self, price: float) -> float:
        return (price - self.avg_cost) * self.shares

    def unrealized_pnl_pct(self, price: float) -> float:
        if self.avg_cost == 0:
            return 0.0
        return (price - self.avg_cost) / self.avg_cost * 100


class PaperTrader:
    """Full paper-money portfolio with P&L tracking."""

    def __init__(self, start_cash: float = 10_000):
        self.cash           = start_cash
        self.start_cash     = start_cash
        self.positions:     Dict[str, Position] = {}
        self.trades:        List[Trade] = []
        self.realized_pnl:  float = 0.0          # cumulative across all SELLs
        # equity snapshots: list of {label, cash, invested, total}
        self.equity_history: List[dict] = [
            {"label": "Start", "cash": start_cash, "invested": 0.0, "total": start_cash}
        ]

    # ── Public interface ──────────────────────────────────────────────────────

    def decide_and_trade(
        self,
        ticker: str,
        last_price: float,
        pred_price: float,
        confidence: float,
    ) -> str:
        """Make a BUY/SELL/HOLD decision and execute. Returns action string."""
        change_pct = (pred_price - last_price) / last_price * 100

        BUY_THRESHOLD  =  1.5
        SELL_THRESHOLD = -1.5
        MIN_CONFIDENCE = 55.0

        if change_pct > BUY_THRESHOLD and confidence > MIN_CONFIDENCE:
            return self._buy(ticker, last_price, confidence, change_pct)
        elif change_pct < SELL_THRESHOLD and confidence > MIN_CONFIDENCE:
            return self._sell(ticker, last_price, change_pct)
        else:
            reason = (
                f"Δ {change_pct:+.1f}% within ±{BUY_THRESHOLD}% band"
                if abs(change_pct) < BUY_THRESHOLD
                else f"confidence {confidence:.0f}% below {MIN_CONFIDENCE}% threshold"
            )
            trade = Trade(
                ticker=ticker, action="HOLD", shares=0, price=last_price,
                value=0, reason=reason, cash_after=self.cash,
            )
            self.trades.append(trade)
            print(f"        → HOLD  ({reason})")
            return "HOLD"

    def total_value(self, current_prices: Optional[Dict[str, float]] = None) -> float:
        """Cash + mark-to-market value of all open positions."""
        invested = self._invested_value(current_prices)
        return self.cash + invested

    def positions_snapshot(self, current_prices: Optional[Dict[str, float]] = None) -> List[dict]:
        """Return a list of open position dicts with full P&L fields."""
        snap = []
        for ticker, pos in self.positions.items():
            if pos.shares <= 0:
                continue
            price = (current_prices or {}).get(ticker, pos.avg_cost)
            mkt_val   = pos.market_value(price)
            unreal    = pos.unrealized_pnl(price)
            unreal_pct = pos.unrealized_pnl_pct(price)
            snap.append({
                "ticker":          ticker,
                "shares":          round(pos.shares, 6),
                "avg_cost":        round(pos.avg_cost, 4),
                "current_price":   round(price, 2),
                "market_value":    round(mkt_val, 2),
                "cost_basis":      round(pos.shares * pos.avg_cost, 2),
                "unrealized_pnl":  round(unreal, 2),
                "unrealized_pct":  round(unreal_pct, 2),
            })
        return snap

    def portfolio_summary(self, current_prices: Optional[Dict[str, float]] = None) -> dict:
        positions = self.positions_snapshot(current_prices)
        invested  = sum(p["market_value"] for p in positions)
        total     = self.cash + invested
        total_unreal = sum(p["unrealized_pnl"] for p in positions)
        total_pnl    = self.realized_pnl + total_unreal
        total_pnl_pct = total_pnl / self.start_cash * 100

        return {
            "start_cash":       round(self.start_cash, 2),
            "cash":             round(self.cash, 2),
            "invested":         round(invested, 2),
            "total":            round(total, 2),
            "pnl_pct":          round((total - self.start_cash) / self.start_cash * 100, 2),
            "realized_pnl":     round(self.realized_pnl, 2),
            "unrealized_pnl":   round(total_unreal, 2),
            "total_pnl":        round(total_pnl, 2),
            "total_pnl_pct":    round(total_pnl_pct, 2),
            "positions":        positions,
            "equity_history":   self.equity_history,
            "trade_count":      len([t for t in self.trades if t.action != "HOLD"]),
        }

    # ── Private ───────────────────────────────────────────────────────────────

    def _buy(self, ticker: str, price: float, confidence: float, change_pct: float) -> str:
        pos_pct       = 0.20 + (confidence - 55) / (95 - 55) * 0.20
        invest_amount = self.cash * min(pos_pct, 0.40)

        if invest_amount < price:
            print(f"        → SKIP  (insufficient cash for 1 share of {ticker})")
            return "SKIP"

        shares = invest_amount / price
        cost   = shares * price
        self.cash -= cost

        if ticker not in self.positions:
            self.positions[ticker] = Position(ticker=ticker)
        pos = self.positions[ticker]
        total_shares   = pos.shares + shares
        pos.avg_cost   = (pos.avg_cost * pos.shares + cost) / total_shares
        pos.shares     = total_shares

        trade = Trade(
            ticker=ticker, action="BUY", shares=shares,
            price=price, value=cost, cash_after=self.cash,
            reason=f"predicted {change_pct:+.1f}%, conf {confidence:.0f}%",
        )
        self.trades.append(trade)
        self._record_equity(ticker, price)

        print(f"        → BUY   {shares:.4f} sh @ ${price:.2f} = ${cost:.2f}  |  cash left: ${self.cash:,.2f}")
        return "BUY"

    def _sell(self, ticker: str, price: float, change_pct: float) -> str:
        pos = self.positions.get(ticker)
        if not pos or pos.shares <= 0:
            print(f"        → SKIP  (no {ticker} position to sell)")
            return "SKIP"

        proceeds     = pos.shares * price
        cost_basis   = pos.shares * pos.avg_cost
        realized     = proceeds - cost_basis
        realized_pct = realized / cost_basis * 100 if cost_basis else 0

        self.cash         += proceeds
        self.realized_pnl += realized

        trade = Trade(
            ticker=ticker, action="SELL", shares=pos.shares,
            price=price, value=proceeds, cash_after=self.cash,
            realized_pnl=round(realized, 2),
            reason=f"predicted {change_pct:+.1f}%, realized {realized_pct:+.1f}%",
        )
        self.trades.append(trade)

        print(f"        → SELL  {pos.shares:.4f} sh @ ${price:.2f} = ${proceeds:.2f}  |  P&L: ${realized:+.2f} ({realized_pct:+.1f}%)")

        pos.shares   = 0.0
        pos.avg_cost = 0.0
        self._record_equity(ticker, price)
        return "SELL"

    def _invested_value(self, current_prices: Optional[Dict[str, float]] = None) -> float:
        total = 0.0
        for ticker, pos in self.positions.items():
            if pos.shares > 0:
                price = (current_prices or {}).get(ticker, pos.avg_cost)
                total += pos.shares * price
        return total

    def _record_equity(self, last_ticker: str, last_price: float):
        """Snapshot portfolio value after a trade, using last_price for that ticker."""
        prices = {last_ticker: last_price}
        invested = self._invested_value(prices)
        total    = self.cash + invested
        label    = f"T{len(self.equity_history)}"
        self.equity_history.append({
            "label":    label,
            "cash":     round(self.cash, 2),
            "invested": round(invested, 2),
            "total":    round(total, 2),
        })
