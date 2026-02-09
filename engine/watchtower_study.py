"""
Kiyomi — Weekly Watchtower Study Answers
Fetches the upcoming Watchtower study article from jw.org,
generates deeper answers for each paragraph group,
and sends each as a SEPARATE Telegram message for easy copy/paste.

Triggered by cron every Tuesday at 10am.
"""
import asyncio
import json
import logging
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import httpx

logger = logging.getLogger("kiyomi.watchtower")

# Add engine dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Config ──────────────────────────────────────────────────

def _load_config() -> dict:
    config_file = Path.home() / ".kiyomi" / "config.json"
    if config_file.exists():
        with open(config_file) as f:
            return json.load(f)
    return {}


# ── Fetch Article ───────────────────────────────────────────

async def fetch_watchtower_article() -> tuple[str, str]:
    """Fetch the current week's Watchtower study article.

    Strategy:
    1. Use the WOL meetings page to extract the study article title and issue info
    2. Construct the jw.org URL (has full server-rendered content with data-pid paragraphs)
    3. Fetch and return the article HTML

    Returns:
        Tuple of (article_html, article_title)
    """
    now = datetime.now()

    # JW meeting weeks run Mon-Sun. Use Monday of this week.
    monday = now - timedelta(days=now.weekday())
    year, month, day = monday.year, monday.month, monday.day

    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        # Step 1: Get meetings page to find the study article title and issue
        meetings_url = f"https://wol.jw.org/en/wol/dt/r1/lp-e/{year}/{month}/{day}"
        logger.info(f"Fetching meetings page: {meetings_url}")

        resp = await client.get(meetings_url)
        page_text = re.sub(r'<[^>]+>', ' ', resp.text)
        page_text = re.sub(r'\s+', ' ', page_text)

        # Extract article title from: "Study Article NN: date_range N Article Title"
        title_match = re.search(
            r'Study Article \d+:\s+\w+ \d+-\d+,\s+\d+\s+\d+\s+(.*?)(?:English|$)',
            page_text
        )
        article_title = ""
        if title_match:
            article_title = title_match.group(1).strip()
            logger.info(f"Found article title: {article_title}")

        # Extract issue info: "The Watchtower (Study)—YYYY | Month"
        issue_match = re.search(
            r'Watchtower \(Study\)[—–-](\d{4})\s*\|\s*(\w+)',
            page_text
        )
        issue_year = ""
        issue_month = ""
        if issue_match:
            issue_year = issue_match.group(1)
            issue_month = issue_match.group(2).lower()
            logger.info(f"Issue: {issue_month} {issue_year}")

        # Step 2: Construct jw.org URL
        article_html = ""

        if article_title and issue_year and issue_month:
            # Build URL slug from title
            slug = article_title.replace(' ', '-')
            slug = re.sub(r'[^a-zA-Z0-9-]', '', slug)
            slug = re.sub(r'-+', '-', slug)

            issue_slug = f"watchtower-study-{issue_month}-{issue_year}"
            article_url = f"https://www.jw.org/en/library/magazines/{issue_slug}/{slug}/"
            logger.info(f"Fetching article from jw.org: {article_url}")

            resp = await client.get(article_url)
            if resp.status_code == 200 and len(resp.text) > 10000:
                article_html = resp.text
                # Verify title from the actual page
                h1 = re.search(r'<h1[^>]*>(.*?)</h1>', article_html, re.DOTALL)
                if h1:
                    article_title = re.sub(r'<[^>]+>', '', h1.group(1)).strip()
            else:
                logger.warning(f"jw.org returned status {resp.status_code}, trying WOL fallback")

        # Step 3: Fallback — try WOL article IDs directly
        if not article_html:
            all_ids = re.findall(r'/en/wol/d/r1/lp-e/(\d{7})', resp.text if hasattr(resp, 'text') else '')
            wt_candidates = [aid for aid in all_ids if int(aid) % 1000 >= 682]
            if not wt_candidates:
                wt_candidates = [aid for aid in all_ids if int(aid) % 1000 >= 600]

            for aid in wt_candidates:
                url = f"https://wol.jw.org/en/wol/d/r1/lp-e/{aid}"
                logger.info(f"Trying WOL fallback: {url}")
                resp = await client.get(url)
                if len(resp.text) > 5000:
                    article_html = resp.text
                    h1 = re.search(r'<h1[^>]*>(.*?)</h1>', article_html, re.DOTALL)
                    if h1:
                        title_text = re.sub(r'<[^>]+>', '', h1.group(1)).strip()
                        if title_text and 'Table of Contents' not in title_text:
                            article_title = title_text
                            break

        if not article_html:
            logger.error("Could not fetch Watchtower study article from any source")

        return article_html, article_title


