---
name: news-research-workflow
description: Comprehensive research methodology for news and current events. Covers real-time gathering via Grok/X, source verification, fact-checking, summarization, and analysis. Use when researching news stories, verifying claims, or preparing content about current events.
metadata:
  clawdbot:
    emoji: "📰"
    tags: ["research", "news", "grok", "twitter", "fact-check", "analysis"]
    author: "Brock"
    version: "1.0.0"
---

# News Research Workflow

Comprehensive methodology for researching current events, verifying sources, and producing accurate news analysis.

## Overview

This skill covers:
1. Real-time news gathering (Grok, web search, social media)
2. Source identification and verification
3. Fact-checking methodology
4. Bias awareness and balance
5. Summarization and synthesis

## Research Stack

| Tool | Purpose | Best For |
|------|---------|----------|
| **Grok API** | Real-time X/Twitter data | Social sentiment, breaking news, trending takes |
| **web_search** | Traditional news sources | Verified facts, official statements |
| **web_fetch** | Full article content | Deep reading, quotes, context |
| **Browser** | Complex research | Videos, paywalled content, interactive |

## Phase 1: Story Discovery

### Breaking News Sources

**Real-time (within minutes):**
- X/Twitter (via Grok API)
- Reddit front page / relevant subreddits
- Google News alerts

**Fast news (within hours):**
- AP News, Reuters (wire services)
- Breaking Points
- Local news affiliates

**Analysis (within days):**
- Long-form journalism
- Investigative pieces
- Expert commentary

### Using Grok for Real-Time Research

```bash
# Grok API call for X/Twitter search
curl -s https://api.x.ai/v1/chat/completions \
  -H "Authorization: Bearer $GROK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "grok-3",
    "messages": [
      {
        "role": "user", 
        "content": "Search X for posts about [TOPIC] from the last 24 hours. Include actual tweets with usernames, engagement metrics, and notable threads."
      }
    ]
  }'
```

**Grok research prompts:**

```
# For breaking news
"What are people on X saying about [EVENT] right now? Include tweets from journalists, officials, and notable accounts."

# For sentiment analysis
"Analyze the sentiment on X about [TOPIC]. Show examples from different political perspectives - left, right, and independent voices."

# For primary sources
"Find tweets from [PERSON/ORGANIZATION] about [TOPIC]. Include any official statements or announcements."

# For trending context
"What related topics are trending alongside [MAIN TOPIC]? What's the broader conversation?"
```

### Web Search Strategy

```bash
# News-specific search
web_search query="[topic] news" count=10

# Time-restricted search
web_search query="[topic] after:2024-01-01" count=10

# Source-specific
web_search query="site:reuters.com [topic]" count=5
```

## Phase 2: Source Verification

### Source Credibility Tiers

| Tier | Description | Examples | Trust Level |
|------|-------------|----------|-------------|
| **1 - Primary** | Original source, first-hand | Official statements, documents, video footage | Highest |
| **2 - Wire Services** | Professional news agencies | AP, Reuters, AFP | Very High |
| **3 - Major Outlets** | Established news organizations | NYT, WSJ, BBC | High (verify bias) |
| **4 - Specialty** | Topic-specific experts | Trade publications, academic sources | High (for expertise area) |
| **5 - Commentary** | Analysis and opinion | Podcasts, Substacks, opinion columns | Medium (valuable for perspective) |
| **6 - Social Media** | Individual accounts | Tweets, posts | Low (verify independently) |

### Verification Checklist

For each claim:

- [ ] **Who said it?** - Named source or anonymous?
- [ ] **Primary source available?** - Can you find the original?
- [ ] **Multiple outlets reporting?** - Independent confirmation?
- [ ] **Official denial/confirmation?** - What do involved parties say?
- [ ] **Timeline consistent?** - Does the sequence make sense?
- [ ] **Evidence provided?** - Documents, video, data?

### Red Flags

⚠️ Be cautious when:
- Single unnamed source
- "Sources say" without specifics
- Story only in partisan outlets
- No response sought from accused
- Extraordinary claim, ordinary evidence
- Rapid viral spread before verification

## Phase 3: Fact-Checking

### Fact-Check Workflow

```
1. IDENTIFY the specific claim
2. FIND the original source
3. VERIFY with independent sources (2+ required)
4. CHECK for context (is claim missing important context?)
5. ASSESS overall accuracy
6. DOCUMENT your findings
```

### Fact-Check Documentation

```markdown
## CLAIM: [Exact quote or claim]

**Source:** [Who made the claim, when, where]

**Verification:**

| Source | Says | Notes |
|--------|------|-------|
| [Source 1] | [Finding] | [Context] |
| [Source 2] | [Finding] | [Context] |
| [Source 3] | [Finding] | [Context] |

**Assessment:** [TRUE / FALSE / PARTIALLY TRUE / UNVERIFIED / MISLEADING]

**Context:** [Important context that affects understanding]
```

### Common Misleading Patterns

