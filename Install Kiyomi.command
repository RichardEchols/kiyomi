#!/bin/bash
# Kiyomi v4.0 Installer — Double-click to install
# Works on any Mac with Python 3.10+

set -e

clear
echo "🌸 Kiyomi v4.0 Installer"
echo "========================="
echo ""

# Find the script's directory (where the user downloaded Kiyomi)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
INSTALL_DIR="$HOME/.kiyomi"
APP_DIR="$INSTALL_DIR/app"

echo "📦 Installing Kiyomi to $INSTALL_DIR..."

# Create directories
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/memory"
mkdir -p "$INSTALL_DIR/skills"
mkdir -p "$INSTALL_DIR/logs"

# Copy app files
echo "📂 Copying files..."
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR"
cp -R "$SCRIPT_DIR/engine" "$APP_DIR/"
cp -R "$SCRIPT_DIR/onboarding" "$APP_DIR/"
cp -R "$SCRIPT_DIR/sdk-bridge" "$APP_DIR/" 2>/dev/null || true
cp "$SCRIPT_DIR/app.py" "$APP_DIR/"
cp "$SCRIPT_DIR/import_brain.py" "$APP_DIR/" 2>/dev/null || true
cp "$SCRIPT_DIR/requirements.txt" "$APP_DIR/"

# Check Python
echo "🐍 Checking Python..."
if command -v python3 &> /dev/null; then
    PY=$(python3 --version)
    echo "   Found: $PY"
else
    echo "❌ Python 3 not found. Please install Python from python.org"
    echo "   Press Enter to exit..."
    read
    exit 1
fi

# Install Python dependencies
echo "📚 Installing dependencies (this may take a minute)..."
pip3 install --quiet --break-system-packages \
    python-telegram-bot \
    google-genai \
    anthropic \
    pytz \
    rumps 2>/dev/null || \
pip3 install --quiet \
    python-telegram-bot \
    google-genai \
    anthropic \
    pytz \
    rumps

echo "✅ Python dependencies installed!"

# Set up SDK Bridge (for Claude Pro/Max users — enables multi-turn AI sessions)
if [ -d "$APP_DIR/sdk-bridge" ]; then
    if command -v node &> /dev/null; then
        NODE_V=$(node --version)
        echo "🔗 Setting up SDK Bridge (Node.js $NODE_V found)..."
        cd "$APP_DIR/sdk-bridge"
        npm install --silent 2>/dev/null || npm install 2>/dev/null
        echo "   SDK Bridge ready (enables multi-turn Claude sessions)"
    else
        echo "ℹ️  Node.js not found — SDK Bridge skipped (optional)"
        echo "   Install Node.js from nodejs.org for enhanced Claude experience"
    fi
fi

# Create launcher script that starts both bot and SDK bridge
cat > "$INSTALL_DIR/start.command" << 'LAUNCHER'
#!/bin/bash
APP_DIR="$HOME/.kiyomi/app"

# Start SDK Bridge in background if available
if [ -d "$APP_DIR/sdk-bridge" ] && command -v node &> /dev/null; then
    # Kill any existing bridge
    lsof -ti :3456 2>/dev/null | xargs kill -9 2>/dev/null || true
    cd "$APP_DIR/sdk-bridge"
    node server.js > "$HOME/.kiyomi/logs/sdk-bridge.log" 2>&1 &
    echo "🔗 SDK Bridge started on port 3456"
    sleep 1
fi

cd "$APP_DIR"
python3 app.py
LAUNCHER
chmod +x "$INSTALL_DIR/start.command"

echo ""
echo "✅ Installation complete!"
echo ""

# Start SDK Bridge in background
if [ -d "$APP_DIR/sdk-bridge" ] && command -v node &> /dev/null; then
    lsof -ti :3456 2>/dev/null | xargs kill -9 2>/dev/null || true
    cd "$APP_DIR/sdk-bridge"
    node server.js > "$INSTALL_DIR/logs/sdk-bridge.log" 2>&1 &
    echo "🔗 SDK Bridge started"
    sleep 1
fi

# Check if config exists (returning user)
if [ -f "$INSTALL_DIR/config.json" ]; then
    echo "✅ Existing config found! Starting Kiyomi..."
    echo ""
    cd "$APP_DIR"
    python3 app.py &
    sleep 3
    echo "🌸 Kiyomi is running!"
    echo "   Open Telegram to chat with her."
    echo ""
    echo "   To stop: Close this terminal window"
    echo "   To start again: Double-click ~/.kiyomi/start.command"
else
    echo "   Opening setup wizard in your browser..."
    echo ""
    cd "$APP_DIR"
    python3 app.py &
    sleep 4
    open "http://127.0.0.1:8765/index.html" 2>/dev/null || true
    echo "   If the browser didn't open, go to: http://127.0.0.1:8765"
    echo ""
    echo "   Keep this window open while Kiyomi is running."
    echo "   To stop: Close this terminal window"
fi

# Wait for user
echo ""
echo "Press Ctrl+C or close this window to stop Kiyomi."
wait
