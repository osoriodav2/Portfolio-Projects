"""
data_fetcher.py
───────────────
Downloads historical OHLCV data from Yahoo Finance and calculates
technical indicators used as features for the ML models.
"""

import pandas as pd
import numpy as np
import yfinance as yf


def fetch_stock_data(ticker: str, period: str = "2y") -> pd.DataFrame:
    """
    Download historical daily OHLCV data for a ticker.

    Parameters
    ----------
    ticker : str   e.g. "AAPL"
    period : str   yfinance period string: "1y", "2y", "5y", etc.

    Returns
    -------
    pd.DataFrame with columns: Open, High, Low, Close, Volume
    """
    stock = yf.Ticker(ticker)
    df = stock.history(period=period)

    # Keep only core OHLCV columns
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.dropna(inplace=True)
    df.index = pd.to_datetime(df.index)
    return df


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Enrich the DataFrame with common technical indicators.

    Added features
    --------------
    - Returns & lag returns (1d, 5d, 10d)
    - Simple moving averages (SMA) 5, 10, 20, 50 days
    - Exponential moving average (EMA) 12 & 26 days
    - MACD line and signal
    - Relative Strength Index (RSI) 14 days
    - Bollinger Bands (upper, middle, lower)
    - Average True Range (ATR) – volatility measure
    - On-Balance Volume (OBV)
    - Price position within day's range
    """
    df = df.copy()

    # ── Returns ───────────────────────────────────────────────────────────────
    df["Return_1d"]  = df["Close"].pct_change(1)
    df["Return_5d"]  = df["Close"].pct_change(5)
    df["Return_10d"] = df["Close"].pct_change(10)

    # ── Moving averages ───────────────────────────────────────────────────────
    for w in [5, 10, 20, 50]:
        df[f"SMA_{w}"] = df["Close"].rolling(w).mean()
        df[f"SMA_{w}_ratio"] = df["Close"] / df[f"SMA_{w}"]   # price / MA ratio

    df["EMA_12"] = df["Close"].ewm(span=12, adjust=False).mean()
    df["EMA_26"] = df["Close"].ewm(span=26, adjust=False).mean()

    # ── MACD ──────────────────────────────────────────────────────────────────
    df["MACD"]        = df["EMA_12"] - df["EMA_26"]
    df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_hist"]   = df["MACD"] - df["MACD_signal"]

    # ── RSI ───────────────────────────────────────────────────────────────────
    delta = df["Close"].diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    df["RSI"] = 100 - (100 / (1 + rs))

    # ── Bollinger Bands ───────────────────────────────────────────────────────
    df["BB_mid"]   = df["Close"].rolling(20).mean()
    bb_std         = df["Close"].rolling(20).std()
    df["BB_upper"] = df["BB_mid"] + 2 * bb_std
    df["BB_lower"] = df["BB_mid"] - 2 * bb_std
    df["BB_width"] = (df["BB_upper"] - df["BB_lower"]) / df["BB_mid"]
    df["BB_pct"]   = (df["Close"] - df["BB_lower"]) / (df["BB_upper"] - df["BB_lower"] + 1e-9)

    # ── ATR (Average True Range) ───────────────────────────────────────────────
    hl   = df["High"] - df["Low"]
    hpc  = (df["High"] - df["Close"].shift()).abs()
    lpc  = (df["Low"]  - df["Close"].shift()).abs()
    tr   = pd.concat([hl, hpc, lpc], axis=1).max(axis=1)
    df["ATR"] = tr.rolling(14).mean()

    # ── On-Balance Volume ─────────────────────────────────────────────────────
    obv = [0]
    for i in range(1, len(df)):
        if df["Close"].iloc[i] > df["Close"].iloc[i - 1]:
            obv.append(obv[-1] + df["Volume"].iloc[i])
        elif df["Close"].iloc[i] < df["Close"].iloc[i - 1]:
            obv.append(obv[-1] - df["Volume"].iloc[i])
        else:
            obv.append(obv[-1])
    df["OBV"] = obv

    # ── Intraday range position ───────────────────────────────────────────────
    df["Day_range_pct"] = (df["Close"] - df["Low"]) / (df["High"] - df["Low"] + 1e-9)

    # ── Volume features ───────────────────────────────────────────────────────
    df["Volume_SMA20"]   = df["Volume"].rolling(20).mean()
    df["Volume_ratio"]   = df["Volume"] / (df["Volume_SMA20"] + 1e-9)

    # ── Target: next day close (for training) ─────────────────────────────────
    df["Target"] = df["Close"].shift(-1)

    df.dropna(inplace=True)
    return df
