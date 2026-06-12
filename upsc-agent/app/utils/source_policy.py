"""
UPSC Daily Digest — Source Policy Module
==========================================
Single source of truth for:
  - LLM-based relevance classification

All filtering is done solely by the LLM. No hardcoded keyword lists,
no protected sources — every article from every tier is evaluated
equally by the classifier.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from app.utils.logging import get_logger

log = get_logger(__name__)


# ============================================================
# LLM-BASED RELEVANCE CLASSIFICATION
# Replaces all hardcoded keyword/category filtering with a
# single LLM call per article for nuanced content classification.
# ============================================================

CLASSIFICATION_SYSTEM_PROMPT = """You are a UPSC Civil Services news relevance classifier. Your ONLY job is to decide whether a news article is relevant to UPSC preparation or should be DROPPED as noise.

Respond with ONLY a valid JSON object: {"relevant": true, "reason": "..."} or {"relevant": false, "reason": "..."}
The "reason" field must be 10 words or fewer.

=== INCLUDE (relevant = true) ===
- Government policy, legislation, bills, ordinances, executive orders
- Court judgments: Supreme Court, High Courts, tribunals, landmark rulings
- Constitutional matters: amendments, Article interpretations, federalism
- International relations: treaties, bilateral/multilateral summits, diplomacy, foreign policy
- Economy: RBI policy, fiscal/monetary policy, trade agreements, GDP, inflation, budgets, banking reforms
- Science & technology: ISRO, DRDO, nuclear, biotech, AI policy, digital governance
- Environment & biodiversity: climate change, conservation, wildlife, pollution policy, international environmental agreements
- Social issues with policy angle: education reform, health policy, caste/reservation policy, gender policy, tribal rights
- Awards & achievements at national/international level: Padma awards, Bharat Ratna, Nobel Prize, Booker Prize, Olympic/World Cup medals, cricket World Cup/trophy wins, national sports awards (Arjuna, Khel Ratna, Dronacharya)
- Governance reforms: electoral reforms, anti-corruption measures, e-governance, administrative reforms
- Internal security: terrorism, insurgency, border security, cyber security policy, Naxalism, defence acquisitions
- Defence: military exercises, defence deals, strategic partnerships, border disputes
- Disasters & disaster management: earthquakes, floods, cyclones, NDMA policy
- Reports by government bodies: NITI Aayog, CAG, parliamentary committees, Law Commission, Finance Commission, NSSO surveys, Census data, Economic Survey
- Infrastructure: major projects (railways, highways, ports, smart cities) with policy significance
- Union Budget, State Budgets, fiscal policy announcements, GST Council decisions
- Ethics in governance: whistleblower cases, corruption convictions, institutional integrity, conflict of interest (GS4 relevant)
- Historical/cultural events with national significance

=== EXCLUDE (relevant = false) ===
- Local/routine crime: individual murders, robberies, kidnappings, chain-snatching, road accidents, domestic disputes, bar brawls, stalking cases, dowry deaths, honour killings, love triangle murders, suicide cases, petty theft, burglary, shoplifting
- Celebrity/entertainment gossip: personal life, weddings, breakups, divorces, affairs, selfies, viral videos, social media drama, fan reactions, birthday celebrations, vacation photos, photoshoots, red carpet
- Bollywood/Hollywood/Tollywood: movie reviews, box office collections, trailer launches, OTT releases, web series, album launches, concerts, reality shows (Bigg Boss etc.), award shows (Filmfare, IIFA), standup comedy
- Lifestyle content: recipes, cooking tips, fashion trends, beauty tips, skincare, fitness tips, workout routines, diet plans, weight loss, travel guides, hotel reviews, home decor, parenting tips, pet care, gardening tips, relationship advice, dating tips, self-help
- Sports match results & league updates: cricket scores, IPL match results/auctions/playoffs, football league scores (Premier League, La Liga etc.), tennis match results, F1 race results, kabaddi/hockey scores, fantasy cricket/football, player transfers, playing XI, Dream11
- Inter-party political mudslinging: Party A blames/attacks/slams Party B, opposition criticizes ruling party (or vice versa) with NO policy substance, political blame-games, "war of words" between politicians, personal attacks between politicians — UNLESS the exchange is about a specific policy, bill, or governance issue
- Horoscopes, astrology, numerology, vastu tips, tarot, rashifal, kundli
- Product reviews, gadget reviews, smartphone/laptop/earbuds reviews, unboxing
- Deals, sales, discount offers, sponsored content, advertorials, brand stories
- Real estate prices, home loan tips, stock tips, mutual fund picks, EMI calculators, credit card offers
- Daily commodity prices (gold/silver/petrol/diesel price today)
- Puzzles, crosswords, sudoku, quizzes, trivia
- Weather forecasts, traffic updates, power cut schedules, water supply, school holidays, exam date sheets

