"""
UPSC Daily Digest — Normalization Agent
========================================
Standardizes source names, parses dates, cleans text.
Preserves raw_text alongside clean_text for traceability.
Uses LLM-based classification to filter out noise articles.
"""

from __future__ import annotations

import re
from typing import Optional

from app.models.schemas_app import NormalizedArticle, ErrorRecord
from app.utils.dates_app import parse_date
from app.utils.text_app import remove_boilerplate, clean_whitespace
from app.utils.logging_app import get_logger
from app.utils.source_policy_app import classify_article_relevance

log = get_logger(__name__)

# Source name normalization map
SOURCE_MAP = {
    "Indian Express": "Indian Express",
    "The Hindu": "The Hindu",
    "PIB": "PIB",
    "MEA": "MEA",
    "Down To Earth": "Down To Earth",
    "The Wire": "The Wire",
    "Livemint": "Livemint",
    "Economic Times": "Economic Times",
    "Scroll": "Scroll",
    "The Print": "The Print",
    "Times of India": "Times of India",
}


def parse_source_name(full_source: str) -> tuple[str, str]:
    """Split 'Indian Express -- India' into ('Indian Express', 'India')."""
    if " -- " in full_source:
        parts = full_source.split(" -- ", 1)
        source = parts[0].strip()
        section = parts[1].strip()
    elif " - " in full_source:
        parts = full_source.split(" - ", 1)
        source = parts[0].strip()
        section = parts[1].strip()
    else:
        source = full_source.strip()
        section = "General"

    # Normalize source name
    for key in SOURCE_MAP:
        if key.lower() in source.lower():
            source = SOURCE_MAP[key]
            break

    return source, section


def normalize_articles(state: dict) -> dict:
    """
    Normalization Agent: Clean and standardize all ingested articles.

    - Standardizes source names
    - Parses dates to ISO format
    - Cleans boilerplate from text
    - Preserves raw_text for traceability
    - Uses LLM-based classification to filter noise articles
    """
    from app.services.settings_app import get_settings

    settings = get_settings()
    articles_raw = state.get("articles_raw", [])
    run_id = state.get("run_id", "unknown")

    log.info("normalization_start", run_id=run_id, count=len(articles_raw))

    # ── Pass 1: Clean and normalize all articles ──────────────
    candidates = []
    errors = []

    for article in articles_raw:
        try:
            # Parse source name
            source, section = parse_source_name(article.get("source_name", ""))

            # Parse date
            published_at = parse_date(article.get("published", ""))

            # Clean text
            raw_text = article.get("full_text", "")
            clean_text = remove_boilerplate(raw_text)

            # Skip if clean text is completely empty
            if len(clean_text) == 0:
                log.debug(
                    "skipping_empty_clean_text",
                    title=article.get("title", ""),
                )
                continue

            art_id = article.get("article_id")
            if not art_id:
                import hashlib
                s_name = article.get("source_name", "Unknown")
                url_str = article.get("url", "")
                h = hashlib.md5(f"{s_name}:{url_str}".encode("utf-8")).hexdigest()
                art_id = f"art_{h[:12]}"

            normalized_article = NormalizedArticle(
                article_id=art_id,
                source=source,
                source_section=section,
                url=article.get("url", ""),
                title=clean_whitespace(article.get("title", "")),
                published_at=published_at,
                raw_text=raw_text,
                clean_text=clean_text,
                char_count=len(clean_text),
                category=article.get("category", "General"),
                gs_papers=article.get("gs_relevance", []),
                tier=article.get("tier", 3),
                scrape_method=article.get("scrape_method", ""),
            )
            candidates.append(normalized_article.model_dump())

        except Exception as e:
            error = ErrorRecord(
                phase="normalization",
                article_id=article.get("article_id"),
                error_type="normalization_error",
                message=str(e),
            )
            errors.append(error.model_dump())
            log.warning(
                "normalization_failed",
                article_id=article.get("article_id"),
                error=str(e),
            )

    log.info(
        "normalization_pass1_complete",
        run_id=run_id,
        input_count=len(articles_raw),
        candidates=len(candidates),
        empty_or_error=len(articles_raw) - len(candidates),
    )

    # ── Pass 2: LLM-based relevance classification ────────────
    if candidates:
        log.info(
            "llm_classification_starting",
            candidate_count=len(candidates),
            model=settings.nim_model_classifier,
        )

        classification_results = classify_article_relevance(
            articles=candidates,
            api_key=settings.nim_api_key,
            base_url=settings.nim_base_url,
            model=settings.nim_model_classifier,
            max_retries=settings.llm_max_retries,
            timeout=settings.llm_timeout,
            delay=settings.llm_delay_seconds,
            max_workers=4,
        )

        # Filter based on classification
        normalized = []
        dropped_count = 0

        for article in candidates:
            article_id = article["article_id"]
            classification = classification_results.get(
                article_id, {"relevant": True, "reason": "not classified"}
            )

            if classification["relevant"]:
                normalized.append(article)
            else:
                dropped_count += 1
                log.info(
                    "article_dropped_by_llm",
                    article_id=article_id,
                    title=article.get("title", "")[:100],
                    source=article.get("source", ""),
                    reason=classification["reason"],
                )

        log.info(
            "llm_classification_complete",
            run_id=run_id,
            candidates=len(candidates),
            kept=len(normalized),
            dropped=dropped_count,
        )

        try:
            import json
            run_date = state.get("run_date", "unknown")
            output_file = settings.scraper_output_path / f"classification_results_{run_date}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(classification_results, f, indent=2, default=str)
            log.info("classification_results_saved", path=str(output_file))
        except Exception as e:
            log.error("failed_to_save_classification_results", error=str(e))
    else:
        normalized = []

    log.info(
        "normalization_complete",
        run_id=run_id,
        input_count=len(articles_raw),
        output_count=len(normalized),
        filtered=len(articles_raw) - len(normalized) - len(errors),
    )

    return {
        "articles_normalized": normalized,
        "errors": errors,
        "current_phase": "normalized",
    }
