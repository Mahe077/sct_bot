#!/bin/bash

# Update and install dependencies
echo "[1/4] Updating system packages..."
sudo apt-get update -y
sudo apt-get install -y python3-pip python3-venv

# Create virtual environment
echo "[2/4] Creating virtual environment (venv)..."
python3 -m venv venv

# Install requirements
echo "[3/4] Installing Python dependencies from requirements.txt..."
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# Make run script executable
if [ -f "run_bot.sh" ]; then
    echo "[4/4] Making run_bot.sh executable..."
    chmod +x run_bot.sh
fi

echo "------------------------------------------------"
echo "Setup Complete!"
echo "To start the bot, run: ./run_bot.sh"
echo "------------------------------------------------"
