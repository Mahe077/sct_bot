import asyncio
import os
import sys
import time
from datetime import datetime, timedelta
from binance import AsyncClient, BinanceSocketManager
from config import get_config, get_sanitized_config
from strategies import check_strategy_final
from portfolio_tracker import PortfolioTracker
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)

async def main():
    while True: # Main Reconnection Loop
        config = get_config()
        client = None
        try:
            # Initialize Async Client
            client = await AsyncClient.create(
                api_key=config["API_KEY"], 
                api_secret=config["API_SECRET"], 
                testnet=config["TESTNET"]
            )
            
            print(Style.BRIGHT + Fore.CYAN + f"\n=== Binance Robust System Pro Started ===")
            print(f"Symbol: {config['SYMBOL']} | Testnet: {config['TESTNET']}")
            print(f"EMA Trend: {config['EMA_PERIOD']} | SL: {config['STOP_LOSS_PCT']*100}% | TP: {config['TAKE_PROFIT_PCT']*100}%")

            # Bootstrapping: Fetch enough data for EMA 200
            print(Fore.YELLOW + f"Bootstrapping {config['EMA_PERIOD']} periods for trend analysis...")
            klines = await client.get_klines(
                symbol=config["SYMBOL"], 
                interval=AsyncClient.KLINE_INTERVAL_1MINUTE, 
                limit=config['EMA_PERIOD'] + 20
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

            # WebSocket Manager
            bm = BinanceSocketManager(client)
            ts = bm.kline_socket(symbol=config["SYMBOL"], interval=AsyncClient.KLINE_INTERVAL_1MINUTE)

            async with ts as tscm:
                while True:
                    try:
                        # HEARTBEAT: Wait for data with 70s timeout (1m klines)
                        res = await asyncio.wait_for(tscm.recv(), timeout=70)
                        
                        if res:
                            kline = res['k']
                            is_kline_closed = kline['x']
                            current_price = float(kline['c'])

                            if is_kline_closed:
                                closes.append(current_price)
                                if len(closes) > 300: # Slightly over EMA_PERIOD
                                    closes.pop(0)
                            
                            temp_closes = closes + [current_price] if not is_kline_closed else closes
                            
                            # FINAL STRATEGY: Trend + RSI + SL/TP
                            signal, rsi_value = check_strategy_final(
                                temp_closes, 
                                current_pos_price=float(tracker.entry_price) if in_position else 0
                            )
                            
                            # Visual Feedback
                            sig_color = Fore.GREEN if signal == "BUY" else (Fore.RED if "SELL" in signal else Fore.WHITE)
                            rsi_color = Fore.YELLOW if rsi_value and (rsi_value > 70 or rsi_value < 30) else Fore.WHITE
                            
                            spin_char = spinner[spin_idx % 4]
                            spin_idx += 1
                            
                            sys.stdout.write(f"\r{Fore.CYAN}{spin_char}{Style.RESET_ALL} {Style.DIM}[{time.strftime('%H:%M:%S')}] {Fore.WHITE}Price: {current_price:.2f} | {Style.DIM}RSI: {rsi_color}{rsi_value if rsi_value else 0.0:.2f} | {Style.DIM}Signal: {sig_color}{signal}{Style.RESET_ALL} | {Style.DIM}NW: ${tracker.get_net_worth(current_price):.2f}")
                            sys.stdout.flush()

                            # Snapshot local backup
                            tracker.record_snapshot(current_price)

                            # Hourly Chart Task
                            if datetime.now() - last_chart_time > timedelta(hours=1):
                                tracker.generate_performance_chart()
                                last_chart_time = datetime.now()

                            # --- EXECUTION ---
                            if signal == "BUY" and not in_position:
                                print(f"\n{Fore.GREEN}{Style.BRIGHT} [TRADE] BUY Order (Uptrend Confirmed)...")
                                try:
                                    await client.order_market_buy(symbol=config["SYMBOL"], quantity=config["QUANTITY"])
                                    tracker.log_trade("BUY", current_price, config['QUANTITY'])
                                    in_position = True
                                except Exception as e:
                                    print(f"{Fore.RED} [ERROR] BUY failed: {e}")

                            elif "SELL" in signal and in_position:
                                label = signal.replace("SELL_", "")
                                print(f"\n{Fore.RED}{Style.BRIGHT} [TRADE] {signal} triggered...")
                                try:
                                    await client.order_market_sell(symbol=config["SYMBOL"], quantity=config["QUANTITY"])
                                    tracker.log_trade("SELL", current_price, config['QUANTITY'], label=label)
                                    in_position = False
                                except Exception as e:
                                    print(f"{Fore.RED} [ERROR] SELL failed: {e}")

                    except asyncio.TimeoutError:
                        print(f"\n{Fore.RED}[!!!] WebSocket Heartbeat Timeout. Reconnecting...")
                        break # Exit inner loop to trigger reset

        except Exception as e:
            print(f"\n{Fore.RED}[ERROR] Critical failure: {e}")
            await asyncio.sleep(5) # Delay before retry
        finally:
            if client:
                await client.close_connection()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}System shutdown requested.")
