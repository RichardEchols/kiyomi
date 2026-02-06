#!/bin/bash
# Kiyomi Bot — Installer for CLI Distribution
# Run this from inside the extracted Kiyomi zip folder
set -euo pipefail

KIYOMI_DIR="$HOME/.kiyomi"
KIYOMI_APP="$KIYOMI_DIR/app"
KIYOMI_VENV="$KIYOMI_DIR/venv"
KIYOMI_CONFIG="$KIYOMI_DIR/config.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

print_banner() {
  echo ""
  echo -e "${CYAN}${BOLD}"
  echo "  🌸 Kiyomi Bot Installer v3.0.0"
  echo "  The AI That Actually Remembers You"
  echo -e "${NC}"
  echo ""
}

info()  { echo -e "${BLUE}▸${NC} $1"; }
ok()    { echo -e "${GREEN}✓${NC} $1"; }
fail()  { echo -e "${RED}✗${NC} $1"; exit 1; }
warn()  { echo -e "${YELLOW}⚠${NC} $1"; }
ask()   { echo -ne "${CYAN}?${NC} $1: "; read -r REPLY; }

# ─── Preflight ─────────────────────────────────────────────
print_banner

# macOS only
[[ "$(uname)" == "Darwin" ]] || fail "Kiyomi only runs on macOS right now."

# Check we're in the right directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -f "$SCRIPT_DIR/app.py" ]] || [[ ! -d "$SCRIPT_DIR/engine" ]]; then
  fail "Please run this script from inside the extracted Kiyomi folder (where app.py is located)."
fi
ok "Installation package found"

# Python 3.10+
if ! command -v python3 &>/dev/null; then
  fail "Python 3 not found. Install it: brew install python3"
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if [[ "$PY_MAJOR" -lt 3 ]] || [[ "$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 10 ]]; then
  fail "Python 3.10+ required (found $PY_VERSION). Run: brew install python3"
fi
ok "Python $PY_VERSION"

# ─── License Validation ─────────────────────────────────────
echo ""
echo -e "${BOLD}🔑 License Validation${NC}"
echo ""

# Check if license already exists
LICENSE_FILE="$HOME/.kiyomi/license.json"
NEED_LICENSE=true

if [[ -f "$LICENSE_FILE" ]]; then
  info "Found existing license file..."
  
  # Try to validate existing license
  cd "$SCRIPT_DIR"
  if python3 -c "
import sys, os
sys.path.insert(0, os.path.join('engine'))
from license import check_license
import sys
if check_license():
    sys.exit(0)
else:
    sys.exit(1)
" 2>/dev/null; then
    ok "Existing license is valid"
    NEED_LICENSE=false
  else
    warn "Existing license is invalid or expired"
    rm -f "$LICENSE_FILE" 2>/dev/null || true
  fi
fi

if [[ "$NEED_LICENSE" == "true" ]]; then
  echo ""
  echo "  To use Kiyomi, you need a valid license key."
  echo "  Purchase one at: https://kiyomibot.ai"
  echo ""
  
  while true; do
    ask "Enter your license key"
    LICENSE_KEY="$REPLY"
    
    if [[ -z "$LICENSE_KEY" ]]; then
      echo -e "${RED}  Please enter a valid license key${NC}"
      continue
    fi
    
    info "Validating license key..."
    
    # Create temporary license validator
    cat > "$SCRIPT_DIR/temp_license_check.py" << 'TEMP_LICENSE'
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'engine'))

# Mock input for check_license function
import builtins
original_input = builtins.input

def mock_input(prompt):
    return sys.argv[1]

builtins.input = mock_input

try:
    from license import check_license
    if check_license():
        print("SUCCESS")
        sys.exit(0)
    else:
        print("FAILED")
        sys.exit(1)
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
finally:
    builtins.input = original_input
TEMP_LICENSE
    
    # Run validation
    cd "$SCRIPT_DIR"
    if python3 temp_license_check.py "$LICENSE_KEY" 2>/dev/null | grep -q "SUCCESS"; then
      rm -f temp_license_check.py
      ok "License validated successfully!"
      break
    else
      rm -f temp_license_check.py
      echo -e "${RED}  License validation failed. Please check your key and try again.${NC}"
      echo ""
    fi
  done
fi

# ─── Install ──────────────────────────────────────────────
info "Installing to $KIYOMI_DIR..."
mkdir -p "$KIYOMI_DIR"
mkdir -p "$KIYOMI_DIR/memory"
mkdir -p "$KIYOMI_DIR/skills"
mkdir -p "$KIYOMI_DIR/logs"

# Copy application files
info "Copying application files..."
rm -rf "$KIYOMI_APP"
mkdir -p "$KIYOMI_APP"

cp -R "$SCRIPT_DIR/engine" "$KIYOMI_APP/"
cp -R "$SCRIPT_DIR/onboarding" "$KIYOMI_APP/"
cp "$SCRIPT_DIR/app.py" "$KIYOMI_APP/"
cp "$SCRIPT_DIR/requirements.txt" "$KIYOMI_APP/"

# Copy optional files if they exist
[[ -f "$SCRIPT_DIR/import_brain.py" ]] && cp "$SCRIPT_DIR/import_brain.py" "$KIYOMI_APP/" || true

ok "Application files copied"

# Python venv
info "Setting up Python environment..."
if [[ ! -d "$KIYOMI_VENV" ]]; then
  python3 -m venv "$KIYOMI_VENV"
