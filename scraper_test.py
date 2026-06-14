"""
UPSC News Scraper — State-of-the-Art Full-Content Version
==========================================================
All sources use the most reliable extraction method per site:
  - RSS feeds → article URLs → full-text (Indian Express, The Hindu, etc.)
  - Direct APIs → structured JSON (MEA internal API, Down To Earth Quintype API)
  - Webpage scraping → article links (PIB listing, IE section pages)

Strategy per source type:
  [rss]       RSS → article URLs → full-text fetch (BS4 + domain selectors)
  [api]       JSON API → article metadata + URL → full-text fetch
  [listing]   HTML listing page → article links → full-text fetch
  [rss+web]   RSS first, then merge with webpage links to catch missing articles

Key improvements over previous version:
  - MEA: uses internal AJAX API instead of static HTML
  - Down To Earth: uses Quintype /api/v1/stories JSON API
  - PIB: uses official RSS feed + article page scraping
  - Indian Express: RSS + webpage scraping to catch paywalled/missing articles
  - The Wire: uses listing page with proper selectors
  - Added NDTV (RSS, free), Scroll.in (RSS, free)
  - Retry logic with exponential backoff
  - Strict "today only" date filtering
  - JSON-LD structured data extraction fallback

Run:
    conda activate upsc-digest
    python scraper_test.py                    # All sources (default)
    python scraper_test.py --tier 1           # Only IE + The Hindu
    python scraper_test.py --tier 2           # Tier 1+2
    python scraper_test.py --delay 2.0        # Slower, more polite
    python scraper_test.py --sources "PIB — Press Releases" "MEA — Press Releases"

Output:
    scraped_articles_YYYY-MM-DD.json
    scrape_report_YYYY-MM-DD.txt
"""

import feedparser
import requests
import json
import time
import re
import argparse
import sys
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
from dataclasses import dataclass, asdict, field
from typing import Optional
from collections import Counter
from urllib.parse import urljoin, urlparse
import io

