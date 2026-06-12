"""
UPSC Daily Digest — UPSC Mapping Agent
========================================
Routes verified units into appropriate section buffers.
Each unit goes to exactly ONE primary section to avoid duplication.

Uses a multi-signal routing strategy:
  1. Source-level category from the newspaper (highest confidence)
  2. LLM-assigned category from analysis
  3. Topic keyword matching (fine-grained disambiguation)
  4. GS paper fallback

Applies a hard relevance floor to exclude low-value content.
"""

from __future__ import annotations

from app.models.schemas import SectionBufferItem, ContentDepth, SectionName
from app.utils.logging import get_logger

log = get_logger(__name__)

# ============================================================
# CONTENT DEPTH THRESHOLDS — Used for depth assignment only,
# NOT for dropping articles.
# ============================================================
HIGH_RELEVANCE_THRESHOLD = 7.0    # Full depth treatment
MEDIUM_RELEVANCE_THRESHOLD = 5.0  # Medium depth treatment

# ============================================================
# SOURCE SECTION → Section routing (from newspaper's own categorization)
# This is the HIGHEST confidence signal — newspapers know their own content
# ============================================================
SOURCE_SECTION_MAP = {
    # Indian Express sections
    "editorials": SectionName.EDITORIAL,
    "explained": SectionName.EDITORIAL,
    "political pulse": SectionName.GS2_POLITY,
    "upsc": SectionName.GS2_POLITY,         # IE UPSC section = governance-heavy
    "world": SectionName.GS2_IR,
    "science": SectionName.GS3_SCITECH,
    # The Hindu sections
    "editorial": SectionName.EDITORIAL,
    "international": SectionName.GS2_IR,
    "business": SectionName.GS3_ECONOMY,
    "national": None,                        # Too broad — fall through to category
    "environment": SectionName.GS3_ENVIRONMENT,
    # Economic Times / Livemint
    "economy": SectionName.GS3_ECONOMY,
    "policy": SectionName.GS3_ECONOMY,
    "politics": SectionName.GS2_POLITY,
    # The Print
    "defence": SectionName.GS2_POLITY,      # Internal security under GS2
    # Down To Earth
    "governance": SectionName.GS2_POLITY,
    # The Wire / Scroll / ToI
    "india": None,                           # Too broad — fall through
}

# Category → Section mapping (from scraper's category field)
CATEGORY_SECTION_MAP = {
    "Editorial": SectionName.EDITORIAL,
    "Analysis": SectionName.EDITORIAL,
    "Polity": SectionName.GS2_POLITY,
    "Governance": SectionName.GS2_POLITY,
    "Government Policy": SectionName.GS2_POLITY,
    "Internal Security": SectionName.GS2_POLITY,
    "International Relations": SectionName.GS2_IR,
    "Foreign Policy": SectionName.GS2_IR,
    "Economy": SectionName.GS3_ECONOMY,
    "Environment": SectionName.GS3_ENVIRONMENT,
    "Science & Tech": SectionName.GS3_SCITECH,
    "UPSC Specific": SectionName.GS2_POLITY,
}

# GS paper → Section fallback
GS_SECTION_MAP = {
    "GS1": SectionName.GS1_SOCIETY,
    "GS2": SectionName.GS2_POLITY,
    "GS3": SectionName.GS3_ECONOMY,
    "GS4": SectionName.GS2_POLITY,
}

# ============================================================
# TOPIC KEYWORD ROUTING — Fine-grained disambiguation
# Order matters: more specific patterns checked first
# ============================================================
IR_KEYWORDS = frozenset([
    "ir", "international", "diplomacy", "bilateral", "multilateral",
    "foreign", "summit", "treaty", "un", "united nations", "g20", "g7",
    "g77", "nato", "quad", "brics", "asean", "saarc", "bimstec",
    "ambassador", "high commissioner", "visa", "indo-pacific",
    "geopolitics", "strategic", "south china sea", "nuclear deal",
    "extradition", "refugee", "asylum", "sanctions", "ceasefire",
    "peace talks", "war", "conflict", "border dispute",
    "trade war", "wto", "imf", "world bank", "adb",
    "oecd", "iaea", "who", "unesco", "unfccc", "cop",
    "ctbt", "npt", "nsg", "mtcr", "wassenaar",
])

