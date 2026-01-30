---
name: scripture-nwt-lookup
description: Look up and retrieve exact New World Translation (NWT) scripture text from jw.org. Use whenever you need accurate Bible quotes for JW content. Ensures Jehovah's name is preserved and exact wording is used.
metadata:
  clawdbot:
    emoji: "📖"
    tags: ["scripture", "bible", "nwt", "jw", "jehovah"]
    author: "Brock"
    version: "1.0.0"
---

# Scripture NWT Lookup

Retrieve exact New World Translation (NWT) scripture text from jw.org for use in JW content.

## Why This Matters

**CRITICAL RULES:**
1. **NEVER paraphrase scriptures** - Use exact NWT wording
2. **ALWAYS use Jehovah's name** - The NWT restores God's name where it belongs
3. **ALWAYS cite book, chapter, verse** - For accountability and study

Other translations may:
- Replace "Jehovah" with "LORD" or "God"
- Use different wording that changes meaning
- Miss nuances important to JW understanding

## Quick Reference URLs

### NWT Study Bible (Recommended)
```
https://www.jw.org/en/library/bible/study-bible/books/[book]/[chapter]/#v[booknum][chapter][verse]
```

### Examples:
| Reference | URL |
|-----------|-----|
| Matthew 24:14 | `https://www.jw.org/en/library/bible/study-bible/books/matthew/24/#v40024014` |
| Psalm 83:18 | `https://www.jw.org/en/library/bible/study-bible/books/psalms/83/#v19083018` |
| Daniel 2:21 | `https://www.jw.org/en/library/bible/study-bible/books/daniel/2/#v27002021` |

### Book Numbers (for URL construction)
| Book | Number | Book | Number |
|------|--------|------|--------|
| Genesis | 01 | Psalms | 19 |
| Exodus | 02 | Proverbs | 20 |
| 1 Samuel | 09 | Isaiah | 23 |
| 2 Samuel | 10 | Jeremiah | 24 |
| Daniel | 27 | Matthew | 40 |
| Mark | 41 | Romans | 45 |
| 1 Corinthians | 46 | 2 Corinthians | 47 |
| 2 Timothy | 55 | Revelation | 66 |

## Lookup Process

### Method 1: Browser Navigation (Most Reliable)

```javascript
// 1. Start browser
browser action=start profile=clawd

// 2. Navigate to scripture
browser action=navigate profile=clawd targetUrl="https://www.jw.org/en/library/bible/study-bible/books/[book]/[chapter]/#v[booknum][chapter][verse]"

// 3. Take snapshot to read text
browser action=snapshot profile=clawd compact=true
```

### Method 2: Direct Fetch (Faster, Less Reliable)

```javascript
web_fetch url="https://www.jw.org/en/library/bible/study-bible/books/matthew/24/" extractMode="text"
```

Note: May need to parse the output to find specific verse.

## Scripture Formatting

### Single Verse
```markdown
**Matthew 24:14** - "And this good news of the Kingdom will be preached in all the inhabited earth for a witness to all the nations, and then the end will come."
```

### Multiple Verses
```markdown
**Psalm 94:20-21** - "Can a throne of corruption be allied with you while it is framing trouble in the name of the law? They make vicious attacks on the righteous one and condemn the innocent one to death."
```

### With Application
```markdown
**Scripture Connection:**
Daniel 2:21 reminds us: "He changes times and seasons, removes kings and sets up kings." Jehovah is ultimately in control. Nations rise and fall according to His purpose.
```

## Common Scriptures Reference

Pre-verified NWT text for frequently used scriptures:

### God's Name
**Psalm 83:18** - "May people know that you, whose name is Jehovah, you alone are the Most High over all the earth."

### Kingdom
**Matthew 6:33** - "Keep on, then, seeking first the Kingdom and his righteousness, and all these other things will be added to you."

**Matthew 24:14** - "And this good news of the Kingdom will be preached in all the inhabited earth for a witness to all the nations, and then the end will come."

