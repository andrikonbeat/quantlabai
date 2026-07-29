"""Tests for prompt templates — Task 2.1 RED + 2.2 GREEN.

Covers:
- PROMPT_TEMPLATES dict with all 4 analysis types
- Fundamental template includes financial metrics
- Technical template excludes macro data
- Templates are proper format strings with expected placeholders
"""

from __future__ import annotations

import pytest

from quantlab.agents.prompts import PROMPT_TEMPLATES


class TestPromptTemplateExists:
    """Verify the PROMPT_TEMPLATES dict exists with expected keys."""

    def test_has_all_analysis_types(self) -> None:
        assert set(PROMPT_TEMPLATES.keys()) == {
            "fundamental", "technical", "macro", "news",
        }

    def test_each_template_is_non_empty_string(self) -> None:
        for key, tmpl in PROMPT_TEMPLATES.items():
            assert isinstance(tmpl, str)
            assert len(tmpl) > 50, f"Template '{key}' is too short ({len(tmpl)} chars)"

    def test_all_templates_are_format_strings(self) -> None:
        for key, tmpl in PROMPT_TEMPLATES.items():
            assert "{" in tmpl and "}" in tmpl, (
                f"Template '{key}' has no format placeholders"
            )


class TestFundamentalTemplate:
    """Fundamental template MUST include structured financial metrics."""

    FUNDAMENTAL_PLACEHOLDERS = {"ticker", "pe", "pb", "roe", "revenue", "debt"}

    def test_has_required_placeholders(self) -> None:
        tmpl = PROMPT_TEMPLATES["fundamental"]
        for ph in self.FUNDAMENTAL_PLACEHOLDERS:
            assert "{" + ph + "}" in tmpl, (
                f"Fundamental template missing placeholder {{{ph}}}"
            )

    def test_format_with_real_values(self) -> None:
        tmpl = PROMPT_TEMPLATES["fundamental"]
        result = tmpl.format(
            ticker="AAPL",
            pe=25.5,
            pb=8.2,
            roe=0.35,
            revenue="394B",
            debt="100B",
        )
        assert "AAPL" in result
        assert "25.5" in result or "25" in result
        assert "0.35" in result
        assert "394B" in result

    def test_does_not_include_macro_indicators(self) -> None:
        tmpl = PROMPT_TEMPLATES["fundamental"]
        macro_terms = {"gdp", "cpi", "inflation", "unemployment", "fed_rate"}
        for term in macro_terms:
            assert term.lower() not in tmpl.lower(), (
                f"Fundamental template should not contain macro term '{term}'"
            )


class TestTechnicalTemplate:
    """Technical template MUST exclude macroeconomic indicators."""

    TECHNICAL_PLACEHOLDERS = {"ticker", "close", "volume", "rsi", "sma"}

    def test_has_required_placeholders(self) -> None:
        tmpl = PROMPT_TEMPLATES["technical"]
        for ph in self.TECHNICAL_PLACEHOLDERS:
            assert "{" + ph + "}" in tmpl, (
                f"Technical template missing placeholder {{{ph}}}"
            )

    def test_format_with_real_values(self) -> None:
        tmpl = PROMPT_TEMPLATES["technical"]
        result = tmpl.format(
            ticker="AAPL",
            close=175.5,
            volume=52000000,
            rsi=55,
            sma_50=170.2,
            sma=170.2,
        )
        assert "175.5" in result
        assert "52000000" in result

    def test_excludes_macro_indicators(self) -> None:
        tmpl = PROMPT_TEMPLATES["technical"]
        macro_terms = {"gdp", "cpi", "inflation", "unemployment", "gross_domestic"}
        for term in macro_terms:
            assert term.lower() not in tmpl.lower(), (
                f"Technical template should not contain macro term '{term}'"
            )


class TestMacroTemplate:
    """Macro template MUST include GDP, CPI, rates."""

    MACRO_PLACEHOLDERS = {"gdp", "cpi", "rate", "unemployment"}

    def test_has_required_placeholders(self) -> None:
        tmpl = PROMPT_TEMPLATES["macro"]
        for ph in self.MACRO_PLACEHOLDERS:
            assert "{" + ph + "}" in tmpl, (
                f"Macro template missing placeholder {{{ph}}}"
            )

    def test_format_with_real_values(self) -> None:
        tmpl = PROMPT_TEMPLATES["macro"]
        result = tmpl.format(
            gdp="3.1%",
            cpi="2.8%",
            rate="5.25%",
            unemployment="3.7%",
        )
        assert "3.1%" in result
        assert "2.8%" in result
        assert "5.25%" in result
        assert "3.7%" in result


class TestNewsTemplate:
    """News template MUST include articles/content placeholders."""

    NEWS_PLACEHOLDERS = {"query", "articles"}

    def test_has_required_placeholders(self) -> None:
        tmpl = PROMPT_TEMPLATES["news"]
        for ph in self.NEWS_PLACEHOLDERS:
            assert "{" + ph + "}" in tmpl, (
                f"News template missing placeholder {{{ph}}}"
            )

    def test_format_with_real_values(self) -> None:
        tmpl = PROMPT_TEMPLATES["news"]
        result = tmpl.format(
            query="AAPL earnings",
            articles="Article 1: AAPL beat estimates\nArticle 2: iPhone sales up",
        )
        assert "AAPL earnings" in result
        assert "Article 1" in result
