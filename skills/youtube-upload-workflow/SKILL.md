---
name: youtube-upload-workflow
description: Complete workflow for uploading videos to YouTube via browser automation or API. Covers metadata, thumbnails, scheduling, playlists, and optimization. Use when uploading video content to YouTube.
metadata:
  clawdbot:
    emoji: "📺"
    tags: ["youtube", "upload", "video", "automation", "browser"]
    author: "Brock"
    version: "1.0.0"
---

# YouTube Upload Workflow

Complete workflow for uploading videos to YouTube, including metadata optimization, thumbnail handling, scheduling, and playlist management.

## Overview

This skill covers:
1. Pre-upload preparation (file, metadata, thumbnail)
2. Browser-based upload automation
3. API-based upload (for programmatic use)
4. Post-upload optimization
5. Scheduling and playlist management

## Prerequisites

- **YouTube channel** with upload permissions
- **Video file** in supported format (MP4 recommended)
- **Thumbnail image** (1280x720 px recommended)
- **Browser automation** (Clawdbot) OR **YouTube Data API v3** credentials

## Pre-Upload Checklist

Before uploading, prepare:

- [ ] Video file exported and quality-checked
- [ ] Thumbnail created (1280x720 px, <2MB)
- [ ] Title written (max 100 characters)
- [ ] Description written (max 5000 characters)
- [ ] Tags prepared (max 500 characters total)
- [ ] Category selected
- [ ] Visibility decided (public/unlisted/private/scheduled)
- [ ] Playlist(s) identified

## Method 1: Browser Automation

### Step 1: Navigate to YouTube Studio

```
browser action=navigate targetUrl="https://studio.youtube.com"
```

Ensure you're logged into the correct YouTube account.

### Step 2: Click Upload Button

```
browser action=snapshot
# Look for "Create" or "Upload" button
browser action=act request={"kind": "click", "ref": "[upload-button-ref]"}
```

Or click the camera icon with "+" → "Upload videos"

### Step 3: Select Video File

The file picker will open. For automation:

```
browser action=upload paths=["[/path/to/video.mp4]"]
```

Or use the file picker manually.

### Step 4: Fill Metadata (During Upload)

While video uploads, fill in details:

**Title:**
```
browser action=act request={"kind": "type", "ref": "[title-input]", "text": "[Your Video Title]"}
```

**Description:**
```
browser action=act request={"kind": "type", "ref": "[description-input]", "text": "[Your Description]"}
```

### Step 5: Add Thumbnail

Click "Upload thumbnail" and select your image:
```
browser action=upload paths=["[/path/to/thumbnail.jpg]"]
```

### Step 6: Set Additional Options

**Playlist:**
- Click "Playlists" dropdown
- Select or create playlist

**Audience:**
- Select "No, it's not made for kids" (unless applicable)

**Tags (via "Show More"):**
- Add comma-separated tags

### Step 7: Video Elements (Optional)

- Add end screen
- Add cards
- Add subtitles

### Step 8: Visibility Settings

**Immediate publish:**
- Select "Public"

**Scheduled:**
- Select "Schedule"
- Set date and time
- Choose timezone

**Private/Unlisted:**
- Select accordingly

### Step 9: Publish

Click "Publish" or "Schedule" to complete.

## Method 2: YouTube Data API v3

### Setup API Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create project or select existing
3. Enable "YouTube Data API v3"
4. Create OAuth 2.0 credentials
5. Download credentials JSON

### Authentication Flow

```python
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

flow = InstalledAppFlow.from_client_secrets_file(
    'client_secrets.json', SCOPES)
credentials = flow.run_local_server(port=0)

youtube = build('youtube', 'v3', credentials=credentials)
```

### Upload Video

```python
def upload_video(youtube, file_path, title, description, tags, category_id='22'):
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags,
            'categoryId': category_id
        },
        'status': {
            'privacyStatus': 'public',  # or 'private', 'unlisted'
            'selfDeclaredMadeForKids': False
        }
    }
    
    media = MediaFileUpload(file_path, 
                            mimetype='video/*',
                            resumable=True)
    
    request = youtube.videos().insert(
        part='snippet,status',
        body=body,
        media_body=media
    )
    
    response = request.execute()
    return response['id']
```

### Set Thumbnail via API

```python
def set_thumbnail(youtube, video_id, thumbnail_path):
    request = youtube.thumbnails().set(
        videoId=video_id,
        media_body=MediaFileUpload(thumbnail_path)
    )
    return request.execute()
```

### Add to Playlist

```python
def add_to_playlist(youtube, playlist_id, video_id):
    body = {
        'snippet': {
            'playlistId': playlist_id,
            'resourceId': {
                'kind': 'youtube#video',
                'videoId': video_id
            }
        }
    }
    
    request = youtube.playlistItems().insert(
        part='snippet',
        body=body
    )
    return request.execute()
```

## Metadata Best Practices

### Title (Max 100 characters)

