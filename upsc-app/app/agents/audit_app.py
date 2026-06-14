"""
UPSC Daily Digest — Audit Agent
=================================
Produces run reports with counts, timings, and quality metrics.
"""

from __future__ import annotations

import time
from datetime import datetime

from app.models.schemas_app import RunMetrics
from app.utils.logging_app import get_logger

log = get_logger(__name__)


def generate_audit_report(state: dict) -> dict:
    """
    Audit Agent: Generate comprehensive run report.

    Logs all metrics, counts, timings, and error summaries.
    """
    run_id = state.get("run_id", "unknown")
    run_date = state.get("run_date", "")
    metrics_updates = state.get("metrics", {})

    log.info("audit_start", run_id=run_id)

    # Gather metrics from state
    articles_raw = state.get("articles_raw", [])
    articles_normalized = state.get("articles_normalized", [])
    clusters = state.get("article_clusters", [])
    analyzed = state.get("analyzed_units", [])
    verified = state.get("verified_units", [])
    errors = state.get("errors", [])

    report = RunMetrics(
        run_id=run_id,
        run_date=run_date,
        completed_at=datetime.now(),
        articles_ingested=len(articles_raw),
        articles_normalized=len(articles_normalized),
        clusters_formed=len(clusters),
        units_analyzed=len(analyzed),
        units_verified=len(verified),
        units_failed_verification=len(analyzed) - len(verified),
        sections_written=metrics_updates.get("sections_written", 0),
        total_words=metrics_updates.get("total_words", 0),
        estimated_pages=metrics_updates.get("estimated_pages", 0),
        actual_pages=metrics_updates.get("actual_pages", 0),
        render_time_seconds=metrics_updates.get("render_time_seconds", 0),
        delivery_status=state.get("delivery_status", "unknown"),
    )

    # Save report
    from app.services.storage_app import StorageService
    from app.services.settings_app import get_settings
    settings = get_settings()
    storage = StorageService(settings.data_path)
    storage.save_run_report(run_id, report.model_dump())

    log.info(
        "audit_complete",
        run_id=run_id,
        articles=report.articles_ingested,
        clusters=report.clusters_formed,
        verified=report.units_verified,
        pages=report.actual_pages,
        delivery=report.delivery_status,
        errors=len(errors),
    )

    return {
        "current_phase": "completed",
    }
