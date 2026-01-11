import os
import csv
import boto3
import threading
from datetime import datetime
from config import get_config
import matplotlib.pyplot as plt
import pandas as pd

class PortfolioTracker:
    def __init__(self, initial_balance=1000.0):
        self.config = get_config()
        self.initial_balance = initial_balance
        self.current_cash = initial_balance
        self.crypto_held = 0.0
        self.trades = [] # List of trade results
        self.entry_price = 0.0
        self.entry_time = None
        self.stop_loss_pct = self.config.get('STOP_LOSS_PCT', 0.02)
        self.take_profit_pct = self.config.get('TAKE_PROFIT_PCT', 0.05)
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
        fee = price * quantity * self.config['FEE_RATE']
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        pnl = 0.0
        pnl_pct = 0.0
        
        if side == "BUY":
            self.entry_price = price
            self.entry_time = timestamp
            self.crypto_held = quantity
            self.current_cash -= (price * quantity + fee)
            self.is_active = True
            
            # Log to CSV
            self._write_to_csv([timestamp, 'BUY', price, quantity, fee, 0.0, 0.0, self.get_net_worth(price), label])
            
        elif side == "SELL":
            exit_price = price
            # PnL = (Sell Value - Buy Value) - (Buy Fee + Sell Fee)
            # Note: self.entry_price * quantity is the approximate cost basis
            buy_value = self.entry_price * quantity
            sell_value = exit_price * quantity
            buy_fee = buy_value * self.config['FEE_RATE']
            
            pnl = (sell_value - buy_value) - (buy_fee + fee)
            pnl_pct = ((sell_value - fee) / (buy_value + buy_fee) - 1) * 100
            
            self.current_cash += (sell_value - fee)
            self.crypto_held = 0.0
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
            self._write_to_csv([timestamp, 'SELL', price, quantity, fee, pnl, pnl_pct, self.current_cash, label])
            self._print_performance(pnl, pnl_pct)

        # Record Net Worth History
        self.record_snapshot(price)
        
        # Upload CSV to S3
        self._sync_to_s3(self.config['CSV_FILE'])

    def record_snapshot(self, current_price):
        """Records the current net worth for history and charting."""
        self.nw_history.append((datetime.now(), self.get_net_worth(current_price)))
        # Keep history manageable (e.g., last 1000 snapshots)
        if len(self.nw_history) > 1000:
            self.nw_history.pop(0)

    def get_net_worth(self, current_price):
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
                # Don't crash the bot if S3 fails, just log it locally
                print(f"\n[ERROR] S3 Upload Failed: {e}")

        # Start the upload in a separate thread
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
            plt.plot(df.index, df['NetWorth'], label='Net Worth', color='#00ffcc', linewidth=2)
            plt.title('Trading Bot Performance', color='white', fontsize=16)
            plt.xlabel('Time', color='white')
            plt.ylabel('Net Worth (USDT)', color='white')
            plt.grid(True, alpha=0.2)
            plt.legend()
            
            # Dark mode aesthetic
            plt.gcf().set_facecolor('#1e1e1e')
            plt.gca().set_facecolor('#1e1e1e')
            plt.gca().tick_params(colors='white')
            
            plt.savefig(self.config['CHART_FILE'])
            plt.close()
            
            # Upload Chart to S3
            self._sync_to_s3(self.config['CHART_FILE'])
            print(f"\n[INFO] Performance Chart updated and uploaded to S3.")
        except Exception as e:
            print(f"\n[ERROR] Chart Generation failed: {e}")

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

        pnl_pct = (current_price - self.entry_price) / self.entry_price

        if pnl_pct <= -self.stop_loss_pct:
            return "STOP_LOSS"
        
        if pnl_pct >= self.take_profit_pct:
            return "TAKE_PROFIT"

        return None