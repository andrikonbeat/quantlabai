"""G2 flag-first dispatch: flag=0→legacy byte-identical, flag=1→CustomProject."""

from __future__ import annotations

import zipfile
from io import BytesIO

import pytest

from quantlab.agents.builder_agent import BuilderAgent
from quantlab.dsl.models import ResearchConfig, Strategy


def _valid_research_config() -> ResearchConfig:
    return ResearchConfig(
        campaign="g2-flag-test",
        market="EURUSD",
        timeframe="H1",
        strategies=[Strategy(name="StratA", direction="BOTH")],
    )


class TestG2FlagDispatch:
    """G2: QUANTLAB_CUSTOM_PROJECT flag-first dispatch."""

    @pytest.mark.asyncio
    async def test_flag_disabled_produces_legacy_single_task(self, monkeypatch):
        """GIVEN QUANTLAB_CUSTOM_PROJECT=0 (legacy default)
        WHEN translate_to_cfx() is called
        THEN the archive is a single-task CfxConfig with schema 141.2219.
        """
        monkeypatch.setenv("QUANTLAB_CUSTOM_PROJECT", "0")
        agent = BuilderAgent()
        cfx_bytes = await agent.translate_to_cfx(_valid_research_config())

        with zipfile.ZipFile(BytesIO(cfx_bytes), "r") as zf:
            cfg_xml = zf.read("config.xml").decode("utf-8")
            names = zf.namelist()

        assert 'version="141.2219"' in cfg_xml
        assert "<Project" not in cfg_xml
        task_xmls = [n for n in names if n.endswith(".xml") and n != "config.xml"]
        assert len(task_xmls) == 1

    @pytest.mark.asyncio
    async def test_flag_enabled_produces_custom_project_archive(self, monkeypatch):
        """GIVEN QUANTLAB_CUSTOM_PROJECT=1
        WHEN translate_to_cfx() is called
        THEN the archive is a CfxProject with schema 144.2953 and per-task XML files.
        """
        monkeypatch.setenv("QUANTLAB_CUSTOM_PROJECT", "1")
        agent = BuilderAgent()
        cfx_bytes = await agent.translate_to_cfx(_valid_research_config())

        with zipfile.ZipFile(BytesIO(cfx_bytes), "r") as zf:
            cfg_xml = zf.read("config.xml").decode("utf-8")
            names = zf.namelist()

        assert 'version="144.2953"' in cfg_xml
        assert "<Project" in cfg_xml
        task_xmls = [n for n in names if n.endswith(".xml") and n != "config.xml"]
        assert len(task_xmls) >= 1

    @pytest.mark.asyncio
    async def test_flag_disabled_byte_identical_to_legacy_translator(self, monkeypatch):
        """GIVEN QUANTLAB_CUSTOM_PROJECT=0
        WHEN translate_to_cfx() is called
        THEN the bytes match the legacy translator.generate_cfx_archive output exactly.
        """
        from quantlab.translate.translator import generate_cfx_archive

        monkeypatch.setenv("QUANTLAB_CUSTOM_PROJECT", "0")
        agent = BuilderAgent()
        cfx_bytes = await agent.translate_to_cfx(_valid_research_config())

        legacy_bytes = await agent._translate(_valid_research_config())
        # When flag=0, _translate must delegate to the legacy translator,
        # producing byte-identical output to a direct translator call.
        legacy_archive = generate_cfx_archive(_valid_research_config())
        from quantlab.cfx.writer import CfxWriter
        expected_bytes = CfxWriter.to_bytes(legacy_archive)

        assert cfx_bytes == expected_bytes
