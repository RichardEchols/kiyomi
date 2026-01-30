#!/bin/bash
set -e

echo "🦊 Installing Keiko..."

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Create directories if they don't exist
echo "Creating directories..."
mkdir -p logs memory workspace

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

# Install dependencies
echo "Installing Python dependencies..."
pip3 install -r requirements.txt

# Make bot.py executable
chmod +x bot.py

# Create/update launchd plist
PLIST_NAME="com.richardechols.keiko.plist"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "Creating launchd daemon..."
cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.richardechols.keiko</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Library/Frameworks/Python.framework/Versions/3.13/bin/python3</string>
        <string>$SCRIPT_DIR/bot.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$SCRIPT_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$SCRIPT_DIR/logs/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>$SCRIPT_DIR/logs/stderr.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
    </dict>
</dict>
</plist>
EOF

# Unload if already loaded
launchctl unload "$PLIST_PATH" 2>/dev/null || true

# Load the daemon
echo "Loading daemon..."
launchctl load "$PLIST_PATH"

echo ""
echo "✅ Keiko is installed and running!"
echo ""
echo "Commands:"
echo "  Check status:    launchctl list | grep keiko"
echo "  View logs:       tail -f $SCRIPT_DIR/logs/bot.log"
echo "  View stdout:     tail -f $SCRIPT_DIR/logs/stdout.log"
echo "  View stderr:     tail -f $SCRIPT_DIR/logs/stderr.log"
echo "  Stop:            launchctl unload ~/Library/LaunchAgents/com.richardechols.keiko.plist"
echo "  Restart:         launchctl kickstart -k gui/\$(id -u)/com.richardechols.keiko"
echo ""
echo "🦊 Keiko is now your 24/7 assistant!"
