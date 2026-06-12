"""
UPSC Daily Digest — Article Analysis Agent
============================================
Processes one cluster at a time using the LLM.
Extracts source-grounded structured UPSC analysis.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from app.models.schemas import AnalysisUnit, EvidenceItem, ErrorRecord
from app.utils.logging import get_logger
from app.utils.text import truncate_text

from app.utils.syllabus import SYLLABUS_MAP

log = get_logger(__name__)

# Build compact syllabus code list for the prompt (descriptions resolved post-hoc
# by write_sections.py's syllabus resolver, saving ~500 tokens per call)
_syllabus_codes_str = ", ".join(SYLLABUS_MAP.keys())

ANALYSIS_SYSTEM_PROMPT = f"""You are a UPSC Current Affairs Analysis Expert. Your job is to analyze a news article and extract structured, source-grounded UPSC-relevant information.

CRITICAL RULES:
1. Extract ONLY facts present in the source text. Do NOT speculate or add information not in the article.
2. Preserve exact numbers, names, institutions, dates, and figures as they appear.
3. Map content to specific UPSC GS papers and subtopics.
4. Identify prelims-worthy facts (specific names, numbers, schemes, institutions) separately from mains-worthy analysis.
5. Every claim in factual_summary MUST be directly traceable to the source text.
6. Provide evidence_map linking each key claim to a direct quote from the article.
7. Map the article to one or more specific UPSC syllabus codes from the list below. Assign these codes to the `syllabus_codes` array field.
8. Identify arguments/facts supporting the reform/policy/event for `mains_arguments_favor`, and challenges/limitations/criticisms for `mains_challenges_concerns`.
9. Extract Prelims structured metadata in `prelims_metadata` with keys: `nodal_ministry_or_agency`, `constitutional_or_statutory_status`, `constitutional_articles_or_amendments`, `iucn_or_conservation_status`. If any field is not applicable or not in the text, use "N/A".
10. Generate a `revision_one_line_summary`: A single concise sentence (max 20 words) that captures EXACTLY what happened — like a newspaper headline but slightly more informative. This is for a quick revision cheat sheet.
11. Generate `revision_key_data_points`: Extract ONLY the 2-3 most important numbers, statistics, or named facts from the article. Each must be short (under 15 words). If no quantitative data exists, use the most critical named entities or dates. This is for quick revision, not exhaustive listing.
12. Assign `primary_category` — the SINGLE best-fit section for this article. Choose from: "gs2_polity", "gs2_ir", "gs3_economy", "gs3_environment", "gs3_scitech", "gs1_society", "editorial", "pib". If an article covers multiple GS papers, assign all to `gs_papers` but put the PRIMARY topic first in that array.

OFFICIAL UPSC SYLLABUS CODES (pick from these):
{_syllabus_codes_str}

OUTPUT FORMAT: Return ONLY valid JSON matching this exact schema:
{{
  "title": "Concise event/topic title",
  "factual_summary": ["Fact 1 from article", "Fact 2 from article", ...],
  "why_it_matters": ["Significance point 1", "Significance point 2"],
  "background_context": ["Any background context mentioned in the article"],
  "gs_papers": ["GS1", "GS2", "GS3", "GS4"],
  "topics": ["Polity", "Economy", "IR", "Environment", "Science", "Society", "Governance", "Internal Security"],
  "prelims_facts": ["Specific fact for prelims: name/number/scheme/institution"],
  "mains_angles": ["Analytical angle for mains answer writing"],
  "static_links": ["Connected static/theory topic from UPSC syllabus"],
  "syllabus_codes": ["GS2.1", "GS3.5"],
  "mains_arguments_favor": ["Argument in favor 1", "Argument in favor 2"],
  "mains_challenges_concerns": ["Concern/challenge 1", "Concern/challenge 2"],
  "prelims_metadata": {{
    "nodal_ministry_or_agency": "Ministry/Agency name or N/A",
    "constitutional_or_statutory_status": "Statutory/Constitutional/Executive or N/A",
    "constitutional_articles_or_amendments": "Relevant Articles/Acts or N/A",
    "iucn_or_conservation_status": "IUCN/WPA conservation status or N/A"
  }},
  "entities": ["Named entities: persons, orgs, places, treaties, acts"],
  "data_points": ["Specific numbers, statistics, amounts mentioned"],
  "way_forward": ["Policy suggestions or forward-looking points from the article"],
  "implications": ["Short and long-term implications mentioned or clearly implied"],
  "revision_one_line_summary": "Single sentence (max 20 words) capturing exactly what happened",
  "revision_key_data_points": ["Most critical stat/number 1", "Most critical stat/number 2"],
  "evidence_map": [
    {{
      "claim": "A key factual claim",
      "article_id": "the article ID",
      "evidence_span": "Exact quote from the article supporting this claim"
    }}
  ],
  "primary_category": "gs2_polity",
  "upsc_relevance_score": 7.5,
  "confidence": 0.85
}}

