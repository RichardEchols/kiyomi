"""
Kiyomi Configuration - All credentials and settings
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================
# TELEGRAM
# ============================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8549475880:AAFGvXc3sP9XmzuYYZt6R-wKdAjwWGuaTok")
ALLOWED_USER_IDS = [8295554376]  # ONLY Richard

# ============================================
# RICHARD'S CONTACT INFO
# ============================================
RICHARD_EMAIL = "richardbechols92@gmail.com"
RICHARD_PHONE = "+14045529941"
TIMEZONE = "America/New_York"

# ============================================
# BOT EMAIL (Gmail)
# ============================================
BOT_EMAIL = "richardecholsai@gmail.com"
BOT_EMAIL_PASSWORD = os.getenv("BOT_EMAIL_PASSWORD")

# ============================================
# TWILIO (SMS)
# ============================================
TWILIO_PHONE = "+18559394918"
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "ACa5efe19dc73b88d9d54e4aa904b2b095")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

# ============================================
# API KEYS
# ============================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
FAL_API_KEY = os.getenv("FAL_KEY")
GROK_API_KEY = os.getenv("GROK_API_KEY")
GROK_API_BASE = "https://api.x.ai/v1"
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_RICK = "jK2hyA4zXCYkb4uxC8VS"
ELEVENLABS_VOICE_RICHARD = "lzZ0ATDHnN7wEsC4KSxt"

# ============================================
# SUPABASE
# ============================================
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://dtfhraicexuerdxxybpo.supabase.co")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# ============================================
# YOUTUBE CHANNELS
# ============================================
YOUTUBE_RICHARDBECHOLS = "UCvZNH8z8q38CJ3Cqe1PMLCw"  # Vibe coding
YOUTUBE_SCRIBBLESTOKES = "UCOrYIzxF9JIipnpt8sq7Bgg"  # Commentary

# ============================================
# PATHS
# ============================================
BASE_DIR = Path(__file__).parent
WORKSPACE_DIR = BASE_DIR / "workspace"
MEMORY_DIR = BASE_DIR / "memory"
LOGS_DIR = BASE_DIR / "logs"

# Workspace files
IDENTITY_FILE = WORKSPACE_DIR / "IDENTITY.md"
SOUL_FILE = WORKSPACE_DIR / "SOUL.md"
USER_FILE = WORKSPACE_DIR / "USER.md"
MEMORY_FILE = WORKSPACE_DIR / "MEMORY.md"
COMMITMENTS_FILE = WORKSPACE_DIR / "COMMITMENTS.md"
HEARTBEAT_FILE = WORKSPACE_DIR / "HEARTBEAT.md"
TOOLS_FILE = WORKSPACE_DIR / "TOOLS.md"

# Richard's directories (allowed access)
ALLOWED_DIRECTORIES = [
    "/Users/richardecholsai2/Apps/",
    "/Users/richardecholsai2/Desktop/Work/",
    "/Users/richardecholsai2/Documents/",
    "/Users/richardecholsai2/Downloads/",
]

# ============================================
# SCHEDULE
# ============================================
HEARTBEAT_INTERVAL_MINUTES = 30
MORNING_BRIEF_HOUR = 8
MORNING_BRIEF_MINUTE = 30
QUIET_HOURS_START = 23  # 11 PM
QUIET_HOURS_END = 8     # 8 AM


# ============================================
# NIGHTLY WORK
# ============================================
NIGHTLY_WORK_HOUR = 1      # 1 AM
NIGHTLY_WORK_MINUTE = 0
NIGHTLY_WORK_ENABLED = True

# ============================================
# CLAUDE CLI
# ============================================
CLAUDE_CLI_PATH = "/opt/homebrew/bin/claude"
SKILLS_DIR = "/Users/richardecholsai2/kiyomi/skills"
MASTER_ENV_FILE = None
APPS_DIR = "/Users/richardecholsai2/projects"

# ============================================
# KIYOMI IDENTITY
# ============================================
BOT_NAME = "Kiyomi"
BOT_EMOJI = "🌸"
