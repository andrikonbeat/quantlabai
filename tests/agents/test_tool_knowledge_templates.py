"""Tests for TOOL_KNOWLEDGE_TEMPLATES in prompts.py (REQ-LMR-01, task T-01).

Covers:
- The three official tool-knowledge surfaces: block->snippet, JForex
  lifecycle, SQX HTTP API.
- Content quality: IStrategy lifecycle + @Configurable present; templates are
  curated (populated via retrieval/cheat-sheets only, no full corpus).
- Backward compatibility: the 4 market-data PROMPT_TEMPLATES stay untouched.
"""

from __future__ import annotations

import pytest

from quantlab.agents.prompts import PROMPT_TEMPLATES, TOOL_KNOWLEDGE_TEMPLATES


class TestToolKnowledgeTemplates:
    """TOOL_KNOWLEDGE_TEMPLATES exposes the three official surfaces."""

    def test_has_three_official_templates(self) -> None:
        assert set(TOOL_KNOWLEDGE_TEMPLATES.keys()) == {
            "sqx_block_snippet",
            "jforex_lifecycle",
            "sqx_http_api",
        }

    def test_each_template_is_substantive_text(self) -> None:
        for key, template in TOOL_KNOWLEDGE_TEMPLATES.items():
            assert isinstance(template, str)
            assert len(template) > 80, (
                f"Template '{key}' is too short ({len(template)} chars)"
            )

    def test_jforex_lifecycle_covers_istrategy_and_configurable(self) -> None:
        template = TOOL_KNOWLEDGE_TEMPLATES["jforex_lifecycle"]
        assert "IStrategy" in template
        assert "@Configurable" in template

    def test_block_snippet_template_points_to_curated_cheat_sheet(self) -> None:
        template = TOOL_KNOWLEDGE_TEMPLATES["sqx_block_snippet"]
        assert "cheat-sheet" in template.lower()
        assert "block" in template.lower()
        assert "snippet" in template.lower()

    def test_http_api_template_points_to_curated_endpoints(self) -> None:
        template = TOOL_KNOWLEDGE_TEMPLATES["sqx_http_api"]
        assert "endpoint" in template.lower()

    def test_no_full_corpus_injection(self) -> None:
        # REQ-LMR-01: templates SHALL be populated via retrieval or curated
        # cheat-sheets only; full corpora MUST NOT be injected.
        for key, template in TOOL_KNOWLEDGE_TEMPLATES.items():
            assert "knowledge/raw" not in template, (
                f"'{key}' references the raw corpus path"
            )
            assert len(template) <= 1200, (
                f"'{key}' exceeds the curated-size bound ({len(template)} chars)"
            )

    def test_existing_market_data_templates_untouched(self) -> None:
        # Backward compatibility: the 4 market-data templates keep their keys.
        assert set(PROMPT_TEMPLATES.keys()) == {
            "fundamental", "technical", "macro", "news",
        }