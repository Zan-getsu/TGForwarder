#!/usr/bin/env bash
# TGForwarder Session Generator
# Quick script to generate Telegram session files for Docker deployment

clear
echo -e "\e[1m"
echo "  _____ _ _       _     _            _    _               _ "
echo " |_   _(_) |_ ___| |__ | | ___   ___| | _(_)_ __    _ __| |"
echo "   | | | | __/ __| '_ \| |/ _ \ / __| |/ / | '_ \  | '__| |"
echo "   | | | | || (__| | | | | (_) | (__|   <| | |_) | | |  |_|"
echo "   |_| |_|\__\___|_| |_|_|\___/ \___|_|\_\_| .__/  |_|  (_)"
echo "                                           |_|            "
echo -e "\e[0m"
echo -e "\e[36m  Telegram Forwarder - Session Generator\e[0m"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "\e[31mError: Python3 is not installed!\e[0m"
    echo "Please install Python3 first:"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-pip"
    echo "  Fedora: sudo dnf install python3 python3-pip"
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "\e[33mWarning: .env file not found!\e[0m"
    echo "Please create a .env file with API_ID and API_HASH first."
    echo ""
    read -p "Do you want to create .env now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cp .env.example .env 2>/dev/null || echo "API_ID=" > .env
        echo "Created .env file. Please edit it with your credentials."
        exit 1
    fi
    exit 1
fi

# Check if API_ID and API_HASH are set
if ! grep -q "^API_ID=" .env || ! grep -q "^API_HASH=" .env; then
    echo -e "\e[31mError: API_ID or API_HASH not set in .env!\e[0m"
    echo "Please edit .env and add your Telegram API credentials."
    echo "Get them from: https://my.telegram.org"
    exit 1
fi

# Install/upgrade dependencies
echo -e "\e[1;32mInstalling/Checking Dependencies...\e[0m"
pip3 install -r requirements.txt -q 2>/dev/null || pip3 install telethon python-dotenv -q

# Create sessions directory
mkdir -p sessions

# Run session generator
echo -e "\e[1;32mStarting Session Generator...\e[0m"
echo ""
python3 generate_session.py

# Fix permissions (in case Docker created files as root)
if [ -d sessions ]; then
    echo -e "\e[1;33mFixing session file permissions...\e[0m"
    sudo chown -R $USER:$USER sessions/ 2>/dev/null || chown -R $USER:$USER sessions/ 2>/dev/null || true
fi

# Ask if user wants to reset sync state
echo ""
echo -e "\e[1;33mDo you want to sync ALL existing messages from source chats?\e[0m"
echo -e "\e[36m  (This will delete the sync state and re-forward all messages)\e[0m"
read -p "  Reset sync state? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -f sessions/sync_state.json
    echo -e "\e[1;32m✓ Sync state reset. All messages will be synced on next run.\e[0m"
fi

# Check if session was created
if [ -f sessions/user_session.session ]; then
    echo ""
    echo -e "\e[1;32m✓ Session file created successfully!\e[0m"
    echo -e "\e[36m  Location: sessions/user_session.session\e[0m"
    echo ""
    echo -e "\e[1;33mNext steps:\e[0m"
    echo "  1. Start Docker: docker compose up -d"
    echo "  2. View logs: docker compose logs -f"
    echo ""
else
    echo -e "\e[31m✗ Session generation failed!\e[0m"
    echo "Please check the error messages above."
    exit 1
fi
