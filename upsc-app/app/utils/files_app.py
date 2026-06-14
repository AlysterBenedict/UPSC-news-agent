"""
UPSC Daily Digest — File I/O Utilities
=======================================
JSON read/write, directory management, path helpers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json(path: Path | str) -> Any:
    """Read and parse a JSON file."""
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(data: Any, path: Path | str, indent: int = 2) -> Path:
    """Write data to a JSON file, creating parent directories."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False, default=str)
    return path


def write_text(content: str, path: Path | str) -> Path:
    """Write text content to a file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def read_text(path: Path | str) -> str:
    """Read text content from a file."""
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def ensure_dir(path: Path | str) -> Path:
    """Ensure a directory exists, creating if needed."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def find_scraper_output(scraper_dir: Path, date_str: str) -> Path | None:
    """Find the scraper output JSON for a given date."""
    # Try exact match first
    exact = scraper_dir / f"scraped_articles_{date_str}.json"
    if exact.exists():
        return exact

    # Try glob for any matching file
    matches = list(scraper_dir.glob(f"scraped_articles_{date_str}*.json"))
    if matches:
        return sorted(matches)[-1]  # latest

    return None
