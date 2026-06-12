"""
UPSC Daily Digest — Ingestion Agent
====================================
Reads scraper JSON output, validates schemas, creates run_id.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from pathlib import Path

from app.models.schemas import RawArticle, ErrorRecord
from app.utils.dates import get_today_str
from app.utils.files import read_json
from app.utils.logging import get_logger
from app.agents.normalize import parse_source_name

log = get_logger(__name__)


def generate_article_id(url: str, source: str) -> str:
    """Generate a deterministic article ID from URL."""
    hash_input = f"{url}:{source}"
    return hashlib.sha256(hash_input.encode()).hexdigest()[:16]


def generate_run_id(date_str: str) -> str:
    """Generate a unique run ID."""
    short_uuid = uuid.uuid4().hex[:8]
    return f"digest_{date_str}_{short_uuid}"


def ingest_articles(state: dict) -> dict:
    """
    Ingestion Agent: Load and validate scraper output.

    Reads the scraped_articles_{date}.json file, validates each article
    against the RawArticle schema, and produces validated raw articles.
    """
    run_date = state.get("run_date", get_today_str())
    scraper_dir = Path(state.get("scraper_output_dir", "../")).resolve()
    run_id = state.get("run_id", generate_run_id(run_date))
    skip_scrape = state.get("skip_scrape", False)

    log.info("ingestion_start", run_id=run_id, run_date=run_date, scraper_dir=str(scraper_dir), skip_scrape=skip_scrape)

    # Check if the scraper output already exists
    scraper_file = scraper_dir / f"scraped_articles_{run_date}.json"
    matches = list(scraper_dir.glob(f"scraped_articles_{run_date}*.json"))
    
    # Automatically run the scraper first unless skip_scrape is True AND the file already exists
    if not skip_scrape or (not scraper_file.exists() and not matches):
        scraper_script = scraper_dir / "scraper_test.py"
        if scraper_script.exists():
            log.info("auto_running_scraper", script=str(scraper_script), tier=3, date=run_date)
            print(f"\n=============================================================")
            print(f"  [Auto] Starting UPSC News Scraper (Tier 3)...")
            print(f"  This crawls all RSS/listing feeds. Please wait.")
            print(f"=============================================================\n")
            try:
                import subprocess
                import sys
                
                cmd = [sys.executable, str(scraper_script)]
                if run_date:
                    cmd.extend(["--date", run_date])

                result = subprocess.run(
                    cmd,
                    cwd=str(scraper_dir),
                )
                if result.returncode != 0:
                    log.error("scraper_run_failed", returncode=result.returncode)
                    print(f"\n[WARN] Scraper exited with code {result.returncode}. Proceeding with pipeline...")
                else:
                    log.info("scraper_run_success")
                    print(f"\n[OK] Scraper finished successfully!\n")
            except Exception as e:
                log.error("scraper_auto_run_failed", error=str(e))
                print(f"\n[WARN] Failed to auto-run scraper: {e}. Proceeding with pipeline...")

    # Find scraper output file again (in case it was just created or matches other names)
    if not scraper_file.exists():
        # Try glob
        matches = list(scraper_dir.glob(f"scraped_articles_{run_date}*.json"))
        if matches:
            scraper_file = sorted(matches)[-1]
        else:
            error = ErrorRecord(
                phase="ingestion",
                error_type="file_not_found",
                message=f"No scraper output found for {run_date} in {scraper_dir}",
            )
            log.error("scraper_output_missing", date=run_date, dir=str(scraper_dir))
            return {
                "run_id": run_id,
                "run_date": run_date,
                "errors": [error.model_dump()],
                "current_phase": "ingestion_failed",
            }

    log.info("scraper_file_found", path=str(scraper_file))

    # Load raw data
    raw_data = read_json(scraper_file)
    if not isinstance(raw_data, list):
        raw_data = [raw_data]

    articles_raw = []
    errors = []

    for i, item in enumerate(raw_data):
        try:
            # Validate against schema
            article = RawArticle.model_validate(item)

            # Skip error entries from scraper
            if article.error and article.full_text_chars == 0:
                log.debug("skipping_error_article", title=article.title, error=article.error)
                continue

            # Keep all articles regardless of character count, as long as they are not empty error entries.

            # Generate article ID
            article_dict = article.model_dump()
            article_dict["article_id"] = generate_article_id(article.url, article.source_name)

            articles_raw.append(article_dict)

        except Exception as e:
            error = ErrorRecord(
                phase="ingestion",
                error_type="validation_error",
                message=f"Article {i}: {str(e)}",
            )
            errors.append(error.model_dump())
            log.warning("article_validation_failed", index=i, error=str(e))

    log.info(
        "ingestion_complete",
        run_id=run_id,
        total_input=len(raw_data),
        accepted=len(articles_raw),
        rejected=len(raw_data) - len(articles_raw),
        errors=len(errors),
    )

    return {
        "run_id": run_id,
        "run_date": run_date,
        "articles_raw": articles_raw,
        "errors": errors,
        "current_phase": "ingested",
        "metrics": {
            "articles_ingested": len(articles_raw),
            "articles_rejected": len(raw_data) - len(articles_raw),
        },
    }
