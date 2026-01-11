import asyncio
from binance import AsyncClient, BinanceSocketManager

class PortfolioTracker:
    def __init__(self, initial_balance):
        self.initial_balance = initial_balance
        self.current_cash = initial_balance
        self.crypto_held = 0.0
        self.trade = [] #List of trade results
        self.entry_price = 0.0

    def log_trade(self, side, price, quantity):
        if side == "BUY":
            self.entry_price = price
            self.crypto_held = quantity
            self.current_cash -= (price * quantity)
            print(f"BUY: {quantity} {config['SYMBOL']} at {price}")
        elif side == "SELL":
            exit_price = price
            pnl = (exit_price - self.entry_price) * self.quantity
            pnl_pct = ((exit_price / self.entry_price) - 1) * 100
            
        