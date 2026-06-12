"""
UPSC Daily Digest — Main Entry Point
======================================
CLI with commands: run, schedule, render-only, deliver-only.

Usage:
    python main.py run                    # Full pipeline for today
    python main.py run --date 2026-06-09  # Specific date
    python main.py schedule               # Daily 8 AM IST scheduler
    python main.py render-only --run-id <id>
    python main.py deliver-only --pdf <path>
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load .env before anything else
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")


def cmd_run(args):
    """Run the full digest pipeline."""
    # Prompt for email delivery FIRST, before anything else
    skip_delivery = False
    if args.local_only:
        skip_delivery = True
    elif args.send_email:
        skip_delivery = False
    else:
        if sys.stdin.isatty():
            try:
                choice = input("\nWould you like to send the generated PDF via email? [y/N]: ").strip().lower()
                skip_delivery = choice not in ["y", "yes"]
            except Exception:
                skip_delivery = False
        else:
            skip_delivery = False

    from config.settings import get_settings
    from app.utils.logging import setup_logging, get_logger
    from app.utils.dates import get_today_str
    from app.graph.workflow import run_workflow

    settings = get_settings()
    run_date = args.date or get_today_str()

    # Setup logging
    log_dir = settings.data_path / "logs"
    setup_logging(log_dir=log_dir)
    log = get_logger("main")

    log.info("=== UPSC Daily Digest Pipeline ===")
    log.info("run_config", date=run_date, model=settings.nim_model)

    start = time.time()

    scraper_dir = str(settings.scraper_output_path)
    db_path = str(settings.data_path / "checkpoints.db")

    try:
        final_state = run_workflow(
            run_date=run_date,
            scraper_output_dir=scraper_dir,
            checkpoint_db_path=db_path,
            run_id=args.run_id,
            skip_delivery=skip_delivery,
        )

        elapsed = time.time() - start
        pdf_path = final_state.get("compiled_pdf_path", "N/A") if final_state else "N/A"
        delivery = final_state.get("delivery_status", "N/A") if final_state else "N/A"

        log.info(
            "pipeline_complete",
            elapsed=f"{elapsed:.0f}s",
            pdf=pdf_path,
            delivery=delivery,
        )

        print(f"\n{'='*60}")
        print(f"  Pipeline completed in {elapsed:.0f} seconds")
        print(f"  PDF: {pdf_path}")
        print(f"  Delivery: {delivery}")
        print(f"{'='*60}")

    except Exception as e:
        log.error("pipeline_failed", error=str(e))
        import traceback
        traceback.print_exc()
        sys.exit(1)


def cmd_schedule(args):
    """Start the daily scheduler."""
    from config.settings import get_settings
    from app.utils.logging import setup_logging, get_logger
    from app.services.scheduler import start_scheduler

    settings = get_settings()
    log_dir = settings.data_path / "logs"
    setup_logging(log_dir=log_dir)
    log = get_logger("scheduler")

    log.info(
        "scheduler_starting",
        hour=settings.schedule_hour,
        minute=settings.schedule_minute,
        timezone=settings.timezone,
    )

    print(f"\n{'='*60}")
    print(f"  UPSC Daily Digest Scheduler")
    print(f"  Schedule: {settings.schedule_hour:02d}:{settings.schedule_minute:02d} {settings.timezone}")
    print(f"  Press Ctrl+C to stop")
    print(f"{'='*60}\n")

    start_scheduler(settings)


def cmd_render_only(args):
    """Render PDF from existing compiled HTML."""
    from config.settings import get_settings
    from app.utils.logging import setup_logging
    from app.agents.render_pdf import render_pdf

    settings = get_settings()
    setup_logging()

    run_dir = settings.data_path / "runs" / args.run_id
    html_path = run_dir / "compiled_digest.html"

    if not html_path.exists():
        print(f"ERROR: HTML not found: {html_path}")
        sys.exit(1)

    state = {
        "compiled_html_path": str(html_path),
        "run_id": args.run_id,
        "run_date": args.run_id.split("_")[1] if "_" in args.run_id else "",
    }

    result = render_pdf(state)
    print(f"PDF: {result.get('compiled_pdf_path', 'FAILED')}")


def cmd_deliver_only(args):
    """Send an existing PDF via email."""
    from config.settings import get_settings
    from app.utils.logging import setup_logging
    from app.services.mailer import MailerService

    settings = get_settings()
    setup_logging()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}")
        sys.exit(1)

    mailer = MailerService(
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_user=settings.smtp_user,
        smtp_pass=settings.smtp_pass,
        email_from=settings.email_from,
    )

    result = mailer.send_digest(
        recipients=settings.recipient_list,
        pdf_path=pdf_path,
        date_str=args.date or "",
    )

    print(f"Delivered: {result['delivered']}")
    if result.get("error"):
        print(f"Error: {result['error']}")


def main():
    parser = argparse.ArgumentParser(
        description="UPSC Daily Digest — Multi-Agent Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run
    run_parser = subparsers.add_parser("run", help="Run the full pipeline")
    run_parser.add_argument("--date", help="Date (YYYY-MM-DD), default=today")
    run_parser.add_argument("--run-id", help="Custom run ID")
    run_parser.add_argument("--local-only", action="store_true", help="Save PDF locally only (do not send email)")
    run_parser.add_argument("--send-email", action="store_true", help="Send PDF via email (skip prompt)")

    # schedule
    subparsers.add_parser("schedule", help="Start daily scheduler")

    # render-only
    render_parser = subparsers.add_parser("render-only", help="Render PDF from HTML")
    render_parser.add_argument("--run-id", required=True, help="Run ID to render")

    # deliver-only
    deliver_parser = subparsers.add_parser("deliver-only", help="Send existing PDF")
    deliver_parser.add_argument("--pdf", required=True, help="Path to PDF")
    deliver_parser.add_argument("--date", help="Date for email subject")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "run": cmd_run,
        "schedule": cmd_schedule,
        "render-only": cmd_render_only,
        "deliver-only": cmd_deliver_only,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
