"""
predictor.py
────────────
Trains either an XGBoost regressor or a simple LSTM network on
historical stock features and predicts the next trading day's close price.
"""

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_error
from xgboost import XGBRegressor


# ── Feature columns used by both models ───────────────────────────────────────
FEATURE_COLS = [
    "Return_1d", "Return_5d", "Return_10d",
    "SMA_5_ratio", "SMA_10_ratio", "SMA_20_ratio", "SMA_50_ratio",
    "MACD", "MACD_signal", "MACD_hist",
    "RSI",
    "BB_width", "BB_pct",
    "ATR",
    "Volume_ratio",
    "Day_range_pct",
]


# ══════════════════════════════════════════════════════════════════════════════
#  XGBoost
# ══════════════════════════════════════════════════════════════════════════════

def train_xgboost(df: pd.DataFrame):
    """
    Train an XGBoost model to predict next-day close price.

    Returns
    -------
    model        : trained XGBRegressor
    scaler       : fitted MinMaxScaler (for features)
    feature_cols : list of feature column names used
    """
    feature_cols = [c for c in FEATURE_COLS if c in df.columns]

    X = df[feature_cols].values
    y = df["Target"].values          # next day's close

    # 80/20 train-test split (chronological – no shuffle!)
    split = int(len(X) * 0.80)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    # Scale features
    scaler = MinMaxScaler()
    X_train = scaler.fit_transform(X_train)
    X_test  = scaler.transform(X_test)

    model = XGBRegressor(
        n_estimators=400,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbosity=0,
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    # Quick validation print
    preds = model.predict(X_test)
    mae   = mean_absolute_error(y_test, preds)
    print(f"        Validation MAE: ${mae:.2f}")

    return model, scaler, feature_cols


# ══════════════════════════════════════════════════════════════════════════════
#  LSTM
# ══════════════════════════════════════════════════════════════════════════════

def train_lstm(df: pd.DataFrame, lookback: int = 20):
    """
    Train a simple LSTM network to predict next-day close price.

    Parameters
    ----------
    lookback : int  Number of past trading days fed into the LSTM at each step.

    Returns
    -------
    model        : trained Keras Sequential model
    scaler       : fitted MinMaxScaler
    feature_cols : list of feature column names used
    """
    try:
        import tensorflow as tf
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import LSTM, Dense, Dropout
        from tensorflow.keras.callbacks import EarlyStopping
    except ImportError:
        raise ImportError(
            "TensorFlow is required for LSTM mode.\n"
            "Install it with:  pip install tensorflow"
        )

    feature_cols = [c for c in FEATURE_COLS if c in df.columns]

    X_raw = df[feature_cols].values
    y_raw = df["Target"].values

    # Scale
    scaler = MinMaxScaler()
    X_scaled = scaler.fit_transform(X_raw)

    # Build sequences of shape (samples, lookback, features)
    Xs, ys = [], []
    for i in range(lookback, len(X_scaled)):
        Xs.append(X_scaled[i - lookback : i])
        ys.append(y_raw[i])
    Xs = np.array(Xs)
    ys = np.array(ys)

    split   = int(len(Xs) * 0.80)
    X_train, X_test = Xs[:split], Xs[split:]
    y_train, y_test = ys[:split], ys[split:]

    model = Sequential([
        LSTM(64, return_sequences=True, input_shape=(lookback, len(feature_cols))),
        Dropout(0.2),
        LSTM(32),
        Dropout(0.2),
        Dense(1),
    ])
    model.compile(optimizer="adam", loss="mae")

    es = EarlyStopping(monitor="val_loss", patience=10, restore_best_weights=True)
    model.fit(
        X_train, y_train,
        validation_data=(X_test, y_test),
        epochs=100,
        batch_size=16,
        callbacks=[es],
        verbose=0,
    )

    preds = model.predict(X_test, verbose=0).flatten()
    mae   = mean_absolute_error(y_test, preds)
    print(f"        Validation MAE: ${mae:.2f}")

    # Store lookback on model so predict_next_day can use it
    model._lookback = lookback
    return model, scaler, feature_cols


# ══════════════════════════════════════════════════════════════════════════════
#  Shared prediction interface
# ══════════════════════════════════════════════════════════════════════════════

def predict_next_day(df, model, scaler, feature_cols, model_type: str):
    """
    Use the trained model to predict tomorrow's closing price.

    Returns
    -------
    pred_price  : float  predicted close price
    confidence  : float  0–100 score derived from recent MAE vs price
    last_price  : float  most recent actual close price
    """
    last_price = float(df["Close"].iloc[-1])

    if model_type == "xgboost":
        X_last  = df[feature_cols].iloc[-1:].values
        X_scaled = scaler.transform(X_last)
        pred_price = float(model.predict(X_scaled)[0])

        # Confidence: based on how large recent residuals are vs price
        recent = df.tail(30)
        X_r    = scaler.transform(recent[feature_cols].values)
        preds_r = model.predict(X_r)
        mae_pct = np.mean(np.abs(preds_r - recent["Target"].values)) / last_price
        confidence = max(10.0, min(95.0, (1 - mae_pct * 10) * 100))

    else:  # LSTM
        lookback = getattr(model, "_lookback", 20)
        X_raw   = df[feature_cols].values[-lookback:]
        X_scaled = scaler.transform(X_raw)
        X_seq    = X_scaled.reshape(1, lookback, len(feature_cols))
        pred_price = float(model.predict(X_seq, verbose=0)[0][0])

        recent = df.tail(lookback + 10)
        seqs, actuals = [], []
        X_r_scaled = scaler.transform(recent[feature_cols].values)
        for i in range(lookback, len(X_r_scaled)):
            seqs.append(X_r_scaled[i - lookback : i])
            actuals.append(recent["Target"].values[i])
        if seqs:
            seqs = np.array(seqs)
            preds_r = model.predict(seqs, verbose=0).flatten()
            mae_pct = np.mean(np.abs(preds_r - np.array(actuals))) / last_price
            confidence = max(10.0, min(95.0, (1 - mae_pct * 10) * 100))
        else:
            confidence = 50.0

    return pred_price, confidence, last_price
