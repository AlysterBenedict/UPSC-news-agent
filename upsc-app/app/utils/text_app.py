"""
UPSC Daily Digest — Text Processing Utilities
==============================================
Boilerplate removal, whitespace normalization, and text cleaning
tailored to Indian news sources.
"""

from __future__ import annotations

import re
from typing import Optional


# Patterns to strip from article text (compiled for speed)
BOILERPLATE_PATTERNS: list[re.Pattern] = [
    # Social share / navigation CTAs
    re.compile(
        r"Make us preferred source on Google\s*(Whatsapp|twitter|Facebook|Reddit|PRINT)*",
        re.IGNORECASE,
    ),
    re.compile(r"Story continues below this ad", re.IGNORECASE),
    re.compile(r"Also Read\s*\|[^\n]+", re.IGNORECASE),
    re.compile(r"ALSO READ\s*\|[^\n]+", re.IGNORECASE),
    # Copyright / footer
    re.compile(r"©.*?(Pvt\.?\s*Ltd|Media Services|All rights reserved).*", re.IGNORECASE),
    re.compile(r"Expand\s+Tags?:.*$", re.IGNORECASE | re.MULTILINE),
    # Byline blocks (Indian Express style)
    re.compile(
        r"(Written by|By):\s*[A-Z][a-z]+ [A-Z][a-z]+\s*\d+\s*min read[^\n]*",
        re.IGNORECASE,
    ),
    # Updated timestamps
    re.compile(r"Updated:\s*\w+ \d+,\s*\d{4}\s*\d+:\d+\s*(AM|PM)\s*IST", re.IGNORECASE),
    # Reporter bio blocks (IE, Hindu)
    re.compile(
        r"\.\.\.\s*Read More\s+Tags?:.*$", re.IGNORECASE | re.MULTILINE | re.DOTALL
    ),
    # Social media embeds
    re.compile(r"pic\.twitter\.com/\w+", re.IGNORECASE),
    re.compile(r"— .+? \(@\w+\) \w+ \d+, \d{4}", re.IGNORECASE),
    # PIB-specific
    re.compile(r"\*+\s*(MV|YB|RKJ|SNC|AKS|NB)\s*$", re.MULTILINE),
    # Image captions
    re.compile(r"\((?:File |AI generated |Representative |PTI |Reuters |ANI )?(?:Photo|Image)\)", re.IGNORECASE),
    re.compile(r"\(Credits?:\s*[^\)]+\)", re.IGNORECASE),
    # Subscription prompts
    re.compile(r"Subscribe to.*?newsletter", re.IGNORECASE),
    re.compile(r"Sign up for\s+.*?alerts?", re.IGNORECASE),
    # RSS stubs
    re.compile(r"^\[RSS Summary\]\s*", re.IGNORECASE),
    re.compile(r"^\[Visible Teaser\]\s*", re.IGNORECASE),
    re.compile(r"^\[Subheadline\]\s*", re.IGNORECASE),
]

# Reporter bio detection: long blocks at end of articles
REPORTER_BIO_PATTERN = re.compile(
    r"(?:Expertise|Experience|Specializ|Background|Professional|Coverage|"
    r"Analytical Depth|Digital|Find all stories|Read More).*$",
    re.IGNORECASE | re.DOTALL,
)


def clean_whitespace(text: str) -> str:
    """Normalize whitespace: collapse runs, strip lines, remove blank lines."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def remove_boilerplate(text: str) -> str:
    """Remove known boilerplate patterns from Indian news sources."""
    for pattern in BOILERPLATE_PATTERNS:
        text = pattern.sub("", text)
    # Remove reporter bios (typically long blocks at end)
    text = REPORTER_BIO_PATTERN.sub("", text)
    return clean_whitespace(text)


def truncate_text(text: str, max_chars: int = 12000) -> str:
    """Truncate text to max_chars at a sentence boundary."""
    if len(text) <= max_chars:
        return text
    # Find last sentence boundary before limit
    truncated = text[:max_chars]
    last_period = truncated.rfind(".")
    if last_period > max_chars * 0.7:
        return truncated[: last_period + 1]
    return truncated


def extract_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    # Simple sentence splitter for English news text
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z"])', text)
    return [s.strip() for s in sentences if len(s.strip()) > 10]


def word_count(text: str) -> int:
    """Count words in text."""
    return len(text.split())


def estimate_pages(total_words: int, words_per_page: int = 550) -> int:
    """Estimate A4 page count from word count."""
    return max(1, round(total_words / words_per_page))