def extract_article_text(html: str) -> str:
    """Convert article HTML to clean plain text suitable for AI processing."""
    if not html:
        return ""

    # Remove script and style tags
    text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # Preserve paragraph breaks
    text = re.sub(r'</p>', '\n\n', text)
    text = re.sub(r'<br\s*/?>', '\n', text)

    # Remove all remaining HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)

    # Clean up whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = text.strip()

    return text


# ── Generate Answers ────────────────────────────────────────

WATCHTOWER_SYSTEM_PROMPT = """You are Kiyomi, preparing Watchtower study answers for Richard, a Jehovah's Witness elder.

FORMAT RULES (follow EXACTLY):
- Each paragraph group gets 2-3 bullet points
- Start each bullet with the bullet character followed by a space: "• "
- Go deeper than surface-level — add insight, not just restatement
- Quote cited scriptures INLINE in the bullet (e.g., "Have you noticed my servant Job? There is no one like him on the earth." (Job 1:8))
- Only include Insight book or research material points if they NATURALLY fit — don't force it
- Keep each bullet 1-3 sentences max
- Do NOT use markdown formatting (no **, no *, no _) — this goes into Telegram as plain text
- Start each section with the paragraph symbol and number like: ¶1-2 or ¶3

EXAMPLE OUTPUT for a single paragraph group:
¶1-2
• Job was a real person, not a fictional character — "Have you noticed my servant Job? There is no one like him on the earth." (Job 1:8) Jehovah himself vouched for him, which shows this account carries personal weight from God.
• The book answers a universal question: why do good people suffer? "All Scripture is inspired of God and beneficial for teaching, for reproving, for setting things straight." (2 Tim. 3:16) — Job's story is there because we need it.
• Job's integrity was tested to the extreme, but the account isn't just about endurance — it's about vindicating Jehovah's name and proving Satan's claim wrong. (Job 1:9-11)

IMPORTANT: Output ONLY the bullet points for the requested paragraph group. No intro, no outro, no commentary. No "Here are the answers" or similar."""


async def generate_paragraph_answers(article_text: str, paragraph_groups: list[str]) -> list[str]:
    """Generate answers for each paragraph group using AI.

    Args:
        article_text: Full article text (plain text)
        paragraph_groups: List of paragraph group labels like ["1-2", "3", "4", "5"]

    Returns:
        List of formatted answer strings, one per paragraph group
    """
    config = _load_config()

    try:
        from engine.ai import chat
    except ImportError:
        from ai import chat

    from engine.config import get_api_key, get_cli_timeout

    answers = []

    for pg in paragraph_groups:
        prompt = f"""Here is the full Watchtower study article text:

---
{article_text}
---

Generate the study answers for paragraph(s) {pg} ONLY. Follow the format rules exactly. Start with ¶{pg} on the first line."""

        # Use Claude CLI (Richard's preferred provider)
        provider = config.get("provider", "claude-cli")
        model = config.get("model", "claude-opus-4-6")
        api_key = get_api_key(config)

        result = await chat(
            message=prompt,
            provider=provider,
            model=model,
            api_key=api_key if not provider.endswith("-cli") else "",
            system_prompt=WATCHTOWER_SYSTEM_PROMPT,
            history=[],
            cli_path=config.get("cli_path", ""),
            cli_timeout=get_cli_timeout(config),
        )

        answers.append(result.strip())
        logger.info(f"Generated answer for ¶{pg}")

        # Small delay between API calls to avoid rate limiting
        await asyncio.sleep(2)

    return answers


# ── Send to Telegram ────────────────────────────────────────

