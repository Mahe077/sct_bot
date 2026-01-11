import pandas as pd

# def calculate_rsi(prices, period=14):
#     """
#     Calculate the Relative Strength Index (RSI) for a given series of prices.
#     """
#     if len(prices) < period + 1:
#         return None
    
#     delta = pd.Series(prices).diff()
#     gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
#     loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

#     rs = gain / loss
#     rsi = 100 - (100 / (1 + rs))
#     return rsi.iloc[-1]

# def check_rsi_strategy(prices, overbought=70, oversold=30):
#     """
#     Check RSI strategy and return a signal.
#     """
#     rsi = calculate_rsi(prices)
#     if rsi is None:
#         return "HOLD", None

#     if rsi < oversold:
#         return "BUY", rsi
#     elif rsi > overbought:
#         return "SELL", rsi
#     else:
#         return "HOLD", rsi

def calculate_rsi_robust(prices, period=14):
    if len(prices) < period + 1:
        return None
    
    delta = pd.Series(prices).diff()
    # Wilder's Smoothing (EMA-based)
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

def check_rsi_strategy_pro(prices, current_pos_price=0):
    rsi = calculate_rsi_robust(prices)
    if rsi is None: return "HOLD", None

    current_price = prices[-1]
    
    # 1. EXIT LOGIC (Risk Management)
    if current_pos_price > 0:
        # Stop Loss at 2%
        if current_price < current_pos_price * 0.98:
            return "SELL_STOP_LOSS", rsi
        # Take Profit at 5% or Overbought
        if rsi > 70 or current_price > current_pos_price * 1.05:
            return "SELL_TAKE_PROFIT", rsi

    # 2. ENTRY LOGIC
    if rsi < 30:
        return "BUY", rsi
        
    return "HOLD", rsi

def calculate_metrics(prices, rsi_period=14, ema_period=200):
    if len(prices) < ema_period:
        return None, None
    
    series = pd.Series(prices)
    
    # 1. Calculate RSI with Wilder's Smoothing
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(com=rsi_period - 1, adjust=False).mean()
    loss = -delta.clip(upper=0).ewm(com=rsi_period - 1, adjust=False).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    # 2. Calculate 200 EMA (The Trend Filter)
    ema_200 = series.ewm(span=ema_period, adjust=False).mean()
    
    return rsi.iloc[-1], ema_200.iloc[-1]

def check_strategy_with_trend(prices, in_position=False):
    rsi, ema_200 = calculate_metrics(prices)
    if rsi is None: return "HOLD", rsi
    
    current_price = prices[-1]

    # --- BUY LOGIC ---
    # Only buy if RSI is oversold AND price is above the 200 EMA (Uptrend)
    if not in_position:
        if rsi < 30 and current_price > ema_200:
            return "BUY", rsi
        else:
            return "HOLD", rsi

    # --- SELL LOGIC ---
    # Sell if RSI becomes overbought
    if in_position:
        if rsi > 70:
            return "SELL", rsi
            
    return "HOLD", rsi

def check_strategy_final(prices, current_pos_price=0):
    rsi, ema_200 = calculate_metrics(prices)
    if rsi is None: return "HOLD", None

    current_price = prices[-1]
    
    # --- 1. EXIT LOGIC (Always checked first) ---
    if current_pos_price > 0:
        # Emergency Stop Loss (2%)
        if current_price < current_pos_price * 0.98:
            return "SELL_STOP_LOSS", rsi
        # Take Profit (5%) or Overbought (70)
        if rsi > 70 or current_price > current_pos_price * 1.05:
            return "SELL_TAKE_PROFIT", rsi

    # --- 2. ENTRY LOGIC (Trend + RSI) ---
    else:
        # Only enter if we are in an UPTREND and OVERSOLD
        if current_price > ema_200 and rsi < 30:
            return "BUY", rsi
        
    return "HOLD", rsi