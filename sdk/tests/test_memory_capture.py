"""Phase-boundary memory capture tests (REQ-102/103) + dual-write/privacy.

REQ-102: every phase boundary captures the Result Contract envelope
(``status``, ``executive_summary``, ``artifacts``, ``next_recommended``,
``risks``) plus the phase config. Missing envelope fields default to null.
Save failures are non-blocking.

REQ-103: save_decision writes BOTH Engram (topic ``agent/{agent}/{campaign}``)
and the Knowledge Lake ``agent-memory/`` YAML; an Engram failure never blocks
the lake write. REQ-107: records are privacy-scrubbed before persisting.
D1: capture is config-disabled.
"""

import pytest

from quantlab.agents.memory import AgentMemoryManager
from quantlab.agents.research_director import ResearchDirector
from quantlab.knowledge.memory_capture import MemoryCaptureService
from quantlab.knowledge.privacy import REDACTED

LICENSE = "FUTLABF255"


class FakeEngram:
    """Records calls without talking to a real Engram server."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __call__(self, **kwargs) -> None:
        self.calls.append(kwargs)


class FailingEngram:
    """Engram stub that always raises (REQ-103 unavailable scenario)."""

    async def __call__(self, **kwargs) -> None:
        raise RuntimeError("engram down")


@pytest.fixture
def enabled_config() -> dict:
    return {"enabled": True}


class TestCaptureAtPhaseBoundary:
    """REQ-102 scenario: capture at phase boundary (dual write)."""

    @pytest.mark.asyncio
    async def test_dual_write_engram_and_lake(self, tmp_path, enabled_config) -> None:
        engram = FakeEngram()
        service = MemoryCaptureService(
            knowledge_root=tmp_path,
            engram_save_fn=engram,
            capture_config=enabled_config,
        )
        envelope = {
            "status": "success",
            "executive_summary": "Config validated",
            "artifacts": ["build_config"],
            "next_recommended": "review",
            "risks": ["overfit"],
        }
        await service.capture_phase(
            "research-director", "campaign-7", "config", envelope
        )

        # Engram side: called once, topic agent/{agent}/{campaign}.
        assert len(engram.calls) == 1
        assert engram.calls[0]["topic_key"] == "agent/research-director/campaign-7"

        # Lake side: agent-memory/{agent}/{campaign}/memory.yaml holds the record.
        memory_file = tmp_path / "agent-memory" / "research-director" / "campaign-7" / "memory.yaml"
        import yaml

        records = yaml.safe_load(memory_file.read_text(encoding="utf-8"))
        assert isinstance(records, list)
        assert records[0]["status"] == "success"
        assert records[0]["executive_summary"] == "Config validated"
        assert records[0]["phase"] == "config"

    @pytest.mark.asyncio
    async def test_decision_includes_phase_and_config(self, tmp_path, enabled_config) -> None:
        engram = FakeEngram()
        service = MemoryCaptureService(
            knowledge_root=tmp_path,
            engram_save_fn=engram,
            capture_config=enabled_config,
        )
        phase_config = {"sqx_install_path": "/opt/SQX", "license_note": "default"}
        await service.capture_phase(
            "research-director", "campaign-7", "review",
            {"status": "success", "executive_summary": "ok"},
            config=phase_config,
        )
        import yaml

        memory_file = tmp_path / "agent-memory" / "research-director" / "campaign-7" / "memory.yaml"
        records = yaml.safe_load(memory_file.read_text(encoding="utf-8"))
        assert records[0]["phase"] == "review"
        assert records[0]["config"] == phase_config


class TestMissingFieldsDefault:
    """REQ-102 scenario: missing envelope fields default to null."""

    @pytest.mark.asyncio
    async def test_missing_next_recommended_defaults_null(self, tmp_path, enabled_config) -> None:
        engram = FakeEngram()
        service = MemoryCaptureService(
            knowledge_root=tmp_path,
            engram_save_fn=engram,
            capture_config=enabled_config,
        )
        envelope = {
            "status": "success",
            "executive_summary": "Phase done",
            "artifacts": [],
            # next_recommended and risks intentionally missing
        }
        await service.capture_phase(
            "research-director", "campaign-7", "monitor", envelope
        )
        import yaml

        memory_file = tmp_path / "agent-memory" / "research-director" / "campaign-7" / "memory.yaml"
        records = yaml.safe_load(memory_file.read_text(encoding="utf-8"))
        assert "next_recommended" in records[0]
        assert records[0]["next_recommended"] is None
        assert records[0]["risks"] is None


class TestEngramUnavailable:
    """REQ-103 scenario: Engram write failure still persists the lake."""

    @pytest.mark.asyncio
    async def test_engram_fail_lake_ok(self, tmp_path, enabled_config) -> None:
        service = MemoryCaptureService(
            knowledge_root=tmp_path,
            engram_save_fn=FailingEngram(),
            capture_config=enabled_config,
        )
        # Must NOT raise even though Engram fails.
        await service.capture_phase(
            "research-director", "campaign-7", "dispatch",
            {"status": "success", "executive_summary": "dispatched"},
        )
        import yaml

        memory_file = tmp_path / "agent-memory" / "research-director" / "campaign-7" / "memory.yaml"
        records = yaml.safe_load(memory_file.read_text(encoding="utf-8"))
        assert records[0]["status"] == "success"


class TestSaveFailureNonBlocking:
    """REQ-102 scenario: lake write failure is non-blocking."""

    @pytest.mark.asyncio
    async def test_lake_write_failure_does_not_raise(self, tmp_path, enabled_config) -> None:
        # knowledge_root points at a FILE, so agent-memory/ cannot be created.
        blocker = tmp_path / "blocker"
        blocker.write_text("not a dir", encoding="utf-8")
        service = MemoryCaptureService(
            knowledge_root=blocker,
            engram_save_fn=FakeEngram(),
            capture_config=enabled_config,
        )
        await service.capture_phase(
            "research-director", "campaign-7", "portfolio",
            {"status": "success", "executive_summary": "ok"},
        )
        # Reaching here proves the failure was swallowed (non-blocking).


class TestPrivacyScrubInSaveDecision:
    """REQ-107: save_decision scrubs before persisting to both stores."""

    @pytest.mark.asyncio
    async def test_save_decision_scrubs_license_before_write(self, tmp_path) -> None:
        engram = FakeEngram()
        manager = AgentMemoryManager(
            knowledge_root=tmp_path,
            engram_save_fn=engram,
        )
        await manager.save_decision(
            "research-director",
            "campaign-7",
            {"status": "success", "config": {"sqx_license": LICENSE}},
            phase="config",
        )
        import yaml

        memory_file = tmp_path / "agent-memory" / "research-director" / "campaign-7" / "memory.yaml"
        records = yaml.safe_load(memory_file.read_text(encoding="utf-8"))
        # Lake record: scrubbed, phase/config injected.
        assert records[0]["config"]["sqx_license"] == REDACTED
        assert records[0]["phase"] == "config"
        assert LICENSE not in str(records)
        # Engram content: scrubbed too.
        assert len(engram.calls) == 1
        assert LICENSE not in str(engram.calls[0]["content"])


class TestConfigDisabled:
    """D1: capture is config-disabled — nothing persists when disabled."""

    @pytest.mark.asyncio
    async def test_disabled_capture_writes_nothing(self, tmp_path) -> None:
        engram = FakeEngram()
        service = MemoryCaptureService(
            knowledge_root=tmp_path,
            engram_save_fn=engram,
            capture_config={"enabled": False},
        )
        await service.capture_phase(
            "research-director", "campaign-7", "research",
            {"status": "success", "executive_summary": "ok"},
        )
        memory_file = tmp_path / "agent-memory" / "research-director" / "campaign-7" / "memory.yaml"
        assert not memory_file.exists()
        assert engram.calls == []

    @pytest.mark.asyncio
    async def test_research_director_default_is_disabled(self, tmp_path) -> None:
        # ResearchDirector default: no capture config -> capture disabled.
        director = ResearchDirector(knowledge_root=tmp_path, engram_save_fn=FakeEngram())
        await director.capture_phase(
            "research-director", "campaign-7", "research",
            {"status": "success", "executive_summary": "ok"},
        )
        memory_file = tmp_path / "agent-memory" / "research-director" / "campaign-7" / "memory.yaml"
        assert not memory_file.exists()

    @pytest.mark.asyncio
    async def test_research_director_enabled_writes(self, tmp_path) -> None:
        director = ResearchDirector(
            knowledge_root=tmp_path,
            engram_save_fn=FakeEngram(),
            memory_capture_config={"enabled": True},
        )
        await director.capture_phase(
            "research-director", "campaign-7", "research",
            {"status": "success", "executive_summary": "ok"},
        )
        memory_file = tmp_path / "agent-memory" / "research-director" / "campaign-7" / "memory.yaml"
        assert memory_file.exists()


class TestSelfCorrectionCapture:
    """REQ-105: capture_phase reports repeated failure signatures (flag)."""

    @pytest.mark.asyncio
    async def test_capture_flags_repeated_failure_signature(self, tmp_path, enabled_config) -> None:
        import yaml

        camp_dir = tmp_path / "agent-memory" / "research-director" / "campaign-7"
        camp_dir.mkdir(parents=True)
        (camp_dir / "memory.yaml").write_text(
            yaml.dump(
                [
                    {
                        "status": "failed",
                        "executive_summary": "dispatch failed: data gaps in M1",
                        "phase": "dispatch",
                        "risks": ["missing data"],
                        "timestamp": "2026-01-01T00:00:00+00:00",
                    },
                    {
                        "status": "failed",
                        "executive_summary": "dispatch failed: data gaps in M1",
                        "phase": "dispatch",
                        "risks": ["missing data"],
                        "timestamp": "2026-01-02T00:00:00+00:00",
                    },
                ],
                default_flow_style=False,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        engram = FakeEngram()
        service = MemoryCaptureService(
            knowledge_root=tmp_path,
            engram_save_fn=engram,
            capture_config=enabled_config,
        )
        await service.capture_phase(
            "research-director",
            "campaign-7",
            "dispatch",
            {
                "status": "failed",
                "executive_summary": "dispatch failed: data gaps prevent execution",
                "risks": ["missing data"],
            },
        )

        records = yaml.safe_load((camp_dir / "memory.yaml").read_text(encoding="utf-8"))
        latest = records[-1]
        assert latest.get("self_correction"), "expected a self-correction flag on the captured decision"
        assert any("dispatch" in r for r in latest["self_correction"])

class TestParameterMatrixMetadataCapture:
    """Task 4.3: save_decision captures parameter-matrix metadata (REQ-34)."""

    @pytest.mark.asyncio
    async def test_save_decision_captures_matrix_meta(self, tmp_path) -> None:
        """GIVEN a decision carrying a parameter matrix
        WHEN save_decision() runs
        THEN parameter_matrix_meta (entry count + flagged deltas) is persisted
        to BOTH stores — matrix confidence < 0.3 flags feed next-cycle review.
        """
        engram = FakeEngram()
        manager = AgentMemoryManager(
            knowledge_root=tmp_path,
            engram_save_fn=engram,
        )
        matrix = [
            {"parameter": "sl_atr", "value": 2.5, "confidence": 0.2},
            {"parameter": "tp_ratio", "value": 1.8, "confidence": 0.8},
        ]
        await manager.save_decision(
            "builder-agent",
            "campaign-matrix-1",
            {"status": "success", "parameter_matrix": matrix},
            phase="config",
        )

        import yaml

        memory_file = tmp_path / "agent-memory" / "builder-agent" / "campaign-matrix-1" / "memory.yaml"
        records = yaml.safe_load(memory_file.read_text(encoding="utf-8"))
        meta = records[0]["parameter_matrix_meta"]
        assert meta["entry_count"] == 2
        assert meta["flagged"] == ["sl_atr"]
        # Engram content carries the same metadata.
        assert len(engram.calls) == 1
        assert "sl_atr" in str(engram.calls[0]["content"])

    @pytest.mark.asyncio
    async def test_matrix_meta_read_from_nested_config(self, tmp_path) -> None:
        """GIVEN the parameter matrix nested under the phase config
        WHEN save_decision() runs
        THEN the metadata is still captured (matrix may travel on config).
        """
        engram = FakeEngram()
        manager = AgentMemoryManager(
            knowledge_root=tmp_path,
            engram_save_fn=engram,
        )
        await manager.save_decision(
            "builder-agent",
            "campaign-matrix-2",
            {"status": "success"},
            phase="optimize",
            config={
                "parameter_matrix": [
                    {"parameter": "ma_period", "value": 20, "confidence": 0.15}
                ]
            },
        )

        import yaml

        memory_file = tmp_path / "agent-memory" / "builder-agent" / "campaign-matrix-2" / "memory.yaml"
        records = yaml.safe_load(memory_file.read_text(encoding="utf-8"))
        assert records[0]["parameter_matrix_meta"] == {
            "entry_count": 1,
            "flagged": ["ma_period"],
        }
        assert records[0]["phase"] == "optimize"

    @pytest.mark.asyncio
    async def test_engram_content_carries_phase(self, tmp_path) -> None:
        """GIVEN save_decision with a phase label
        THEN the Engram content records the phase explicitly (new phase
        types such as demo/archive/live-ops are captured, REQ-34/REQ-37).
        """
        engram = FakeEngram()
        manager = AgentMemoryManager(
            knowledge_root=tmp_path,
            engram_save_fn=engram,
        )
        await manager.save_decision(
            "monitoring-agent",
            "campaign-live-1",
            {"status": "success"},
            phase="live-ops",
        )

        assert len(engram.calls) == 1
        assert "**Phase**: live-ops" in engram.calls[0]["content"]

    @pytest.mark.asyncio
    async def test_no_matrix_adds_no_meta(self, tmp_path) -> None:
        """GIVEN a decision without a parameter matrix
        WHEN save_decision() runs
        THEN no parameter_matrix_meta key is injected (backward compatible).
        """
        engram = FakeEngram()
        manager = AgentMemoryManager(
            knowledge_root=tmp_path,
            engram_save_fn=engram,
        )
        await manager.save_decision(
            "research-agent",
            "campaign-plain",
            {"status": "success"},
            phase="research",
        )

        import yaml

        memory_file = tmp_path / "agent-memory" / "research-agent" / "campaign-plain" / "memory.yaml"
        records = yaml.safe_load(memory_file.read_text(encoding="utf-8"))
        assert "parameter_matrix_meta" not in records[0]
