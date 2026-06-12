import pytest
from pathlib import Path
from app.agents.deliver import deliver_digest

def test_deliver_digest_skip(tmp_path):
    # Create a dummy PDF file so Path.exists() is True if it checks it
    pdf_file = tmp_path / "UPSC_Digest_2026-06-09.pdf"
    pdf_file.write_text("dummy pdf content")

    state = {
        "compiled_pdf_path": str(pdf_file),
        "run_id": "test_run_123",
        "run_date": "2026-06-09",
        "skip_delivery": True,
    }

    result = deliver_digest(state)
    assert result["delivery_status"] == "skipped"
    assert result["current_phase"] == "delivery_skipped"
