"""
UPSC Daily Digest — Central Configuration (App-Local)
======================================================
Internalized settings for the desktop app. Does NOT depend on
an external .env file — reads from environment variables set by
the PyWebView wrapper (app_app.py) at runtime.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings

# Cached singleton instance
_settings_instance: Optional["Settings"] = None


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- NVIDIA NIM ---
    # FIX: Default to empty string instead of Field(...) which crashes
    # when no .env file is present (the EXE context).
    # The app_app.py wrapper sets os.environ["NIM_API_KEY"] before
    # any agent node instantiates Settings.
    nim_api_key: str = Field(default="", alias="NIM_API_KEY")
    nim_base_url: str = Field(
        default="https://integrate.api.nvidia.com/v1", alias="NIM_BASE_URL"
    )
    nim_model: str = Field(
        default="nvidia/llama-3.3-nemotron-super-49b-v1", alias="NIM_MODEL"
    )
    nim_model_fast: str = Field(
        default="meta/llama-3.1-8b-instruct", alias="NIM_MODEL_FAST"
    )
    nim_model_classifier: str = Field(
        default="meta/llama-3.1-8b-instruct", alias="NIM_MODEL_CLASSIFIER"
    )

    # --- Email ---
    smtp_host: str = Field(default="smtp.gmail.com", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_pass: str = Field(default="", alias="SMTP_PASS")
    email_from: str = Field(default="", alias="EMAIL_FROM")
    email_recipients: str = Field(default="", alias="EMAIL_RECIPIENTS")

    # --- Paths ---
    scraper_output_dir: str = Field(default="../zartifacts", alias="SCRAPER_OUTPUT_DIR")
    output_dir: str = Field(default="./output", alias="OUTPUT_DIR")
    data_dir: str = Field(default="./data", alias="DATA_DIR")

    # --- Schedule ---
    schedule_hour: int = Field(default=8, alias="SCHEDULE_HOUR")
    schedule_minute: int = Field(default=0, alias="SCHEDULE_MINUTE")
    timezone: str = Field(default="Asia/Kolkata", alias="TIMEZONE")

    # --- Page Budget ---
    min_pages: int = Field(default=25, alias="MIN_PAGES")
    target_pages: int = Field(default=35, alias="TARGET_PAGES")
    max_pages: int = Field(default=40, alias="MAX_PAGES")

    # --- Processing ---
    analysis_batch_size: int = Field(default=1, alias="ANALYSIS_BATCH_SIZE")
    writer_batch_size: int = Field(default=10, alias="WRITER_BATCH_SIZE")
    llm_delay_seconds: float = Field(default=0.0, alias="LLM_DELAY_SECONDS")
    llm_max_retries: int = Field(default=3, alias="LLM_MAX_RETRIES")
    llm_timeout: int = Field(default=120, alias="LLM_TIMEOUT")

    # --- Database ---
    db_path: str = Field(default="./data/checkpoints.db", alias="DB_PATH")

    model_config = {
        # FIX: Don't require .env file — gracefully handle missing files.
        # In the EXE context, there is no .env file. The API key is set
        # via os.environ by the PyWebView wrapper.
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "populate_by_name": True,
    }

    # --- Derived properties ---

    @property
    def scraper_output_path(self) -> Path:
        p = Path(self.scraper_output_dir).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def output_path(self) -> Path:
        p = Path(self.output_dir).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def data_path(self) -> Path:
        p = Path(self.data_dir).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def recipient_list(self) -> list[str]:
        return [r.strip() for r in self.email_recipients.split(",") if r.strip()]

    def run_dir(self, run_id: str) -> Path:
        p = self.data_path / "runs" / run_id
        p.mkdir(parents=True, exist_ok=True)
        return p


def get_settings() -> Settings:
    """Get cached settings singleton.
    
    Uses a singleton pattern so Settings() is only instantiated once
    (avoiding repeated .env reads and validation).
    """
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance


def reset_settings() -> None:
    """Reset the cached settings (useful when env vars change at runtime)."""
    global _settings_instance
    _settings_instance = None
