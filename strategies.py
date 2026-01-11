import pandas as pd

def calculate_rsi(prices, period=14):
    """
    Calculate the Relative Strength Index (RSI) for a given series of prices.
    """
    if len(prices) < period + 1:
        return None
    
    delta = pd.Series(prices).diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

def check_rsi_strategy(prices, overbought=70, oversold=30):
    """
    Check RSI strategy and return a signal.
    """
    rsi = calculate_rsi(prices)
    if rsi is None:
        return "HOLD", None

    if rsi < oversold:
        return "BUY", rsi
    elif rsi > overbought:
        return "SELL", rsi
    else:
        return "HOLD", rsi
