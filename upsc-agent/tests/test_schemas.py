"""Tests for Pydantic schemas."""

import pytest
from app.models.schemas import (
    RawArticle, NormalizedArticle, ArticleCluster,
    AnalysisUnit, VerifiedUnit, EvidenceItem,
    SectionBufferItem, RunMetrics, ErrorRecord,
)


class TestRawArticle:
    def test_valid_article(self, sample_raw_articles):
        """Test that sample articles validate correctly."""
        for raw in sample_raw_articles:
            article = RawArticle.model_validate(raw)
            assert article.title
            assert article.url
            assert article.source_name

    def test_gs_relevance_string_coercion(self):
        """Test that string gs_relevance is coerced to list."""
        data = {
            "title": "Test",
            "url": "https://example.com",
            "source_name": "Test Source",
            "category": "National",
            "gs_relevance": "GS2",
        }
        article = RawArticle.model_validate(data)
        assert article.gs_relevance == ["GS2"]

    def test_missing_optional_fields(self):
        """Test that articles with minimal fields still validate."""
        data = {
            "title": "Test Article",
            "url": "https://example.com/article",
            "source_name": "Test",
            "category": "National",
        }
        article = RawArticle.model_validate(data)
        assert article.full_text == ""
        assert article.error is None


class TestAnalysisUnit:
    def test_evidence_item(self):
        """Test evidence item creation."""
        evidence = EvidenceItem(
            claim="372 civilians were killed",
            article_id="abc123",
            evidence_span="372 civilians were killed and 397 injured",
        )
        assert evidence.claim
        assert evidence.article_id

    def test_analysis_unit_with_evidence(self):
        """Test analysis unit with evidence map."""
        unit = AnalysisUnit(
            unit_id="cluster_0001",
            article_ids=["abc123"],
            title="Test Analysis",
            factual_summary=["Fact 1", "Fact 2"],
            gs_papers=["GS2"],
            evidence_map=[
                EvidenceItem(
                    claim="Fact 1",
                    article_id="abc123",
                    evidence_span="supporting text",
                )
            ],
            upsc_relevance_score=8.0,
        )
        assert len(unit.evidence_map) == 1
        assert unit.upsc_relevance_score == 8.0


class TestRunMetrics:
    def test_default_metrics(self):
        """Test default metrics values."""
        metrics = RunMetrics(run_id="test_001", run_date="2026-06-09")
        assert metrics.articles_ingested == 0
        assert metrics.delivery_status == "pending"
        assert metrics.errors == []
