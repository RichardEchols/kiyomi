# Mac Mini Headless Server Setup

Complete guide to running Keiko 24/7 on a Mac Mini.

---

## 1. System Settings (GUI)

### Energy Settings
```
System Settings → Energy
├── Turn display off after: 1 minute
├── Prevent automatic sleeping when display is off: ✅ ON
├── Wake for network access: ✅ ON
└── Start up automatically after power failure: ✅ ON
```

### Lock Screen
```
System Settings → Lock Screen
├── Start Screen Saver when inactive: Never
├── Turn display off on power adapter: 1 minute
└── Require password after screen saver: OFF
```

### Auto Login
```
System Settings → Users & Groups → Login Options
└── Automatic login: [Your Username]

Note: May need to disable FileVault temporarily
```

### Remote Access
```
System Settings → General → Sharing
├── Remote Login (SSH): ✅ ON
├── Remote Management: ✅ ON (optional, for VNC)
└── File Sharing: ✅ ON (optional)
```

---

## 2. Terminal Commands

Run these in Terminal:

### Prevent Sleep
```bash
# Disable system sleep entirely
sudo pmset -a sleep 0
sudo pmset -a disksleep 0
sudo pmset -a displaysleep 1

# Prevent sleeping when on power
sudo pmset -a powernap 0
sudo pmset -a standby 0
sudo pmset -a autopoweroff 0

# Wake on network activity
sudo pmset -a womp 1

# Restart after freeze
sudo pmset -a restartfreeze 1

# Auto restart after power failure
sudo pmset -a autorestart 1
```

### Verify Settings
```bash
pmset -g
```

### Enable SSH (if not done in GUI)
```bash
sudo systemsetup -setremotelogin on
```

### Set Computer to Never Sleep via Command Line
```bash
sudo systemsetup -setcomputersleep Never
```

### Disable Spotlight Indexing (saves CPU)
```bash
sudo mdutil -a -i off
```

### Keep Mac Awake with Caffeinate (optional backup)
```bash
# Run in background - prevents sleep
caffeinate -s &
```

---

## 3. Keiko Launchd Setup

### Create the plist file
Location: `~/Library/LaunchAgents/com.richardechols.keiko.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.richardechols.keiko</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Library/Frameworks/Python.framework/Versions/3.13/bin/python3</string>
        <string>/Users/richardechols/Apps/keiko-telegram-bot/bot.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/richardechols/Apps/keiko-telegram-bot</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
        <key>Crashed</key>
        <true/>
    </dict>

    <key>ThrottleInterval</key>
    <integer>10</integer>

    <key>StandardOutPath</key>
    <string>/Users/richardechols/Apps/keiko-telegram-bot/logs/stdout.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/richardechols/Apps/keiko-telegram-bot/logs/stderr.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/Users/richardechols/.local/bin:/Library/Frameworks/Python.framework/Versions/3.13/bin:/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
        <key>PYTHONUNBUFFERED</key>
        <string>1</string>
    </dict>

    <key>ProcessType</key>
    <string>Interactive</string>

    <key>LowPriorityIO</key>
    <false/>

    <key>Nice</key>
    <integer>-10</integer>
</dict>
</plist>
```

### Load the service
```bash
launchctl load ~/Library/LaunchAgents/com.richardechols.keiko.plist
```

### Check status
```bash
launchctl list | grep keiko
```

### View logs
```bash
tail -f /Users/richardechols/Apps/keiko-telegram-bot/logs/bot.log
```

---

## 4. SSH Access from Another Machine

### From your main Mac:
```bash
# Add to ~/.ssh/config for easy access
Host keiko-server
    HostName 192.168.x.x  # Your Mac Mini's IP
    User richardechols
    IdentityFile ~/.ssh/id_rsa

# Then just:
ssh keiko-server
```

### Find Mac Mini IP:
```bash
# On Mac Mini:
ipconfig getifaddr en0
```

### Set Static IP (recommended):
```
System Settings → Network → Wi-Fi/Ethernet → Details → TCP/IP
├── Configure IPv4: Manually
├── IP Address: 192.168.1.100 (or similar)
├── Subnet Mask: 255.255.255.0
└── Router: 192.168.1.1 (your router)
```

---

## 5. Monitoring Commands

### Check if Keiko is running:
```bash
pgrep -f "keiko-telegram-bot/bot.py" && echo "Running" || echo "Not running"
```

### Check uptime:
```bash
uptime
```

### Check memory:
```bash
top -l 1 | head -n 10
```

### Check disk:
```bash
df -h
```

### Restart Keiko:
```bash
launchctl unload ~/Library/LaunchAgents/com.richardechols.keiko.plist
launchctl load ~/Library/LaunchAgents/com.richardechols.keiko.plist
```

---

## 6. Troubleshooting

### If Keiko won't start:
```bash
# Check for errors
cat /Users/richardechols/Apps/keiko-telegram-bot/logs/stderr.log

# Check launchd logs
log show --predicate 'subsystem == "com.apple.launchd"' --last 5m | grep keiko

# Try running manually
cd /Users/richardechols/Apps/keiko-telegram-bot
python3 bot.py
```

### If Mac Mini goes to sleep anyway:
```bash
# Check current settings
pmset -g

# Nuclear option - run caffeinate permanently
# Add to your .zshrc or create a launchd job
caffeinate -s -d -i &
```

### If SSH connection drops:
Add to your local `~/.ssh/config`:
```
Host *
    ServerAliveInterval 60
    ServerAliveCountMax 3
```

---

*Last updated: 2026-01-28*
