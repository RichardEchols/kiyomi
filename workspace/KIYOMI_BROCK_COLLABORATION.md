# Kiyomi + Brock Collaboration Plan

*Richard's goal: Be the approver, not the doer. We handle everything.*

---

## Who We Are

| | **Kiyomi** (Claude Opus 4.5 — CLI) | **Brock** (ClawdBot — Browser) |
|---|---|---|
| **Strengths** | Code, deploy, file ops, API calls, content writing, strategy | Browser automation, web scraping, NotebookLM, visual tasks |
| **Runs on** | Claude Code CLI (terminal) | Chrome extension + browser |
| **Best at** | Building, shipping, analyzing | Clicking, navigating, form-filling |

---

## Division of Labor

### Brock Owns
- Morning brief (text to Richard)
- Weather, news, day's priorities
- NotebookLM podcast generation (browser-dependent)
- Any task requiring real browser interaction (logins, UI clicks, form submissions)
- YouTube Studio actions (upload, scheduling, thumbnail upload)
- Patreon dashboard actions

### Kiyomi Owns
- All coding and deployments
- Content generation (scripts, posts, descriptions, tags)
- API integrations and automation scripts
- Git operations, PRs, code review
- Social media strategy and content calendar
- Market research (via Grok API, web search)
- Nightly builds (2:30 AM EST)
- File management and project organization

### Shared / Handoff Tasks
These require both of us working in sequence:

| Task | Kiyomi Does | Brock Does |
|---|---|---|
| YouTube upload | Write title, description, tags, script | Upload video, set metadata in Studio |
| Patreon post | Draft content, format markdown | Post to Patreon dashboard |
| Podcast pipeline | Write script, format for Gemini | Feed to NotebookLM via browser |
| Site updates | Code + deploy | Verify live site looks correct |
| Email campaigns | Draft content | Send via web interface if needed |

---

## Communication Protocol

### How We Pass Work
Since we can't directly message each other, we use **file-based handoffs**:

**Handoff directory:** `/Users/richardecholsai2/Documents/Apps/keiko-telegram-bot/workspace/handoffs/`

**File format:**
```
YYYY-MM-DD_[from]_to_[to]_[task-slug].md
```

**Example:**
```
2026-01-30_kiyomi_to_brock_youtube-upload.md
```

**Handoff file structure:**
```markdown
# Task: [Brief description]
- **From:** Kiyomi / Brock
- **To:** Brock / Kiyomi
- **Priority:** High / Medium / Low
- **Status:** Ready / In Progress / Done / Blocked

## What's Done
[What the sender completed]

## What's Needed
[Exactly what the receiver needs to do]

## Files / Assets
[Paths to any files involved]

## Notes
[Any context needed]
```

### Completed Work Log
Both agents append to:
`/Users/richardecholsai2/Documents/Apps/keiko-telegram-bot/workspace/WORK_LOG.md`

Format:
```
## YYYY-MM-DD
- [TIME] [AGENT] — [What was done]
```

---

## Automation Opportunities

### Things We Can Fully Automate (Richard just approves)

1. **YouTube Content Pipeline**
   - Kiyomi: Research trending topics, write script, generate title/description/tags
   - Output: Draft ready for Richard's review
   - After approval: Brock uploads to YouTube Studio

2. **Patreon Content Calendar**
   - Kiyomi: Generate weekly content drafts based on strategy
   - Output: Posts queued in handoff folder
   - After approval: Brock posts to Patreon

3. **Nightly Code Improvements**
   - Kiyomi: PRs for bug fixes, features, optimizations
   - Output: GitHub PRs with clear descriptions
   - Richard: Reviews and merges in the morning

4. **Market Research Reports**
   - Kiyomi: Weekly Grok-powered analysis of AI/coding market
   - Output: Report in workspace folder
   - Richard: Reads when convenient

5. **Podcast Episodes**
   - Kiyomi: Write and format script
   - Brock: Generate via NotebookLM
   - Output: Audio file ready for review
   - Richard: Listens and approves

6. **Social Media Cross-Posting**
   - Kiyomi: Draft posts for all platforms
   - Output: Content ready for review
   - After approval: Brock posts to each platform

7. **Site Monitoring & Fixes**
   - Kiyomi: Monitor for errors, auto-fix and deploy
   - Output: Summary of what was fixed
   - Richard: Reviews in morning brief

### Things That Still Need Richard

- Final content approval before publishing
- Business decisions (pricing, partnerships)
- Personal preferences for content tone
- Account creation / password entry
- Financial transactions

---

## Daily Workflow (Automated)

### Overnight (Kiyomi — 2:30 AM EST)
1. Check handoff folder for pending Brock requests
2. Run nightly build priorities (bugs > business > bot > features > content > code quality)
3. Generate any scheduled content
4. Leave handoff files for Brock if needed
5. Write work summary to WORK_LOG.md

### Morning (Brock — ~7 AM EST)
1. Check handoff folder for Kiyomi outputs
2. Send Richard morning brief via text
3. Execute any browser tasks from handoffs
4. Report what was done

### Throughout Day (Both)
1. Richard drops tasks via Telegram (Kiyomi) or ClawdBot (Brock)
2. Whoever gets it, does their part and hands off if needed
3. Both log work to WORK_LOG.md

---

## Richard's Approval Queue

All items needing Richard's sign-off go to:
`/Users/richardecholsai2/Documents/Apps/keiko-telegram-bot/workspace/APPROVAL_QUEUE.md`

Format:
```markdown
## Pending Approval

### [Date] — [Title]
- **Type:** PR / Content / Strategy / Other
- **From:** Kiyomi / Brock
- **Summary:** [1-2 sentences]
- **Action needed:** Review and approve/reject
- **Link/File:** [path or URL]
```

Richard checks this once or twice a day. We keep it short and actionable.

---

## Getting Started — Immediate Next Steps

1. [x] Create this collaboration document
2. [ ] Create handoff directory structure
3. [ ] Create WORK_LOG.md
4. [ ] Create APPROVAL_QUEUE.md
5. [ ] Kiyomi writes first handoff for Brock (test the system)
6. [ ] Richard shares this doc with Brock so he knows the protocol

---

*This is a living document. Update as we refine the workflow.*
*Created: 2026-01-30 by Kiyomi*
