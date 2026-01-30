#!/bin/bash
# Keiko Mac Mini Update Script

echo "Updating Keiko on Mac Mini..."

cd /Users/richardecholsai2/Documents/Apps

echo "Removing old version..."
rm -rf keiko-telegram-bot

echo "Cloning from GitHub..."
git clone https://github.com/RichardEchols/keiko-telegram-bot.git

cd keiko-telegram-bot

echo "Installing requirements..."
pip3 install -r requirements.txt

echo "Creating logs directory..."
mkdir -p logs

echo "Stopping old Keiko..."
launchctl unload ~/Library/LaunchAgents/com.richardechols.keiko.plist 2>/dev/null

echo "Installing new plist..."
cp com.richardechols.keiko.macmini.plist ~/Library/LaunchAgents/com.richardechols.keiko.plist

echo "Starting Keiko..."
launchctl load ~/Library/LaunchAgents/com.richardechols.keiko.plist

echo ""
echo "Done! Keiko is updated and running."
