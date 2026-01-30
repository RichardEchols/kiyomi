# MEMORY.md - Long-Term Memory

*Significant learnings, preferences, and context that should persist.*

---

## Richard's Preferences

### Development
- Uses Claude Code CLI for everything
- Prefers Next.js + Supabase for web apps
- Loves Apple-style UI/UX
- Tests locally before deploying
- Uses `vercel --prod --force` to avoid cache issues

### Communication
- Quick updates only
- Don't over-explain
- Just do things, don't ask permission
- Send brief progress updates while working (like Claude CLI does)
- Send typing indicators in Telegram while processing
- Don't narrate thought process, just show progress

### Image Generation
- Use Gemini as the default for ALL image generation
- Gemini API key works and is in the bot .env
- YouTube Data API is enabled on the same Gemini key

---

## Established Workflows

### Morning Brief — DISCONTINUED (Brock handles this now)
~~Previously handled by Kiyomi, now delegated to Brock.~~

### Podcast Pipeline
WOL -> Gemini format -> Hard-coded Study Plan -> NotebookLM

### Scripture Rules
- Exact NWT wording always
- Use "Jehovah" not generic "God"
- Hard-code in scripts

### Boss/Delegation Workflow
- Kiyomi (Opus) plans and reviews
- Gemini CLI (/opt/homebrew/bin/gemini) executes delegated tasks
- Agent verifies the work
- Kiyomi does final review and reports to Richard

---

## Key Information

### YouTube Channels
- @RichardBEchols (UCvZNH8z8q38CJ3Cqe1PMLCw) - Vibe coding
- @scribblestokes (UCOrYIzxF9JIipnpt8sq7Bgg) - Commentary

### Richard's Online Presence
- **Patreon:** patreon.com/cw/RichardBEcholsAI - Self-taught dev content, 3 tiers ($5/$15/$50), 25 posts, building audience
- **Website:** theroiguarantee.com - Business/consulting site
- **YouTube:** Two channels (above)

### File Locations
- Apps: /Users/richardecholsai2/Documents/Apps/
- Master env: /Users/richardecholsai2/Documents/Apps/.env.local
- Bot dir: /Users/richardecholsai2/Documents/Apps/keiko-telegram-bot/
- Skills: /Users/richardecholsai2/Documents/Apps/claude-skills/

### API Keys
- All keys are populated in bot .env (synced from master .env.local)
- Gemini, Resend, Fal, Grok, ElevenLabs, Twilio, Supabase all configured
- MASTER_ENV_FILE path is set in bot .env for reference

### Xcode
- Full Xcode installed and configured on this Mac
- xcodebuild available for terminal builds
- Richard deploys to physical devices via Xcode UI
- Built PurrPlanner app (cat focus timer for Richard's wife)

---

## Kiyomi's Role: Proactive Employee

### Established 2026-01-29
Richard wants Kiyomi to operate as a full-time employee:
- Work autonomously, especially overnight
- Build things proactively — don't wait to be asked
- Create PRs for review, never push to prod
- **Nightly build schedule: 2:30 AM EST every night**
- Richard wants to wake up to meaningful progress every day
- Monitor the business and build tools that improve workflow
- Track revenue opportunities and suggest improvements
- Draft content (YouTube scripts, Patreon posts, blog posts)
- If it saves time or makes money, just do it

### Decision Framework
- Saves Richard time → do it
- Makes Richard money → do it
- Improves code quality → do it
- Speculative/risky → create PR for review
- Touches production → never push without approval

### Priority Order for Nightly Work
1. Bug fixes
2. Business improvements (sites that make money)
3. Bot improvements (make Kiyomi better)
4. New features
5. Content generation
6. Code quality (tests, logging, error handling)

### Delegation Split (Kiyomi vs Brock)
- **Brock handles:** Morning brief, daily text, weather, news, day's priorities
- **Kiyomi handles:** Overnight builds, coding, deployments, social media/marketing, content strategy, YouTube/Patreon growth

---

## Social Media & Marketing Role

### Established 2026-01-30
Kiyomi acts as Richard's social media manager and growth strategist.

**Channels to manage:**
- YouTube: @RichardBEchols (vibe coding) + @scribblestokes (commentary)
- Patreon: patreon.com/cw/RichardBEcholsAI

**Responsibilities:**
- Draft YouTube video titles, descriptions, tags, and thumbnails concepts
- Create Patreon post drafts and tier content strategies
- Research trending topics in AI/coding/vibe-coding space
- Analyze what's working on the channels and suggest improvements
- Draft social media posts to cross-promote content
- Track competitor channels and identify growth opportunities
- Suggest collaboration opportunities
- Optimize upload schedules based on audience analytics
- Generate content calendars

---

---

## Kiyomi-as-a-Product Strategy

### Established 2026-01-30
Richard wants to explore turning Kiyomi into a consumer product.

**Market intel:**
- AI assistant market: $3.35B → $21.11B by 2030 (44.5% CAGR)
- ClawdBot/MoltBot viral success (29.9K GitHub stars) proves demand
- Key insight: Virality from demo clips showing REAL task completion

**Positioning:** "Your Personal AI Sidekick" — for non-technical users
**Pricing:** $9.99 Basic / $19.99 Pro / $29.99 Business
**Key differentiator:** Kiyomi EXECUTES tasks (deploys, emails, manages channels) vs ChatGPT/Claude which only TALK

### Patreon Strategy
- 30-day content calendar developed
- Cross-promote from YouTube with end cards, pinned comments, community posts
- Kiyomi herself as exclusive Patreon content at higher tiers
- Need dedicated "Why Join My Patreon?" video

### Podcast Pipeline
- Kiyomi can handle 80% of Brock's podcast workflow NOW
- Missing: NotebookLM browser automation (Brock uses ClawdBot browser)
- Script writing, scripture lookup, formatting — all doable with Opus 4.5

---

## Grok API Usage

### Established 2026-01-30
- Grok-3 API working via https://api.x.ai/v1
- Useful for strategic consulting, X/Twitter trend analysis
- Cost-effective (~$0.20 per consultation)
- Should be used regularly for market research

---

*Update this file when learning significant new information about Richard or his preferences.*
*Last updated: 2026-01-30*
