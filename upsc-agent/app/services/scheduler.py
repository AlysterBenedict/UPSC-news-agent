"""
UPSC Daily Digest — Scheduler Service
=======================================
APScheduler-based daily execution at 8:00 AM IST.
"""

from __future__ import annotations

import time
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app.utils.logging import get_logger

log = get_logger(__name__)


def _daily_job(settings):
    """Execute the daily digest pipeline."""
    from app.utils.dates import get_today_str
    from app.graph.workflow import run_workflow

    run_date = get_today_str()
    log.info("scheduled_run_start", date=run_date)

    try:
        scraper_dir = str(settings.scraper_output_path)
        db_path = str(settings.data_path / "checkpoints.db")

        final_state = run_workflow(
            run_date=run_date,
            scraper_output_dir=scraper_dir,
            checkpoint_db_path=db_path,
        )

        pdf = final_state.get("compiled_pdf_path", "N/A") if final_state else "N/A"
        delivery = final_state.get("delivery_status", "N/A") if final_state else "N/A"
        log.info("scheduled_run_complete", date=run_date, pdf=pdf, delivery=delivery)

    except Exception as e:
        log.error("scheduled_run_failed", date=run_date, error=str(e))


def start_scheduler(settings):
    """Start the APScheduler with daily cron trigger."""
    scheduler = BlockingScheduler()

    trigger = CronTrigger(
        hour=settings.schedule_hour,
        minute=settings.schedule_minute,
        timezone=settings.timezone,
    )

    scheduler.add_job(
        _daily_job,
        trigger=trigger,
        args=[settings],
        id="upsc_daily_digest",
        name="UPSC Daily Digest Pipeline",
        replace_existing=True,
    )

    log.info(
        "scheduler_started",
        schedule=f"{settings.schedule_hour:02d}:{settings.schedule_minute:02d}",
        timezone=settings.timezone,
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("scheduler_stopped")
        scheduler.shutdown()
