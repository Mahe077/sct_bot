#!/bin/bash

# Ensure we are in the script directory
cd "$(dirname "$0")"

# Activate venv and run bot
echo "Starting Binance Trading Bot..."

# Use nohup to keep running after logout, and redirect logs to bot_output.log
nohup ./venv/bin/python bot.py > bot_output.log 2>&1 &

echo "------------------------------------------------"
echo "Bot started in the background (PID: $!)"
echo "To view logs, run: tail -f bot_output.log"
echo "To stop the bot, find the PID and kill it: ps aux | grep bot.py"
echo "------------------------------------------------"
