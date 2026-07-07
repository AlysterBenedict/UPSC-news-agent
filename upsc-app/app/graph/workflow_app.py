"""
UPSC Daily Digest — LangGraph Workflow Definition
===================================================
StateGraph with 10 nodes connected in a sequential pipeline.
Supports checkpointing and resumability via SQLite.

FIX: Added conditional routing after ingest and normalize nodes
to fail fast when data is empty, preventing blank PDF generation.
"""

from __future__ import annotations

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from app.graph.state_app import DigestState
from app.agents.ingestion_app import ingest_articles
from app.agents.normalize_app import normalize_articles
from app.agents.dedup_app import deduplicate_articles
from app.agents.analyze_app import analyze_clusters
from app.agents.verify_app import verify_units
from app.agents.map_upsc_app import map_to_sections
from app.agents.write_sections_app import write_sections
from app.agents.assemble_app import assemble_document
from app.agents.render_pdf_app import render_pdf
from app.agents.deliver_app import deliver_digest
from app.agents.audit_app import generate_audit_report
from app.utils.logging_app import get_logger

log = get_logger(__name__)


# =============================================================================
# ABORT NODE — Sets a clear error when the pipeline short-circuits
# =============================================================================

def abort_pipeline(state: dict) -> dict:
    """Abort node: carries the failure reason to the final state."""
    reason = state.get("abort_reason", "Pipeline aborted due to empty data.")
    log.error("pipeline_aborted", reason=reason)
    print(f"\n{'='*60}")
    print(f"  [ABORT] Pipeline stopped: {reason}")
    print(f"{'='*60}\n")
    return {
        "current_phase": "aborted",
        "errors": [{
            "phase": "pipeline",
            "error_type": "pipeline_abort",
            "message": reason,
        }],
    }


# =============================================================================
# CONDITIONAL ROUTERS — Check for empty data at critical points
# =============================================================================

def check_after_ingest(state: dict) -> str:
    """Route after ingestion: continue if we have articles, abort if empty."""
    articles = state.get("articles_raw", [])
    phase = state.get("current_phase", "")

    if not articles or phase == "ingestion_failed":
        reason = state.get("abort_reason") or (
            "Ingestion produced no articles. The scraper may have failed "
            "or no scraped_articles JSON file was found for this date. "
            "Check that the scraper ran successfully and produced output."
        )
        log.error("check_after_ingest_failed", article_count=len(articles), phase=phase)
        return "abort"

    log.info("check_after_ingest_ok", article_count=len(articles))
    return "normalize"


def check_after_normalize(state: dict) -> str:
    """Route after normalization: continue if we have normalized articles, abort if empty."""
    articles = state.get("articles_normalized", [])

    if not articles:
        log.error("check_after_normalize_failed", article_count=0)
        return "abort_normalize"

    log.info("check_after_normalize_ok", article_count=len(articles))
    return "deduplicate"


def abort_after_normalize(state: dict) -> dict:
    """Abort node for normalization failure."""
    reason = (
        "Normalization produced no articles. All articles may have been "
        "classified as irrelevant by the LLM, or the LLM API calls failed. "
        "Check your NIM API key and network connection."
    )
    log.error("pipeline_aborted_after_normalize", reason=reason)
    print(f"\n{'='*60}")
    print(f"  [ABORT] Pipeline stopped: {reason}")
    print(f"{'='*60}\n")
    return {
        "current_phase": "aborted",
        "abort_reason": reason,
        "errors": [{
            "phase": "normalize",
            "error_type": "pipeline_abort",
            "message": reason,
        }],
    }


# =============================================================================
# WORKFLOW BUILDER
# =============================================================================

