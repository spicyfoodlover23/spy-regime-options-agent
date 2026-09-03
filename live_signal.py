import os
import csv
import pickle
import pandas as pd
import yfinance as yf
import ta
from datetime import date

# Download the minimum rolling window required to compute our features
spy = yf.download("SPY", period="300d", interval="1d")
spy.columns = spy.columns.droplevel(1)

vix = yf.download("^VIX", period="300d", interval="1d")
vix.columns = vix.columns.droplevel(1)

treasury_10y = yf.download("^TNX", period="300d", interval="1d")
treasury_10y.columns = treasury_10y.columns.droplevel(1)

treasury_2y = yf.download("^IRX", period="300d", interval="1d")
treasury_2y.columns = treasury_2y.columns.droplevel(1)

# ============================================================
# STEP 3: FEATURE ENGINEERING
# ============================================================

# 1. Align external features into the main SPY DataFrame
spy['VIX'] = vix['Close']
spy['Yield_Spread'] = treasury_10y['Close'] - treasury_2y['Close']

# 2. Calculate returns and lags
spy['Current_Return'] = spy['Close'].pct_change(1)
spy['Lagged_Return_1'] = spy['Current_Return'].shift(1)
spy['Lagged_Return_2'] = spy['Current_Return'].shift(2)

# 3. Calculate technical indicators
spy['RSI'] = ta.momentum.RSIIndicator(spy['Close'], window=14).rsi()
spy['BB_Width'] = ta.volatility.BollingerBands(spy['Close'], window=20, window_dev=2).bollinger_wband()
spy['SMA_200'] = ta.trend.sma_indicator(close=spy['Close'], window=200)

# 4. Drop the warm-up rows (the first 200 rows will be NaN due to the SMA_200)
spy_cleaned = spy.dropna(subset=['Lagged_Return_1', 'Lagged_Return_2', 'RSI', 'BB_Width', 'VIX', 'Yield_Spread', 'SMA_200'])

# ============================================================
# STEP 4: ISOLATE YESTERDAY
# ============================================================

# Define the exact features and ordering our model was trained on
feature_columns = ['Lagged_Return_1', 'Lagged_Return_2', 'RSI', 'BB_Width', 'VIX', 'Yield_Spread']

# Grab the absolute last row of data, and filter for only those 6 columns
latest_features = spy_cleaned[feature_columns].iloc[[-1]]

# Track yesterday's closing price and SMA just for our printed confirmation/filters later
latest_close = spy_cleaned['Close'].iloc[-1]
latest_sma = spy_cleaned['SMA_200'].iloc[-1]

# ============================================================
# STEP 5: SCALE AND PREDICT
# ============================================================

# 1. Open and load the pre-trained machine learning "brain"
with open('ensemble_model.pkl', 'rb') as f:
    ensemble = pickle.load(f)  # Ensure the variable name is 'ensemble'

with open('scaler.pkl', 'rb') as f:
    scaler = pickle.load(f)

# 2. Scale the fresh single row using our training rules
latest_features_scaled = scaler.transform(latest_features)

# 3. Generate today's official regime signal (0 or 1)
prediction = ensemble.predict(latest_features_scaled)[0]
signal_label = "RISK-ON" if prediction == 1 else "RISK-OFF"

# ============================================================
# STEP 6: STAMP THE LOG BOOK
# ============================================================
today = date.today()
log_file = "paper_trading_log.csv"
file_exists = os.path.exists(log_file)

with open(log_file, 'a', newline='') as f:
    writer = csv.writer(f)
    if not file_exists:
        writer.writerow(['Date', 'Signal', 'Signal_Value', 'SPY_Close'])
    writer.writerow([today, signal_label, prediction, round(latest_close, 2)])

# Print the final production dashboard
print("=" * 50)
print(f"LIVE PRODUCTION SIGNAL GENERATION COMPLETE")
print("=" * 50)
print(f"Current Date:       {today}")
print(f"Yesterday's Close:  ${latest_close:.2f}")
print(f"Yesterday's SMA200: ${latest_sma:.2f}")
print("-" * 50)
print(f"TODAY'S REGIME:     >>> {signal_label} <<< (Value: {prediction})")
print(f"Log Updated:        {log_file}")
print("=" * 50)










