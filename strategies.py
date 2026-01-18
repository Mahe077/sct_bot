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

def calculate_metrics(prices, volumes=None, rsi_period=14, ema_period=200, atr_period=14):
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
    
    # 3. ATR (Volatility Filter)
    high_low = series.diff().abs()
    atr = high_low.rolling(window=atr_period).mean()
    
    # 4. Volume Confirmation (Wait for buying pressure)
    vol_confirm = True
    if volumes is not None:
        vol_series = pd.Series(volumes)
        avg_vol = vol_series.rolling(window=10).mean()
        vol_confirm = vol_series.iloc[-1] > avg_vol.iloc[-1]

    return rsi.iloc[-1], ema_200.iloc[-1], atr.iloc[-1], vol_confirm

def check_strategy_final(prices, volumes, current_pos_price=0, highest_since_entry=0):
    rsi, ema_200, atr, vol_confirm = calculate_metrics(prices, volumes)
    if rsi is None: return "HOLD", None, 0

    current_price = prices[-1]
    # Calculate break-even price (covers buy and sell fees)
    break_even = float(current_pos_price) * (1 + (fee_rate * 2))
    
    if current_pos_price > 0:
        # A. Dynamic ATR-based Stop Loss (e.g., 2.0x ATR below entry)
        # This gives the trade "room to breathe" during volatility
        stop_loss_price = float(current_pos_price) - (float(atr) * 2.0)
        if current_price < stop_loss_price:
            return "SELL_STOP_LOSS", rsi

        # B. Trailing Take Profit
        # If price is up significantly, and drops 1 ATR from its peak, lock in profit
        trailing_stop = float(highest_since_entry) - (float(atr) * 1.5)
        if current_price > break_even and current_price < trailing_stop:
            return "SELL_TRAILING_TP", rsi

        # C. RSI Exit (Only if in profit to avoid fee drain)
        if rsi > 70 and current_price > break_even:
            return "SELL_RSI_EXIT", rsi

    # --- 2. ENTRY LOGIC (Trend + RSI + Volume) ---
    else:
        # Only buy if: Uptrend (Price > EMA200) AND Oversold (RSI < 30) AND Volume is Rising
        if current_price > ema_200 and rsi < 30 and vol_confirm:
            return "BUY", rsi
        
    return "HOLD", rsi