| Pattern | Description | How to Catch |
|---------|-------------|--------------|
| **Outdated info** | True once, not anymore | Check dates |
| **Missing context** | True but misleading | Find full quote/story |
| **Cherry-picking** | Selective data | Look for full dataset |
| **False equivalence** | Treating unequal things as equal | Assess actual weight |
| **Correlation ≠ causation** | Assuming A caused B | Look for actual evidence |

## Phase 4: Bias Awareness

### Recognize Bias Sources

**Selection bias:** What stories are covered/ignored?
**Confirmation bias:** Seeking info that confirms beliefs
**Framing bias:** How is the story presented?
**Source bias:** Who is quoted/not quoted?

### Multi-Perspective Research

**ALWAYS gather perspectives from:**
- [ ] Mainstream left (CNN, MSNBC, NYT opinion)
- [ ] Mainstream right (Fox News, WSJ opinion)
- [ ] Independent/alternative (Breaking Points, Glenn Greenwald)
- [ ] Academic/expert (subject matter experts)
- [ ] International (BBC, Al Jazeera, foreign press)

### Bias Documentation

```markdown
## STORY: [Topic]

### Perspective Summary

**Left-leaning sources emphasize:**
- [Point 1]
- [Point 2]

**Right-leaning sources emphasize:**
- [Point 1]
- [Point 2]

**Independent sources emphasize:**
- [Point 1]
- [Point 2]

### Common Ground
[What all sides agree on]

### Key Disagreements
[Where perspectives diverge]
```

## Phase 5: Summarization

### News Summary Template

```markdown
# [HEADLINE]

**Date:** [Date of events]
**Category:** [Politics/Tech/Business/etc.]
**Status:** [Developing/Confirmed/Analysis]

## TL;DR
[2-3 sentence summary of key facts]

## What Happened
[Chronological account of verified facts]

## Key Players
- **[Person/Org 1]:** [Role in story]
- **[Person/Org 2]:** [Role in story]

## What We Know (Verified)
- [Fact 1]
- [Fact 2]
- [Fact 3]

## What We Don't Know
- [Unanswered question 1]
- [Unanswered question 2]

## Reactions
- **[Group 1]:** "[Quote or summary]"
- **[Group 2]:** "[Quote or summary]"

## Context
[Historical context, related events, why this matters]

## What's Next
[Expected developments, upcoming events]

## Sources
- [Source 1]
- [Source 2]
- [Source 3]
```

### Quick Brief Format

For rapid summaries:

```markdown
**[TOPIC]** | [Category] | [Date]

**What:** [One sentence on what happened]
**Why it matters:** [One sentence on significance]
**Key quote:** "[Notable quote]" —[Source]
**Watch for:** [What happens next]
```

## Research Templates

### Breaking News Template

```markdown
## BREAKING: [Headline]

**Status:** DEVELOPING | As of [Time/Date]

### What We Know Now
- [Verified fact 1]
- [Verified fact 2]

### Unconfirmed Reports
- [Unverified claim 1] (Source: [who])
- [Unverified claim 2] (Source: [who])

### Official Statements
> "[Quote]" —[Official/Organization]

### Timeline
- [Time]: [Event]
- [Time]: [Event]

### Sources Being Monitored
- [Source 1]
- [Source 2]

**Last Updated:** [Time]
```

### Investigation Template

```markdown
## INVESTIGATION: [Topic]

### Key Question
[What we're trying to understand]

### Background
[Context and history]

### Evidence Gathered

| Type | Description | Source | Verified? |
|------|-------------|--------|-----------|
| [Doc/Video/etc.] | [What it shows] | [Source] | [Y/N/Partial] |

### Key Figures
- **[Person]:** [Relevance, what we know]

### Timeline of Events
| Date | Event | Source |
|------|-------|--------|
| | | |

### Open Questions
1. [Question 1]
2. [Question 2]

### Conclusion
[Current assessment]
```

### Controversy/Debate Template

```markdown
## CONTROVERSY: [Topic]

### The Issue
[What's being debated]

### Position A: [Label]
**Argues:** [Summary of position]
**Key voices:** [Who holds this view]
**Evidence cited:** [What they point to]

### Position B: [Label]
**Argues:** [Summary of position]
**Key voices:** [Who holds this view]
**Evidence cited:** [What they point to]

### Position C (if applicable): [Label]
...

### Common Ground
[What most agree on]

### Key Disputes
[Specific points of disagreement]

### Expert Consensus (if any)
[What experts generally say]
```

## Quality Checklist

Before publishing any research:

- [ ] Multiple sources verify key facts
- [ ] Primary sources consulted where possible
- [ ] Different perspectives represented
- [ ] Unverified claims clearly labeled
- [ ] Dates and times specified
- [ ] Sources documented
- [ ] Own bias acknowledged
- [ ] Context provided

## Ethics Guidelines

**DO:**
- Clearly distinguish fact from opinion
- Acknowledge uncertainty
- Correct errors promptly
- Protect confidential sources
- Consider impact of reporting

**DON'T:**
- Present unverified claims as fact
- Cherry-pick data to support narrative
- Ignore contradicting evidence
- Use inflammatory language unnecessarily
- Doxx or endanger individuals

## Version History

- **1.0.0** (2026-01-27): Initial version - generalized from Kingdom Watch methodology