async def send_answers_to_telegram(answers: list[str], article_title: str = ""):
    """Send each paragraph answer as a separate Telegram message."""
    config = _load_config()
    token = config.get("telegram_token", "")
    chat_id = config.get("telegram_user_id", "")

    if not token or not chat_id:
        logger.error("Missing Telegram token or chat_id")
        return

    base_url = f"https://api.telegram.org/bot{token}"

    async with httpx.AsyncClient(timeout=30) as client:
        # Send header message
        header = f"📖 Watchtower Study Answers\n{article_title}\n\nHere are your paragraph answers — each in a separate message for easy copy/paste into JW Library:"
        await client.post(f"{base_url}/sendMessage", json={
            "chat_id": chat_id,
            "text": header,
        })
        await asyncio.sleep(1)

        # Send each answer as a separate message
        for answer in answers:
            if not answer.strip():
                continue
            try:
                resp = await client.post(f"{base_url}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": answer,
                })
                if resp.status_code != 200:
                    logger.error(f"Telegram send failed: {resp.text}")
                await asyncio.sleep(1.5)  # Avoid Telegram rate limits
            except Exception as e:
                logger.error(f"Failed to send answer: {e}")

        # Send footer
        await client.post(f"{base_url}/sendMessage", json={
            "chat_id": chat_id,
            "text": "✅ All paragraph answers sent! You're going to crush it at the meeting 💪🌸",
        })


# ── Paragraph Group Detection ──────────────────────────────

def detect_paragraph_groups(article_text: str) -> list[str]:
    """Detect paragraph groupings from the article text.

    WT study articles have numbered review questions like:
    "1-2. What are some reasons..." or "3. How did Job..."
    These question numbers correspond directly to the paragraph groups.
    """
    # Primary method: find question numbers in the article
    # Pattern: number or number-range followed by period at start of line
    # e.g., "1-2. What are...", "3. As illustrated...", "14-15. What line..."
    groups = re.findall(r'(?:^|\n)\s*(\d+(?:\s*[-–]\s*\d+)?)\.\s', article_text)

    if groups:
        # Clean up and deduplicate while preserving order
        cleaned = []
        seen = set()
        for g in groups:
            g = g.replace('–', '-').replace(' ', '').strip()
            # Only include reasonable paragraph numbers (1-25)
            nums = g.split('-')
            if all(1 <= int(n) <= 25 for n in nums):
                if g not in seen:
                    seen.add(g)
                    cleaned.append(g)
        if cleaned:
            return cleaned

    # Fallback: try the "paragraphs N" pattern from review questions
    groups = re.findall(
        r'paragraphs?\s+(\d+(?:\s*[-–,]\s*\d+)?)',
        article_text,
        re.IGNORECASE
    )
    if groups:
        cleaned = []
        for g in groups:
            g = g.replace('–', '-').replace(',', '-').strip()
            if g not in cleaned:
                cleaned.append(g)
        return cleaned

    # Last fallback: assume standard 17-paragraph article
    result = ["1-2"]
    for i in range(3, 18):
        result.append(str(i))
    return result


# ── Main Runner ─────────────────────────────────────────────

async def run_watchtower_study():
    """Main function: fetch article, generate answers, send to Telegram."""
    logger.info("Starting weekly Watchtower study answer generation...")

    # Step 1: Fetch the article
    html, title = await fetch_watchtower_article()
    if not html:
        logger.error("Failed to fetch Watchtower article")
        # Notify Richard
        config = _load_config()
        token = config.get("telegram_token", "")
        chat_id = config.get("telegram_user_id", "")
        if token and chat_id:
            async with httpx.AsyncClient(timeout=30) as client:
                await client.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": "⚠️ Hey Richard, I couldn't fetch this week's Watchtower article from jw.org. Can you send me the link?",
                })
        return

    logger.info(f"Article title: {title}")

    # Step 2: Extract clean text
    article_text = extract_article_text(html)

    # Trim to reasonable size for AI context
    if len(article_text) > 15000:
        article_text = article_text[:15000]

    logger.info(f"Article text length: {len(article_text)} chars")

    # Step 3: Detect paragraph groups
    paragraph_groups = detect_paragraph_groups(article_text)
    logger.info(f"Paragraph groups: {paragraph_groups}")

    # Step 4: Generate answers
    answers = await generate_paragraph_answers(article_text, paragraph_groups)

    # Step 5: Send to Telegram as separate messages
    await send_answers_to_telegram(answers, title)

    logger.info("Watchtower study answers sent successfully!")


# ── Entry point for cron / direct execution ─────────────────

def run():
    """Synchronous entry point for cron task integration."""
    asyncio.run(run_watchtower_study())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