POLITY_KEYWORDS = frozenset([
    "polity", "governance", "constitution", "judiciary", "parliament",
    "supreme court", "high court", "article", "amendment", "panchayat",
    "governor", "rti", "ngt", "election commission", "cag",
    "lok sabha", "rajya sabha", "bill", "act", "ordinance",
    "fundamental rights", "dpsp", "federalism", "centre-state",
    "anti-defection", "privilege motion", "no-confidence",
    "impeachment", "contempt of court", "pil",
    "scheduled tribe", "scheduled caste", "obc", "reservation",
    "delimitation", "evm", "vvpat", "eci", "redistricting",
    "niti aayog", "finance commission", "inter-state council",
    "cms conference", "governors conference",
    "welfare scheme", "dbt", "jan dhan", "ayushman bharat",
    "swachh bharat", "ujjwala", "pmay", "mgnrega",
    "ias", "ips", "civil services", "upsc",
])

ECONOMY_KEYWORDS = frozenset([
    "economy", "rbi", "fiscal", "trade", "inflation", "gdp", "budget",
    "monetary policy", "repo rate", "msme", "fdi", "fpi", "gst",
    "sebi", "stock market", "nse", "bse", "sensex", "nifty",
    "disinvestment", "privatization", "psu",
    "current account", "forex", "rupee depreciation",
    "credit rating", "fiscal deficit", "revenue deficit",
    "capex", "subsidy", "pli scheme", "make in india",
    "startup india", "upi", "digital payments", "fintech",
    "npci", "insurance", "pension", "epfo",
    "agriculture", "msp", "procurement", "apmc",
    "food security", "pds", "buffer stock",
])

ENVIRONMENT_KEYWORDS = frozenset([
    "environment", "ecology", "climate", "biodiversity", "conservation",
    "pollution", "deforestation", "wildlife", "national park",
    "tiger reserve", "wetland", "ramsar", "coral reef",
    "carbon emission", "net zero", "renewable energy", "solar",
    "wind energy", "ev", "electric vehicle", "green hydrogen",
    "waste management", "plastic ban", "air quality", "aqi",
    "ngt order", "eia", "coastal regulation", "crz",
    "forest rights", "sacred grove", "mangrove",
    "endangered species", "iucn", "cites", "cms",
    "water crisis", "river pollution", "ganga rejuvenation",
    "monsoon", "flood", "drought", "cyclone", "glacier",
])

SCITECH_KEYWORDS = frozenset([
    "science", "technology", "space", "ai", "health", "isro", "defence tech",
    "quantum", "semiconductor", "5g", "6g", "satellite",
    "chandrayaan", "gaganyaan", "aditya", "mangalyaan",
    "drdo", "missile", "tejas", "ins", "hal",
    "genome", "crispr", "stem cell", "vaccine",
    "pandemic", "epidemic", "antimicrobial resistance",
    "nuclear energy", "thorium", "fusion",
    "supercomputer", "param", "blockchain",
    "cybersecurity", "data protection", "digital personal data",
    "deep tech", "robotics", "iot", "cloud computing",
    "biotech", "pharma", "drug approval", "clinical trial",
])

SOCIETY_KEYWORDS = frozenset([
    "society", "social", "gender", "caste", "migration", "education",
    "tribal", "rural", "urban", "demography", "census",
    "child marriage", "domestic violence", "dowry",
    "lgbtq", "transgender", "disability", "elderly",
    "poverty", "inequality", "gini coefficient",
    "nep", "education policy", "iit", "iim", "university",
    "healthcare", "malnutrition", "maternal mortality",
    "infant mortality", "sanitation", "open defecation",
    "communalism", "secularism", "regionalism", "linguistic",
    "urbanization", "smart city", "slum",
    "disaster management", "ndrf", "sdma",
    "geography", "plate tectonics", "river system",
    "monsoon mechanism", "ocean current", "soil type",
])