=== EDGE CASES — PAY ATTENTION ===
- "Sports Ministry reforms cricket governance" → INCLUDE (policy angle)
- "India wins World Cup trophy" → INCLUDE (national achievement)
- "Virat Kohli scores century in IPL match" → EXCLUDE (match result)
- "Sachin receives Bharat Ratna" → INCLUDE (national award)
- "BJP slams Congress over farm bill" → INCLUDE (policy substance: farm bill)
- "BJP calls Congress corrupt, Congress hits back" → EXCLUDE (mudslinging, no policy)
- "Actress wedding photos go viral" → EXCLUDE (celebrity gossip)
- "Film director wins National Film Award" → INCLUDE (national award)
- "New Netflix series review" → EXCLUDE (entertainment)
- "Murder accused arrested in Delhi" → EXCLUDE (local crime)
- "NCRB releases annual crime statistics report" → INCLUDE (government report/data)
- "Communal violence erupts in state X" → INCLUDE (internal security)

Return ONLY the JSON object. No explanation, no markdown."""


def classify_article_relevance(
    articles: list[dict[str, Any]],
    api_key: str,
    base_url: str,
    model: str,
    max_retries: int = 3,
    timeout: int = 60,
    delay: float = 0.5,
    max_workers: int = 8,
) -> dict[str, dict[str, Any]]:
    """Classify UPSC relevance for a list of articles using parallel LLM calls.

    Each article dict must have keys: article_id, title, clean_text, category.

    Args:
        articles: List of article dicts to classify.
        api_key: API key for the LLM service.
        base_url: Base URL for the LLM service.
        model: Model name for classification (should be fast model).
        max_retries: Max retry attempts per LLM call.
        timeout: Timeout per LLM call in seconds.
        delay: Delay between calls for rate limiting.
        max_workers: Number of parallel classification threads.

    Returns:
        Dict mapping article_id -> {"relevant": bool, "reason": str}
    """
    from app.services.llm_client import LLMClient

    if not articles:
        return {}

    results: dict[str, dict[str, Any]] = {}
    total_calls = 0
    total_tokens = 0

    def classify_single(article: dict) -> tuple[str, dict, int, int]:
        """Classify a single article. Returns (article_id, result, calls, tokens)."""
        article_id = article["article_id"]
        title = article.get("title", "")
        # Use first 800 chars of clean_text as snippet for classification
        snippet = article.get("clean_text", "")[:800]
        category = article.get("category", "General")

        llm = LLMClient(
            api_key=api_key,
            base_url=base_url,
            model=model,
            max_retries=max_retries,
            timeout=timeout,
            delay=delay,
        )

        try:
            result = llm.classify_relevance(
                system_prompt=CLASSIFICATION_SYSTEM_PROMPT,
                article_title=title,
                article_snippet=snippet,
                article_category=category,
                article_id=article_id,
            )
            return article_id, result, llm.total_calls, llm.total_tokens
        except Exception as e:
            log.error(
                "classification_failed",
                article_id=article_id,
                title=title,
                error=str(e),
            )
            # On failure, default to INCLUDE (don't drop articles we can't classify)
            return article_id, {"relevant": True, "reason": f"classification error: {e}"}, 0, 0

    log.info(
        "classification_start",
        article_count=len(articles),
        model=model,
        max_workers=max_workers,
    )

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(classify_single, art): art for art in articles}

        for idx, future in enumerate(as_completed(futures)):
            article = futures[future]
            try:
                article_id, result, calls, tokens = future.result()
                results[article_id] = result
                total_calls += calls
                total_tokens += tokens

                log.debug(
                    "article_classified",
                    article_id=article_id,
                    title=article.get("title", "")[:80],
                    relevant=result["relevant"],
                    reason=result["reason"],
                    progress=f"{idx + 1}/{len(articles)}",
                )
            except Exception as e:
                article_id = article.get("article_id", "unknown")
                log.error("classification_thread_failed", article_id=article_id, error=str(e))
                results[article_id] = {"relevant": True, "reason": f"thread error: {e}"}

    elapsed = time.time() - start_time
    relevant_count = sum(1 for r in results.values() if r["relevant"])
    dropped_count = sum(1 for r in results.values() if not r["relevant"])

    log.info(
        "classification_complete",
        total_articles=len(articles),
        relevant=relevant_count,
        dropped=dropped_count,
        elapsed_seconds=round(elapsed, 1),
        llm_calls=total_calls,
        llm_tokens=total_tokens,
    )

    return results
