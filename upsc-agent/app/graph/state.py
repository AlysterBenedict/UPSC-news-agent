"""
UPSC Daily Digest — LangGraph State Definition
================================================
Strongly typed shared workflow state with annotated reducers.
"""

from __future__ import annotations

import operator
from typing import Annotated, Optional, TypedDict


class DigestState(TypedDict, total=False):
    """
    Shared state for the UPSC Digest LangGraph workflow.

    Uses Annotated[list, operator.add] for list fields so that
    each node can return partial updates that get merged.
    """
    # Run identity
    run_id: str
    run_date: str
    scraper_output_dir: str
    skip_scrape: bool

    # Pipeline data (accumulated via operator.add)
    articles_raw: Annotated[list[dict], operator.add]
    articles_normalized: Annotated[list[dict], operator.add]
    article_clusters: Annotated[list[dict], operator.add]
    analyzed_units: Annotated[list[dict], operator.add]
    verified_units: Annotated[list[dict], operator.add]

    # Section data (replaced, not accumulated)
    section_buffers: dict[str, list[dict]]
    section_fragments: dict[str, list[str]]
    top_story_ids: list[str]

    # Output paths
    compiled_html_path: Optional[str]
    compiled_pdf_path: Optional[str]

    # Status
    delivery_status: Optional[str]
    current_phase: str
    skip_delivery: bool

    # Metrics and errors (errors accumulated via operator.add)
    metrics: dict
    errors: Annotated[list[dict], operator.add]
