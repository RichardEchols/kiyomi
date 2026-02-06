#!/bin/bash
# Kiyomi Lite Installer — Double-click to install
# Works on any Mac with Python 3.10+

set -e

clear
echo "🌸 Kiyomi Installer"
echo "==================="
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

# Install dependencies
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

echo "✅ Dependencies installed!"

# License validation
echo "🔑 License validation..."
cd "$APP_DIR"

# Create a simple license checker script
cat > "$APP_DIR/check_license.py" << 'LICENSE_CHECK'
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'engine'))
from license import check_license

if __name__ == "__main__":
    if check_license():
        print("License validated successfully!")
        sys.exit(0)
    else:
        sys.exit(1)
LICENSE_CHECK

# Run license check
if ! python3 check_license.py; then
    echo "❌ License validation failed. Installation cancelled."
    echo "   Press Enter to exit..."
    read
    exit 1
fi

# Clean up temporary script
rm -f "$APP_DIR/check_license.py"

# Create launcher script
cat > "$INSTALL_DIR/start.command" << 'LAUNCHER'
#!/bin/bash
cd "$HOME/.kiyomi/app"
python3 app.py
LAUNCHER
chmod +x "$INSTALL_DIR/start.command"

# Check if config exists (returning user)
if [ -f "$INSTALL_DIR/config.json" ]; then
    echo ""
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
    echo ""
    echo "🌸 Installation complete!"
    echo ""
    echo "   Opening setup wizard in your browser..."
    echo ""
    cd "$APP_DIR"
    python3 app.py &
    sleep 4
    # Open onboarding directly from installer (more reliable than backgrounded Python)
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
