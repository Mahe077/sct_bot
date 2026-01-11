from config import get_sanitized_config
import os

print("--- Testing Configuration Logic ---")
config = get_sanitized_config()

print(f"Testnet Mode: {config['TESTNET']}")
print(f"API Key: {config['API_KEY']}")
print(f"Symbol: {config['SYMBOL']}")
print(f"S3 Bucket: {config['S3_BUCKET']}")
print(f"AWS Region: {config['AWS_REGION']}")

if os.getenv('BINANCE_API_KEY'):
    print("\n[SUCCESS] Local .env values detected.")
else:
    print("\n[WARNING] No local .env values found (this is expected if .env is missing or empty).")

print("\n--- Detection Proof ---")
from config import is_running_on_ec2
print(f"Running on EC2: {is_running_on_ec2()}")