SCORING GUIDE for upsc_relevance_score (1-10):
- 9-10: Direct UPSC syllabus topic (constitutional amendment, landmark judgment, major policy, international treaty)
- 7-8: High relevance (government scheme, bilateral relations, economic policy, environment regulation)
- 5-6: Moderate relevance (state politics, business news, scientific discovery)
- 3-4: Low relevance (human interest, entertainment-adjacent, routine events)
- 1-2: Minimal relevance (celebrity news, sports without policy angle)

Return ONLY the JSON object. No markdown, no explanation."""


def analyze_clusters(state: dict) -> dict:
    """
    Analysis Agent: Process clusters in parallel through LLM.

    Filters out single-article clusters from Tier 3 sources, then uses a
    ThreadPoolExecutor to run LLM analysis concurrently.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from app.services.llm_client import LLMClient
    from config.settings import get_settings

    settings = get_settings()
    clusters = state.get("article_clusters", [])
    run_id = state.get("run_id", "unknown")
    existing_units = state.get("analyzed_units", [])

    # Skip already-analyzed clusters (for resumability)
    analyzed_ids = {u["unit_id"] for u in existing_units}
    pending = [c for c in clusters if c["cluster_id"] not in analyzed_ids]

    # Quality and Page-Budget Optimization: Score quality and cap clusters
    # NOTE: Noise filtering is now handled upstream by LLM classification in normalize.py
    articles_normalized = state.get("articles_normalized", [])
    article_tier_map = {a["article_id"]: a.get("tier", 3) for a in articles_normalized}
    article_source_map = {a["article_id"]: a.get("source", "") for a in articles_normalized}
    # Build source_section lookup for leveraging newspaper's own categorization
    article_section_map = {a["article_id"]: a.get("source_section", "").lower() for a in articles_normalized}
    
    # HIGH-VALUE source sections (from the newspaper's own classification)
    UPSC_PRIORITY_SECTIONS = frozenset([
        "editorials", "editorial", "explained", "upsc", "political pulse",
        "international", "world", "business", "economy", "policy",
        "environment", "science", "defence", "governance",
    ])
    
    scored_pending = []

    for c in pending:
        primary_id = c.get("primary_article_id")
        tier = article_tier_map.get(primary_id, 3)
        all_article_ids = [primary_id] + c.get("supporting_article_ids", [])
        
        # Build source_sections for scoring
        source_sections = [article_section_map.get(aid, "") for aid in all_article_ids]
            
        # Calculate heuristic importance score for quality selection
        # consensus: +10 pts per source/article in cluster (max 50)
        article_count = c.get("article_count", 1)
        consensus_score = min(article_count, 5) * 10
        
        # source quality: Tier 1 = 30, Tier 2 = 20, Tier 3 = 10
        tiers = [article_tier_map.get(aid, 3) for aid in all_article_ids]
        min_tier = min(tiers) if tiers else tier
        source_score = (4 - min_tier) * 10
        
        # content type: editorials, opinions, and analysis are highly relevant for UPSC Mains
        categories = [cat.lower() for cat in c.get("categories", [])]
        category_score = 0
        if any(cat in categories for cat in ["editorial", "analysis", "opinion"]):
            category_score = 25
        elif any(cat in categories for cat in ["polity", "governance", "government policy",
                                                 "international relations", "foreign policy"]):
            category_score = 20
        elif any(cat in categories for cat in ["economy", "environment", "science & tech",
                                                 "internal security", "upsc specific"]):
            category_score = 15
        elif "national" in categories:
            category_score = 10
        
        # SOURCE SECTION bonus: newspaper's own categorization is high-confidence signal
        section_score = 0
        for ss in source_sections:
            if ss in UPSC_PRIORITY_SECTIONS:
                section_score = max(section_score, 15)
                break
            
        score = consensus_score + source_score + category_score + section_score
        scored_pending.append((score, c))

    # Sort in descending order of score (highest priority first)
    scored_pending.sort(key=lambda x: x[0], reverse=True)
    
    # No cap — analyze ALL quality clusters. Page budget enforced at write time.
    pending = [item[1] for item in scored_pending]
    
    log.info(
        "analysis_filtering_and_budgeting",
        original_pending=len(clusters),
        after_scoring=len(scored_pending),
        selected_to_analyze=len(pending),
    )

    if not pending:
        return {"analyzed_units": existing_units, "current_phase": "analyzed"}

    analyzed_units = list(existing_units)
    errors = []

    # Thread worker function
    def analyze_single_cluster(cluster: dict) -> tuple[dict | None, dict | None, int, int]:
        cluster_id = cluster["cluster_id"]
        llm = LLMClient(
            api_key=settings.nim_api_key,
            base_url=settings.nim_base_url,
            model=settings.nim_model,
            max_retries=settings.llm_max_retries,
            timeout=settings.llm_timeout,
            delay=settings.llm_delay_seconds,
        )
        try:
            # Prepare article text (truncate to fit context window)
            article_text = truncate_text(cluster.get("combined_text", ""), max_chars=32000)
            article_title = cluster.get("representative_title", "Untitled")
            sources = ", ".join(cluster.get("sources", []))
            primary_id = cluster.get("primary_article_id", cluster_id)

            # Call LLM
            result = llm.analyze_article(
                system_prompt=ANALYSIS_SYSTEM_PROMPT,
                article_text=article_text,
                article_title=article_title,
                article_source=sources,
                article_id=primary_id,
            )

            if not result:
                log.warning("empty_analysis_result", cluster_id=cluster_id)
                err = ErrorRecord(
                    phase="analysis",
                    article_id=primary_id,
                    error_type="empty_result",
                    message=f"LLM returned empty result for {cluster_id}",
                ).model_dump()
                return None, err, llm.total_calls, llm.total_tokens

            # Build AnalysisUnit
            article_ids = [primary_id] + cluster.get("supporting_article_ids", [])

            unit = AnalysisUnit(
                unit_id=cluster_id,
                article_ids=article_ids,
                title=result.get("title", article_title),
                factual_summary=result.get("factual_summary", []),
                why_it_matters=result.get("why_it_matters", []),
                background_context=result.get("background_context", []),
                gs_papers=result.get("gs_papers", cluster.get("gs_papers", [])),
                topics=result.get("topics", []),
                prelims_facts=result.get("prelims_facts", []),
                mains_angles=result.get("mains_angles", []),
                static_links=result.get("static_links", []),
                syllabus_codes=result.get("syllabus_codes", []),
                entities=result.get("entities", []),
                data_points=result.get("data_points", []),
                way_forward=result.get("way_forward", []),
                implications=result.get("implications", []),
                mains_arguments_favor=result.get("mains_arguments_favor", []),
                mains_challenges_concerns=result.get("mains_challenges_concerns", []),
                prelims_metadata=result.get("prelims_metadata", {}),
                evidence_map=[
                    EvidenceItem(**e) if isinstance(e, dict) else e
                    for e in result.get("evidence_map", [])
                    if isinstance(e, dict) and "claim" in e
                ],
                revision_one_line_summary=result.get("revision_one_line_summary", ""),
                revision_key_data_points=result.get("revision_key_data_points", []),
                primary_category=result.get("primary_category", ""),
                upsc_relevance_score=float(result.get("upsc_relevance_score", 5.0)),
                confidence=float(result.get("confidence", 0.5)),
            )

            return unit.model_dump(), None, llm.total_calls, llm.total_tokens

        except Exception as e:
            log.error("analysis_error", cluster_id=cluster_id, error=str(e))
            err = ErrorRecord(
                phase="analysis",
                article_id=cluster.get("primary_article_id"),
                error_type="analysis_exception",
                message=str(e),
            ).model_dump()
            return None, err, 0, 0

    # Execute parallel queries
    max_workers = 8
    total_calls = 0
    total_tokens = 0
    log.info("analysis_parallel_start", workers=max_workers, pending_count=len(pending))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(analyze_single_cluster, c): c for c in pending}
        
        for idx, future in enumerate(as_completed(futures)):
            cluster = futures[future]
            cluster_id = cluster["cluster_id"]
            try:
                unit_dict, error_dict, calls, tokens = future.result()
                total_calls += calls
                total_tokens += tokens

                if unit_dict:
                    analyzed_units.append(unit_dict)
                    log.info(
                        "cluster_analyzed",
                        cluster_id=cluster_id,
                        progress=f"{idx+1}/{len(pending)}",
                        relevance=unit_dict["upsc_relevance_score"],
                        facts=len(unit_dict["factual_summary"]),
                        prelims=len(unit_dict["prelims_facts"]),
                    )
                if error_dict:
                    errors.append(error_dict)
            except Exception as e:
                log.error("thread_execution_failed", cluster_id=cluster_id, error=str(e))
                errors.append(ErrorRecord(
                    phase="analysis",
                    article_id=cluster.get("primary_article_id"),
                    error_type="thread_exception",
                    message=f"Thread execution failed: {e}",
                ).model_dump())

    log.info(
        "analysis_complete",
        run_id=run_id,
        analyzed=len(analyzed_units),
        errors=len(errors),
        llm_stats={"total_calls": total_calls, "total_tokens": total_tokens},
    )

    return {
        "analyzed_units": analyzed_units,
        "errors": errors,
        "current_phase": "analyzed",
    }
