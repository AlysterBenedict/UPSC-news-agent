"""Tests for PIB article routing and section mapping."""

import pytest
from app.models.schemas import SectionName
from app.agents.map_upsc import determine_primary_section, map_to_sections


def test_pib_routing_in_determine_primary_section():
    # Unit with PIB in sources
    unit_pib = {
        "unit_id": "unit_001",
        "title": "Government announcement on agriculture",
        "sources": ["PIB", "The Hindu"],
        "category": "Economy",
        "gs_papers": ["GS3"],
    }
    assert determine_primary_section(unit_pib) == SectionName.PIB.value

    # Unit with no PIB in sources
    unit_non_pib = {
        "unit_id": "unit_002",
        "title": "Inflation rises",
        "sources": ["The Hindu", "Economic Times"],
        "category": "Economy",
        "gs_papers": ["GS3"],
    }
    assert determine_primary_section(unit_non_pib) == SectionName.GS3_ECONOMY.value


def test_map_to_sections_with_pib_unit():
    state = {
        "verified_units": [
            {
                "unit_id": "unit_001",
                "article_ids": ["art_pib_1"],
                "title": "PIB Press Release",
                "factual_summary": ["Something happened"],
                "upsc_relevance_score": 8.0,
            },
            {
                "unit_id": "unit_002",
                "article_ids": ["art_hindu_1"],
                "title": "Hindu Article",
                "factual_summary": ["Another thing happened"],
                "upsc_relevance_score": 7.0,
            }
        ],
        "articles_normalized": [
            {
                "article_id": "art_pib_1",
                "source": "PIB",
                "source_section": "Press Releases",
            },
            {
                "article_id": "art_hindu_1",
                "source": "The Hindu",
                "source_section": "Editorial",
            }
        ],
        "run_id": "test_pib_run",
    }
    result = map_to_sections(state)
    buffers = result["section_buffers"]
    
    assert "pib" in buffers
    assert len(buffers["pib"]) == 1
    assert buffers["pib"][0]["unit_id"] == "unit_001"
    
    assert "editorial" in buffers
    assert len(buffers["editorial"]) == 1
    assert buffers["editorial"][0]["unit_id"] == "unit_002"
    
    # Assert unit_001 is only in pib, not in editorial
    pib_unit_ids = [b["unit_id"] for b in buffers["pib"]]
    editorial_unit_ids = [b["unit_id"] for b in buffers["editorial"]]
    assert "unit_001" not in editorial_unit_ids
    assert "unit_002" not in pib_unit_ids
