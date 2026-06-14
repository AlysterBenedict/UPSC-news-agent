"""
Tests for centralized LLM Client infinite retries and pipeline fail-fast logic.
"""

import pytest
from unittest.mock import MagicMock
from app.services.llm_client import LLMClient
from app.agents.verify import verify_units


def test_llm_client_generate_retries_on_failure(monkeypatch):
    """Test that LLMClient.generate retries infinitely on API exceptions and uses exponential backoff."""
    client = LLMClient(
        api_key="mock_key",
        base_url="mock_url",
        model="mock_model",
        delay=1.0,
    )

    # 1. Simulate API failure on first 2 calls, then success
    call_count = 0
    def mock_create(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RuntimeError("NIM API Rate Limit exceeded")
        # Return a mock chat completions response object
        mock_response = MagicMock()
        mock_response.usage = MagicMock()
        mock_response.usage.total_tokens = 100
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "success text"
        return mock_response

    monkeypatch.setattr(client.client.chat.completions, "create", mock_create)

    # 2. Track time.sleep calls
    sleep_calls = []
    def mock_sleep(seconds):
        sleep_calls.append(seconds)
    monkeypatch.setattr("time.sleep", mock_sleep)

    # 3. Call generate
    content = client.generate("sys", "user")

    assert content == "success text"
    assert call_count == 3
    # First sleep is backoff after 1st failure: max(2.0, delay) * 2^0 = 2.0s
    # Second sleep is backoff after 2nd failure: max(2.0, delay) * 2^1 = 4.0s
    # Third sleep is normal self.delay after success: 1.0s
    assert sleep_calls == [2.0, 4.0, 1.0]


def test_llm_client_generate_json_retries_on_malformed_json(monkeypatch):
    """Test that LLMClient.generate_json retries when the response is not valid JSON."""
    client = LLMClient(
        api_key="mock_key",
        base_url="mock_url",
        model="mock_model",
        delay=1.0,
    )

    # 1. Simulate generate returning bad text on first 2 calls, then valid JSON
    call_count = 0
    def mock_generate(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "This is plain text and not JSON"
        elif call_count == 2:
            return "{'invalid_json': True}"  # Single quotes are invalid JSON
        return '{"valid_json": true}'

    monkeypatch.setattr(client, "generate", mock_generate)

    # 2. Track time.sleep calls
    sleep_calls = []
    def mock_sleep(seconds):
        sleep_calls.append(seconds)
    monkeypatch.setattr("time.sleep", mock_sleep)

    # 3. Call generate_json
    result = client.generate_json("sys", "user")

    assert result == {"valid_json": True}
    assert call_count == 3
    # First sleep is backoff after 1st JSON parse failure: 2.0s
    # Second sleep is backoff after 2nd JSON parse failure: 4.0s
    assert sleep_calls == [2.0, 4.0]


def test_verify_units_fails_on_exception(monkeypatch):
    """Test that verify_units propagates exception and fails fast instead of falling back."""
    # 1. Prepare sample analyzed units and clusters
    analyzed_units = [
        {
            "unit_id": "unit_123",
            "article_ids": ["art_123"],
            "title": "UPSC Syllabus Reform",
        }
    ]
    clusters = [
        {
            "cluster_id": "unit_123",
            "combined_text": "Source text...",
        }
    ]

    # 2. Force verify_analysis to raise an exception
    def mock_verify_analysis(*args, **kwargs):
        raise RuntimeError("Fatal Database Connection Error")

    monkeypatch.setattr(LLMClient, "verify_analysis", mock_verify_analysis)

    # 3. Run verify_units and assert it propagates the exception
    state = {
        "analyzed_units": analyzed_units,
        "article_clusters": clusters,
        "run_id": "test_run",
    }

    with pytest.raises(RuntimeError) as exc_info:
        verify_units(state)

    assert "Fatal Database Connection Error" in str(exc_info.value)


def test_saving_results_json(tmp_path, monkeypatch):
    """Test that classification, verification, and writing save JSON files to the scraper path."""
    import json
    from app.agents.normalize import normalize_articles
    from app.agents.verify import verify_units
    from app.agents.write_sections import write_sections
    from config.settings import Settings

    # 1. Setup mock settings
    mock_settings = Settings()
    mock_settings.scraper_output_dir = str(tmp_path)
    mock_settings.nim_api_key = "test_key"
    mock_settings.nim_base_url = "test_url"
    mock_settings.llm_max_retries = 1
    mock_settings.llm_timeout = 10
    mock_settings.llm_delay_seconds = 0.0

    monkeypatch.setattr("config.settings.get_settings", lambda: mock_settings)

    # 2. Mock classification results and normalize_articles call
    def mock_classify(*args, **kwargs):
        return {"art_1": {"relevant": True, "reason": "Test"}}
    monkeypatch.setattr("app.agents.normalize.classify_article_relevance", mock_classify)

    state = {
        "run_date": "2026-06-13",
        "articles_raw": [{
            "article_id": "art_1",
            "source_name": "Indian Express",
            "published": "2026-06-13",
            "full_text": "Important news.",
            "title": "A title"
        }]
    }

    res_norm = normalize_articles(state)
    classification_file = tmp_path / "classification_results_2026-06-13.json"
    assert classification_file.exists()

    # 3. Mock verification results and verify_units call
    def mock_verify_analysis(*args, **kwargs):
        return {
            "verification_status": "pass",
            "verified_factual_summary": ["Claim verified."],
        }
    monkeypatch.setattr(LLMClient, "verify_analysis", mock_verify_analysis)

    state_verify = {
        "run_date": "2026-06-13",
        "analyzed_units": [{
            "unit_id": "unit_1",
            "article_ids": ["art_1"],
            "title": "A title",
        }],
        "article_clusters": [{
            "cluster_id": "unit_1",
            "combined_text": "Important news.",
        }],
        "articles_normalized": res_norm["articles_normalized"],
    }
    res_verify = verify_units(state_verify)
    verification_file = tmp_path / "verification_results_2026-06-13.json"
    assert verification_file.exists()

    # 4. Mock section writing and write_sections call
    def mock_write_section(*args, **kwargs):
        return "<div class='brief-card'><h3>1. A title</h3><p class='gs-tag'>GS2</p></div>"
    monkeypatch.setattr(LLMClient, "write_section", mock_write_section)

    state_write = {
        "run_date": "2026-06-13",
        "verified_units": res_verify["verified_units"],
        "articles_normalized": res_norm["articles_normalized"],
        "section_buffers": {
            "gs2_polity": [{"unit_id": "unit_1", "content_depth": "medium"}]
        }
    }
    res_write = write_sections(state_write)
    writing_file = tmp_path / "written_sections_2026-06-13.json"
    assert writing_file.exists()