**Formula:** [Hook/Result] + [Topic] + [Year/Context]

**Good examples:**
- "I Built an App in 24 Hours with AI (Here's What Happened)"
- "5 Mistakes Destroying Your Productivity in 2024"
- "The Truth About [Topic] Nobody Talks About"

**Tips:**
- Front-load keywords
- Use numbers when applicable
- Create curiosity gap
- Keep under 60 chars for full mobile display

### Description (Max 5000 characters)

**Structure:**
```
[Compelling first 2-3 lines - shows in search results]

[Main description - what the video covers]

⏱️ TIMESTAMPS
0:00 - Intro
1:23 - [Topic 1]
3:45 - [Topic 2]
...

🔗 LINKS MENTIONED
- [Resource 1]: [URL]
- [Resource 2]: [URL]

📱 CONNECT
- Twitter: [URL]
- Website: [URL]

#hashtag1 #hashtag2 #hashtag3
```

### Tags (Max 500 characters total)

**Priority order:**
1. Exact video topic keywords
2. Broader category terms
3. Related topics
4. Channel name
5. Common misspellings (if applicable)

**Example for a coding video:**
```
python tutorial, python for beginners, learn python, python programming, coding tutorial, programming for beginners, python 2024, [channel name]
```

### Category IDs

| ID | Category |
|----|----------|
| 1 | Film & Animation |
| 2 | Autos & Vehicles |
| 10 | Music |
| 15 | Pets & Animals |
| 17 | Sports |
| 19 | Travel & Events |
| 20 | Gaming |
| 22 | People & Blogs |
| 23 | Comedy |
| 24 | Entertainment |
| 25 | News & Politics |
| 26 | How-to & Style |
| 27 | Education |
| 28 | Science & Technology |

## Thumbnail Requirements

### Technical Specs

| Spec | Requirement |
|------|-------------|
| Resolution | 1280x720 px (minimum) |
| Aspect Ratio | 16:9 |
| File Size | Under 2MB |
| Formats | JPG, PNG, GIF, BMP |

### Design Best Practices

**DO:**
- Use high contrast colors
- Include readable text (3-5 words max)
- Show faces with emotion
- Use consistent branding
- Test at small sizes (how it looks in search)

**DON'T:**
- Use misleading images (clickbait penalty)
- Overcrowd with text
- Use small/unreadable fonts
- Copy competitor thumbnails exactly
- Use low-quality images

### Thumbnail Templates

See `thumbnail-generation` skill for detailed templates and generation workflow.

## Scheduling Best Practices

### Best Times to Publish (General)

| Day | Best Times (EST) |
|-----|------------------|
| Weekdays | 2-4 PM |
| Saturday | 9-11 AM |
| Sunday | 9-11 AM |

**Note:** Optimal times vary by audience. Check YouTube Analytics for YOUR audience's active hours.

### Scheduling via Browser

1. In visibility settings, select "Schedule"
2. Set date and time
3. Verify timezone (defaults to channel timezone)
4. Click "Schedule"

### Scheduling via API

```python
from datetime import datetime, timezone

body = {
    'snippet': {...},
    'status': {
        'privacyStatus': 'private',
        'publishAt': '2024-01-27T14:00:00.000Z'  # ISO 8601 format
    }
}
```

## Playlist Management

### Create Playlist

```python
def create_playlist(youtube, title, description, privacy='public'):
    body = {
        'snippet': {
            'title': title,
            'description': description
        },
        'status': {
            'privacyStatus': privacy
        }
    }
    
    request = youtube.playlists().insert(
        part='snippet,status',
        body=body
    )
    return request.execute()['id']
```

### Playlist Strategy

**Series playlists:** Group related content
**Topic playlists:** Curate by subject
**Best of playlists:** Highlight top content

## Post-Upload Checklist

After upload completes:

- [ ] Verify video plays correctly
- [ ] Check thumbnail displays properly
- [ ] Confirm title/description are correct
- [ ] Add to relevant playlist(s)
- [ ] Set end screen (after 24h if using templates)
- [ ] Add cards at relevant timestamps
- [ ] Share to social media
- [ ] Pin comment with links/CTA

## Troubleshooting

### Upload Stuck/Failed

**Browser:**
- Check internet connection
- Try smaller file size
- Clear browser cache
- Use incognito mode

**API:**
- Check quota limits
- Verify credentials
- Use resumable upload for large files

### Thumbnail Not Uploading

- Verify file size < 2MB
- Check dimensions (min 1280x720)
- Try different format (PNG → JPG)
- Wait for video processing to complete

### Processing Taking Too Long

- Higher resolutions take longer (4K = hours)
- Check video isn't corrupted
- Very long videos take longer
- Wait before troubleshooting (can take hours)

### Video Blocked/Restricted

- Check Content ID claims
- Review YouTube's community guidelines
- Appeal if wrongly flagged

## Version History

- **1.0.0** (2026-01-27): Initial version - browser and API upload workflows
