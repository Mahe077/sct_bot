import os
import json
import boto3
import requests
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

def is_running_on_ec2():
    """Detects if the code is running on an EC2 instance by checking IMDSv2."""
    try:
        # Step 1: Get Token for IMDSv2
        token_url = "http://169.254.169.254/latest/api/token"
        headers = {"X-aws-ec2-metadata-token-ttl-seconds": "21600"}
        token_response = requests.put(token_url, headers=headers, timeout=2)
        token_response.raise_for_status()
        token = token_response.text

        # Step 2: Get Instance ID to confirm we are on EC2
        id_url = "http://169.254.169.254/latest/meta-data/instance-id"
        id_headers = {"X-aws-ec2-metadata-token": token}
        id_response = requests.get(id_url, headers=id_headers, timeout=2)
        id_response.raise_for_status()
        return True
    except (requests.exceptions.RequestException, requests.exceptions.HTTPError):
        return False

def fetch_secrets_from_aws(secret_name="sct_bot_config", region_name="us-east-1"):
    """Fetches secrets from AWS Secrets Manager."""
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        print(f"[ERROR] Could not fetch secret '{secret_name}' from AWS: {e}")
        return {}

    if 'SecretString' in get_secret_value_response:
        return json.loads(get_secret_value_response['SecretString'])
    return {}

def get_config():
    # Detect environment
    on_ec2 = is_running_on_ec2()
    aws_secrets = {}
    
    if on_ec2:
        print("[INFO] EC2 Environment detected. Fetching secrets from AWS Secrets Manager...")
        aws_secrets = fetch_secrets_from_aws(
            secret_name=os.getenv('AWS_SECRET_NAME', 'sct_bot_config'),
            region_name=os.getenv('AWS_REGION', 'us-east-1')
        )

    # Helper to resolve value from AWS, then .env, then default
    def res(key, default=None):
        return aws_secrets.get(key) or os.getenv(key) or default

    is_testnet = res('BINANCE_TESTNET', 'False').lower() == 'true'
    
    if is_testnet:
        api_key = res('BINANCE_TESTNET_API_KEY')
        api_secret = res('BINANCE_TESTNET_API_SECRET')
        print("Using Testnet API keys")
    else:
        api_key = res('BINANCE_API_KEY')
        api_secret = res('BINANCE_API_SECRET')
        print("Using Production API keys")

    return {
        "API_KEY": api_key,
        "API_SECRET": api_secret,
        "TESTNET": is_testnet,
        "SYMBOL": res("SYMBOL", "BTCUSDT"),
        "QUANTITY": float(res("QUANTITY", 0.001)),
        "FEE_RATE": float(res("FEE_RATE", 0.001)),
        "TIMEFRAME": res("TIMEFRAME", "5m"),
        # --- Legacy Fallbacks ---
        "STOP_LOSS_PCT": float(res("STOP_LOSS_PCT", 0.02)),
        "TAKE_PROFIT_PCT": float(res("TAKE_PROFIT_PCT", 0.05)),
        "EMA_PERIOD": int(res("EMA_PERIOD", 200)),
        "RSI_PERIOD": int(res("RSI_PERIOD", 14)),
        # --- New Adaptive Settings ---
        "ATR_PERIOD": int(res("ATR_PERIOD", 14)), # Added ATR Period
        "ATR_MULTIPLIER_SL": float(res("ATR_MULTIPLIER_SL", 2.0)), # How many "volatility units" (ATR) below the entry to set the Stop Loss
        "ATR_MULTIPLIER_TP": float(res("ATR_MULTIPLIER_TP", 1.5)), # How much the price must drop from its peak to trigger the Trailing Stop.
        "MIN_PROFIT_BUFFER": float(res("MIN_PROFIT_BUFFER", 0.0025)), # (0.25%) Ensures the bot doesn't exit via RSI unless fees (0.2%) are covered.
        "S3_BUCKET": res('AWS_S3_BUCKET', '032281018699-trading-bot-logs-bucket'),
        "CSV_FILE": "trades_log.csv",
        "CHART_FILE": "performance_chart.png",
        "AWS_REGION": res('AWS_REGION', 'us-east-1')
    }

def get_sanitized_config():
    """Returns the configuration without sensitive API keys for logging."""
    config = get_config()
    safe_config = config.copy()
    safe_config['API_KEY'] = '********'
    safe_config['API_SECRET'] = '********'
    return safe_config
