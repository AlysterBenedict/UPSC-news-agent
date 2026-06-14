"""
UPSC Daily Digest — Verification Agent
========================================
Checks every analysis unit against source text.
Removes unsupported claims. Produces verified JSON only.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.models.schemas_app import VerifiedUnit, EvidenceItem, VerificationStatus, ErrorRecord
from app.utils.logging_app import get_logger
from app.utils.text_app import truncate_text
# No imports from source_policy needed in verification anymore

log = get_logger(__name__)

VERIFICATION_SYSTEM_PROMPT = """You are a Fact-Checking Verification Agent. Your job is to compare an analysis output against the original source text and verify every claim.

CRITICAL RULES:
1. Check EVERY claim in factual_summary against the source text.
2. A claim is SUPPORTED if the source text contains information that directly substantiates it.
3. A claim is UNSUPPORTED if there is no evidence in the source text for it.
4. A claim is PARTIALLY SUPPORTED if only part of it can be verified.
5. Remove all unsupported claims entirely.
6. Preserve all supported claims with their evidence spans.
7. Do NOT add new information. Only verify what exists.
8. Be strict: if a specific number, name, or date in a claim doesn't match the source, mark it unsupported.
9. Also verify mains_arguments_favor and mains_challenges_concerns — remove any argument not supported by the source text.
10. Verify revision_one_line_summary — it must accurately reflect what the source text says. If inaccurate, rewrite it to match the source.
11. Verify revision_key_data_points — each must be traceable to the source text. Remove any that are fabricated.
12. Calculate evidence_quality as: count_of_supported_claims / count_of_total_claims_checked. Round to 2 decimal places.

OUTPUT FORMAT: Return ONLY valid JSON:
{
  "verification_status": "pass" | "partial" | "fail",
  "verified_factual_summary": ["Only claims supported by source text"],
  "verified_prelims_facts": ["Only prelims facts found in source"],
  "verified_data_points": ["Only data points confirmed in source"],
  "verified_entities": ["Only entities mentioned in source"],
  "verified_mains_arguments_favor": ["Only supported arguments in favor"],
  "verified_mains_challenges_concerns": ["Only supported challenges/concerns"],
  "verified_revision_one_line_summary": "Verified or corrected one-line summary",
  "verified_revision_key_data_points": ["Only verified key data points"],
  "removed_claims": ["Claims that could not be verified"],
  "evidence_map": [
    {
      "claim": "Verified claim text",
      "article_id": "source article ID",
      "evidence_span": "Exact supporting quote from source"
    }
  ],
  "evidence_quality": 0.85,
  "notes": "Brief verification summary"
}

VERIFICATION STATUS:
- "pass": 80%+ of claims verified, no fabricated content detected
- "partial": 50-80% of claims verified, some unsupported claims removed
- "fail": Less than 50% of claims verified, or fabricated content detected

