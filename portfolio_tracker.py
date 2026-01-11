import os
import csv
import boto3
import threading
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from config import get_config
import matplotlib.pyplot as plt
import pandas as pd

class PortfolioTracker:
    def __init__(self, initial_balance=1000.0):
        self.config = get_config()
        # Financial Precision using Decimal
        self.initial_balance = Decimal(str(initial_balance))
        self.current_cash = Decimal(str(initial_balance))
        self.crypto_held = Decimal('0.0')
        self.trades = [] # List of trade results
        self.entry_price = Decimal('0.0')
        self.entry_time = None
        self.stop_loss_pct = Decimal(str(self.config.get('STOP_LOSS_PCT', 0.02)))
        self.take_profit_pct = Decimal(str(self.config.get('TAKE_PROFIT_PCT', 0.05)))
        self.is_active = False # Track if we are currently in a trade
        
        self.nw_history = [] # List of (timestamp, net_worth)
        
        # S3 Client initialization
        self.s3 = boto3.client('s3', region_name=self.config['AWS_REGION'])
        
        # Initialize CSV file if it doesn't exist
        if not os.path.exists(self.config['CSV_FILE']):
            with open(self.config['CSV_FILE'], mode='w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Timestamp', 'Side', 'Price', 'Quantity', 'Fee', 'PnL', 'PnL_Pct', 'Net_Worth', 'Type'])

    def log_trade(self, side, price, quantity, label="STRATEGY"):
        price = Decimal(str(price))
        quantity = Decimal(str(quantity))
        fee_rate = Decimal(str(self.config['FEE_RATE']))
        
        fee = (price * quantity * fee_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        pnl = Decimal('0.0')
        pnl_pct = Decimal('0.0')
        
        if side == "BUY":
            self.entry_price = price
            self.entry_time = timestamp
            self.crypto_held = quantity
            # Cost = Price * Quantity + Fee
            self.current_cash -= (price * quantity + fee)
            self.is_active = True
            
            # Log to CSV
            self._write_to_csv([timestamp, 'BUY', f"{price:.8f}", f"{quantity:.8f}", f"{fee:.4f}", "0.00", "0.00", f"{self.get_net_worth(price):.2f}", label])
            
        elif side == "SELL":
            exit_price = price
            buy_value = self.entry_price * quantity
            sell_value = exit_price * quantity
            buy_fee = (buy_value * fee_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            # PnL = (Sell Value - Buy Value) - (Buy Fee + Sell Fee)
            pnl = (sell_value - buy_value) - (buy_fee + fee)
            pnl_pct = (((sell_value - fee) / (buy_value + buy_fee)) - 1) * 100
            
            self.current_cash += (sell_value - fee)
            self.crypto_held = Decimal('0.0')
            self.is_active = False
            
            trade_info = {
                'timestamp': timestamp,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'entry_price': self.entry_price,
                'exit_price': exit_price,
                'quantity': quantity,
                'fee': fee + buy_fee,
                'type': label
            }
            self.trades.append(trade_info)
            
            # Log to CSV
            self._write_to_csv([timestamp, 'SELL', f"{price:.8f}", f"{quantity:.8f}", f"{fee:.4f}", f"{pnl:.2f}", f"{pnl_pct:.2f}", f"{self.current_cash:.2f}", label])
            self._print_performance(pnl, pnl_pct)

        # Record Net Worth History
        self.record_snapshot(price)
        
        # Upload CSV to S3
        self._sync_to_s3(self.config['CSV_FILE'])

    def record_snapshot(self, current_price):
        """Records the current net worth for history and charting."""
        self.nw_history.append((datetime.now(), float(self.get_net_worth(Decimal(str(current_price))))))
        # Keep history manageable (last 1440 entries = 24 hours of 1m data)
        if len(self.nw_history) > 1440:
            self.nw_history.pop(0)

    def get_net_worth(self, current_price):
        current_price = Decimal(str(current_price))
        return self.current_cash + (self.crypto_held * current_price)

    def _write_to_csv(self, row):
        with open(self.config['CSV_FILE'], mode='a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(row)

    def _sync_to_s3(self, filename):
        def upload():
            try:
                self.s3.upload_file(filename, self.config['S3_BUCKET'], filename)
            except Exception as e:
                # Silent failure is fine here, local CSV is the source of truth
                pass

        thread = threading.Thread(target=upload)
        thread.start()

    def generate_performance_chart(self):
        """Generates a PNG chart of Net Worth over time and uploads to S3."""
        if not self.nw_history:
            return

        try:
            df = pd.DataFrame(self.nw_history, columns=['Timestamp', 'NetWorth'])
            df.set_index('Timestamp', inplace=True)

            plt.figure(figsize=(10, 6))
            plt.plot(df.index, df['NetWorth'], label='Performance (Net Worth)', color='#00ffcc', linewidth=2)
            plt.title('Trading Assistant Performance', color='white', fontsize=16)
            plt.xlabel('Time', color='white')
            plt.ylabel('USDT Balance', color='white')
            plt.grid(True, alpha=0.1)
            
            # Format UI
            plt.gcf().set_facecolor('#1e1e1e')
            plt.gca().set_facecolor('#1e1e1e')
            plt.gca().tick_params(colors='white')
            plt.legend(facecolor='#1e1e1e', labelcolor='white')
            
            plt.savefig(self.config['CHART_FILE'])
            plt.close()
            
            # Upload Chart to S3
            self._sync_to_s3(self.config['CHART_FILE'])
        except Exception:
            pass

    def _print_performance(self, pnl, pnl_pct):
        if not self.trades:
            return
            
        wins = [t for t in self.trades if t['pnl'] > 0]
        win_rate = (len(wins) / len(self.trades)) * 100 if self.trades else 0
        total_pnl = sum(t['pnl'] for t in self.trades)
        
        print(f"\n>> TRADE CLOSED | PnL: ${pnl:.2f} ({pnl_pct:.2f}%)")
        print(f">> STRATEGY STATS | Win Rate: {win_rate:.1f}% | Total Profit: ${total_pnl:.2f}")
        print(f">> NET WORTH: ${self.current_cash:.2f}\n")

    def check_exit_conditions(self, current_price):
        if not self.is_active or self.entry_price == 0:
            return None

        current_price = Decimal(str(current_price))
        pnl_pct_decimal = (current_price - self.entry_price) / self.entry_price

        if pnl_pct_decimal <= -self.stop_loss_pct:
            return "STOP_LOSS"
        
        if pnl_pct_decimal >= self.take_profit_pct:
            return "TAKE_PROFIT"

        return None