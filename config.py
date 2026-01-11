import os
from dotenv import load_dotenv

load_dotenv()

def get_config():
    is_testnet = os.getenv('BINANCE_TESTNET', 'False').lower() == 'true'
    
    if is_testnet:
        api_key = os.getenv('BINANCE_TESTNET_API_KEY')
        api_secret = os.getenv('BINANCE_TESTNET_API_SECRET')
        print("Using Testnet API keys")
    else:
        api_key = os.getenv('BINANCE_API_KEY')
        api_secret = os.getenv('BINANCE_API_SECRET')
        print("Using Production API keys")

    return {
        "API_KEY": api_key,
        "API_SECRET": api_secret,
        "TESTNET": is_testnet,
        "SYMBOL": "BTCUSDT",
        "QUANTITY": 0.001,
        "FEE_RATE": 0.001, # 0.1% Binance Standard Fee
        "STOP_LOSS_PCT": 0.02, # 2% Stop Loss
        "TAKE_PROFIT_PCT": 0.05, # 5% Take Profit
        "EMA_PERIOD": 200,
        "RSI_PERIOD": 14,
        "S3_BUCKET": os.getenv('AWS_S3_BUCKET', '032281018699-trading-bot-logs-bucket'),
        "CSV_FILE": "trades_log.csv",
        "CHART_FILE": "performance_chart.png",
        "AWS_REGION": os.getenv('AWS_REGION') or os.getenv('AWS_DEFAULT_REGION') or 'us-east-1'
    }
