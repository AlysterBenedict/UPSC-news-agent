"""Tests for deduplication agent."""

import pytest
from app.agents.dedup import deduplicate_articles


class TestDeduplication:
    def test_dedup_groups_similar(self, sample_normalized_articles):
        """Test that similar articles about Zojila are grouped."""
        state = {
            "articles_normalized": sample_normalized_articles,
            "run_id": "test",
        }
        result = deduplicate_articles(state)
        clusters = result["article_clusters"]

        # Two similar Zojila articles should form one cluster
        assert len(clusters) == 1
        assert clusters[0]["article_count"] == 2
        assert result["current_phase"] == "clustered"

    def test_dedup_preserves_provenance(self, sample_normalized_articles):
        """Test that source provenance is preserved in clusters."""
        state = {
            "articles_normalized": sample_normalized_articles,
            "run_id": "test",
        }
        result = deduplicate_articles(state)
        cluster = result["article_clusters"][0]

        assert cluster["primary_article_id"]
        assert len(cluster["sources"]) >= 1
        assert cluster["combined_text"]

    def test_dedup_single_article(self):
        """Test that a single article becomes its own cluster."""
        state = {
            "articles_normalized": [{
                "article_id": "solo_001",
                "source": "Test",
                "source_section": "India",
                "url": "https://example.com",
                "title": "Unique Story",
                "clean_text": "This is a completely unique story about something.",
                "char_count": 50,
                "category": "National",
                "gs_papers": ["GS2"],
                "tier": 1,
                "scrape_method": "test",
            }],
            "run_id": "test",
        }
        result = deduplicate_articles(state)
        assert len(result["article_clusters"]) == 1
        assert result["article_clusters"][0]["article_count"] == 1

    def test_dedup_empty_input(self):
        """Test empty input handling."""
        state = {"articles_normalized": [], "run_id": "test"}
        result = deduplicate_articles(state)
        assert result["article_clusters"] == []
