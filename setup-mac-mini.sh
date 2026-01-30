#!/bin/bash

# Keiko Mac Mini Setup Script
# Run this on the Mac Mini after AirDropping the keiko-telegram-bot folder and .env.local

set -e

echo "=========================================="
echo "  Keiko Mac Mini Setup"
echo "=========================================="
echo ""

# Check if running on Mac Mini (or any Mac)
if [[ "$(uname)" != "Darwin" ]]; then
    echo "❌ This script is for macOS only"
    exit 1
fi

# Step 1: Install Homebrew
echo "📦 Step 1: Installing Homebrew..."
if ! command -v brew &> /dev/null; then
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # Add to path for Apple Silicon
    if [[ -f "/opt/homebrew/bin/brew" ]]; then
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zshrc
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
else
    echo "✅ Homebrew already installed"
fi

# Step 2: Install Python
echo ""
echo "🐍 Step 2: Installing Python 3.13..."
brew install python@3.13 || echo "Python may already be installed"

# Step 3: Install Claude CLI
echo ""
echo "🤖 Step 3: Installing Claude CLI..."
brew install claude-code || echo "Claude CLI may already be installed"

# Step 4: Install Claude Desktop
echo ""
echo "💻 Step 4: Installing Claude Desktop..."
brew install --cask claude || echo "Claude Desktop may already be installed"

# Step 5: Check for Keiko folder
echo ""
echo "📁 Step 5: Checking for Keiko..."
KEIKO_DIR="$HOME/Apps/keiko-telegram-bot"

if [[ ! -d "$KEIKO_DIR" ]]; then
    echo "❌ Keiko folder not found at $KEIKO_DIR"
    echo "   Please AirDrop the keiko-telegram-bot folder to ~/Apps/ first"
    exit 1
fi
echo "✅ Keiko folder found"

# Step 6: Check for .env.local
echo ""
echo "🔑 Step 6: Checking for .env.local..."
if [[ ! -f "$HOME/Apps/.env.local" ]]; then
    echo "⚠️  Warning: .env.local not found at ~/Apps/.env.local"
    echo "   Make sure to AirDrop it before running Keiko"
fi

# Step 7: Install Python packages
echo ""
echo "📚 Step 7: Installing Python packages..."
cd "$KEIKO_DIR"

if [[ -f "requirements.txt" ]]; then
    pip3 install -r requirements.txt
else
    echo "Installing packages manually..."
    pip3 install python-telegram-bot anthropic python-dotenv pytz aiohttp apscheduler psutil
fi

# Step 8: Create logs directory
echo ""
echo "📝 Step 8: Creating logs directory..."
mkdir -p "$KEIKO_DIR/logs"

# Step 9: Setup launchd
echo ""
echo "⚙️  Step 9: Setting up launchd..."
mkdir -p ~/Library/LaunchAgents

if [[ -f "$KEIKO_DIR/com.richardechols.keiko.plist" ]]; then
    cp "$KEIKO_DIR/com.richardechols.keiko.plist" ~/Library/LaunchAgents/
    echo "✅ Launchd plist copied"
else
    echo "❌ plist file not found - you may need to create it"
fi

# Step 10: Headless settings
echo ""
echo "🖥️  Step 10: Configuring headless settings..."
echo "   (This requires sudo - enter your password)"

sudo pmset -a sleep 0
sudo pmset -a disksleep 0
sudo pmset -a standby 0
sudo pmset -a autopoweroff 0
sudo pmset -a restartfreeze 1
sudo pmset -a autorestart 1
sudo pmset -a womp 1

echo "✅ Headless settings configured"

# Step 11: Start Keiko
echo ""
echo "🚀 Step 11: Starting Keiko..."
launchctl unload ~/Library/LaunchAgents/com.richardechols.keiko.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.richardechols.keiko.plist

# Verify
sleep 2
if launchctl list | grep -q "com.richardechols.keiko"; then
    echo "✅ Keiko is running!"
else
    echo "⚠️  Keiko may not have started. Check logs:"
    echo "   tail -f ~/Apps/keiko-telegram-bot/logs/stderr.log"
fi

echo ""
echo "=========================================="
echo "  Setup Complete!"
echo "=========================================="
echo ""
echo "Keiko should now be running 24/7."
echo ""
echo "Useful commands:"
echo "  Check status:  launchctl list | grep keiko"
echo "  View logs:     tail -f ~/Apps/keiko-telegram-bot/logs/bot.log"
echo "  Restart:       launchctl unload ~/Library/LaunchAgents/com.richardechols.keiko.plist && launchctl load ~/Library/LaunchAgents/com.richardechols.keiko.plist"
echo ""