fi
source "$KIYOMI_VENV/bin/activate"

# Install deps
if [[ -f "$KIYOMI_APP/requirements.txt" ]]; then
  pip install --quiet --upgrade pip
  pip install --quiet -r "$KIYOMI_APP/requirements.txt"
fi
ok "Dependencies installed"

# ─── Setup ────────────────────────────────────────────────
if [[ ! -f "$KIYOMI_CONFIG" ]]; then
  echo ""
  echo -e "${BOLD}Let's set up Kiyomi!${NC}"
  echo ""

  ask "Your name"
  USER_NAME="$REPLY"

  ask "Bot name (default: Kiyomi)"
  BOT_NAME="${REPLY:-Kiyomi}"

  echo ""
  echo "  Which AI provider? (Gemini is free!)"
  echo "  1) Gemini (recommended — free tier)"
  echo "  2) Claude (Anthropic)"
  echo "  3) OpenAI (GPT)"
  echo ""
  ask "Pick 1-3 (default: 1)"
  PROVIDER_CHOICE="${REPLY:-1}"

  case "$PROVIDER_CHOICE" in
    2) PROVIDER="anthropic"; MODEL="claude-sonnet-4-20250514" ;;
    3) PROVIDER="openai";    MODEL="gpt-4o" ;;
    *)  PROVIDER="gemini";    MODEL="gemini-2.0-flash" ;;
  esac

  API_KEY=""
  if [[ "$PROVIDER" == "gemini" ]]; then
    echo ""
    echo "  Get a free Gemini API key: https://aistudio.google.com/apikey"
    ask "Gemini API key"
    API_KEY="$REPLY"
  elif [[ "$PROVIDER" == "anthropic" ]]; then
    ask "Anthropic API key"
    API_KEY="$REPLY"
  elif [[ "$PROVIDER" == "openai" ]]; then
    ask "OpenAI API key"
    API_KEY="$REPLY"
  fi

  echo ""
  echo "  Telegram lets Kiyomi message you on your phone."
  echo "  Create a bot: talk to @BotFather on Telegram → /newbot"
  ask "Telegram bot token (or press Enter to skip)"
  BOT_TOKEN="$REPLY"

  # Write config
  GEMINI_KEY=""; ANTHROPIC_KEY=""; OPENAI_KEY=""
  case "$PROVIDER" in
    gemini)    GEMINI_KEY="$API_KEY" ;;
    anthropic) ANTHROPIC_KEY="$API_KEY" ;;
    openai)    OPENAI_KEY="$API_KEY" ;;
  esac

  cat > "$KIYOMI_CONFIG" << CONF
{
  "name": "$USER_NAME",
  "bot_name": "$BOT_NAME",
  "provider": "$PROVIDER",
  "model": "$MODEL",
  "gemini_key": "$GEMINI_KEY",
  "anthropic_key": "$ANTHROPIC_KEY",
  "openai_key": "$OPENAI_KEY",
  "bot_token": "$BOT_TOKEN",
  "telegram_token": "$BOT_TOKEN",
  "telegram_user_id": "",
  "setup_complete": true,
  "imported_chats": false,
  "timezone": "$(readlink /etc/localtime | sed 's|.*/zoneinfo/||')"
}
CONF
  ok "Config saved to $KIYOMI_CONFIG"
else
  ok "Config already exists"
fi

# ─── Launch script ────────────────────────────────────────
LAUNCH_SCRIPT="$KIYOMI_DIR/start.sh"
cat > "$LAUNCH_SCRIPT" << 'LAUNCH'
#!/bin/bash
source "$HOME/.kiyomi/venv/bin/activate"
cd "$HOME/.kiyomi/app"
python app.py
LAUNCH
chmod +x "$LAUNCH_SCRIPT"

# Create simple start command file
LAUNCH_COMMAND="$KIYOMI_DIR/start.command"
cat > "$LAUNCH_COMMAND" << 'COMMAND'
#!/bin/bash
cd "$HOME/.kiyomi/app"
python app.py
COMMAND
chmod +x "$LAUNCH_COMMAND"

# Shell alias
SHELL_RC="$HOME/.zshrc"
[[ "$(basename "$SHELL")" == "bash" ]] && SHELL_RC="$HOME/.bashrc"
if ! grep -q "alias kiyomi=" "$SHELL_RC" 2>/dev/null; then
  echo '' >> "$SHELL_RC"
  echo '# Kiyomi Bot' >> "$SHELL_RC"
  echo 'alias kiyomi="$HOME/.kiyomi/start.sh"' >> "$SHELL_RC"
  ok "Added 'kiyomi' command to your shell"
fi

# ─── Done ─────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}  🌸 Kiyomi is installed!${NC}"
echo ""
echo "  Start Kiyomi:"
echo -e "    ${CYAN}Double-click: ~/.kiyomi/start.command${NC}"
echo -e "    ${CYAN}Terminal: kiyomi${NC}  (open a new terminal first)"
echo ""
echo "  Or run directly:"
echo -e "    ${CYAN}~/.kiyomi/start.sh${NC}"
echo ""
echo "  Config: ~/.kiyomi/config.json"
echo "  License: ~/.kiyomi/license.json"
echo ""
echo -e "  ${BOLD}Kiyomi remembers. Always. 🌸${NC}"
echo ""