Return ONLY the JSON object."""


def verify_units(state: dict) -> dict:
    """
    Verification Agent: Check every analysis unit against source text.

    Uses a ThreadPoolExecutor to verify units concurrently in parallel.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from app.services.llm_client_app import LLMClient
    from app.services.settings_app import get_settings

    settings = get_settings()
    analyzed_units = state.get("analyzed_units", [])
    clusters = state.get("article_clusters", [])
    run_id = state.get("run_id", "unknown")
    existing_verified = state.get("verified_units", [])

    # Build cluster lookup for source text
    cluster_map = {c["cluster_id"]: c for c in clusters}

    # Build source lookup from normalized articles
    articles_normalized = state.get("articles_normalized", [])
    article_source_map = {a["article_id"]: a.get("source", "") for a in articles_normalized}

    # Skip already-verified units
    verified_ids = {u["unit_id"] for u in existing_verified}
    pending = [u for u in analyzed_units if u["unit_id"] not in verified_ids]

    log.info("verification_start", run_id=run_id, total_units=len(analyzed_units), pending=len(pending))

    if not pending:
        return {"verified_units": existing_verified, "current_phase": "verified"}

    verified_units = list(existing_verified)
    errors = []

    # Thread worker function
    def verify_single_unit(unit: dict) -> tuple[dict | None, dict | None, int, int]:
        unit_id = unit["unit_id"]
        llm = LLMClient(
            api_key=settings.nim_api_key,
            base_url=settings.nim_base_url,
            model=settings.nim_model,
            max_retries=settings.llm_max_retries,
            timeout=settings.llm_timeout,
            delay=settings.llm_delay_seconds,
        )
        try:
            # Get source text from cluster
            cluster = cluster_map.get(unit_id, {})
            source_text = truncate_text(cluster.get("combined_text", ""), max_chars=32000)

            if not source_text:
                log.warning("no_source_text", unit_id=unit_id)
                raise ValueError(f"No source text available for unit {unit_id}")

            # Call LLM for verification
            analysis_json = json.dumps(unit, default=str, indent=2)
            result = llm.verify_analysis(
                system_prompt=VERIFICATION_SYSTEM_PROMPT,
                analysis_json=analysis_json,
                source_text=source_text,
            )

            if not result:
                log.warning("empty_verification_result", unit_id=unit_id)
                raise ValueError(f"Empty verification result returned by LLM for unit {unit_id}")

            # Build verified unit
            status_str = result.get("verification_status", "partial")
            try:
                status = VerificationStatus(status_str)
            except ValueError:
                status = VerificationStatus.PARTIAL

            # Safely build evidence items — skip individual items that fail validation
            raw_evidence = result.get("evidence_map", unit.get("evidence_map", []))
            safe_evidence = []
            for e in raw_evidence:
                if not isinstance(e, dict) or "claim" not in e:
                    continue
                try:
                    safe_evidence.append(
                        EvidenceItem(**e) if isinstance(e, dict) else e
                    )
                except Exception as ev_err:
                    log.warning(
                        "evidence_item_skipped",
                        unit_id=unit_id,
                        error=str(ev_err),
                        raw_item=str(e)[:200],
                    )

            # Safely parse evidence_quality
            raw_eq = result.get("evidence_quality", 0.5)
            try:
                evidence_quality = float(raw_eq)
            except (TypeError, ValueError):
                evidence_quality = 0.5

            verified = VerifiedUnit(
                unit_id=unit["unit_id"],
                article_ids=unit["article_ids"],
                title=unit["title"],
                factual_summary=result.get("verified_factual_summary", unit.get("factual_summary", [])),
                why_it_matters=unit.get("why_it_matters", []),
                background_context=unit.get("background_context", []),
                gs_papers=unit.get("gs_papers", []),
                topics=unit.get("topics", []),
                prelims_facts=result.get("verified_prelims_facts", unit.get("prelims_facts", [])),
                mains_angles=unit.get("mains_angles", []),
                static_links=unit.get("static_links", []),
                syllabus_codes=unit.get("syllabus_codes", []),
                mains_arguments_favor=result.get("verified_mains_arguments_favor", unit.get("mains_arguments_favor", [])),
                mains_challenges_concerns=result.get("verified_mains_challenges_concerns", unit.get("mains_challenges_concerns", [])),
                prelims_metadata=unit.get("prelims_metadata", {}),
                entities=result.get("verified_entities", unit.get("entities", [])),
                data_points=result.get("verified_data_points", unit.get("data_points", [])),
                way_forward=unit.get("way_forward", []),
                implications=unit.get("implications", []),
                evidence_map=safe_evidence,
                upsc_relevance_score=unit.get("upsc_relevance_score", 5.0),
                revision_one_line_summary=result.get("verified_revision_one_line_summary", unit.get("revision_one_line_summary", "")),
                revision_key_data_points=result.get("verified_revision_key_data_points", unit.get("revision_key_data_points", [])),
                primary_category=unit.get("primary_category", ""),
                confidence=unit.get("confidence", 0.5),
                verification_status=status,
                removed_claims=result.get("removed_claims", []),
                evidence_quality=evidence_quality,
                verified_at=datetime.now(),
            )
            return verified.model_dump(), None, llm.total_calls, llm.total_tokens

        except Exception as e:
            log.error("verification_error", unit_id=unit_id, error=str(e))
            raise e

    # Execute verification in parallel
    max_workers = 8
    total_calls = 0
    total_tokens = 0
    log.info("verification_parallel_start", workers=max_workers, pending_count=len(pending))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(verify_single_unit, u): u for u in pending}
        
        for idx, future in enumerate(as_completed(futures)):
            unit = futures[future]
            unit_id = unit["unit_id"]
            try:
                verified_dict, error_dict, calls, tokens = future.result()
                total_calls += calls
                total_tokens += tokens
                
                if verified_dict:
                    status_str = verified_dict["verification_status"]
                    if status_str == "fail":
                        verified_dict["verification_status"] = "partial"
                        status_str = "partial"
                    verified_units.append(verified_dict)
                    log.info(
                        "unit_verified",
                        unit_id=unit_id,
                        progress=f"{idx+1}/{len(pending)}",
                        status=status_str,
                        evidence_quality=verified_dict["evidence_quality"],
                        removed=len(verified_dict.get("removed_claims", [])),
                    )
                if error_dict:
                    errors.append(error_dict)
            except Exception as e:
                log.error("thread_verification_failed", unit_id=unit_id, error=str(e))
                errors.append({
                    "phase": "verification",
                    "article_id": unit_id,
                    "error_type": type(e).__name__,
                    "message": str(e)[:500],
                    "timestamp": datetime.now().isoformat(),
                })

    log.info(
        "verification_complete",
        run_id=run_id,
        verified=len(verified_units),
        errors=len(errors),
        llm_stats={"total_calls": total_calls, "total_tokens": total_tokens},
    )

    try:
        run_date = state.get("run_date", "unknown")
        output_file = settings.scraper_output_path / f"verification_results_{run_date}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(verified_units, f, indent=2, default=str)
        log.info("verification_results_saved", path=str(output_file))
    except Exception as e:
        log.error("failed_to_save_verification_results", error=str(e))

    return {
        "verified_units": verified_units,
        "errors": errors,
        "current_phase": "verified",
    }