# Fix Windows console encoding
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ─────────────────────────────────────────────────────────────────────────────
# 1.  SOURCE REGISTRY
# ─────────────────────────────────────────────────────────────────────────────
SOURCES = {

    # ══════════════════════════════════════════════════════════════════════════
    # TIER 1 — Primary newspapers (RSS + webpage for completeness)
    # ══════════════════════════════════════════════════════════════════════════

    "Indian Express — India": {
        "mode": "rss+web",
        "rss": "https://indianexpress.com/section/india/feed/",
        "web_url": "https://indianexpress.com/section/india/",
        "web_link_selector": "div.articles a[href*='/article/'], h2 a, h3 a",
        "domain": "indianexpress.com",
        "category": "National", "gs": ["GS2", "GS3"], "tier": 1,
    },
    "Indian Express — Explained": {
        "mode": "rss+web",
        "rss": "https://indianexpress.com/section/explained/feed/",
        "web_url": "https://indianexpress.com/section/explained/",
        "web_link_selector": "div.articles a[href*='/article/'], h2 a, h3 a",
        "domain": "indianexpress.com",
        "category": "Analysis", "gs": ["GS1","GS2","GS3"], "tier": 1,
    },
    "Indian Express — Editorials": {
        "mode": "rss+web",
        "rss": "https://indianexpress.com/section/opinion/editorials/feed/",
        "web_url": "https://indianexpress.com/section/opinion/editorials/",
        "web_link_selector": "div.articles a[href*='/article/'], h2 a, h3 a",
        "domain": "indianexpress.com",
        "category": "Editorial", "gs": ["GS2","GS4"], "tier": 1,
    },
    "Indian Express — Economy": {
        "mode": "rss+web",
        "rss": "https://indianexpress.com/section/business/economy/feed/",
        "web_url": "https://indianexpress.com/section/business/economy/",
        "web_link_selector": "div.articles a[href*='/article/'], h2 a, h3 a",
        "domain": "indianexpress.com",
        "category": "Economy", "gs": ["GS3"], "tier": 1,
    },
    "Indian Express — World": {
        "mode": "rss+web",
        "rss": "https://indianexpress.com/section/world/feed/",
        "web_url": "https://indianexpress.com/section/world/",
        "web_link_selector": "div.articles a[href*='/article/'], h2 a, h3 a",
        "domain": "indianexpress.com",
        "category": "International Relations", "gs": ["GS2"], "tier": 1,
    },
    "Indian Express — UPSC": {
        "mode": "rss+web",
        "rss": "https://indianexpress.com/section/upsc-current-affairs/feed/",
        "web_url": "https://indianexpress.com/section/upsc-current-affairs/",
        "web_link_selector": "div.articles a[href*='/article/'], h2 a, h3 a",
        "domain": "indianexpress.com",
        "category": "UPSC Specific", "gs": ["GS1","GS2","GS3"], "tier": 1,
    },
    "Indian Express — Political Pulse": {
        "mode": "rss+web",
        "rss": "https://indianexpress.com/section/political-pulse/feed/",
        "web_url": "https://indianexpress.com/section/political-pulse/",
        "web_link_selector": "div.articles a[href*='/article/'], h2 a, h3 a",
        "domain": "indianexpress.com",
        "category": "Polity", "gs": ["GS2"], "tier": 1,
    },
    "Indian Express — Science": {
        "mode": "rss+web",
        "rss": "https://indianexpress.com/section/technology/science/feed/",
        "web_url": "https://indianexpress.com/section/technology/science/",
        "web_link_selector": "div.articles a[href*='/article/'], h2 a, h3 a",
        "domain": "indianexpress.com",
        "category": "Science & Tech", "gs": ["GS3"], "tier": 1,
    },
    "The Hindu — National": {
        "mode": "rss",
        "rss": "https://www.thehindu.com/news/national/feeder/default.rss",
        "domain": "thehindu.com",
        "category": "National", "gs": ["GS2","GS3"], "tier": 1,
    },
    "The Hindu — Editorial": {
        "mode": "rss",
        "rss": "https://www.thehindu.com/opinion/editorial/feeder/default.rss",
        "domain": "thehindu.com",
        "category": "Editorial", "gs": ["GS2","GS4"], "tier": 1,
    },
    "The Hindu — International": {
        "mode": "rss",
        "rss": "https://www.thehindu.com/news/international/feeder/default.rss",
        "domain": "thehindu.com",
        "category": "International Relations", "gs": ["GS2"], "tier": 1,
    },
    "The Hindu — Business": {
        "mode": "rss",
        "rss": "https://www.thehindu.com/business/feeder/default.rss",
        "domain": "thehindu.com",
        "category": "Economy", "gs": ["GS3"], "tier": 1,
    },
    "The Hindu — Science": {
        "mode": "rss",
        "rss": "https://www.thehindu.com/sci-tech/science/feeder/default.rss",
        "domain": "thehindu.com",
        "category": "Science & Tech", "gs": ["GS3"], "tier": 1,
    },
    "The Hindu — Environment": {
        "mode": "rss",
        "rss": "https://www.thehindu.com/sci-tech/energy-and-environment/feeder/default.rss",
        "domain": "thehindu.com",
        "category": "Environment", "gs": ["GS3"], "tier": 1,
    },

    # ══════════════════════════════════════════════════════════════════════════
    # TIER 1 — Free news sources (no paywall, supplement IE/Hindu)
    # ══════════════════════════════════════════════════════════════════════════

    # NDTV blocks article-page fetching (Akamai CDN 403), so use
    # RSS content:encoded as the full text (headline + summary).
    "NDTV — Top Stories": {
        "mode": "rss",
        "rss": "https://feeds.feedburner.com/ndtvnews-top-stories",
        "domain": "ndtv.com",
        "rss_content_fallback": True,
        "category": "National", "gs": ["GS2","GS3"], "tier": 1,
    },
    "NDTV — World": {
        "mode": "rss",
        "rss": "https://feeds.feedburner.com/ndtvnews-world-news",
        "domain": "ndtv.com",
        "rss_content_fallback": True,
        "category": "International Relations", "gs": ["GS2"], "tier": 1,
    },

    # ══════════════════════════════════════════════════════════════════════════
    # TIER 2 — Government & Policy
    # ══════════════════════════════════════════════════════════════════════════

    # ── PIB: Use RSS feed (ASP.NET ViewState page blocks static scraping) ──────
    # RSS has article URLs with PRID; the OG meta tags contain title/description.
    # Full article text is loaded via JS (__doPostBack), so we extract from OG tags.
    "PIB — Press Releases": {
        "mode": "api",
        "api_type": "pib",
        "api_url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3",
        "base_url": "https://pib.gov.in",
        "domain": "pib.gov.in",
        "category": "Government Policy", "gs": ["GS2","GS3"], "tier": 2,
    },

    # ── MEA: Direct AJAX API ──────────────────────────────────────────────────
    "MEA — Press Releases": {
        "mode": "api",
        "api_type": "mea",
        "api_url": "https://www.mea.gov.in/FrontEnd/FetchPublicationListingData",
        "api_params": {"publicationId": 51, "page": 1, "PageSize": 30, "PLngId": 1, "SortBy": "new"},
        "base_url": "https://www.mea.gov.in",
        "domain": "mea.gov.in",
        "category": "Foreign Policy", "gs": ["GS2"], "tier": 2,
    },

    # ── Down To Earth: Quintype JSON API ──────────────────────────────────────
    "Down To Earth — Environment": {
        "mode": "api",
        "api_type": "dte",
        "api_url": "https://www.downtoearth.org.in/api/v1/stories",
        "api_params": {"section-slug": "environment", "limit": 15},
        "domain": "downtoearth.org.in",
        "category": "Environment", "gs": ["GS3"], "tier": 2,
    },
    "Down To Earth — Governance": {
        "mode": "api",
        "api_type": "dte",
        "api_url": "https://www.downtoearth.org.in/api/v1/stories",
        "api_params": {"section-slug": "governance", "limit": 15},
        "domain": "downtoearth.org.in",
        "category": "Governance", "gs": ["GS2"], "tier": 2,
    },
    "Down To Earth — Science": {
        "mode": "api",
        "api_type": "dte",
        "api_url": "https://www.downtoearth.org.in/api/v1/stories",
        "api_params": {"section-slug": "science-technology", "limit": 15},
        "domain": "downtoearth.org.in",
        "category": "Science & Tech", "gs": ["GS3"], "tier": 2,
    },

    # ── Tier 2 RSS sources ────────────────────────────────────────────────────
    "Livemint — Economy": {
        "mode": "rss",
        "rss": "https://www.livemint.com/rss/economy",
        "domain": "livemint.com",
        "category": "Economy", "gs": ["GS3"], "tier": 2,
    },
    "Livemint — Politics": {
        "mode": "rss",
        "rss": "https://www.livemint.com/rss/politics",
        "domain": "livemint.com",
        "category": "Polity", "gs": ["GS2"], "tier": 2,
    },
    "Economic Times — Economy": {
        "mode": "rss",
        "rss": "https://economictimes.indiatimes.com/news/economy/rssfeeds/1373380680.cms",
        "domain": "economictimes.indiatimes.com",
        "category": "Economy", "gs": ["GS3"], "tier": 2,
    },
    "Economic Times — Policy": {
        "mode": "rss",
        "rss": "https://economictimes.indiatimes.com/news/politics-and-nation/rssfeeds/1052732854.cms",
        "domain": "economictimes.indiatimes.com",
        "category": "Government Policy", "gs": ["GS2","GS3"], "tier": 2,
    },

    # ══════════════════════════════════════════════════════════════════════════
    # TIER 3 — Supplementary
    # ══════════════════════════════════════════════════════════════════════════

    "Times of India — India": {
        "mode": "rss",
        "rss": "https://timesofindia.indiatimes.com/rssfeeds/296589292.cms",
        "domain": "timesofindia.indiatimes.com",
        "category": "National", "gs": ["GS2"], "tier": 3,
    },
    "The Print — India": {
        "mode": "rss",
        "rss": "https://theprint.in/category/india/feed/",
        "domain": "theprint.in",
        "category": "National", "gs": ["GS2","GS3"], "tier": 3,
    },
    "The Wire — India": {
        "mode": "rss",
        "rss": "https://cms.thewire.in/feed/",
        "domain": "thewire.in",
        "category": "National", "gs": ["GS2"], "tier": 3,
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# 2.  PER-DOMAIN FULL-TEXT SELECTORS (updated with live DOM inspection)
# ─────────────────────────────────────────────────────────────────────────────
DOMAIN_SELECTORS = {
    "indianexpress.com":            ["div.full-details", "div[itemprop='articleBody']",
                                     "div.story_details", "div.pcl-full-content"],
    "thehindu.com":                 ["div[itemprop='articleBody']", "div.article-text",
                                     "div.articlebodycontent", "div#content-body-14269002"],
    "pib.gov.in":                   ["div#PdfDiv", "div#PressReleaseContent", "div.innner-page-content-about-us",
                                     "div#WriteReadData", "div.release-content",
                                     "div.content-area"],
    "mea.gov.in":                   ["div.description", "div.pressReleaseContent", "div.detail-content",
                                     "div.press-release-detail", "div#publicationContent",
                                     "div.view-content",
                                     "div.field-items", "article"],
    "livemint.com":                 ["div.articleDiv", "div[itemprop='articleBody']",
                                     "div.mainArea", "div.storyPage_storyContent"],
    "economictimes.indiatimes.com": ["div.artText", "div[itemprop='articleBody']",
                                     "div.article_content", "article"],
    "downtoearth.org.in":           ["div.story-element-text", "div.arr--text-element",
                                     "div.story-card", "article",
                                     "div.article-detail", "div.node__content"],
    "thewire.in":                   ["div.article__body", "div.article-body",
                                     "div[itemprop='articleBody']", "div.grey-text",
                                     "div.content-area", "div.entry-content"],
    "timesofindia.indiatimes.com":  ["div.ga-article", "div[itemprop='articleBody']",
                                     "div._3WlLe", "article"],
    "scroll.in":                    ["div.article-content", "div.entry-content",
                                     "div[class*='story']", "article"],
    "theprint.in":                  ["div.entry-content", "article",
                                     "div.post-content"],
    "ndtv.com":                     ["div.sp-cn", "div[itemprop='articleBody']",
                                     "div.story__content", "div.Art_Text",
                                     "article"],
}

# ─────────────────────────────────────────────────────────────────────────────
# 3.  DATACLASS
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Article:
    title:            str
    url:              str
    source_name:      str
    category:         str
    gs_relevance:     list
    tier:             int
    published:        str        = ""
    full_text:        str        = ""
    full_text_chars:  int        = 0
    scrape_method:    str        = "pending"
    error:            Optional[str] = None
    scraped_at:       str        = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

# ─────────────────────────────────────────────────────────────────────────────
# 4.  SHARED HTTP SESSION + RETRY LOGIC
# ─────────────────────────────────────────────────────────────────────────────
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) "
        "Gecko/20100101 Firefox/120.0"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})

