"""
UPSC Daily Digest — Central Configuration
==========================================
Loads all settings from environment variables / .env file.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    # --- NVIDIA NIM ---
    nim_api_key: str = Field(..., alias="NIM_API_KEY")
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
    llm_classification_enabled: bool = Field(
        default=True, alias="LLM_CLASSIFICATION_ENABLED"
    )

    # --- Email ---
    smtp_host: str = Field(default="smtp.gmail.com", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_pass: str = Field(default="", alias="SMTP_PASS")
    email_from: str = Field(default="", alias="EMAIL_FROM")
    email_recipients: str = Field(default="", alias="EMAIL_RECIPIENTS")

    # --- Paths ---
    scraper_output_dir: str = Field(default="../", alias="SCRAPER_OUTPUT_DIR")
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
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "populate_by_name": True,
    }

    # --- Derived properties ---

    @property
    def scraper_output_path(self) -> Path:
        return Path(self.scraper_output_dir).resolve()

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
    """Get cached settings instance."""
    return Settings()
