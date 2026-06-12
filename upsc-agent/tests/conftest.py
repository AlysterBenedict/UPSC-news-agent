"""
Shared test fixtures for UPSC Digest tests.
"""

import pytest
import json
from pathlib import Path


@pytest.fixture
def sample_raw_articles():
    """Sample raw articles matching scraper output format."""
    return [
        {
            "title": "Zojila tunnel breakthrough connects Kashmir and Ladakh route",
            "url": "https://indianexpress.com/article/india/zojila-tunnel-kashmir-ladakh-10731425/",
            "source_name": "Indian Express -- India",
            "category": "National",
            "gs_relevance": ["GS2", "GS3"],
            "tier": 1,
            "published": "Tue, 09 Jun 2026 10:31:54 +0000",
            "full_text": "A final 2.5 metres of rock inside the strategically significant Zojila Tunnel was blasted away with 300 kg of explosives on Tuesday, marking a major breakthrough in the construction of the 13.153-km tunnel that will provide all-weather road connectivity between Kashmir and Ladakh. The breakthrough was flagged off by Union Road Transport and Highways Minister Nitin Gadkari. Once completed, the tunnel connecting Baltal and Meenamarg will provide an alternative to the Zojila Pass. At an altitude of 11,578 feet, the Zojila Tunnel is set to become the world's longest bi-directional single-tube road tunnel at such a height. The project is expected to be ready for military use by December 2026. The Rs 6,808.69-crore project is being executed by Megha Engineering.",
            "full_text_chars": 650,
            "scrape_method": "dom_selector:div.full-details",
            "error": None,
            "scraped_at": "2026-06-09T13:40:13.337506+00:00",
        },
        {
            "title": "Zojila tunnel hits breakthrough stage, Nitin Gadkari highlights strategic importance",
            "url": "https://indianexpress.com/article/india/kashmir-zojila-tunnel-breakthrough-10731203/",
            "source_name": "Indian Express -- India",
            "category": "National",
            "gs_relevance": ["GS2", "GS3"],
            "tier": 1,
            "published": "Tue, 09 Jun 2026 09:01:52 +0000",
            "full_text": "Marking a major milestone, NHIDCL achieved a breakthrough of the ambitious Zojila tunnel on Sonmarg-Kargil section of National Highway-01. This tunnel will provide all-weather connectivity between Sonamarg and Minamarg. Located in the snowy peaks of the Himalayas, the 14-km tunnel is scheduled to be completed by February 2028. The total cost of both projects are around Rs. 7000 crore. Union minister Nitin Gadkari said that the project will prove to be a lifeline for Ladakh. 80% of the workers here were from this area.",
            "full_text_chars": 510,
            "scrape_method": "dom_selector:div.full-details",
            "error": None,
            "scraped_at": "2026-06-09T13:40:15.343749+00:00",
        },
        {
            "title": "India slams Pakistani strikes on Afghanistan at UNSC",
            "url": "https://indianexpress.com/article/india/india-unsc-pakistan-trade-transit-terrorism-10731681/",
            "source_name": "Indian Express -- India",
            "category": "International Relations",
            "gs_relevance": ["GS2"],
            "tier": 1,
            "published": "Tue, 09 Jun 2026 13:06:06 +0000",
            "full_text": "In a sharp attack on Pakistan at the United Nations, New Delhi accused Islamabad of carrying out trade and transit terrorism against Afghanistan and condemned its airstrikes on Afghan territory. India's Permanent Representative Harish Parvathaneni said Pakistan's military strikes had caused significant civilian casualties. 372 civilians were killed and 397 injured during the first three months of the year according to UNAMA. India also criticised Pakistan's decision to refer to militant groups as Fitna al Hindustan.",
            "full_text_chars": 480,
            "scrape_method": "dom_selector:div.full-details",
            "error": None,
            "scraped_at": "2026-06-09T13:40:11.380921+00:00",
        },
        {
            "title": "RBI holds repo rate at 6%",
            "url": "https://economictimes.indiatimes.com/rbi-repo-rate-hold",
            "source_name": "Economic Times -- Economy",
            "category": "Economy",
            "gs_relevance": ["GS3"],
            "tier": 2,
            "published": "2026-06-09",
            "full_text": "The Reserve Bank of India kept its key lending rate unchanged at 6 percent for the third consecutive meeting, citing elevated inflation risks amid global uncertainty. Governor Das noted that food inflation remains a concern. GDP growth projection maintained at 7.2%.",
            "full_text_chars": 260,
            "scrape_method": "dom_selector:div.artText",
            "error": None,
            "scraped_at": "2026-06-09T14:00:00+00:00",
        },
        {
            "title": "New species of frog discovered in Western Ghats",
            "url": "https://thehindu.com/sci-tech/new-frog-species-western-ghats",
            "source_name": "The Hindu -- Science",
            "category": "Environment",
            "gs_relevance": ["GS3"],
            "tier": 1,
            "published": "Tue, 09 Jun 2026 08:00:00 +0530",
            "full_text": "Scientists from the Centre for Ecological Sciences at IISc Bangalore have discovered a new species of bush frog in the Western Ghats. The frog, named Raorchestes emeraldi, was found in the Agasthyamalai hills of Kerala. The discovery highlights the rich but threatened biodiversity of the Western Ghats, a UNESCO World Heritage Site. The species is distinguished by its bright emerald-green dorsum and unique call pattern.",
            "full_text_chars": 410,
            "scrape_method": "dom_selector:div[itemprop='articleBody']",
            "error": None,
            "scraped_at": "2026-06-09T13:50:00+00:00",
        },
    ]


@pytest.fixture
def sample_scraper_file(tmp_path, sample_raw_articles):
    """Create a temporary scraper output file."""
    file_path = tmp_path / "scraped_articles_2026-06-09.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(sample_raw_articles, f)
    return file_path


@pytest.fixture
def sample_normalized_articles():
    """Sample normalized articles."""
    return [
        {
            "article_id": "abc123",
            "source": "Indian Express",
            "source_section": "India",
            "url": "https://indianexpress.com/article/zojila",
            "title": "Zojila tunnel breakthrough connects Kashmir and Ladakh",
            "published_at": "2026-06-09T16:01:54+05:30",
            "raw_text": "Full raw text...",
            "clean_text": "A final 2.5 metres of rock inside the Zojila Tunnel was blasted away with 300 kg of explosives, marking a major breakthrough. The 13.153-km tunnel will provide all-weather road connectivity between Kashmir and Ladakh.",
            "char_count": 210,
            "category": "National",
            "gs_papers": ["GS2", "GS3"],
            "tier": 1,
            "scrape_method": "dom_selector:div.full-details",
        },
        {
            "article_id": "def456",
            "source": "Indian Express",
            "source_section": "India",
            "url": "https://indianexpress.com/article/zojila-breakthrough",
            "title": "Zojila tunnel breakthrough connects Kashmir and Ladakh route",
            "published_at": "2026-06-09T14:31:52+05:30",
            "raw_text": "Full raw text...",
            "clean_text": "A final 2.5 metres of rock inside the Zojila Tunnel was blasted away, marking a major breakthrough. The 13.153-km tunnel will provide all-weather road connectivity between Kashmir and Ladakh.",
            "char_count": 190,
            "category": "National",
            "gs_papers": ["GS2", "GS3"],
            "tier": 1,
            "scrape_method": "dom_selector:div.full-details",
        },
    ]
