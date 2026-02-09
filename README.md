# Kiyomi v5.0

**Your AI subscription, supercharged.**

Kiyomi turns your existing AI subscription (Claude, ChatGPT, or Gemini) into a personalized assistant that lives in Telegram. Pick a preset, customize it in plain English, and chat from anywhere.

## Install

Download the DMG from [kiyomibot.ai](https://kiyomibot.ai).

Or install via command line:

```bash
curl -fsSL https://kiyomibot.ai/install.sh | bash
```

## How It Works

Kiyomi is a bridge between Telegram and your AI CLI tool. It runs on your Mac as a menu bar app, forwarding your Telegram messages to whichever AI CLI you choose (Claude CLI, Codex CLI, or Gemini CLI), then sending the response back.

Your AI's full capabilities — web search, code execution, file creation, research — come directly from the CLI you pick. Kiyomi adds Telegram integration, identity presets, session persistence, scheduled messages, photo analysis, and file delivery on top.

## Features

- **Multi-CLI Bridge** — Supports Claude CLI, Codex CLI (ChatGPT), and Gemini CLI. Switch anytime with `/cli`.
- **6 Industry Presets** — Personal Assistant, Law Firm, Crypto Trader, Student, Small Business, and Customer Service. Or write your own from scratch.
- **Self-Modifying Identity** — Tell your assistant to change its personality or add capabilities in plain English. It updates its own identity file (`~/.kiyomi/identity.md`).
- **Telegram Integration** — Chat with your AI from your phone, desktop, or any device with Telegram.
- **Session Persistence** — Conversations maintain context across messages. Use `/reset` to start fresh.
- **Scheduled Messages (Cron)** — Set up recurring prompts (morning briefings, reminders, check-ins) via `~/.kiyomi/cron.json`.
- **Photo Analysis** — Send any photo and get instant analysis (powered by whatever vision capabilities your CLI supports).
- **File Delivery** — When the AI creates files (documents, code, images), they are automatically sent back to you in Telegram.
- **Auto-Updates** — Kiyomi checks GitHub Releases for new versions and can update itself via `/update`.
- **Menu Bar App** — Runs quietly in your macOS menu bar. Open Telegram, view settings, or check status from the menu.

## Quick Start

1. Install with the DMG or command above
2. Enter your name and pick a preset (or write your own)
3. Select your AI provider (Gemini is free with a Google account)
4. Create a Telegram bot via @BotFather and paste the token
5. Open Telegram and start chatting

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/start` | Initialize the bot and see tips |
| `/reset` | Clear conversation context |
| `/cli` | View or switch AI provider |
| `/cli gemini` | Switch to a specific provider |
| `/identity` | View your assistant's personality file |
| `/update` | Check for and install updates |

## Architecture

```
Telegram <-> Kiyomi (macOS) <-> AI CLI (Claude/Codex/Gemini)
                |
          identity.md (personality)
          config.json (settings)
          sessions.json (conversation state)
          cron.json (scheduled messages)
```

All configuration lives in `~/.kiyomi/`. The identity file is synced to the appropriate CLI format (CLAUDE.md, AGENTS.md, or GEMINI.md) before each message.

## Requirements

- macOS 12+ (Apple Silicon or Intel)
- Python 3.10+ (for command-line install) or just the DMG (bundles everything)
- A Telegram account
- At least one AI CLI installed: Claude CLI, Codex CLI, or Gemini CLI

## Data & Privacy

- **Config and identity** are stored locally at `~/.kiyomi/`
- **Messages** are sent to Telegram's servers (inherent to using Telegram) and processed by your chosen AI provider (Anthropic, OpenAI, or Google)
- **No Kiyomi servers** — there is no RMDW backend collecting your data
- **No telemetry** — Kiyomi does not phone home (except for update checks against the public GitHub Releases API)

## License

Proprietary -- (c) 2026 RMDW LLC. All rights reserved.
