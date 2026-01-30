# Keiko Product Roadmap

*Plan for turning Keiko into a sellable product on Gumroad.*

---

## Product Vision

**Keiko - Your 24/7 AI Development Employee**

An autonomous AI assistant that works while you sleep. Deploy apps, monitor sites, fix bugs, manage git, spawn worker agents - all from Telegram.

---

## Target Audience

1. **Solo Developers** - Need an extra pair of hands, can't afford to hire
2. **Small Agencies** - Managing multiple client projects
3. **Indie Hackers** - Building side projects, limited time
4. **Technical Founders** - Want to focus on product, not ops

---

## Pricing Strategy

### Recommended Tiers

| Tier | Price | Includes |
|------|-------|----------|
| **Starter** | $49 | Core bot, self-setup, community support |
| **Pro** | $99 | Full features, skill packs, email support |
| **Business** | $199 | Multi-user, priority support, custom onboarding |

### Alternative: Single Tier
- **$79 one-time** - Everything included
- Early bird: **$49** (first 100 buyers)

### Why One-Time Works
- Users pay their own Claude API costs
- No recurring revenue burden on seller
- High perceived value vs subscriptions
- "Pay once, own forever" is attractive

---

## Feature Comparison (For Sale)

### Core Features (All Tiers)

| Feature | Description |
|---------|-------------|
| Telegram Bot | Main interface, always available |
| Claude Code Execution | Run any task via Claude CLI |
| Memory System | Remembers everything, learns preferences |
| Project Registry | Knows your apps, paths, deploy commands |
| Smart Deployment | Build → Deploy → Verify workflow |
| Git Integration | Auto-commit, push, rollback |
| Site Monitoring | Hourly health checks, downtime alerts |
| Sub-Agent Spawning | Background workers for parallel tasks |
| Morning Brief | Daily summary with weather, tasks, news |
| Reminders | Natural language scheduling |
| Skills System | Loadable skill files for specific tasks |
| Voice Responses | TTS via ElevenLabs (optional) |
| Image Analysis | Fix bugs from screenshots |

### Pro Features

| Feature | Description |
|---------|-------------|
| Swarm Intelligence | Auto-spawn coordinated agent teams |
| Self-Update | "Add this feature to yourself" |
| Email Integration | Check/summarize inbox via Gmail |
| Calendar Integration | Check schedule, add events |
| Advanced Analytics | Weekly reports, cost tracking |
| Priority Escalation | Smart filtering of what needs attention |
| Skill Pack | 20+ pre-built skills for common tasks |

### Business Features

| Feature | Description |
|---------|-------------|
| Multi-User | Team access with permissions |
| Slack/Discord | Alternative to Telegram |
| Custom Onboarding | 1-hour setup call |
| Priority Support | 24-hour response time |
| Custom Skills | We build skills for your workflow |

---

## What Needs to Be Built for Sale

### Must-Have (MVP)

| Item | Status | Notes |
|------|--------|-------|
| Setup Wizard | Not started | User enters API keys, configures bot |
| Documentation | Not started | README, setup guide, feature docs |
| Swarm Intelligence | Not started | Auto-spawn, coordinate, aggregate |
| Self-Update | Not started | Bot modifies own code safely |
| Config Externalization | Not started | Remove hardcoded paths/values |
| Cost Tracking | Not started | Track API usage, set alerts |
| Backup/Export | Not started | Export memory and settings |

### Nice-to-Have (Post-MVP)

| Item | Status | Notes |
|------|--------|-------|
| Email Integration | Not started | Gmail API |
| Calendar Integration | Not started | Google Calendar API |
| Web Dashboard | Not started | Settings, logs, analytics |
| Slack Support | Not started | Alternative interface |
| Discord Support | Not started | Alternative interface |
| Plugin Marketplace | Not started | Community skills |

---

## Setup Wizard Flow (For Buyers)

```
1. Clone repo
2. Run setup script
3. Wizard asks for:
   - Telegram Bot Token (from BotFather)
   - Claude API Key (from Anthropic)
   - Allowed User IDs (Telegram)
   - Timezone
   - Optional: ElevenLabs API Key
   - Optional: Gmail credentials
   - Optional: Google Calendar credentials
4. Wizard creates config file
5. Wizard creates launchd plist (Mac) or systemd service (Linux)
6. Bot starts and sends welcome message
```

---

## Documentation Structure

```
docs/
├── README.md           # Quick start
├── SETUP.md            # Detailed setup guide
├── FEATURES.md         # Full feature documentation
├── COMMANDS.md         # All commands reference
├── SKILLS.md           # How to create/use skills
├── CUSTOMIZATION.md    # How to customize behavior
├── TROUBLESHOOTING.md  # Common issues and fixes
└── API_COSTS.md        # Expected API usage/costs
```

---

## Marketing Copy

### Headline
**Your AI Employee That Never Sleeps**

### Subheadline
Deploy apps, fix bugs, monitor sites, manage git - all from Telegram. One-time purchase, works 24/7.

### Key Benefits
- 🚀 **Deploy in seconds** - "deploy my-app" and it's live
- 🔍 **Fix bugs from screenshots** - Send an error, get a fix
- 📊 **Always monitoring** - Know immediately when sites go down
- 🧠 **Learns your workflow** - Gets smarter over time
- 👥 **Spawns workers** - Parallelizes big tasks automatically
- 🌙 **Works while you sleep** - Wake up to completed tasks

### Social Proof (To Collect)
- "Saved me 10 hours a week"
- "Like having a junior dev on call 24/7"
- "Paid for itself in the first week"

---

## Launch Plan

### Phase 1: Polish (Current)
- Complete all features for Richard
- Test extensively
- Document everything

### Phase 2: Externalize
- Remove hardcoded values
- Create setup wizard
- Write documentation

### Phase 3: Beta
- 10-20 beta testers
- Collect feedback
- Fix issues

### Phase 4: Launch
- Gumroad listing
- Twitter/X announcement
- Product Hunt launch
- YouTube demo video

---

## Revenue Projections

### Conservative (50 sales in year 1)
- $79 × 50 = **$3,950**

### Moderate (200 sales in year 1)
- $79 × 200 = **$15,800**

### Optimistic (500 sales in year 1)
- $79 × 500 = **$39,500**

### With Tiers (200 sales, mixed)
- 100 × $49 (Starter) = $4,900
- 80 × $99 (Pro) = $7,920
- 20 × $199 (Business) = $3,980
- **Total: $16,800**

---

## Competitive Landscape

| Product | Price | Difference |
|---------|-------|------------|
| ClawdBot | ~$30-50 | Keiko has more automation |
| n8n | Free/Self-hosted | Keiko is AI-native |
| Zapier | $20+/mo | Keiko is one-time, AI-powered |
| Custom dev | $50+/hr | Keiko is instant |

**Keiko's Moat:**
- Truly autonomous (not just triggered workflows)
- Self-improving (learns preferences)
- Developer-focused (understands code, git, deploys)
- Spawns workers (parallel execution)

---

## Post-Launch Opportunities

1. **Skill Packs** - $19-29 each
   - E-commerce pack
   - Content creator pack
   - Agency pack

2. **Done-For-You Setup** - $99-199
   - We configure it for you

3. **Custom Skills** - $49-99 each
   - Build specific skills for customers

4. **Keiko Pro (SaaS)** - $29/mo
   - Hosted version, no setup required
   - Higher margin, recurring revenue

---

*Last updated: 2026-01-28*
