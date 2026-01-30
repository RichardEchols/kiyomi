---
name: skill-creator
description: Create and package AgentSkills for Claude Code and Clawdbot. Use when creating new skills from workflows, packaging skills for sale, or publishing to ClawdHub/Patreon.
metadata:
  clawdbot:
    emoji: "🛠️"
    tags: ["skills", "packaging", "patreon", "monetization"]
    author: "Brock"
    version: "1.0.0"
---

# Skill Creator

How to create, package, and sell AgentSkills for Claude Code and Clawdbot.

## What is a Skill?

A skill is a structured set of instructions and resources that teach an AI agent how to perform a specific workflow. It includes:

- **SKILL.md** - Main documentation (required)
- **package.json** - Metadata (recommended)
- **scripts/** - Helper scripts (optional)
- **references/** - Supporting documents (optional)
- **templates/** - Reusable templates (optional)

## Why Skills Are Valuable

1. **Capture expertise** - Your workflows become reusable knowledge
2. **Prevent mistakes** - Checklists and validations built-in
3. **Save time** - No reinventing the wheel each session
4. **Transferable** - Share with others or sell
5. **Future-proof** - Agent always has access to the workflow

## The Skill Creation Process

### Step 1: Identify the Workflow

Good skill candidates:
- Repetitive tasks you do regularly
- Multi-step processes with specific order
- Tasks requiring specific tools/APIs
- Workflows with gotchas or edge cases
- Anything you'd want to document anyway

**Questions to ask:**
- What triggers this workflow?
- What tools/APIs does it require?
- What are the inputs and outputs?
- What can go wrong?
- What's the quality checklist?

### Step 2: Document the Workflow

Create `SKILL.md` with this structure:

```markdown
---
name: skill-name
description: One-line description for skill matching. Be specific about when to use.
metadata:
  clawdbot:
    emoji: "🎯"
    tags: ["tag1", "tag2"]
    author: "Your Name"
    version: "1.0.0"
---

# Skill Name

Brief overview of what this skill does.

## When to Use

- Trigger condition 1
- Trigger condition 2

## Prerequisites

- Required tool 1
- Required API key
- Required access

## Workflow Steps

### Step 1: [Name]

[Detailed instructions]

```bash
# Example command
```

### Step 2: [Name]

[Continue...]

## Templates

### Template Name
```
[Reusable template content]
```

## Troubleshooting

### Problem 1
[Solution]

### Problem 2
[Solution]

## Quality Checklist

- [ ] Check 1
- [ ] Check 2
- [ ] Check 3

## Version History

- **1.0.0** (YYYY-MM-DD): Initial version
```

### Step 3: Add Supporting Files

**package.json** (recommended):
```json
{
  "name": "skill-name",
  "version": "1.0.0",
  "description": "Brief description",
  "keywords": ["tag1", "tag2"],
  "author": "Your Name",
  "license": "MIT"
}
```

**scripts/** - For automation:
```
scripts/
├── setup.sh        # Installation/setup
├── validate.sh     # Validation checks
├── example.py      # Example implementation
└── helper.js       # Helper utilities
```

**references/** - For supporting docs:
```
references/
├── api-docs.md     # API documentation
├── examples.md     # Usage examples
└── schemas/        # JSON schemas
```

**templates/** - For reusable content:
```
templates/
├── prompt.md       # Prompt templates
├── config.json     # Config templates
└── output.md       # Output templates
```

### Step 4: Test the Skill

1. **Fresh session test** - Does the skill work without prior context?
2. **Edge case test** - What happens with unusual inputs?
3. **Error handling** - Are failures handled gracefully?
4. **Completeness** - Is anything missing?

### Step 5: Package for Distribution

**Folder structure:**
```
skill-name/
├── SKILL.md          # Main documentation (required)
├── package.json      # Metadata
├── README.md         # For GitHub/ClawdHub
├── scripts/          # Helper scripts
├── references/       # Supporting docs
└── templates/        # Reusable templates
```

**Create zip for distribution:**
```bash
cd /path/to/skills
zip -r skill-name-1.0.0.zip skill-name/
```

## Pricing Your Skills

### Free Tier Skills
- Basic workflows
- Common use cases
- Good for building audience

### Paid Tier Skills ($5-15/mo)
- Advanced workflows
- Niche expertise
- Time-saving automation
- Regular updates

### Premium Skills ($25-50/mo)
- Complete workflow systems
- Multiple integrated skills
- Priority support
- Custom requests

### Factors Affecting Price
- Time saved for user
- Complexity of workflow
- Uniqueness of expertise
- Ongoing maintenance required

## Publishing to Patreon

### Post Structure
```markdown
# 🎯 [Skill Name] - [Brief Value Prop]

**What it does:** [One sentence]

**Perfect for:** [Target audience]

**What's included:**
- SKILL.md - Complete workflow documentation
- scripts/ - Automation helpers
- templates/ - Ready-to-use templates

**Requirements:**
- [Tool 1]
- [API access]

**Quick Start:**
1. Download the skill
2. Copy to your skills folder
3. [First step to use]

---

Download below and level up your AI workflow! 👇
```

### Tier Assignment
- **Free posts** - Teasers, basic skills
- **$5 tier** - Access to skill library
- **$15 tier** - New skills monthly + updates
- **$50 tier** - Custom skill requests

## Publishing to ClawdHub

```bash
# Login
clawdhub login

# Publish
clawdhub publish ./skill-name \
  --slug skill-name \
  --name "Skill Name" \
  --version 1.0.0 \
  --changelog "Initial release"
```

## Skill Quality Checklist

Before publishing, verify:

- [ ] **Description is specific** - Clearly states when to use
- [ ] **Prerequisites listed** - Tools, APIs, access needed
- [ ] **Steps are complete** - Nothing assumed or skipped
- [ ] **Commands are tested** - All code/commands work
- [ ] **Errors handled** - Troubleshooting section exists
- [ ] **Templates included** - Reusable content provided
- [ ] **Version noted** - Version history maintained
- [ ] **Metadata complete** - package.json has all fields

## Converting Workflows to Skills

### From Chat History

1. Review chat where workflow was developed
2. Extract the final working process
3. Document each step with context
4. Add error handling from lessons learned
5. Create templates from successful outputs

### From Daily Work

After completing a task:
1. Note what worked well
2. Document the exact steps
3. Identify reusable patterns
4. Create skill immediately (while fresh)

### From Existing Documentation

1. Find your notes/docs on a process
2. Structure into SKILL.md format
3. Add automation scripts
4. Test with fresh context

## Example: Converting YouTube Upload to Skill

**Before (scattered knowledge):**
- "I use yt-dlp for something"
- "There's a metadata file format"
- "Thumbnail needs to be certain size"

**After (skill):**
```
youtube-upload/
├── SKILL.md           # Complete upload workflow
├── package.json
├── scripts/
│   ├── prepare.sh     # Prep video + metadata
│   └── upload.py      # Upload automation
├── templates/
│   ├── metadata.json  # Video metadata template
│   └── description.md # Description template
└── references/
    └── api-setup.md   # YouTube API setup guide
```

## Maintaining Skills

### Version Updates
- Bug fixes: 1.0.0 → 1.0.1
- New features: 1.0.0 → 1.1.0
- Breaking changes: 1.0.0 → 2.0.0

### Changelog Format
```markdown
## Version History

- **1.1.0** (2026-01-27): Added template for X, fixed Y
- **1.0.1** (2026-01-26): Fixed bug in step 3
- **1.0.0** (2026-01-25): Initial release
```

### Subscriber Communication
- Announce updates in Patreon posts
- Note breaking changes prominently
- Provide migration guides when needed

## Revenue Optimization

### Bundle Related Skills
Group related skills into packs:
- "Content Creator Pack" (YouTube, Twitter, Podcast skills)
- "Developer Productivity Pack" (Git, CI/CD, Deploy skills)
- "Research & Analysis Pack" (Search, Summarize, Report skills)

### Upsell Path
1. Free skill → Hooks user
2. Paid tier → Full library access
3. Premium tier → Custom skills

### Content Calendar
- 1 new skill per week/month
- Update existing skills regularly
- Respond to subscriber requests

## Version History

- **1.0.0** (2026-01-26): Initial skill-creator skill
