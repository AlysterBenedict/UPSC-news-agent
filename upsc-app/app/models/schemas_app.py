"""
UPSC Daily Digest — Pydantic Schemas
=====================================
All data models for the pipeline. Strict validation ensures
data integrity across all agents.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


# ============================================================
# Enums
# ============================================================

class GSPaper(str, Enum):
    GS1 = "GS1"
    GS2 = "GS2"
    GS3 = "GS3"
    GS4 = "GS4"


class VerificationStatus(str, Enum):
    PASS = "pass"
    PARTIAL = "partial"
    FAIL = "fail"


class ContentDepth(str, Enum):
    FULL = "full"          # 800-1200 words — relevance 9-10
    MEDIUM = "medium"      # 500-800 words  — relevance 7-8
    CONCISE = "concise"    # 200-400 words  — relevance 5-6
    PRELIMS_ONLY = "prelims_only"  # fact extraction only — below 5


# ============================================================
# Scraper Input Schema
# ============================================================

class RawArticle(BaseModel):
    """Direct mapping from scraper JSON output."""
    title: str
    url: str
    source_name: str
    category: str
    gs_relevance: list[str] = Field(default_factory=list)
    tier: int = 1
    published: str = ""
    full_text: str = ""
    full_text_chars: int = 0
    scrape_method: str = ""
    error: Optional[str] = None
    scraped_at: str = ""

    @field_validator("gs_relevance", mode="before")
    @classmethod
    def ensure_gs_list(cls, v):
        if isinstance(v, str):
            return [v]
        return v or []


# ============================================================
# Normalized Article
# ============================================================

class NormalizedArticle(BaseModel):
    """Cleaned and standardized article."""
    article_id: str
    source: str
    source_section: str
    url: str
    title: str
    published_at: Optional[datetime] = None
    raw_text: str
    clean_text: str
    char_count: int
    category: str
    gs_papers: list[str]
    tier: int
    scrape_method: str


# ============================================================
# Clustering
# ============================================================

class ArticleCluster(BaseModel):
    """Group of related articles about the same event/topic."""
    cluster_id: str
    primary_article_id: str
    supporting_article_ids: list[str] = Field(default_factory=list)
    representative_title: str
    combined_text: str
    sources: list[str]
    categories: list[str]
    gs_papers: list[str]
    similarity_score: float = 0.0
    article_count: int = 1


# ============================================================
# Analysis Output
# ============================================================

class EvidenceItem(BaseModel):
    """Maps a claim to its source evidence."""
    claim: str
    article_id: str
    evidence_span: str

    @field_validator("claim", "article_id", "evidence_span", mode="before")
    @classmethod
    def coerce_to_string(cls, v):
        """LLMs sometimes return a list of strings instead of a single string.
        Join them gracefully so Pydantic validation never crashes."""
        if isinstance(v, list):
            # Filter to strings, join with separator
            return " | ".join(str(item) for item in v)
        return v


class AnalysisUnit(BaseModel):
    """Structured UPSC analysis of one article/cluster."""
    unit_id: str
    article_ids: list[str]
    title: str
    factual_summary: list[str] = Field(default_factory=list)
    why_it_matters: list[str] = Field(default_factory=list)
    background_context: list[str] = Field(default_factory=list)
    gs_papers: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    prelims_facts: list[str] = Field(default_factory=list)
    mains_angles: list[str] = Field(default_factory=list)
    static_links: list[str] = Field(default_factory=list)
    syllabus_codes: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    data_points: list[str] = Field(default_factory=list)
    evidence_map: list[EvidenceItem] = Field(default_factory=list)
    way_forward: list[str] = Field(default_factory=list)
    implications: list[str] = Field(default_factory=list)
    mains_arguments_favor: list[str] = Field(default_factory=list)
    mains_challenges_concerns: list[str] = Field(default_factory=list)
    prelims_metadata: dict[str, str] = Field(default_factory=dict)
    revision_one_line_summary: str = ""
    revision_key_data_points: list[str] = Field(default_factory=list)
    primary_category: str = ""
    upsc_relevance_score: float = 5.0
    confidence: float = 0.5


# ============================================================
# Verified Unit
# ============================================================

class VerifiedUnit(BaseModel):
    """Analysis unit after verification pass."""
    unit_id: str
    article_ids: list[str]
    title: str
    factual_summary: list[str] = Field(default_factory=list)
    why_it_matters: list[str] = Field(default_factory=list)
    background_context: list[str] = Field(default_factory=list)
    gs_papers: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    prelims_facts: list[str] = Field(default_factory=list)
    mains_angles: list[str] = Field(default_factory=list)
    static_links: list[str] = Field(default_factory=list)
    syllabus_codes: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    data_points: list[str] = Field(default_factory=list)
    evidence_map: list[EvidenceItem] = Field(default_factory=list)
    way_forward: list[str] = Field(default_factory=list)
    implications: list[str] = Field(default_factory=list)
    mains_arguments_favor: list[str] = Field(default_factory=list)
    mains_challenges_concerns: list[str] = Field(default_factory=list)
    prelims_metadata: dict[str, str] = Field(default_factory=dict)
    revision_one_line_summary: str = ""
    revision_key_data_points: list[str] = Field(default_factory=list)
    primary_category: str = ""
    upsc_relevance_score: float = 5.0
    confidence: float = 0.5
    # Verification fields
    verification_status: VerificationStatus = VerificationStatus.PASS
    removed_claims: list[str] = Field(default_factory=list)
    evidence_quality: float = 0.5
    verified_at: Optional[datetime] = None


# ============================================================
# Section Routing
# ============================================================

class SectionName(str, Enum):
    NATIONAL_PRIORITY = "national_priority"
    GS2_POLITY = "gs2_polity"
    GS2_IR = "gs2_ir"
    GS3_ECONOMY = "gs3_economy"
    GS3_ENVIRONMENT = "gs3_environment"
    GS3_SCITECH = "gs3_scitech"
    GS1_SOCIETY = "gs1_society"
    EDITORIAL = "editorial"
    PRELIMS_BOOSTER = "prelims_booster"
    MAINS_ENRICHMENT = "mains_enrichment"
    QUICK_REVISION = "quick_revision"
    PIB = "pib"


class SectionBufferItem(BaseModel):
    """Routing of a verified unit into a section."""
    unit_id: str
    section: str
    priority: int = 5
    content_depth: ContentDepth = ContentDepth.MEDIUM
    sources: list[str] = Field(default_factory=list)


# ============================================================
# Run Metrics & Monitoring
# ============================================================

class ErrorRecord(BaseModel):
    """Structured error log entry."""
    phase: str
    article_id: Optional[str] = None
    error_type: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)


class DeliveryStatus(BaseModel):
    """Email delivery outcome."""
    delivered: bool = False
    recipient: str = ""
    timestamp: Optional[datetime] = None
    smtp_response: Optional[str] = None
    error: Optional[str] = None


class RunMetrics(BaseModel):
    """Complete run statistics."""
    run_id: str
    run_date: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    articles_ingested: int = 0
    articles_normalized: int = 0
    articles_filtered: int = 0
    clusters_formed: int = 0
    units_analyzed: int = 0
    units_verified: int = 0
    units_failed_verification: int = 0
    sections_written: int = 0
    total_words: int = 0
    estimated_pages: int = 0
    actual_pages: int = 0
    render_time_seconds: float = 0.0
    total_time_seconds: float = 0.0
    delivery_status: str = "pending"
    llm_calls: int = 0
    llm_tokens_used: int = 0
    errors: list[ErrorRecord] = Field(default_factory=list)
    phase_timings: dict[str, float] = Field(default_factory=dict)