def build_workflow(checkpoint_db_path: str | None = None) -> StateGraph:
    """
    Build the UPSC Digest LangGraph workflow.

    Pipeline:
    START → ingest → [check] → normalize → [check] → deduplicate → analyze
          → verify → map_upsc → write_sections → assemble → render
          → deliver → audit → END

    FIX: Conditional edges after ingest and normalize abort the pipeline
    when data is empty, instead of cascading empty data through all nodes.
    """
    # Build the graph
    workflow = StateGraph(DigestState)

    # Add all agent nodes
    workflow.add_node("ingest", ingest_articles)
    workflow.add_node("normalize", normalize_articles)
    workflow.add_node("deduplicate", deduplicate_articles)
    workflow.add_node("analyze", analyze_clusters)
    workflow.add_node("verify", verify_units)
    workflow.add_node("map_upsc", map_to_sections)
    workflow.add_node("write_sections", write_sections)
    workflow.add_node("assemble", assemble_document)
    workflow.add_node("render", render_pdf)
    workflow.add_node("deliver", deliver_digest)
    workflow.add_node("audit", generate_audit_report)

    # Abort nodes for clean short-circuit
    workflow.add_node("abort", abort_pipeline)
    workflow.add_node("abort_normalize", abort_after_normalize)

    # Define edges with conditional routing at critical checkpoints
    workflow.add_edge(START, "ingest")

    # FIX: After ingestion, check if we have articles before continuing
    workflow.add_conditional_edges(
        "ingest",
        check_after_ingest,
        {"normalize": "normalize", "abort": "abort"},
    )

    # FIX: After normalization, check if we have normalized articles
    workflow.add_conditional_edges(
        "normalize",
        check_after_normalize,
        {"deduplicate": "deduplicate", "abort_normalize": "abort_normalize"},
    )

    # Remaining sequential edges
    workflow.add_edge("deduplicate", "analyze")
    workflow.add_edge("analyze", "verify")
    workflow.add_edge("verify", "map_upsc")
    workflow.add_edge("map_upsc", "write_sections")
    workflow.add_edge("write_sections", "assemble")
    workflow.add_edge("assemble", "render")
    workflow.add_edge("render", "deliver")
    workflow.add_edge("deliver", "audit")
    workflow.add_edge("audit", END)

    # Abort nodes go directly to END
    workflow.add_edge("abort", END)
    workflow.add_edge("abort_normalize", END)

    return workflow


def compile_workflow(checkpoint_db_path: str | None = None):
    """Compile the workflow with optional checkpointing."""
    workflow = build_workflow()

    if checkpoint_db_path:
        import sqlite3
        conn = sqlite3.connect(checkpoint_db_path, check_same_thread=False)
        checkpointer = SqliteSaver(conn)
        compiled = workflow.compile(checkpointer=checkpointer)
        log.info("workflow_compiled", checkpointing="sqlite", db=checkpoint_db_path)
    else:
        compiled = workflow.compile()
        log.info("workflow_compiled", checkpointing="none")

    return compiled


def run_workflow(
    run_date: str,
    scraper_output_dir: str,
    checkpoint_db_path: str | None = None,
    run_id: str | None = None,
    skip_delivery: bool = False,
    skip_scrape: bool = False,
) -> dict:
    """
    Execute the full digest pipeline.

    Args:
        run_date: Date string (YYYY-MM-DD)
        scraper_output_dir: Path to scraper output directory
        checkpoint_db_path: SQLite path for checkpointing
        run_id: Optional run ID (auto-generated if None)
        skip_delivery: If True, do not send PDF via email
        skip_scrape: If True, skip running the scraper and use cached file
    """
    from app.agents.ingestion_app import generate_run_id

    if not run_id:
        run_id = generate_run_id(run_date)

    log.info("workflow_start", run_id=run_id, run_date=run_date, skip_delivery=skip_delivery, skip_scrape=skip_scrape)

    # Initial state
    initial_state: dict = {
        "run_id": run_id,
        "run_date": run_date,
        "scraper_output_dir": scraper_output_dir,
        "skip_scrape": skip_scrape,
        "articles_raw": [],
        "articles_normalized": [],
        "article_clusters": [],
        "analyzed_units": [],
        "verified_units": [],
        "section_buffers": {},
        "section_fragments": {},
        "top_story_ids": [],
        "compiled_html_path": None,
        "compiled_pdf_path": None,
        "delivery_status": None,
        "current_phase": "starting",
        "skip_delivery": skip_delivery,
        "metrics": {},
        "errors": [],
        "abort_reason": None,
    }

    # Compile and run
    app = compile_workflow(checkpoint_db_path)

    config = {"configurable": {"thread_id": run_id}}

    for event in app.stream(initial_state, config=config):
        # Log progress
        for node_name, node_output in event.items():
            phase = node_output.get("current_phase", "")
            log.info("node_complete", node=node_name, phase=phase)

    # Retrieve the full final state from LangGraph
    final_state = app.get_state(config).values
    log.info("workflow_complete", run_id=run_id)

    return final_state