**Daniel 2:44** - "In the days of those kings the God of heaven will set up a kingdom that will never be destroyed. And this kingdom will not be passed on to any other people. It will crush and put an end to all these kingdoms, and it alone will stand forever."

### Human Government Failure
**1 Samuel 8:18** - "The day will come when you will cry out because of the king you have chosen for yourselves, but Jehovah will not answer you in that day."

**Daniel 2:21** - "He changes times and seasons, removes kings and sets up kings, gives wisdom to the wise and knowledge to those with discernment."

**Jeremiah 10:23** - "I well know, O Jehovah, that man's way does not belong to him. It does not belong to man who is walking even to direct his step."

**Ecclesiastes 8:9** - "All of this I have seen, and I applied my heart to every work that has been done under the sun, during the time that man has dominated man to his harm."

### Injustice
**Psalm 94:20-21** - "Can a throne of corruption be allied with you while it is framing trouble in the name of the law? They make vicious attacks on the righteous one and condemn the innocent one to death."

**Isaiah 5:20** - "Woe to those who say that good is bad and bad is good, those who substitute darkness for light and light for darkness, those who put bitter for sweet and sweet for bitter!"

### Last Days
**2 Timothy 3:1-5** - "But know this, that in the last days critical times hard to deal with will be here. For men will be lovers of themselves, lovers of money, boastful, haughty, blasphemers, disobedient to parents, unthankful, disloyal, having no natural affection, not open to any agreement, slanderers, without self-control, fierce, without love of goodness, betrayers, headstrong, puffed up with pride, lovers of pleasures rather than lovers of God, having an appearance of godliness but proving false to its power; and from these turn away."

**Matthew 24:6-7** - "You are going to hear of wars and reports of wars. See that you are not alarmed, for these things must take place, but the end is not yet. For nation will rise against nation and kingdom against kingdom, and there will be food shortages and earthquakes in one place after another."

**Matthew 24:12** - "and because of the increasing of lawlessness, the love of the greater number will grow cold."

### Hope & Relief
**Romans 8:22** - "For we know that all creation keeps on groaning together and being in pain together until now."

**2 Corinthians 5:20** - "Therefore, we are ambassadors substituting for Christ, as though God were making an appeal through us. As substitutes for Christ, we beg: 'Become reconciled to God.'"

**Revelation 21:3-4** - "With that I heard a loud voice from the throne say: 'Look! The tent of God is with mankind, and he will reside with them, and they will be his people. And God himself will be with them. And he will wipe out every tear from their eyes, and death will be no more, neither will mourning nor outcry nor pain be anymore. The former things have passed away.'"

### Persecution
**Matthew 24:9** - "Then people will hand you over to tribulation and will kill you, and you will be hated by all the nations on account of my name."

**John 15:20** - "Keep in mind the word I said to you: A slave is not greater than his master. If they have persecuted me, they will also persecute you; if they have observed my word, they will also observe yours."

## Verification Checklist

Before using any scripture:

- [ ] Text matches exactly what's on jw.org NWT
- [ ] Jehovah's name is preserved (not replaced with LORD/God)
- [ ] Book, chapter, and verse are cited
- [ ] Quotation marks around the actual scripture text
- [ ] Bold formatting for the reference

## Troubleshooting

### Scripture doesn't match
1. Always verify against jw.org directly
2. Different editions may have minor updates
3. The NWT Study Bible (2013 revision) is the current standard

### Can't find verse
1. Check book spelling (1 Samuel vs. First Samuel)
2. Verify chapter and verse numbers
3. Some verse numbering differs between translations

### Browser times out
1. Try web_fetch as backup
2. Use the pre-verified common scriptures above
3. Search jw.org manually and copy text

## Adding New Scriptures to Reference

When you look up a new scripture:
1. Verify it's exact NWT text
2. Add it to this skill file under the appropriate category
3. Include full verse text for future reference

## Version History

- **1.0.0** (2026-01-26): Initial version with common scriptures and lookup process
