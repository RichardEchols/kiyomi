---
name: richard-delivery-workflow
description: How to properly deliver work, updates, and requests for approval to Richard. Covers Telegram delivery, file organization, approval workflows, and communication preferences.
metadata:
  clawdbot:
    emoji: "📬"
    tags: ["workflow", "communication", "telegram", "delivery"]
    author: "Brock"
    version: "1.0.0"
---

# Richard Delivery Workflow

How to properly communicate with Richard, deliver work products, and request approvals.

## Richard's Contact Info

| Channel | Address | When to Use |
|---------|---------|-------------|
| **Telegram** | ID: 8295554376 | Primary - all deliverables and updates |
| **Email** | richardbechols92@gmail.com | Formal documents, external sharing |
| **Phone** | +14045529941 | Emergencies only |

## Core Principle

**Richard may not always have computer access.**

He needs to be able to review, approve, and respond from his phone. This means:
- ✅ Send content to Telegram (readable on phone)
- ✅ Include full context in messages
- ❌ Don't just say "I saved a file" - send the content
- ❌ Don't assume he can check the Mac mini

## Telegram Delivery

### Sending Messages
```javascript
message action=send channel=telegram target=8295554376 message="Your message here"
```

### Long Content (Split Messages)
Telegram has message length limits. For long content:
1. Send a header message explaining what's coming
2. Split content into logical chunks (segments, sections)
3. Number them if order matters
4. End with a summary or "ready for approval" message

### Formatting
- Use **bold** for emphasis
- Use headers (##) for sections
- Use bullet points for lists
- Use code blocks for technical content
- Emojis help visual scanning 📝✅🎙️

## Approval Workflows

### When Approval is REQUIRED

| Task | Needs Approval | Why |
|------|----------------|-----|
| JW Podcast generation | ✅ ALWAYS | Content accuracy critical |
| Sending external messages | ✅ ALWAYS | Represents Richard |
| Publishing content | ✅ ALWAYS | Public visibility |
| Major file changes | ⚠️ Usually | Could lose work |
| Installing software | ⚠️ Usually | System changes |
| Internal organization | ❌ No | Low risk |
| Research/analysis | ❌ No | Information gathering |

### Approval Request Format

```markdown
📋 **[TASK TYPE] - Ready for Approval**

**What:** [Brief description]

**Details:**
[Full content or summary]

**Files Created:**
- `path/to/file1.md`
- `path/to/file2.md`

**Next Step:** [What happens after approval]

---
Please reply "approved" or let me know changes needed.
```

### After Approval
1. Proceed with the task
2. Notify Richard when complete
3. Share results/output

## Work Product Delivery

### Scripts & Documents

1. **Send full content to Telegram** (not just file path)
2. Split into multiple messages if needed
3. Save to files for reference

Example:
```
📝 **Kingdom Watch Script - January 26, 2026**

[Full script content here...]

---
Saved to: podcasts/kingdom-watch-jan26-2026-master.md
```

### Generated Content (Podcasts, Videos, etc.)

1. Notify when generation starts
2. Update on progress if long
3. Notify when complete
4. Provide link/access instructions

Example:
```
🎙️ **Podcast READY!**

Kingdom Watch - January 26, 2026 is ready in NotebookLM.

To listen:
1. Open NotebookLM
2. Go to Kingdom Watch notebook
3. Click Play on the latest Deep Dive

Or I can send you the audio file directly.
```

### Research & Analysis

1. Lead with key findings
2. Then provide details
3. Include sources
4. Offer to go deeper if needed

## File Organization

### Standard Locations

| Content Type | Location |
|--------------|----------|
| Podcast files | `/Users/richardecholsai/clawd/podcasts/` |
| Skills | `/Users/richardecholsai/clawd/skills/` |
| Memory/logs | `/Users/richardecholsai/clawd/memory/` |
| Temp work | `/tmp/` or project-specific |

### Naming Conventions

```
[type]-[date]-[descriptor].md

Examples:
kingdom-watch-jan26-2026-master-document.md
kingdom-watch-jan26-2026-prompt.md
midweek-meeting-feb3-2026-script.md
```

## Communication Style

### Richard's Preferences (from USER.md)

1. **Just DO things** - Don't ask permission first (except approval items)
2. **Plan first** - Create PRD/plan together, then execute
3. **Check in when done** - Show finished work for approval
4. **TEST EVERYTHING** - His biggest pain is broken functionality
5. **Fix bugs silently** - Don't explain, just fix
6. **He innovates, I execute** - He has ideas, I make them real

### Message Style

- **Quick updates, only when important**
- **Don't over-explain**
- **Be direct** - Lead with the point
- **Use structure** - Headers, bullets, emojis

### Good Examples

✅ **Good:**
```
🎙️ Kingdom Watch podcast generating! 

Settings: Deep Dive, Long, custom prompt applied.
Will notify when ready (~5-10 min).
```

❌ **Bad:**
```
Hello Richard! I wanted to let you know that I have successfully 
navigated to the NotebookLM interface and after reviewing the 
various options available, I selected the Deep Dive format as 
we discussed, and I also made sure to select the Long duration 
option. I then pasted the custom prompt that we prepared earlier 
into the text field and clicked the Generate button. The system 
is now processing the request and I estimate it will take 
approximately 5-10 minutes to complete...
```

## Proactive Updates

### When to Reach Out

- Task complete (deliverable ready)
- Blocking issue (need decision/input)
- Important discovery (affects plans)
- Time-sensitive information

### When NOT to Reach Out

- Routine progress (just working)
- Questions you can answer yourself
- Information that can wait
- Problems you're actively solving

## Error Handling

### When Something Fails

1. **Try to fix it first** - Don't immediately escalate
2. **If stuck, explain clearly:**
   - What you tried
   - What went wrong
   - What you need

Example:
```
⚠️ NotebookLM generation failed.

Tried: Refreshing page, re-selecting source, regenerating
Error: "Session expired"

Need: Can you re-login to NotebookLM in the Clawd browser? 
Or I can try a different approach.
```

## Templates

### Task Complete
```
✅ **[Task Name] Complete**

[Brief summary of what was done]

**Output:** [Link/location/content]

**Next steps:** [What happens now, or "None - finished"]
```

### Waiting for Input
```
⏳ **Need Your Input: [Topic]**

[Context/question]

**Options:**
1. [Option A]
2. [Option B]

Let me know which direction, or if you have another idea.
```

### Progress Update (Long Tasks)
```
🔄 **[Task Name] Progress**

Started: [time]
Status: [current phase]
ETA: [estimate]

[Any notable info]
```

## Version History

- **1.0.0** (2026-01-26): Initial workflow based on Richard's preferences
