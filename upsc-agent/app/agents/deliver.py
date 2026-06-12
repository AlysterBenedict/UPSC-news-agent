"""
UPSC Daily Digest — Delivery Agent
====================================
Emails the PDF digest to configured recipients.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.utils.logging import get_logger

log = get_logger(__name__)


def deliver_digest(state: dict) -> dict:
    """
    Delivery Agent: Email the PDF to configured recipients.
    """
    from app.services.mailer import MailerService
    from config.settings import get_settings

    settings = get_settings()
    pdf_path = state.get("compiled_pdf_path")
    run_id = state.get("run_id", "unknown")
    run_date = state.get("run_date", "")

    log.info("delivery_start", run_id=run_id, pdf_path=pdf_path)

    if not pdf_path or not Path(pdf_path).exists():
        log.error("pdf_not_found_for_delivery", path=pdf_path)
        return {
            "delivery_status": "failed",
            "errors": [{
                "phase": "delivery",
                "error_type": "file_not_found",
                "message": f"PDF not found for delivery: {pdf_path}",
            }],
            "current_phase": "delivery_failed",
        }

    if state.get("skip_delivery", False):
        log.info("delivery_skipped_by_user", run_id=run_id, message="User opted to save PDF locally only")
        return {
            "delivery_status": "skipped",
            "current_phase": "delivery_skipped",
        }

    # Check if email is configured
    if not settings.smtp_pass or settings.smtp_pass == "changeme":
        log.warning("email_not_configured", message="SMTP password not set, skipping delivery")
        return {
            "delivery_status": "skipped",
            "current_phase": "delivery_skipped",
        }

    mailer = MailerService(
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_user=settings.smtp_user,
        smtp_pass=settings.smtp_pass,
        email_from=settings.email_from,
    )

    # Gather stats for email — read from state lists directly,
    # NOT from metrics dict (which gets overwritten by each pipeline stage)
    article_count = len(state.get("articles_raw", []))
    metrics = state.get("metrics", {})
    page_count = metrics.get("actual_pages", 0)
    verified_units = state.get("verified_units", [])
    themes = [
        u.get("title", "")
        for u in sorted(verified_units, key=lambda x: x.get("upsc_relevance_score", 0), reverse=True)[:8]
    ]

    result = mailer.send_digest(
        recipients=settings.recipient_list,
        pdf_path=Path(pdf_path),
        date_str=run_date,
        article_count=article_count,
        page_count=page_count,
        themes=themes,
    )

    log.info("delivery_complete", delivered=result["delivered"], error=result.get("error"))

    return {
        "delivery_status": "delivered" if result["delivered"] else "failed",
        "current_phase": "delivered" if result["delivered"] else "delivery_failed",
    }
