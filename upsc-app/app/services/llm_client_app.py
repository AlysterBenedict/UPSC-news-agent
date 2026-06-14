"""
UPSC Daily Digest — LLM Client Service
========================================
Abstracted LLM interface using OpenAI-compatible API for NVIDIA NIM.
Supports JSON mode, retry logic, and provider-agnostic design.
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional

from openai import OpenAI

from app.utils.logging_app import get_logger

log = get_logger(__name__)


class LLMClient:
    """OpenAI-compatible LLM client for NVIDIA NIM / Nemotron."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://integrate.api.nvidia.com/v1",
        model: str = "nvidia/llama-3.3-nemotron-super-49b-v1",
        max_retries: int = 3,
        timeout: int = 120,
        delay: float = 1.0,
    ):
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )
        self.model = model
        self.max_retries = max_retries
        self.delay = delay
        self.total_calls = 0
        self.total_tokens = 0

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> str:
        """Generate a text completion with infinite retry logic on exceptions."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # Some providers support response_format for JSON
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        attempt = 0
        while True:
            attempt += 1
            try:
                response = self.client.chat.completions.create(**kwargs)
                self.total_calls += 1

                # Track token usage
                if response.usage:
                    self.total_tokens += response.usage.total_tokens

                content = response.choices[0].message.content or ""
                log.info(
                    "llm_call_success",
                    attempt=attempt,
                    model=self.model,
                    tokens=response.usage.total_tokens if response.usage else 0,
                )

                # Delay between calls for rate limiting
                time.sleep(self.delay)
                return content

            except Exception as e:
                log.warning(
                    "llm_call_failed",
                    attempt=attempt,
                    error=str(e),
                    model=self.model,
                )
                # Exponential backoff capped at 60s
                backoff = min(max(2.0, self.delay) * (2 ** (attempt - 1)), 60.0)
                time.sleep(backoff)

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> dict:
        """Generate a JSON response, parsing the output and retrying on parse failure."""
        max_json_retries = 5
        attempt = 0
        while attempt < max_json_retries:
            attempt += 1
            try:
                raw = self.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    json_mode=True,
                )

                # Try to parse JSON from response
                parsed = None
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    # Try to extract JSON from markdown code blocks
                    import re
                    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
                    if json_match:
                        try:
                            parsed = json.loads(json_match.group(1))
                        except json.JSONDecodeError:
                            pass

                    if parsed is None:
                        # Try to find JSON object in text
                        brace_start = raw.find("{")
                        brace_end = raw.rfind("}")
                        if brace_start != -1 and brace_end != -1:
                            try:
                                parsed = json.loads(raw[brace_start : brace_end + 1])
                            except json.JSONDecodeError:
                                pass

                if parsed is None or not isinstance(parsed, dict) or not parsed:
                    raise ValueError("Empty or malformed JSON returned by LLM")

                return parsed

            except Exception as e:
                log.warning(
                    "json_generation_failed",
                    attempt=attempt,
                    max_retries=max_json_retries,
                    error=str(e),
                )
                if attempt >= max_json_retries:
                    log.error(
                        "json_generation_exhausted",
                        error=str(e),
                        attempts=attempt,
                    )
                    return {}
                backoff = min(max(2.0, self.delay) * (2 ** (attempt - 1)), 60.0)
                time.sleep(backoff)

    def analyze_article(
        self,
        system_prompt: str,
        article_text: str,
        article_title: str,
        article_source: str,
        article_id: str,
    ) -> dict:
        """Analyze a single article for UPSC relevance."""
        user_prompt = (
            f"ARTICLE TITLE: {article_title}\n"
            f"SOURCE: {article_source}\n"
            f"ARTICLE ID: {article_id}\n\n"
            f"ARTICLE TEXT:\n{article_text}"
        )
        return self.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
            max_tokens=6144,
        )

    def verify_analysis(
        self,
        system_prompt: str,
        analysis_json: str,
        source_text: str,
    ) -> dict:
        """Verify an analysis unit against source text."""
        user_prompt = (
            f"ANALYSIS TO VERIFY:\n{analysis_json}\n\n"
            f"ORIGINAL SOURCE TEXT:\n{source_text}"
        )
        return self.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=4096,
        )

    def write_section(
        self,
        system_prompt: str,
        verified_units_json: str,
        section_name: str,
    ) -> str:
        """Write a section of the digest from verified units."""
        user_prompt = (
            f"SECTION: {section_name}\n\n"
            f"VERIFIED CONTENT UNITS:\n{verified_units_json}"
        )
        return self.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.4,
            max_tokens=6144,
            json_mode=False,
        )

    def classify_relevance(
        self,
        system_prompt: str,
        article_title: str,
        article_snippet: str,
        article_category: str,
        article_id: str,
    ) -> dict:
        """Classify a single article's UPSC relevance.

        Returns dict with keys: relevant (bool), reason (str).
        """
        user_prompt = (
            f"ARTICLE ID: {article_id}\n"
            f"TITLE: {article_title}\n"
            f"CATEGORY: {article_category}\n\n"
            f"SNIPPET:\n{article_snippet}"
        )
        result = self.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=512,
        )
        return {
            "relevant": bool(result.get("relevant", True)),
            "reason": str(result.get("reason", "classification failed")),
        }

    def get_stats(self) -> dict:
        """Return usage statistics."""
        return {
            "total_calls": self.total_calls,
            "total_tokens": self.total_tokens,
        }
