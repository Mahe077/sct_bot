import os
from dotenv import load_dotenv
from binance import Client

load_dotenv()

api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_API_SECRET')

print(f"Testing keys against PRODUCTION...")
client = Client(api_key=api_key, api_secret=api_secret, testnet=False)

try:
    account = client.get_account()
    print("SUCCESS: These are PRODUCTION keys.")
    print(f"Permissions: {account.get('permissions')}")
except Exception as e:
    print(f"FAILED on Production: {e}")

print(f"\nTesting keys against TESTNET...")
client_test = Client(api_key=api_key, api_secret=api_secret, testnet=True)
try:
    account_test = client_test.get_account()
    print("SUCCESS: These are TESTNET keys.")
except Exception as e:
    print(f"FAILED on Testnet: {e}")
