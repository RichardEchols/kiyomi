---
name: thumbnail-generation
description: Generate YouTube thumbnails using AI image tools (nano-banana-pro, Fal AI, etc). Covers sizing, best practices, templates, and generation prompts. Use when creating thumbnails for YouTube or social media.
metadata:
  clawdbot:
    emoji: "🎨"
    tags: ["thumbnail", "youtube", "image", "ai", "generation", "design"]
    author: "Brock"
    version: "1.0.0"
---

# Thumbnail Generation

Complete workflow for creating YouTube thumbnails using AI image generation tools.

## Overview

This skill covers:
1. YouTube thumbnail specifications
2. Design principles for high CTR
3. AI image generation setup
4. Prompt engineering for thumbnails
5. Post-processing and refinement

## Prerequisites

- **AI Image Generation API** (one of):
  - Fal AI (nano-banana-pro, flux)
  - Midjourney
  - DALL-E 3
  - Stable Diffusion
- **Image editing tool** (optional): Photoshop, GIMP, Canva

## YouTube Thumbnail Specifications

### Technical Requirements

| Spec | Requirement |
|------|-------------|
| **Resolution** | 1280x720 px (minimum) |
| **Aspect Ratio** | 16:9 |
| **File Size** | Under 2MB |
| **Formats** | JPG, PNG, GIF, BMP |
| **Recommended** | 1920x1080 px for crisp quality |

### Display Contexts

Thumbnails appear at various sizes:

| Context | Approximate Size |
|---------|-----------------|
| Search results (desktop) | 360x202 px |
| Search results (mobile) | 168x94 px |
| Suggested videos | 168x94 px |
| Home feed (desktop) | 320x180 px |
| Watch page (up next) | 168x94 px |

**Key insight:** Design for small! Test your thumbnail at 168px width.

## Design Principles for High CTR

### 1. Visual Hierarchy

**Primary focus (40% of attention):**
- Main subject (face, object, result)
- Should be immediately recognizable

**Secondary focus (35%):**
- Supporting context
- Text headline (if used)

**Background (25%):**
- Non-distracting
- Supports the mood

### 2. The 3-Second Rule

Viewers decide in ~3 seconds. Ensure:
- [ ] Main subject is instantly clear
- [ ] Emotion/hook is obvious
- [ ] Looks professional (not DIY)
- [ ] Stands out from surrounding content

### 3. Color Psychology

| Color | Emotion | Use For |
|-------|---------|---------|
| **Red** | Urgency, excitement | Drama, breaking news |
| **Yellow** | Attention, optimism | Tutorials, positive content |
| **Blue** | Trust, calm | Tech, professional content |
| **Green** | Growth, success | Finance, self-improvement |
| **Orange** | Energy, creativity | Entertainment, vlogs |
| **Purple** | Luxury, creativity | Luxury, creative content |
| **Black** | Power, mystery | Drama, premium content |

### 4. Face & Emotion

**Faces increase CTR by 30-40%**

- Show genuine emotion (not fake smiles)
- Eyes should be visible
- Expression should match content
- High contrast against background

**Effective emotions:**
- 😲 Surprise/shock (for reveals)
- 🤔 Curiosity (for educational)
- 😊 Joy/excitement (for positive)
- 😤 Frustration (for rants)
- 🤯 Mind-blown (for amazing content)

### 5. Text Best Practices

**Rules:**
- Maximum 3-5 words
- 30%+ of thumbnail space
- High contrast (white on dark, black on light)
- Bold, simple fonts (no cursive)
- Complement, don't repeat title

**Good text:**
- "I WAS WRONG"
- "DON'T DO THIS"
- "24 HOURS"
- "$10K MISTAKE"

**Bad text:**
- "Watch to find out what happened when I tried this new thing"
- Text that repeats the title
- Hard-to-read fonts

## AI Image Generation

### Fal AI Setup (nano-banana-pro)

```bash
# Environment
export FAL_KEY="your-api-key"

# Generate image
curl -X POST "https://queue.fal.run/fal-ai/flux-pro/v1.1-ultra" \
  -H "Authorization: Key $FAL_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "[your prompt]",
    "image_size": "landscape_16_9",
    "num_images": 1,
    "output_format": "jpeg"
  }'
```

### Prompt Structure for Thumbnails

```
[Subject/Scene], [Style], [Lighting], [Mood], [Technical specs]
```

**Example prompts:**

**Tech Review:**
```
Close-up of hands holding sleek smartphone with holographic display, 
product photography style, dramatic side lighting, futuristic blue 
color grading, 16:9 aspect ratio, professional product shot
```

**Tutorial:**
```
Person looking surprised at computer screen with code displayed, 
YouTube thumbnail style, bright studio lighting, vibrant colors, 
exaggerated facial expression, bold and punchy aesthetic
```

**News/Commentary:**
```
Split screen composition with contrasting images, news broadcast 
aesthetic, red and blue color scheme, dramatic lighting, bold 
graphics style, 16:9 horizontal format
```

### Prompt Modifiers for YouTube Style

Add these to make images more "YouTube thumbnail-like":

```
- "YouTube thumbnail style"
- "bold and punchy colors"
- "exaggerated expression"
- "dramatic lighting"
- "high contrast"
- "attention-grabbing"
- "viral video thumbnail aesthetic"
- "professional content creator style"
```

