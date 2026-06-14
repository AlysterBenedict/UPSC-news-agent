"""
UPSC Daily Digest — Date Parsing Utilities
==========================================
Handles all date formats from the scraper output.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

IST = timezone(timedelta(hours=5, minutes=30))

# Common date formats from scraper output
DATE_FORMATS = [
    # RSS standard
    "%a, %d %b %Y %H:%M:%S %z",          # "Tue, 09 Jun 2026 13:17:18 +0000"
    "%a, %d %b %Y %H:%M:%S %Z",          # with timezone name
    # ISO formats
    "%Y-%m-%dT%H:%M:%S%z",               # "2026-06-09T12:17:22+05:30"
    "%Y-%m-%dT%H:%M:%S.%f%z",            # with microseconds
    "%Y-%m-%dT%H:%M:%S",                 # no timezone
    "%Y-%m-%d",                           # date only
    # Indian formats
    "%d %b %Y %I:%M %p IST",             # "09 Jun 2026 06:53 PM IST"
    "%d %B %Y %I:%M %p",                 # "09 June 2026 06:53 PM"
    "%b %d, %Y %I:%M %p",                # "Jun 09, 2026 06:53 PM"
    "%B %d, %Y",                          # "June 09, 2026"
    "%d/%m/%Y",                           # "09/06/2026"
    "%d-%m-%Y",                           # "09-06-2026"
]


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse a date string in any known format, returning IST datetime."""
    if not date_str or not date_str.strip():
        return None

    date_str = date_str.strip()

    # Remove "Updated:" prefix if present
    date_str = re.sub(r"^(Updated|Published):\s*", "", date_str, flags=re.IGNORECASE)

    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(date_str, fmt)
            # Convert to IST if timezone-aware
            if dt.tzinfo is not None:
                dt = dt.astimezone(IST)
            else:
                dt = dt.replace(tzinfo=IST)
            return dt
        except (ValueError, OverflowError):
            continue

    # Fallback: try dateutil if available
    try:
        from dateutil import parser as dateutil_parser
        dt = dateutil_parser.parse(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=IST)
        return dt.astimezone(IST)
    except Exception:
        pass

    return None


def get_today_ist() -> datetime:
    """Get current datetime in IST."""
    return datetime.now(IST)


def get_today_str() -> str:
    """Get today's date string in YYYY-MM-DD format."""
    return get_today_ist().strftime("%Y-%m-%d")


def format_date_display(dt: Optional[datetime]) -> str:
    """Format datetime for display in the digest."""
    if not dt:
        return "Date unavailable"
    return dt.strftime("%d %B %Y")


def format_date_short(dt: Optional[datetime]) -> str:
    """Short date format for headers."""
    if not dt:
        return ""
    return dt.strftime("%d %b %Y")