TOPIC_SECTION_MAP = [
    (IR_KEYWORDS, SectionName.GS2_IR),
    (POLITY_KEYWORDS, SectionName.GS2_POLITY),
    (ECONOMY_KEYWORDS, SectionName.GS3_ECONOMY),
    (ENVIRONMENT_KEYWORDS, SectionName.GS3_ENVIRONMENT),
    (SCITECH_KEYWORDS, SectionName.GS3_SCITECH),
    (SOCIETY_KEYWORDS, SectionName.GS1_SOCIETY),
]




def get_content_depth(
    relevance_score: float,
    is_top_story: bool = False,
    evidence_quality: float = 1.0,
) -> ContentDepth:
    """Determine content depth based on relevance score and evidence quality.
    
    Evidence quality (0.0-1.0) can downgrade depth: units with low evidence
    quality are treated more conservatively to avoid presenting unverified
    content at full depth.
    """
    if is_top_story or relevance_score >= 9:
        base = ContentDepth.FULL
    elif relevance_score >= 7:
        base = ContentDepth.MEDIUM
    elif relevance_score >= 5:
        base = ContentDepth.CONCISE
    else:
        base = ContentDepth.PRELIMS_ONLY

    # Downgrade by one level if evidence quality is poor
    if evidence_quality < 0.5 and base != ContentDepth.PRELIMS_ONLY:
        depth_order = [ContentDepth.PRELIMS_ONLY, ContentDepth.CONCISE,
                       ContentDepth.MEDIUM, ContentDepth.FULL]
        idx = depth_order.index(base)
        return depth_order[max(0, idx - 1)]

    return base


def _score_keywords(unit: dict, keyword_set: frozenset) -> int:
    """Count how many keywords from a set appear in unit's topics + title."""
    topics = unit.get("topics", [])
    title = unit.get("title", "")
    text = " ".join(topics).lower() + " " + title.lower()
    return sum(1 for kw in keyword_set if kw in text)


def determine_primary_section(unit: dict) -> str:
    """
    Determine the SINGLE best-fit section for a unit. No duplication.

    Multi-signal routing strategy:
      0. PIB source check (highest priority: must go to PIB section)
      1. Source section from the newspaper (highest confidence)
      2. Scraper-assigned category
      3. Topic keyword scoring (count-based disambiguation)
      4. GS paper fallback
    """
    # 0. Check if any article in this unit is from PIB (case-insensitive)
    sources = unit.get("sources", [])
    if any(s and s.lower() in ("pib", "press information bureau") for s in sources):
        return SectionName.PIB.value

    # 0.5 LLM-assigned primary_category — highest-confidence signal
    # The analysis LLM directly classifies which section fits best
    llm_category = unit.get("primary_category", "")
    VALID_SECTION_VALUES = {s.value for s in SectionName}
    if llm_category and llm_category in VALID_SECTION_VALUES:
        return llm_category

    category = unit.get("category", "")
    topics = unit.get("topics", [])
    gs_papers = unit.get("gs_papers", [])
    source_section = unit.get("source_section", "").lower()

    # 1. Source section routing (newspaper's own categorization — most reliable)
    if source_section:
        for section_key, mapped_section in SOURCE_SECTION_MAP.items():
            if section_key in source_section:
                if mapped_section is not None:
                    return mapped_section.value
                break  # None means "fall through to category"

    # 2. Category-based routing (from scraper's classification)
    for cat, section in CATEGORY_SECTION_MAP.items():
        if cat.lower() in category.lower():
            return section.value

    # 3. Topic keyword scoring (count-based — section with MOST keyword hits wins)
    scores = []
    for keyword_set, section in TOPIC_SECTION_MAP:
        score = _score_keywords(unit, keyword_set)
        if score > 0:
            scores.append((score, section))

    if scores:
        # Pick section with highest keyword match count
        scores.sort(key=lambda x: x[0], reverse=True)
        return scores[0][1].value

    # 4. GS paper fallback (first match)
    for gs in gs_papers:
        if gs in GS_SECTION_MAP:
            return GS_SECTION_MAP[gs].value

    # 5. Default
    return SectionName.GS2_POLITY.value


