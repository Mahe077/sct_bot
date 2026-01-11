import asyncio
import time
from binance import AsyncClient, BinanceSocketManager
from config import get_config
from strategies import check_rsi_strategy

async def main():
    config = get_config()
    # Initialize Async Client
    client = await AsyncClient.create(
        api_key=config["API_KEY"], 
        api_secret=config["API_SECRET"], 
        testnet=config["TESTNET"]
    )
    
    print(f"Starting Asynchronous WebSocket bot for {config['SYMBOL']} on Testnet={config['TESTNET']}")

    try:
        # Initialize Tracker
        tracker = PortfolioTracker(initial_balance=1000.0)
        in_position = False

        # Bootstrapping: Fetch initial historical data for RSI
        print("Bootstrapping historical data...")
        klines = await client.get_klines(symbol=config["SYMBOL"], interval=AsyncClient.KLINE_INTERVAL_1MINUTE, limit=100)
        closes = [float(k[4]) for k in klines]
        
        # Initialize WebSocket Manager
        bm = BinanceSocketManager(client)
        # Subscribe to candlestick (kline) stream for 1m interval
        ts = bm.kline_socket(symbol=config["SYMBOL"], interval=AsyncClient.KLINE_INTERVAL_1MINUTE)

        async with ts as tscm:
            while True:
                res = await tscm.recv()
                if res:
                    # 'k' is the kline data
                    kline = res['k']
                    is_kline_closed = kline['x']
                    current_price = float(kline['c'])

                    # If the candle is closed, add it to our closes buffer
                    if is_kline_closed:
                        closes.append(current_price)
                        if len(closes) > 100:
                            closes.pop(0)
                    
                    # For RSI, we can use the latest price even if the candle isn't closed yet
                    # by temporarily appending it to a copy of our buffer
                    temp_closes = closes + [current_price] if not is_kline_closed else closes
                    
                    signal, rsi_value = check_rsi_strategy(temp_closes)
                    
                    print(f"Price: {current_price:.2f} | RSI: {rsi_value if rsi_value else 'N/A':.2f} | Signal: {signal} | Counter: {len(temp_closes)}")

                    if signal == "BUY":
                        print(f">>> OVERSOLD: Proposal to BUY {config['QUANTITY']} {config['SYMBOL']}")
                        await client.order_market_buy(symbol=config["SYMBOL"], quantity=config["QUANTITY"])
                        tracker.log_trade("BUY", current_price, config['QUANTITY'])
                        in_position = True

                    elif signal == "SELL":
                        print(f">>> OVERBOUGHT: Proposal to SELL {config['QUANTITY']} {config['SYMBOL']}")
                        await client.order_market_sell(symbol=config["SYMBOL"], quantity=config["QUANTITY"])
                        tracker.log_trade("SELL", current_price, config['QUANTITY'])
                        in_position = False

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        await client.close_connection()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