### Image Size Parameters

| Platform | Setting |
|----------|---------|
| Fal AI (flux) | `"image_size": "landscape_16_9"` |
| Midjourney | `--ar 16:9` |
| DALL-E 3 | `"size": "1792x1024"` (closest to 16:9) |
| Stable Diffusion | `width: 1280, height: 720` |

## Template Prompts by Content Type

### Tutorial/How-To
```
Professional [person/hands] demonstrating [skill/action], 
clean modern background, bright even lighting, 
educational YouTube style, 16:9 composition, 
space on [left/right] for text overlay
```

### Product Review
```
[Product] in dramatic product photography style, 
dark gradient background, studio lighting with 
rim light effect, premium aesthetic, 16:9 format, 
centered composition with space for text
```

### Story Time/Drama
```
Expressive person with [emotion] expression, 
dramatic side lighting, moody atmosphere, 
bold colors, YouTube thumbnail style, 
close-up portrait composition, 16:9
```

### Before/After
```
Split-screen composition showing transformation, 
left side: [before state], right side: [after state], 
clear visual divider, dramatic lighting on both sides, 
YouTube comparison thumbnail style, 16:9 format
```

### News/Commentary
```
Breaking news style composition, 
[subject/topic] with red accent colors, 
urgent/dramatic mood, news broadcast aesthetic, 
bold graphic elements, 16:9 horizontal format
```

### Listicle/Countdown
```
Dynamic composition with [number] prominently featured, 
[relevant imagery] arranged graphically, 
bold colorful style, magazine cover aesthetic, 
YouTube viral thumbnail look, 16:9 format
```

## Post-Processing Workflow

### 1. Basic Adjustments

After AI generation:
- Crop to exact 16:9 if needed
- Adjust brightness/contrast (+10-20%)
- Increase saturation slightly (+5-15%)
- Sharpen (+20-30%)

### 2. Adding Text

**Tools:** Canva (free), Photoshop, GIMP

**Text settings:**
- Font: Bold sans-serif (Impact, Bebas Neue, Montserrat Bold)
- Size: Large enough to read at 168px thumbnail width
- Outline: 3-5px black stroke for visibility
- Shadow: Subtle drop shadow for depth

### 3. Adding Branding (Optional)

Consistent elements across thumbnails:
- Logo position (corner)
- Color scheme
- Font style
- Border or frame

### 4. Final Export

- Format: JPG (smaller files) or PNG (text clarity)
- Quality: 85-95% for JPG
- Size: Under 2MB
- Dimensions: 1280x720 minimum

## Thumbnail Text Overlay Workflow

### Using ImageMagick (CLI)

```bash
# Add text to thumbnail
convert input.jpg \
  -font "Impact" \
  -pointsize 120 \
  -fill white \
  -stroke black \
  -strokewidth 3 \
  -gravity Center \
  -annotate +0+0 "YOUR TEXT" \
  output.jpg
```

### Using Python (Pillow)

```python
from PIL import Image, ImageDraw, ImageFont

# Open image
img = Image.open('thumbnail.jpg')
draw = ImageDraw.Draw(img)

# Load font
font = ImageFont.truetype('impact.ttf', 120)

# Add text with outline
text = "YOUR TEXT"
x, y = 100, 500  # Position

# Draw outline
for offset in [(-3,-3), (-3,3), (3,-3), (3,3)]:
    draw.text((x+offset[0], y+offset[1]), text, font=font, fill='black')

# Draw main text
draw.text((x, y), text, font=font, fill='white')

img.save('thumbnail_final.jpg')
```

## A/B Testing Thumbnails

### Strategy

1. Create 2-3 variations
2. Upload with original thumbnail
3. After 48-72 hours, check CTR in Analytics
4. Change to best performer
5. Document what worked

### What to Test

- **Face vs no face**
- **Text vs no text**
- **Different emotions**
- **Color schemes**
- **Zoom levels**
- **Text placement**

### Tracking

Keep a log:
```markdown
| Video | Thumbnail | CTR | Views (48h) | Winner |
|-------|-----------|-----|-------------|--------|
| Video1 | Face + "WOW" | 8.2% | 1200 | ✓ |
| Video1 | Object only | 5.1% | 750 | |
```

## Common Mistakes to Avoid

❌ **Too much text** - Can't read at small sizes
❌ **Low contrast** - Blends into YouTube UI
❌ **Misleading images** - Damages trust, YouTube may penalize
❌ **Cluttered composition** - No clear focal point
❌ **Generic stock look** - Doesn't stand out
❌ **Tiny faces** - Emotion doesn't read
❌ **Copying exactly** - Your thumbnail gets lost

## Quality Checklist

Before using a thumbnail:

- [ ] Readable at 168px width (test it!)
- [ ] Clear focal point / subject
- [ ] Text (if any) is 3-5 words max
- [ ] High contrast colors
- [ ] Emotion is obvious
- [ ] Doesn't mislead about content
- [ ] Under 2MB file size
- [ ] 1280x720 or larger
- [ ] Looks professional

## Version History

- **1.0.0** (2026-01-27): Initial version - AI thumbnail generation workflow