def map_to_sections(state: dict) -> dict:
    """
    UPSC Mapping Agent: Route verified units into section buffers.

    All noise filtering is handled upstream by LLM classification in normalize.py.
    This agent only handles routing to sections and content depth assignment.
    Each unit goes to exactly ONE primary section.
    Identifies top stories for highlight treatment.
    """
    verified_units = state.get("verified_units", [])
    articles_normalized = state.get("articles_normalized", [])
    run_id = state.get("run_id", "unknown")

    log.info("mapping_start", run_id=run_id, unit_count=len(verified_units))

    # Build source_section and source lookups from normalized articles
    article_section_map = {}
    article_source_map = {}
    for art in articles_normalized:
        article_section_map[art["article_id"]] = art.get("source_section", "")
        article_source_map[art["article_id"]] = art.get("source", "")

    # All units pass through — noise filtering is handled by LLM in normalize.py
    filtered_units = []
    for unit in verified_units:
        # Enrich unit with source_section for routing
        primary_article_id = unit.get("article_ids", [None])[0]
        if primary_article_id and primary_article_id in article_section_map:
            unit["source_section"] = article_section_map[primary_article_id]

        # Get all sources for this unit's articles
        unit["sources"] = [article_source_map.get(aid) for aid in unit.get("article_ids", []) if aid in article_source_map]

        filtered_units.append(unit)

    log.info(
        "mapping_units_prepared",
        run_id=run_id,
        total_units=len(filtered_units),
    )

    # Identify top stories (top 10 by relevance score from FILTERED units)
    sorted_by_relevance = sorted(
        filtered_units,
        key=lambda u: u.get("upsc_relevance_score", 0),
        reverse=True,
    )
    top_story_ids = {u["unit_id"] for u in sorted_by_relevance[:10]}

    # Build section buffers — each unit in exactly ONE section
    section_buffers: dict[str, list[dict]] = {}

    for unit in filtered_units:
        section = determine_primary_section(unit)
        relevance = unit.get("upsc_relevance_score", 5.0)
        evidence_qual = unit.get("evidence_quality", 1.0)
        is_top = unit["unit_id"] in top_story_ids
        depth = get_content_depth(relevance, is_top, evidence_qual)

        # Calculate priority (lower = higher priority)
        tier = unit.get("tier", 3)
        tier_bonus = {1: 0, 2: 1, 3: 2}.get(tier, 2)
        priority = max(1, int(11 - relevance)) + tier_bonus

        if section not in section_buffers:
            section_buffers[section] = []

        buffer_item = SectionBufferItem(
            unit_id=unit["unit_id"],
            section=section,
            priority=priority,
            content_depth=depth,
            sources=[],
        )
        section_buffers[section].append(buffer_item.model_dump())

    # Sort each buffer by priority (ascending = highest priority first)
    for section in section_buffers:
        section_buffers[section].sort(key=lambda x: x["priority"])

    # Log section distribution
    section_counts = {s: len(items) for s, items in section_buffers.items()}
    log.info(
        "mapping_complete",
        run_id=run_id,
        section_counts=section_counts,
        total_routings=sum(section_counts.values()),
        top_stories=len(top_story_ids),
    )

    return {
        "section_buffers": section_buffers,
        "top_story_ids": list(top_story_ids),
        "current_phase": "mapped",
    }