def fetch_with_retry(url: str, timeout: int = 20, max_retries: int = 3,
                     params: dict = None, headers: dict = None) -> Optional[requests.Response]:
    """Fetch a URL with exponential backoff retry logic."""
    for attempt in range(max_retries):
        try:
            resp = SESSION.get(url, timeout=timeout, params=params, headers=headers)
            if resp.status_code == 200:
                return resp
            if resp.status_code in (429, 503):
                wait = (2 ** attempt) + 1
                print(f"       ⏳ Rate limited ({resp.status_code}), waiting {wait}s...")
                time.sleep(wait)
                continue
            # Non-retryable error
            return resp
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
    return None


# ─────────────────────────────────────────────────────────────────────────────
# DATE FILTER — STRICT TODAY ONLY
# ─────────────────────────────────────────────────────────────────────────────
IST = timezone(timedelta(hours=5, minutes=30))
TODAY_DT  = datetime.now(IST)
TODAY_STR = TODAY_DT.strftime("%Y-%m-%d")

def is_today(published_str: str) -> bool:
    """Return True ONLY if the published string contains today's date.
    Unknown/empty dates → include (err on side of more content for listing/API sources).
    """
    if not published_str:
        return True   # Unknown date → include
    s = published_str.lower().strip()

    # Check ISO date fragment (2026-06-12)
    if TODAY_STR in s:
        return True

    # Check "12 Jun 2026" / "12 June 2026" style
    d_no_zero = str(TODAY_DT.day)
    d_with_zero = f"{TODAY_DT.day:02d}"
    month_abbr = TODAY_DT.strftime("%b").lower()   # "jun"
    month_full = TODAY_DT.strftime("%B").lower()    # "june"
    year = str(TODAY_DT.year)

    for m in [month_abbr, month_full]:
        for d in [d_no_zero, d_with_zero]:
            if f"{d} {m} {year}" in s or f"{d} {m}, {year}" in s:
                return True
            # Also "June 12, 2026" style
            if f"{m} {d}, {year}" in s or f"{m} {d} {year}" in s:
                return True

    # Check RFC 822 date (from RSS): "Thu, 11 Jun 2026 23:58:47 +0530"
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(published_str)
        return dt.astimezone(IST).strftime("%Y-%m-%d") == TODAY_STR
    except Exception:
        pass

    # Check millisecond timestamp (from DTE API)
    try:
        ts = int(published_str)
        if ts > 1e12:  # milliseconds
            ts = ts / 1000
        dt = datetime.fromtimestamp(ts, tz=IST)
        return dt.strftime("%Y-%m-%d") == TODAY_STR
    except (ValueError, TypeError, OSError):
        pass

    return False


