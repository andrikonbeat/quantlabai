"""Tests for research-literature + sqx-catalog templates (T9 task 2.7)."""

from __future__ import annotations


class TestLiteratureTemplates:
    def test_templates_exist(self) -> None:
        from quantlab.agents.prompts import PROMPT_TEMPLATES

        assert "research-literature" in PROMPT_TEMPLATES
        assert "sqx-catalog" in PROMPT_TEMPLATES

    def test_research_literature_format(self) -> None:
        from quantlab.agents.prompts import PROMPT_TEMPLATES

        text = PROMPT_TEMPLATES["research-literature"].format(
            query="momentum",
            papers="- Attention (https://arxiv.org/abs/1706.03762)",
        )
        assert "momentum" in text
        assert "https://arxiv.org/abs/1706.03762" in text

    def test_sqx_catalog_format(self) -> None:
        from quantlab.agents.prompts import PROMPT_TEMPLATES

        text = PROMPT_TEMPLATES["sqx-catalog"].format(
            preset="gainers",
            symbols="- AAA @ 12.5 (+8.1%)",
        )
        assert "gainers" in text
        assert "AAA" in text


class TestBuildPromptLiterature:
    def _agent(self):
        from quantlab.agents.llm_research_agent import LLMResearchAgent

        return LLMResearchAgent()

    def test_literature_section_included(self) -> None:
        agent = self._agent()
        prompt = agent.build_prompt(
            "momentum",
            {
                "fundamental": {},
                "macro": {},
                "news": [],
                "literature": [
                    {"title": "Paper One", "url": "https://x.example/1",
                     "authors": ["a"], "source": "arxiv"},
                ],
                "screener": {},
                "ticker": "",
            },
        )
        assert "Paper One" in prompt
        assert "https://x.example/1" in prompt

    def test_literature_section_omitted_when_empty(self) -> None:
        agent = self._agent()
        prompt = agent.build_prompt(
            "momentum",
            {"fundamental": {}, "macro": {}, "news": [],
             "literature": [], "screener": {}, "ticker": ""},
        )
        assert "Paper One" not in prompt

    def test_screener_section_included(self) -> None:
        agent = self._agent()
        prompt = agent.build_prompt(
            "momentum",
            {
                "fundamental": {}, "macro": {}, "news": [], "literature": [],
                "screener": {"preset": "gainers",
                             "results": [{"symbol": "AAA", "price": 12.5,
                                          "change_pct": "+8.1%"}]},
                "ticker": "",
            },
        )
        assert "AAA" in prompt
        assert "gainers" in prompt

    def test_screener_section_omitted_when_empty(self) -> None:
        agent = self._agent()
        prompt = agent.build_prompt(
            "momentum",
            {"fundamental": {}, "macro": {}, "news": [],
             "literature": [], "screener": {}, "ticker": ""},
        )
        assert "AAA" not in prompt
