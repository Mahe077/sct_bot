import asyncio
import os
import sys
import time
from datetime import datetime, timedelta
from binance import AsyncClient, BinanceSocketManager
from config import get_config
from strategies import check_rsi_strategy_pro, calculate_metrics
from portfolio_tracker import PortfolioTracker
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)

async def main():
    config = get_config()
    # Initialize Async Client
    client = await AsyncClient.create(
        api_key=config["API_KEY"], 
        api_secret=config["API_SECRET"], 
        testnet=config["TESTNET"]
    )
    
    print(Style.BRIGHT + Fore.CYAN + f"=== Binance RSI Strategy Pro Started ===")
    print(f"Symbol: {config['SYMBOL']} | Testnet: {config['TESTNET']}")
    print(f"RSI Period: {config['RSI_PERIOD']} | SL/TP: 2%/5%")
    print(f"S3 Reporting: {config['S3_BUCKET']}\n")

    try:
        # Bootstrapping: Fetch initial historical data for Strategy
        print(Fore.YELLOW + f"Bootstrapping {config['RSI_PERIOD']} periods for strategy...")
        klines = await client.get_klines(
            symbol=config["SYMBOL"], 
            interval=AsyncClient.KLINE_INTERVAL_1MINUTE, 
            limit=config['RSI_PERIOD'] + 10
        )
        closes = [float(k[4]) for k in klines]
        print(Fore.GREEN + "Bootstrap complete.\n")

        # FETCH ACTUAL STARTING BALANCE
        res = await client.get_asset_balance(asset='USDT')
        starting_balance = float(res['free'])
        print(Fore.YELLOW + f"Initial USDT Balance: ${starting_balance:.2f}")

        # Initialize Tracker
        tracker = PortfolioTracker(initial_balance=starting_balance)
        in_position = False
        
        # Dashboard state
        spinner = ["|", "/", "-", "\\"]
        spin_idx = 0
        last_chart_time = datetime.now()

        # Initialize WebSocket Manager
        bm = BinanceSocketManager(client)
        ts = bm.kline_socket(symbol=config["SYMBOL"], interval=AsyncClient.KLINE_INTERVAL_1MINUTE)

        async with ts as tscm:
            while True:
                res = await tscm.recv()
                if res:
                    kline = res['k']
                    is_kline_closed = kline['x']
                    current_price = float(kline['c'])

                    if is_kline_closed:
                        closes.append(current_price)
                        if len(closes) > 100:
                            closes.pop(0)
                    
                    # Calculate live metrics
                    temp_closes = closes + [current_price] if not is_kline_closed else closes
                    
                    # Call Strategy Pro with current position info
                    signal, rsi_value = check_rsi_strategy_pro(
                        temp_closes, 
                        current_pos_price=tracker.entry_price if in_position else 0
                    )
                    
                    # Dashboard Output with Spinner
                    sig_color = Fore.GREEN if signal == "BUY" else (Fore.RED if "SELL" in signal else Fore.WHITE)
                    rsi_color = Fore.YELLOW if rsi_value and (rsi_value > 70 or rsi_value < 30) else Fore.WHITE
                    
                    spin_char = spinner[spin_idx % 4]
                    spin_idx += 1
                    
                    sys.stdout.write(f"\r{Fore.CYAN}{spin_char}{Style.RESET_ALL} {Style.DIM}[{time.strftime('%H:%M:%S')}] {Fore.WHITE}Price: {current_price:.2f} | {Style.DIM}RSI: {rsi_color}{rsi_value if rsi_value else 0.0:.2f} | {Style.DIM}Signal: {sig_color}{signal}{Style.RESET_ALL} | {Style.DIM}NW: ${tracker.get_net_worth(current_price):.2f}")
                    sys.stdout.flush()

                    # Record snapshot for charting
                    tracker.record_snapshot(current_price)

                    # --- HOURLY PERFORMANCE CHART ---
                    if datetime.now() - last_chart_time > timedelta(hours=1):
                        tracker.generate_performance_chart()
                        last_chart_time = datetime.now()

                    # --- TRADE EXECUTION ---
                    if signal == "BUY" and not in_position:
                        print(f"\n{Fore.GREEN}{Style.BRIGHT} [TRADE] Executing BUY Order...")
                        try:
                            await client.order_market_buy(symbol=config["SYMBOL"], quantity=config["QUANTITY"])
                            tracker.log_trade("BUY", current_price, config['QUANTITY'])
                            in_position = True
                        except Exception as e:
                            print(f"{Fore.RED} [ERROR] BUY failed: {e}")

                    elif "SELL" in signal and in_position:
                        label = signal.replace("SELL_", "") if "_" in signal else "STRATEGY"
                        print(f"\n{Fore.RED}{Style.BRIGHT} [TRADE] Executing {signal} Order...")
                        try:
                            await client.order_market_sell(symbol=config["SYMBOL"], quantity=config["QUANTITY"])
                            tracker.log_trade("SELL", current_price, config['QUANTITY'], label=label)
                            in_position = False
                        except Exception as e:
                            print(f"{Fore.RED} [ERROR] SELL failed: {e}")

    except Exception as e:
        print(f"\n{Fore.RED}{Style.BRIGHT}An error occurred: {e}")
    finally:
        await client.close_connection()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Bot stopped by user.")
