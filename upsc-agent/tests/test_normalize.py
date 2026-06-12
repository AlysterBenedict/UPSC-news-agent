"""Tests for normalization agent."""

import pytest
from app.agents.normalize import parse_source_name, normalize_articles


class TestSourceParsing:
    def test_indian_express_india(self):
        source, section = parse_source_name("Indian Express -- India")
        assert source == "Indian Express"
        assert section == "India"

    def test_the_hindu_editorial(self):
        source, section = parse_source_name("The Hindu -- Editorial")
        assert source == "The Hindu"
        assert section == "Editorial"

    def test_pib(self):
        source, section = parse_source_name("PIB -- Press Releases")
        assert source == "PIB"
        assert section == "Press Releases"

    def test_economic_times(self):
        source, section = parse_source_name("Economic Times -- Economy")
        assert source == "Economic Times"
        assert section == "Economy"

    def test_single_name(self):
        source, section = parse_source_name("SomeSource")
        assert source == "SomeSource"
        assert section == "General"


class TestNormalization:
    def test_normalize_filters_short(self, sample_raw_articles):
        """Test that articles are not filtered unless clean_text is empty."""
        articles = sample_raw_articles.copy()
        
        # Add a short article (6 chars)
        articles.append({
            "title": "Short article",
            "url": "https://example.com/short",
            "source_name": "SomeSource",
            "category": "National",
            "gs_relevance": ["GS3"],
            "tier": 3,
            "published": "Tue, 09 Jun 2026 10:31:54 +0000",
            "full_text": "Short.",
            "full_text_chars": 6,
            "scrape_method": "dom_selector",
            "error": None,
            "scraped_at": "2026-06-09T13:40:13.337506+00:00",
        })
        
        # Add an empty article
        articles.append({
            "title": "Empty article",
            "url": "https://example.com/empty",
            "source_name": "SomeSource",
            "category": "National",
            "gs_relevance": ["GS3"],
            "tier": 3,
            "published": "Tue, 09 Jun 2026 10:31:54 +0000",
            "full_text": "",
            "full_text_chars": 0,
            "scrape_method": "dom_selector",
            "error": None,
            "scraped_at": "2026-06-09T13:40:13.337506+00:00",
        })
        
        state = {
            "articles_raw": articles,
            "run_id": "test_run",
        }
        result = normalize_articles(state)
        normalized = result["articles_normalized"]
        
        urls = {a["url"] for a in normalized}
        assert "https://example.com/short" in urls
        assert "https://example.com/empty" not in urls
        assert result["current_phase"] == "normalized"

    def test_normalized_has_clean_text(self, sample_raw_articles):
        """Test that normalized articles have clean_text field."""
        state = {"articles_raw": sample_raw_articles, "run_id": "test"}
        result = normalize_articles(state)
        for article in result["articles_normalized"]:
            assert "clean_text" in article
            assert "raw_text" in article
            assert article["clean_text"]

    def test_boilerplate_removed(self, sample_raw_articles):
        """Test that boilerplate text is removed."""
        # Add boilerplate to test
        articles = [sample_raw_articles[0].copy()]
        articles[0]["full_text"] += " Story continues below this ad © IE Online Media Services Pvt Ltd"
        articles[0]["full_text_chars"] = len(articles[0]["full_text"])

        state = {"articles_raw": articles, "run_id": "test"}
        result = normalize_articles(state)
        if result["articles_normalized"]:
            clean = result["articles_normalized"][0]["clean_text"]
            assert "Story continues below this ad" not in clean
