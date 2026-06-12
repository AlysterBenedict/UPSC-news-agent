"""
UPSC Daily Digest — Storage Service
====================================
File-based artifact storage with run directory management.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from app.utils.files import write_json, read_json, write_text, read_text, ensure_dir
from app.utils.logging import get_logger

log = get_logger(__name__)


class StorageService:
    """Manages persistent storage of run artifacts."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.runs_dir = data_dir / "runs"
        ensure_dir(self.runs_dir)

    def get_run_dir(self, run_id: str) -> Path:
        """Get or create a run directory."""
        run_dir = self.runs_dir / run_id
        ensure_dir(run_dir)
        return run_dir

    def save_raw_articles(self, run_id: str, articles: list[dict]) -> Path:
        """Save raw ingested articles."""
        path = self.get_run_dir(run_id) / "raw_articles.json"
        write_json(articles, path)
        log.info("saved_raw_articles", run_id=run_id, count=len(articles))
        return path

    def save_normalized_articles(self, run_id: str, articles: list[dict]) -> Path:
        """Save normalized articles."""
        path = self.get_run_dir(run_id) / "normalized_articles.json"
        write_json(articles, path)
        log.info("saved_normalized_articles", run_id=run_id, count=len(articles))
        return path

    def save_clusters(self, run_id: str, clusters: list[dict]) -> Path:
        """Save article clusters."""
        path = self.get_run_dir(run_id) / "clusters.json"
        write_json(clusters, path)
        log.info("saved_clusters", run_id=run_id, count=len(clusters))
        return path

    def save_analysis_unit(self, run_id: str, unit: dict) -> Path:
        """Save a single analysis unit."""
        units_dir = ensure_dir(self.get_run_dir(run_id) / "analysis_units")
        path = units_dir / f"{unit['unit_id']}.json"
        write_json(unit, path)
        return path

    def save_verified_unit(self, run_id: str, unit: dict) -> Path:
        """Save a single verified unit."""
        units_dir = ensure_dir(self.get_run_dir(run_id) / "verified_units")
        path = units_dir / f"{unit['unit_id']}.json"
        write_json(unit, path)
        return path

    def save_section_html(self, run_id: str, section_name: str, html: str) -> Path:
        """Save a section HTML fragment."""
        sections_dir = ensure_dir(self.get_run_dir(run_id) / "sections")
        path = sections_dir / f"{section_name}.html"
        write_text(html, path)
        log.info("saved_section_html", run_id=run_id, section=section_name)
        return path

    def save_compiled_html(self, run_id: str, html: str) -> Path:
        """Save the compiled full digest HTML."""
        path = self.get_run_dir(run_id) / "compiled_digest.html"
        write_text(html, path)
        log.info("saved_compiled_html", run_id=run_id)
        return path

    def save_run_report(self, run_id: str, report: dict) -> Path:
        """Save the run report."""
        path = self.get_run_dir(run_id) / "run_report.json"
        write_json(report, path)
        log.info("saved_run_report", run_id=run_id)
        return path

    def load_checkpoint(self, run_id: str, phase: str) -> Optional[dict]:
        """Load a checkpoint file if it exists."""
        path = self.get_run_dir(run_id) / f"checkpoint_{phase}.json"
        if path.exists():
            return read_json(path)
        return None

    def save_checkpoint(self, run_id: str, phase: str, data: dict) -> Path:
        """Save a checkpoint for a phase."""
        path = self.get_run_dir(run_id) / f"checkpoint_{phase}.json"
        write_json(data, path)
        log.info("saved_checkpoint", run_id=run_id, phase=phase)
        return path

    def list_runs(self) -> list[str]:
        """List all run IDs."""
        if not self.runs_dir.exists():
            return []
        return sorted([d.name for d in self.runs_dir.iterdir() if d.is_dir()])
