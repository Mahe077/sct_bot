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
        "QUANTITY": 0.001
    }
