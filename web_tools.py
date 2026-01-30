"""
Kiyomi Web Tools - Web search, fetch, and browser capabilities

Like Brock's web tools:
- web_search: Search via API
- web_fetch: Fetch and extract content from URLs
"""
import asyncio
import logging
import aiohttp
import re
from typing import Optional, List, Dict
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

# API Keys (loaded from config)
BRAVE_API_KEY = None  # Set from config if available


async def web_search(query: str, num_results: int = 5) -> List[Dict]:
    """
    Search the web using available APIs.

    Args:
        query: Search query
        num_results: Number of results to return

    Returns:
        List of search results with title, url, snippet
    """
    results = []

    # Try DuckDuckGo (no API key needed)
    try:
        results = await _duckduckgo_search(query, num_results)
        if results:
            return results
    except Exception as e:
        logger.warning(f"DuckDuckGo search failed: {e}")

    # Fallback: Return empty with suggestion
    logger.warning(f"Web search failed for: {query}")
    return []


async def _duckduckgo_search(query: str, num_results: int) -> List[Dict]:
    """Search using DuckDuckGo HTML (no API key needed)."""
    results = []

    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }) as response:
            if response.status != 200:
                return []

            html = await response.text()

            # Parse results (simple regex extraction)
            # Look for result links
            pattern = r'<a class="result__a" href="([^"]+)"[^>]*>([^<]+)</a>'
            matches = re.findall(pattern, html)

            for url, title in matches[:num_results]:
                # Clean URL (DuckDuckGo wraps URLs)
                if "uddg=" in url:
                    actual_url = re.search(r'uddg=([^&]+)', url)
                    if actual_url:
                        from urllib.parse import unquote
                        url = unquote(actual_url.group(1))

                results.append({
                    "title": title.strip(),
                    "url": url,
                    "snippet": ""
                })

    return results


async def web_fetch(url: str, extract_text: bool = True) -> Dict:
    """
    Fetch content from a URL.

    Args:
        url: URL to fetch
        extract_text: Whether to extract text from HTML

    Returns:
        Dict with status, content, title
    """
    result = {
        "status": "error",
        "url": url,
        "title": "",
        "content": "",
        "error": None
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }, timeout=aiohttp.ClientTimeout(total=30)) as response:

                if response.status != 200:
                    result["error"] = f"HTTP {response.status}"
                    return result

                content_type = response.headers.get("Content-Type", "")

                if "text/html" in content_type:
                    html = await response.text()

                    # Extract title
                    title_match = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
                    if title_match:
                        result["title"] = title_match.group(1).strip()

                    if extract_text:
                        # Simple HTML to text conversion
                        text = _html_to_text(html)
                        result["content"] = text[:10000]  # Limit size
                    else:
                        result["content"] = html[:50000]

                elif "application/json" in content_type:
                    result["content"] = await response.text()

                else:
                    # Binary or other content
                    result["content"] = f"[Binary content: {content_type}]"

                result["status"] = "success"

    except asyncio.TimeoutError:
        result["error"] = "Request timed out"
    except Exception as e:
        result["error"] = str(e)

    return result


def _html_to_text(html: str) -> str:
    """Convert HTML to plain text."""
    # Remove scripts and styles
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # Remove HTML tags
    html = re.sub(r'<[^>]+>', ' ', html)

    # Decode HTML entities
    html = html.replace('&nbsp;', ' ')
    html = html.replace('&amp;', '&')
    html = html.replace('&lt;', '<')
    html = html.replace('&gt;', '>')
    html = html.replace('&quot;', '"')

    # Clean up whitespace
    html = re.sub(r'\s+', ' ', html)
    html = html.strip()

    return html


async def get_weather(location: str = "Atlanta, GA") -> Optional[str]:
    """
    Get weather for a location.

    Args:
        location: City name

    Returns:
        Weather description or None
    """
    try:
        # Use wttr.in (free, no API key)
        url = f"https://wttr.in/{quote_plus(location)}?format=3"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    return await response.text()

    except Exception as e:
        logger.warning(f"Weather fetch failed: {e}")

    return None


async def get_daily_text() -> Optional[str]:
    """
    Fetch the daily text from wol.jw.org.

    Returns:
        Daily text content or None
    """
    try:
        from datetime import datetime
        today = datetime.now()

        # WOL daily text URL format
        url = f"https://wol.jw.org/en/wol/dt/r1/lp-e/{today.year}/{today.month}/{today.day}"

        result = await web_fetch(url)

        if result["status"] == "success":
            content = result["content"]

            # Try to extract the main text
            # This is a simple extraction - may need refinement
            if content:
                # Look for the scripture and commentary
                return content[:3000]  # Return first 3000 chars

    except Exception as e:
        logger.error(f"Daily text fetch failed: {e}")

    return None