# ─────────────────────────────────────────────────────────────────────────────
# 5.  HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def clean(text: str) -> str:
    if not text:
        return ""
    import html
    import unicodedata
    # Decode HTML entities
    text = html.unescape(text)
    # Normalize unicode compatibility characters
    text = unicodedata.normalize('NFKC', text)
    # Replace non-breaking spaces with normal spaces
    text = text.replace("\xa0", " ")
    
    # Normalize horizontal spaces
    text = re.sub(r"[ \t]+", " ", text)
    # Normalize vertical spaces (multiple newlines) to double newlines (paragraphs)
    text = re.sub(r"\r\n|\r|\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    # Remove leading/trailing space from each line
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(lines).strip()

def get_soup(url: str, timeout: int = 20) -> Optional[BeautifulSoup]:
    """Fetch a URL and return a BeautifulSoup object, or None on failure."""
    resp = fetch_with_retry(url, timeout=timeout)
    if resp and resp.status_code == 200:
        return BeautifulSoup(resp.content, "html.parser")
    return None

def extract_clean_text(element) -> str:
    if not element:
        return ""
    import html
    
    # Block-level tags that should start on a new line.
    block_tags = {
        'p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 
        'li', 'tr', 'table', 'br', 'hr', 'blockquote', 
        'section', 'article', 'pre', 'form', 'tbody', 'thead'
    }
    
    # Header tags prefix map
    header_tags = {
        'h1': '\n\n# ',
        'h2': '\n\n## ',
        'h3': '\n\n### ',
        'h4': '\n\n#### ',
        'h5': '\n\n##### ',
        'h6': '\n\n###### '
    }
    
    def traverse(node, target_list):
        if hasattr(node, 'children'):
            name = node.name.lower() if node.name else ""
            
            # Decompose any tags that might have slipped through the boilerplate filter
            if name in ('script', 'style', 'noscript', 'iframe', 'nav', 'footer', 'header', 'aside'):
                return
            
            # Special case for br: insert a newline
            if name == 'br':
                target_list.append('\n')
                return
            
            # Special case for tables (tr and td/th)
            if name == 'tr':
                target_list.append('\n| ')
                for child in node.children:
                    traverse(child, target_list)
                target_list.append('\n')
                return
            elif name in ('td', 'th'):
                cell_chunks = []
                for child in node.children:
                    traverse(child, cell_chunks)
                
                cell_text = "".join(cell_chunks).strip()
                cell_text = html.unescape(cell_text)
                cell_text = re.sub(r'\s+', ' ', cell_text)
                # Escape pipe symbols inside cell texts to preserve markdown structure
                cell_text = cell_text.replace('|', '\\|')
                target_list.append(cell_text + " | ")
                return
            
            # Special case for li
            if name == 'li':
                target_list.append('\n- ')
                for child in node.children:
                    traverse(child, target_list)
                target_list.append('\n')
                return
            
            is_header = name in header_tags
            is_block = name in block_tags
            
            if is_header:
                target_list.append(header_tags[name])
            elif is_block:
                target_list.append('\n')
                
            for child in node.children:
                traverse(child, target_list)
                
            if is_header:
                target_list.append('\n\n')
            elif is_block:
                target_list.append('\n')
        else:
            # It is a NavigableString/text node
            text = str(node)
            # Normalize spaces inside the node
            text = re.sub(r'\s+', ' ', text)
            if text:
                target_list.append(text)
                
    chunks = []
    traverse(element, chunks)
    
    # Join and clean up
    text = "".join(chunks)
    return clean(text)

def extract_full_text(soup: BeautifulSoup, domain: str) -> tuple[str, str]:
    """
    Given a parsed page, extract clean article full text.
    Tries: domain-specific selectors → JSON-LD → generic <p> fallback.
    Returns (text, method_label).
    """
    # Pre-extract JSON-LD structured data before decomposing script tags
    json_ld_result = None
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            script_str = script.string
            if script_str:
                # Repair empty JSON values (e.g. "height": , or "width": })
                script_str = re.sub(r':\s*,', ': null,', script_str)
                script_str = re.sub(r':\s*([}\]])', ': null\g<1>', script_str)
                script_str = re.sub(r':\s*\n\s*([}\]])', ': null\n\g<1>', script_str)
            data = json.loads(script_str)
            if isinstance(data, list):
                data = data[0]
            body = data.get("articleBody", "")
            if body and len(body) > 200:
                json_ld_result = (clean(body), "json_ld:articleBody")
                break
        except (json.JSONDecodeError, TypeError, AttributeError):
            continue

    # Remove boilerplate
    exclude_tags = ["script", "style", "nav", "footer", "aside", "header", "noscript", "iframe"]
    if domain != "pib.gov.in":
        exclude_tags.append("form")
        
    for tag in soup(exclude_tags):
        tag.decompose()
        
    # Also remove by class / id
    boilerplate_patterns = [
        "advertisement", "related-articles", "tags", "social-share",
        "share-icons", "also-read", "story-tags", "premium-story",
        "twitter-tweet", "tweet", "social-media", "social-embed",
        "embed-container", "facebook", "instagram", "youtube",
        "share-btn", "related-links", "comment", "disqus"
    ]
    for pattern in boilerplate_patterns:
        for el in soup.find_all(class_=re.compile(pattern, re.I)):
            el.decompose()
        for el in soup.find_all(id=re.compile(pattern, re.I)):
            el.decompose()

    # Domain-specific selectors
    for selector in DOMAIN_SELECTORS.get(domain, []):
        node = soup.select_one(selector)
        if node:
            text = extract_clean_text(node)
            if len(text) > 200:
                return text, f"dom_selector:{selector}"

    # JSON-LD structured data fallback (using pre-extracted result)
    if json_ld_result:
        return json_ld_result

    # Generic fallback using cleaned body
    body_node = soup.find("body") or soup
    text = extract_clean_text(body_node)
    if len(text) > 200:
        return text, "generic_body"

    return "", "no_content_found"

def extract_links_from_webpage(url: str, selector: str, base_url: str,
                               domain_filter: str = None) -> list[dict]:
    """Scrape a webpage for article links matching a CSS selector."""
    soup = get_soup(url)
    if not soup:
        return []

    seen = set()
    links = []
    for a_tag in soup.select(selector):
        href = a_tag.get("href", "")
        if not href or href == "#":
            continue
        abs_url = urljoin(base_url, href)

        # Skip non-article URLs
        skip_patterns = ["category", "Allrel.aspx", "/tag/", "?page=",
                         "press-releases.htm", "/feed/", "javascript:",
                         "#", "/author/"]
        if any(skip in abs_url for skip in skip_patterns):
            continue

        if domain_filter and domain_filter not in abs_url:
            continue

        if abs_url in seen:
            continue
        seen.add(abs_url)

        title_text = clean(a_tag.get_text())
        if len(title_text) > 10:
            links.append({"url": abs_url, "title": title_text})

    return links


# ─────────────────────────────────────────────────────────────────────────────
# 6.  RSS MODE — parse feed → fetch full text per article
# ─────────────────────────────────────────────────────────────────────────────
def scrape_rss_source(name: str, meta: dict, delay: float) -> list[Article]:
    articles = []

    try:
        # Fetch RSS with custom headers to bypass some blocks
        resp = fetch_with_retry(meta["rss"], timeout=15, headers={
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        })
        if resp and resp.status_code == 200:
            feed = feedparser.parse(resp.content)
        else:
            feed = feedparser.parse(meta["rss"])
        if feed.bozo and not feed.entries:
            raise ValueError(f"Bad feed: {feed.bozo_exception}")
        entries = feed.entries
    except Exception as e:
        return [Article(
            title="RSS_FEED_ERROR", url=meta["rss"], source_name=name,
            category=meta["category"], gs_relevance=meta["gs"],
            tier=meta["tier"], error=str(e), scrape_method="rss_failed"
        )]

    use_rss_content = meta.get("rss_content_fallback", False)

    for entry in entries:
        url = entry.get("link", "")
        title = clean(entry.get("title", "No title"))
        published = getattr(entry, "published", getattr(entry, "updated", ""))

        # Strict today-only
        if not is_today(published):
            continue

        if not url:
            continue

        # Clean the newsstand param from NDTV URLs
        if "#publisher=" in url:
            url = url.split("#publisher=")[0]

        # For sites that block article fetching, use RSS content directly
        if use_rss_content:
            rss_text = ""
            # Try content:encoded first (usually fuller)
            if hasattr(entry, "content") and entry.content:
                rss_text = clean(BeautifulSoup(entry.content[0].get("value", ""), "html.parser").get_text())
            # Fallback to description/summary
            if not rss_text:
                desc = entry.get("description", entry.get("summary", ""))
                rss_text = clean(BeautifulSoup(desc, "html.parser").get_text())

            full_text = f"{title}. {rss_text}" if rss_text else title

            articles.append(Article(
                title=title, url=url, source_name=name,
                category=meta["category"], gs_relevance=meta["gs"],
                tier=meta["tier"], published=published,
                full_text=full_text,
                full_text_chars=len(full_text),
                scrape_method="rss_content",
                error=None,
            ))
            continue

        soup = get_soup(url)
        if not soup:
            # Fallback: try RSS content if available
            desc = entry.get("description", entry.get("summary", ""))
            rss_text = clean(BeautifulSoup(desc, "html.parser").get_text()) if desc else ""
            full_text = f"{title}. {rss_text}" if rss_text else ""

            articles.append(Article(
                title=title, url=url, source_name=name,
                category=meta["category"], gs_relevance=meta["gs"],
                tier=meta["tier"], published=published,
                full_text=full_text,
                full_text_chars=len(full_text),
                scrape_method="rss_desc_fallback" if full_text else "failed",
                error=None if full_text else "http_fetch_failed",
            ))
            time.sleep(delay)
            continue

        full_text, method = extract_full_text(soup, meta["domain"])

        articles.append(Article(
            title=title, url=url, source_name=name,
            category=meta["category"], gs_relevance=meta["gs"],
            tier=meta["tier"], published=published,
            full_text=full_text,
            full_text_chars=len(full_text),
            scrape_method=method,
            error=None if full_text else "empty_fulltext",
        ))
        time.sleep(delay)

    return articles


# ─────────────────────────────────────────────────────────────────────────────
# 6b.  RSS+WEB MODE — RSS first, then merge webpage links for completeness
# ─────────────────────────────────────────────────────────────────────────────
def scrape_rss_web_source(name: str, meta: dict, delay: float) -> list[Article]:
    """RSS first, then also scrape the section webpage and merge any missing articles."""
    # Step 1: Get RSS articles
    articles = scrape_rss_source(name, meta, delay)
    rss_urls = {a.url for a in articles}

    # Step 2: Also scrape the webpage for links not in RSS
    if meta.get("web_url"):
        web_links = extract_links_from_webpage(
            meta["web_url"],
            meta.get("web_link_selector", "h2 a, h3 a"),
            meta["web_url"],
            domain_filter=meta.get("domain")
        )

        new_links = [l for l in web_links if l["url"] not in rss_urls]

        for link in new_links:
            time.sleep(delay)
            soup = get_soup(link["url"])
            if not soup:
                continue

            full_text, method = extract_full_text(soup, meta["domain"])

            # Try to get published date from the article page
            published = ""
            for date_sel in ["time[datetime]", "span.date", "meta[name='pubdate']",
                             "meta[property='article:published_time']",
                             "span[itemprop='datePublished']"]:
                date_el = soup.select_one(date_sel)
                if date_el:
                    published = date_el.get("datetime") or date_el.get("content") or date_el.get_text()
                    published = clean(published)
                    break

            # Strict today-only check
            if not is_today(published):
                continue

            if full_text:
                # Try to get a better title from the article page
                page_title_tag = soup.find("h1")
                if page_title_tag:
                    better_title = clean(page_title_tag.get_text())
                    if len(better_title) > 10:
                        link["title"] = better_title

                articles.append(Article(
                    title=link["title"], url=link["url"], source_name=name,
                    category=meta["category"], gs_relevance=meta["gs"],
                    tier=meta["tier"], published=published,
                    full_text=full_text,
                    full_text_chars=len(full_text),
                    scrape_method=f"web+{method}",
                    error=None,
                ))

    return articles


# ─────────────────────────────────────────────────────────────────────────────
# 7.  LISTING MODE — scrape category page → extract links → fetch full text
# ─────────────────────────────────────────────────────────────────────────────
def scrape_listing_source(name: str, meta: dict, delay: float) -> list[Article]:
    articles = []

    # Step 1: Fetch the listing page
    listing_soup = get_soup(meta["listing_url"])
    if not listing_soup:
        return [Article(
            title="LISTING_PAGE_ERROR", url=meta["listing_url"], source_name=name,
            category=meta["category"], gs_relevance=meta["gs"],
            tier=meta["tier"], error="Could not fetch listing page",
            scrape_method="listing_failed"
        )]

    # Step 2: Extract article links
    raw_links = listing_soup.select(meta["link_selector"])

    seen = set()
    article_links = []
    for a_tag in raw_links:
        href = a_tag.get("href", "")
        if not href or href == "#":
            continue
        abs_url = urljoin(meta["base_url"], href)
        if abs_url in seen:
            continue
        # Skip listing/category pages themselves
        skip_patterns = ["category", "Allrel.aspx", "/tag/",
                         "press-releases.htm", "?page=", "javascript:"]
        if any(skip in abs_url for skip in skip_patterns):
            seen.add(abs_url)
            continue
        seen.add(abs_url)
        title_text = clean(a_tag.get_text())
        if len(title_text) > 10:
            article_links.append({"url": abs_url, "title": title_text})

    if not article_links:
        return [Article(
            title="NO_LINKS_FOUND", url=meta["listing_url"], source_name=name,
            category=meta["category"], gs_relevance=meta["gs"],
            tier=meta["tier"], error=f"Selector '{meta['link_selector']}' found no links",
            scrape_method="listing_no_links"
        )]

    # Step 3: Fetch full text for each article
    for link in article_links:
        time.sleep(delay)
        soup = get_soup(link["url"])
        if not soup:
            articles.append(Article(
                title=link["title"], url=link["url"], source_name=name,
                category=meta["category"], gs_relevance=meta["gs"],
                tier=meta["tier"], error="http_fetch_failed",
                scrape_method="failed"
            ))
            continue

        full_text, method = extract_full_text(soup, meta["domain"])

        # Get better title
        page_title_tag = soup.find("h1")
        if page_title_tag:
            better_title = clean(page_title_tag.get_text())
            if len(better_title) > 10:
                link["title"] = better_title

        # Extract published date
        published = ""
        for date_sel in ["time[datetime]", "span.date", "span.published",
                         "meta[name='pubdate']", "meta[property='article:published_time']",
                         "span[itemprop='datePublished']", "div.date"]:
            date_el = soup.select_one(date_sel)
            if date_el:
                published = date_el.get("datetime") or date_el.get("content") or date_el.get_text()
                published = clean(published)
                break

        articles.append(Article(
            title=link["title"], url=link["url"], source_name=name,
            category=meta["category"], gs_relevance=meta["gs"],
            tier=meta["tier"], published=published,
            full_text=full_text,
            full_text_chars=len(full_text),
            scrape_method=f"listing+{method}",
            error=None if full_text else "empty_fulltext",
        ))

    return articles


# ─────────────────────────────────────────────────────────────────────────────
# 8.  API MODE — Direct JSON/HTML API calls (MEA, Down To Earth)
# ─────────────────────────────────────────────────────────────────────────────
def scrape_api_mea(name: str, meta: dict, delay: float) -> list[Article]:
    """MEA internal AJAX API returns HTML fragments with press release listings."""
    articles = []
    resp = fetch_with_retry(meta["api_url"], params=meta["api_params"], timeout=20)
    if not resp or resp.status_code != 200:
        return [Article(
            title="API_ERROR", url=meta["api_url"], source_name=name,
            category=meta["category"], gs_relevance=meta["gs"],
            tier=meta["tier"], error=f"MEA API returned {getattr(resp, 'status_code', 'None')}",
            scrape_method="api_failed"
        )]

    # Parse the HTML fragment returned by the API
    soup = BeautifulSoup(resp.content, "html.parser")
    items = soup.select("div.pressRelesastBox")

    for item in items:
        # Extract date
        date_el = item.select_one("span.date")
        published = clean(date_el.get_text()) if date_el else ""

        # Strict today-only
        if not is_today(published):
            continue

        # Extract title and link
        title_el = item.select_one("h3.pressTitle a, h3 a")
        if not title_el:
            continue
        title = clean(title_el.get_text())
        href = title_el.get("href", "")
        if not href:
            continue
        abs_url = urljoin(meta["base_url"], href)

        # Fetch the detail AJAX HTML fragment or fallback to the page template
        match = re.search(r'dtl/(\d+)', href)
        if match:
            pkid = match.group(1)
            detail_url = urljoin(meta["base_url"], "/FrontEnd/FetchPublicationDetailData")
            time.sleep(delay)
            resp = fetch_with_retry(detail_url, params={"pkid": pkid, "languageId": 1}, timeout=15)
            if resp and resp.status_code == 200:
                art_soup = BeautifulSoup(resp.content, "html.parser")
            else:
                art_soup = None
        else:
            time.sleep(delay)
            art_soup = get_soup(abs_url)

        if not art_soup:
            articles.append(Article(
                title=title, url=abs_url, source_name=name,
                category=meta["category"], gs_relevance=meta["gs"],
                tier=meta["tier"], published=published,
                error="http_fetch_failed", scrape_method="api+failed"
            ))
            continue

        full_text, method = extract_full_text(art_soup, meta["domain"])

        articles.append(Article(
            title=title, url=abs_url, source_name=name,
            category=meta["category"], gs_relevance=meta["gs"],
            tier=meta["tier"], published=published,
            full_text=full_text,
            full_text_chars=len(full_text),
            scrape_method=f"api_mea+{method}",
            error=None if full_text else "empty_fulltext",
        ))

    return articles


def scrape_api_dte(name: str, meta: dict, delay: float) -> list[Article]:
    """Down To Earth Quintype JSON API returns structured story data."""
    articles = []
    resp = fetch_with_retry(meta["api_url"], params=meta["api_params"], timeout=20)
    if not resp or resp.status_code != 200:
        return [Article(
            title="API_ERROR", url=meta["api_url"], source_name=name,
            category=meta["category"], gs_relevance=meta["gs"],
            tier=meta["tier"], error=f"DTE API returned {getattr(resp, 'status_code', 'None')}",
            scrape_method="api_failed"
        )]

    try:
        data = resp.json()
        stories = data.get("stories", [])
    except (json.JSONDecodeError, AttributeError):
        return [Article(
            title="API_PARSE_ERROR", url=meta["api_url"], source_name=name,
            category=meta["category"], gs_relevance=meta["gs"],
            tier=meta["tier"], error="Failed to parse DTE JSON",
            scrape_method="api_failed"
        )]

    for story in stories:
        title = story.get("headline", "No title")
        url = story.get("url", "")
        published_ms = story.get("published-at", story.get("last-published-at", ""))

        # Strict today-only
        if published_ms and not is_today(str(published_ms)):
            continue

        if not url:
            continue

        # Format published date
        published = ""
        if published_ms:
            try:
                ts = int(published_ms) / 1000  # milliseconds to seconds
                published = datetime.fromtimestamp(ts, tz=IST).strftime("%Y-%m-%d %H:%M IST")
            except (ValueError, OSError):
                published = str(published_ms)

        # Fetch full article text from the URL
        time.sleep(delay)
        art_soup = get_soup(url)
        if not art_soup:
            articles.append(Article(
                title=title, url=url, source_name=name,
                category=meta["category"], gs_relevance=meta["gs"],
                tier=meta["tier"], published=published,
                error="http_fetch_failed", scrape_method="api_dte+failed"
            ))
            continue

        full_text, method = extract_full_text(art_soup, meta["domain"])

        # DTE articles sometimes have subheadline as summary
        if not full_text and story.get("subheadline"):
            full_text = clean(story["subheadline"])
            method = "api_dte:subheadline"

        articles.append(Article(
            title=title, url=url, source_name=name,
            category=meta["category"], gs_relevance=meta["gs"],
            tier=meta["tier"], published=published,
            full_text=full_text,
            full_text_chars=len(full_text),
            scrape_method=f"api_dte+{method}",
            error=None if full_text else "empty_fulltext",
        ))

    return articles


def scrape_api_pib(name: str, meta: dict, delay: float) -> list[Article]:
    """PIB RSS feed parser — extracts articles from the RSS XML feed.
    Article pages use ASP.NET ViewState (JS-rendered), so we extract
    content from OG meta tags + title which are server-rendered.
    """
    import warnings
    articles = []
    resp = fetch_with_retry(meta["api_url"], timeout=20)
    if not resp or resp.status_code != 200:
        return [Article(
            title="API_ERROR", url=meta["api_url"], source_name=name,
            category=meta["category"], gs_relevance=meta["gs"],
            tier=meta["tier"], error=f"PIB RSS returned {getattr(resp, 'status_code', 'None')}",
            scrape_method="api_failed"
        )]

    # Parse RSS XML using regex (html.parser treats <link> as void element)
    raw_items = re.findall(r'<item>(.*?)</item>', resp.text, re.DOTALL)

    for raw_item in raw_items:
        title_match = re.search(r'<title>(.*?)</title>', raw_item, re.DOTALL)
        link_match = re.search(r'<link>(.*?)</link>', raw_item, re.DOTALL)
        if not title_match or not link_match:
            continue

        hindi_title = clean(title_match.group(1))
        hindi_url = clean(link_match.group(1))
        if not hindi_url:
            continue

        # Step 1: Fetch the Hindi article page
        time.sleep(delay)
        art_resp = fetch_with_retry(hindi_url, timeout=15)
        if not art_resp or art_resp.status_code != 200:
            articles.append(Article(
                title=hindi_title, url=hindi_url, source_name=name,
                category=meta["category"], gs_relevance=meta["gs"],
                tier=meta["tier"], error="http_fetch_failed",
                scrape_method="api_pib+failed"
            ))
            continue

        art_soup = BeautifulSoup(art_resp.content, "html.parser")

        # Step 2: Find the English language toggle link
        # PIB article pages link to the other language version via a tag
        # with href containing a different PRID
        english_url = ""
        first_fallback_url = ""
        for a_tag in art_soup.find_all("a", href=re.compile(r'PRID=', re.I)):
            href = a_tag.get("href", "")
            link_text = a_tag.get_text(strip=True).lower()
            # The language toggle might say "English" or just be a plain link
            # The key pattern: it links to a DIFFERENT PRID
            if href and hindi_url not in href:
                target_url = href if href.startswith("http") else urljoin(meta["base_url"], href)
                if "english" in link_text:
                    english_url = target_url
                    break
                if not first_fallback_url:
                    first_fallback_url = target_url
        if not english_url:
            english_url = first_fallback_url

        # Step 3: Fetch the English page if found
        title = ""
        full_text = ""
        final_url = hindi_url
        method = "api_pib:hindi_only"

        if english_url:
            time.sleep(delay * 0.5)
            eng_resp = fetch_with_retry(english_url, timeout=15)
            if eng_resp and eng_resp.status_code == 200:
                eng_soup = BeautifulSoup(eng_resp.content, "html.parser")
                og_title = ""
                og_desc = ""
                for og_meta in eng_soup.find_all("meta"):
                    prop = og_meta.get("property", "")
                    if prop == "og:title":
                        og_title = clean(og_meta.get("content", ""))
                    elif prop == "og:description":
                        og_desc = clean(og_meta.get("content", ""))

                # Verify this is actually English (not another Hindi page)
                if og_title and all(ord(c) < 128 for c in og_title if c.isalpha()):
                    title = og_title
                    final_url = english_url
                    
                    # Try to extract full text using DOM selectors first
                    full_text, method = extract_full_text(eng_soup, "pib.gov.in")
                    if not full_text:
                        full_text = og_desc if og_desc else og_title
                        method = "api_pib:english_og"
                    else:
                        method = f"api_pib:{method}"

        # Step 4: Fallback to Hindi OG tags / page content if English not found
        if not title:
            # Try to extract Hindi full text using DOM selectors first
            full_text, method = extract_full_text(art_soup, "pib.gov.in")
            
            og_title = ""
            og_desc = ""
            for og_meta in art_soup.find_all("meta"):
                prop = og_meta.get("property", "")
                if prop == "og:title":
                    og_title = clean(og_meta.get("content", ""))
                elif prop == "og:description":
                    og_desc = clean(og_meta.get("content", ""))
            title = og_title if og_title else hindi_title
            
            if not full_text:
                full_text = og_desc if og_desc else title
                method = "api_pib:hindi_og" if og_desc else "api_pib:title_only"
            else:
                method = f"api_pib:hindi_{method}"

        # PIB RSS has no pubDate, articles are assumed to be current day
        articles.append(Article(
            title=title, url=final_url, source_name=name,
            category=meta["category"], gs_relevance=meta["gs"],
            tier=meta["tier"], published=TODAY_STR,
            full_text=full_text,
            full_text_chars=len(full_text),
            scrape_method=method,
            error=None if full_text else "empty_fulltext",
        ))

    return articles


def scrape_api_source(name: str, meta: dict, delay: float) -> list[Article]:
    """Dispatch to the correct API handler based on api_type."""
    api_type = meta.get("api_type", "")
    if api_type == "mea":
        return scrape_api_mea(name, meta, delay)
    elif api_type == "dte":
        return scrape_api_dte(name, meta, delay)
    elif api_type == "pib":
        return scrape_api_pib(name, meta, delay)
    else:
        return [Article(
            title="UNKNOWN_API_TYPE", url="", source_name=name,
            category=meta["category"], gs_relevance=meta["gs"],
            tier=meta["tier"], error=f"Unknown api_type: {api_type}",
            scrape_method="api_failed"
        )]


# ─────────────────────────────────────────────────────────────────────────────
# 9.  MAIN ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────
def run_scraper(tier_limit: int = 3, delay: float = 1.5,
                source_filter: list = None) -> tuple[list[Article], dict]:
    sources = {k: v for k, v in SOURCES.items() if v["tier"] <= tier_limit}

    if source_filter:
        sources = {k: v for k, v in sources.items() if k in source_filter}

    print("\n" + "=" * 65)
    print(f"  UPSC FULL-CONTENT SCRAPER -- {datetime.now(IST).strftime('%d %b %Y  %H:%M IST')}")
    print(f"  Sources : {len(sources)}  |  Tier <= {tier_limit}  |  Delay : {delay}s/article")
    print(f"  Date filter : {TODAY_STR} (strict)")
    print("=" * 65)

    all_articles: list[Article] = []
    stats = {}

    for name, meta in sources.items():
        mode = meta["mode"]
        mode_tag = {"rss": "RSS", "rss+web": "RSS+WEB", "listing": "HTML-LISTING",
                    "api": f"API:{meta.get('api_type','').upper()}"}.get(mode, mode.upper())
        print(f"\n  [{meta['tier']}] {name}  ({mode_tag})")

        try:
            if mode == "rss":
                articles = scrape_rss_source(name, meta, delay)
            elif mode == "rss+web":
                articles = scrape_rss_web_source(name, meta, delay)
            elif mode == "listing":
                articles = scrape_listing_source(name, meta, delay)
            elif mode == "api":
                articles = scrape_api_source(name, meta, delay)
            else:
                articles = []
        except Exception as e:
            articles = [Article(
                title="SCRAPE_ERROR", url="", source_name=name,
                category=meta["category"], gs_relevance=meta["gs"],
                tier=meta["tier"], error=f"Unhandled: {e}",
                scrape_method="error"
            )]

        ok  = [a for a in articles if not a.error]
        err = [a for a in articles if a.error]
        avg_chars = int(sum(a.full_text_chars for a in ok) / len(ok)) if ok else 0

        print(f"       OK: {len(ok)} articles  |  avg {avg_chars} chars", end="")
        if err:
            print(f"  |  ERR: {len(err)} error(s): {err[0].error}", end="")
        print()

        stats[name] = {
            "tier": meta["tier"], "mode": mode_tag,
            "fetched": len(ok), "errors": len(err), "avg_chars": avg_chars,
        }
        all_articles.extend(articles)

    return all_articles, stats


# ─────────────────────────────────────────────────────────────────────────────
# 10.  SAVE OUTPUTS
# ─────────────────────────────────────────────────────────────────────────────
def save_outputs(articles: list[Article], stats: dict):
    today = TODAY_STR
    import os
    from pathlib import Path
    
    env_dir = os.environ.get("SCRAPER_OUTPUT_DIR")
    if env_dir:
        output_dir = Path(env_dir).resolve()
    else:
        output_dir = Path(__file__).resolve().parent / "zartifacts"
        
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path   = str(output_dir / f"scraped_articles_{today}.json")
    report_path = str(output_dir / f"scrape_report_{today}.txt")

    valid  = [a for a in articles if not a.error]
    errors = [a for a in articles if a.error]

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump([asdict(a) for a in valid], f, indent=2, ensure_ascii=False)

    L = []
    div = "-" * 65
    L += [
        f"UPSC SCRAPER REPORT -- {datetime.now(IST).strftime('%d %b %Y  %H:%M IST')}",
        "=" * 65,
        f"  Total articles  : {len(valid)}",
        f"  Total errors    : {len(errors)}",
        f"  Unique sources  : {len(stats)}",
        f"  Date filter     : {TODAY_STR} (strict)",
        f"  Output file     : {json_path}", "",
    ]

    L += [f"{'SOURCE':<42} {'MODE':<14} {'TIER':>4} {'OK':>5} {'ERR':>5} {'AVG CHARS':>10}", div]
    for src, s in stats.items():
        L.append(f"{src:<42} {s['mode']:<14} {s['tier']:>4} {s['fetched']:>5} {s['errors']:>5} {s['avg_chars']:>10}")

    gs_c = Counter(gs for a in valid for gs in a.gs_relevance)
    L += ["", "BY GS PAPER:", div]
    for gs, n in sorted(gs_c.items()):
        L.append(f"  {gs:<10}: {n} articles")

    cat_c = Counter(a.category for a in valid)
    L += ["", "BY CATEGORY:", div]
    for cat, n in cat_c.most_common():
        L.append(f"  {cat:<32}: {n}")

    meth_c = Counter(a.scrape_method for a in valid)
    L += ["", "EXTRACTION METHODS:", div]
    for m, n in meth_c.most_common():
        L.append(f"  {m:<50}: {n}")

    L += ["", "SAMPLE ARTICLES (first 5):", div]
    for a in valid[:5]:
        preview = a.full_text[:300].replace("\n", " ")
        L += [
            f"  Source  : {a.source_name}",
            f"  Title   : {a.title}",
            f"  URL     : {a.url}",
            f"  GS      : {', '.join(a.gs_relevance)}",
            f"  Method  : {a.scrape_method}",
            f"  Chars   : {a.full_text_chars}",
            f"  Preview : {preview}...", "",
        ]

    if errors:
        L += ["FAILED SOURCES:", div]
        seen_errors = set()
        for e in errors:
            key = f"{e.source_name}: {e.error}"
            if key not in seen_errors:
                L.append(f"  {key}")
                seen_errors.add(key)

    report_text = "\n".join(L)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    return json_path, report_path, report_text


# ─────────────────────────────────────────────────────────────────────────────
# 11. CLI ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="UPSC Full-Content News Scraper (State-of-the-Art)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scraper_test.py                    # All sources (default, ~15 mins)
  python scraper_test.py --tier 1           # IE + Hindu + NDTV only (~5 mins)
  python scraper_test.py --tier 2           # Tier 1+2 (~10 mins)
  python scraper_test.py --delay 2.0        # Slower, safer for rate limits
  python scraper_test.py --sources "PIB — Press Releases" "MEA — Press Releases"
        """,
    )
    ap.add_argument("--tier",  type=int,   default=3,
                    help="Max tier (1=primary only, 2=+govt/finance, 3=all). Default: 3")
    ap.add_argument("--delay", type=float, default=1.5,
                    help="Seconds between article fetches. Default: 1.5")
    ap.add_argument("--sources", nargs="+", default=None,
                    help="Filter only specific source names to run")
    ap.add_argument("--date", type=str, default=None,
                    help="Target date to scrape (e.g. 'yesterday', 'today', or 'YYYY-MM-DD'). Default: today")
    args = ap.parse_args()

    if args.date:
        date_str = args.date.strip().lower()
        if date_str == "yesterday":
            target_dt = datetime.now(IST) - timedelta(days=1)
        elif date_str == "today":
            target_dt = datetime.now(IST)
        else:
            try:
                target_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=IST)
            except ValueError:
                print(f"Error: Invalid date format '{args.date}'. Expected YYYY-MM-DD, 'yesterday', or 'today'.")
                sys.exit(1)
        
        TODAY_DT = target_dt
        TODAY_STR = TODAY_DT.strftime("%Y-%m-%d")

    articles, stats = run_scraper(
        tier_limit=args.tier,
        delay=args.delay,
        source_filter=args.sources
    )
    json_path, report_path, report_text = save_outputs(articles, stats)

    print("\n" + report_text)
    print(f"\n  [OK]  Saved : {json_path}")
    print(f"  [OK]  Saved : {report_path}\n")
