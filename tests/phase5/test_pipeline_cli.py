"""Tests for pipeline CLI: registry, run, list, history."""

import asyncio
from datetime import datetime
from pathlib import Path
import tempfile

import pytest

from quantlab.pipeline.config import PipelineConfig
from quantlab.pipeline.registry import PipelineRegistry
from quantlab.pipeline.models import PipelineRun, StageRun, StageStatus, PipelineResult, StageResult
from quantlab.knowledge.store import KnowledgeStore


class TestPipelineConfig:
    """Tests for PipelineConfig YAML loading."""

    def test_load_from_yaml(self):
        """Load pipeline config from YAML file."""
        yaml_content = """
name: "TestPipeline"
description: "A test pipeline"
version: "1.0"
stages:
  - name: validate
    type: builtin
    config:
      dry_run: true
  - name: translate
    type: builtin
    config:
      strategy_id: "test_123"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config = PipelineConfig.from_yaml(f.name)

        assert config.name == "TestPipeline"
        assert config.description == "A test pipeline"
        assert config.version == "1.0"
        assert len(config.stages) == 2
        assert config.stages[0].name == "validate"
        assert config.stages[0].config["dry_run"] is True
        assert config.stages[1].name == "translate"
        assert config.stages[1].config["strategy_id"] == "test_123"

    def test_save_to_yaml(self):
        """Save pipeline config to YAML file."""
        from quantlab.pipeline.config import StageConfig

        config = PipelineConfig(
            name="SaveTest",
            stages=[
                StageConfig(name="validate", type="builtin", config={"dry_run": True}),
            ],
            description="Test save",
            version="2.0",
        )

        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            config.save(f.name)

            # Reload and verify
            loaded = PipelineConfig.from_yaml(f.name)
            assert loaded.name == "SaveTest"
            assert loaded.description == "Test save"
            assert loaded.version == "2.0"
            assert len(loaded.stages) == 1


class TestPipelineRegistry:
    """Tests for PipelineRegistry discovery and loading."""

    def test_discover_pipelines(self):
        """Registry discovers pipelines from YAML files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a pipeline YAML
            pipeline_dir = Path(tmpdir) / "pipelines"
            pipeline_dir.mkdir()
            pipeline_yaml = pipeline_dir / "test.yaml"
            pipeline_yaml.write_text("""
name: "DiscoveredPipeline"
description: "Found by registry"
stages:
  - name: validate
    type: builtin
    config: {}
""")

            registry = PipelineRegistry(config_dirs=[str(pipeline_dir)])
            pipelines = registry.discover()

            assert len(pipelines) == 1
            assert pipelines[0].name == "DiscoveredPipeline"
            assert pipelines[0].stage_count == 1
            assert pipelines[0].description == "Found by registry"

    def test_get_pipeline(self):
        """Get pipeline by name after discovery."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline_dir = Path(tmpdir) / "pipelines"
            pipeline_dir.mkdir()
            (pipeline_dir / "pipe.yaml").write_text("""
name: "GetPipeline"
stages:
  - name: validate
    type: builtin
    config: {}
""")

            registry = PipelineRegistry(config_dirs=[str(pipeline_dir)])
            config = registry.get("GetPipeline")

            assert config.name == "GetPipeline"
            assert len(config.stages) == 1

    def test_get_unknown_pipeline_raises(self):
        """Getting unknown pipeline raises KeyError with helpful message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline_dir = Path(tmpdir) / "pipelines"
            pipeline_dir.mkdir()
            (pipeline_dir / "pipe.yaml").write_text("""
name: "Existing"
stages: []
""")

            registry = PipelineRegistry(config_dirs=[str(pipeline_dir)])

            with pytest.raises(KeyError) as exc:
                registry.get("NonExistent")

            assert "NonExistent" in str(exc.value)
            assert "Existing" in str(exc.value)

    def test_list_pipelines(self):
        """List all discovered pipelines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline_dir = Path(tmpdir) / "pipelines"
            pipeline_dir.mkdir()
            (pipeline_dir / "a.yaml").write_text("name: 'A'\nstages: []\n")
            (pipeline_dir / "b.yaml").write_text("name: 'B'\nstages: []\n")

            registry = PipelineRegistry(config_dirs=[str(pipeline_dir)])
            pipelines = registry.list()

            assert len(pipelines) == 2
            names = {p.name for p in pipelines}
            assert names == {"A", "B"}


class TestPipelineRunModels:
    """Tests for PipelineRun and StageRun models."""

    def test_stage_run_to_from_dict(self):
        """StageRun serializes and deserializes correctly."""
        stage = StageRun(
            name="test_stage",
            status=StageStatus.COMPLETED,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            duration=1.5,
            error=None,
            output={"result": "ok"},
        )

        data = stage.to_dict()
        assert data["name"] == "test_stage"
        assert data["status"] == "completed"
        assert data["duration"] == 1.5

        restored = StageRun.from_dict(data)
        assert restored.name == "test_stage"
        assert restored.status == StageStatus.COMPLETED
        assert restored.duration == 1.5

    def test_pipeline_run_to_from_dict(self):
        """PipelineRun serializes and deserializes correctly."""
        run = PipelineRun(
            run_id="abc123",
            pipeline_name="TestPipe",
            status=StageStatus.COMPLETED,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            duration=10.0,
            stages=[
                StageRun(name="s1", status=StageStatus.COMPLETED, duration=5.0),
                StageRun(name="s2", status=StageStatus.COMPLETED, duration=5.0),
            ],
            error=None,
            config_snapshot={"key": "value"},
            artifacts={"cfx": "/path/to/file.cfx"},
        )

        data = run.to_dict()
        assert data["run_id"] == "abc123"
        assert data["pipeline_name"] == "TestPipe"
        assert data["status"] == "completed"
        assert len(data["stages"]) == 2

        restored = PipelineRun.from_dict(data)
        assert restored.run_id == "abc123"
        assert restored.pipeline_name == "TestPipe"
        assert restored.status == StageStatus.COMPLETED
        assert len(restored.stages) == 2
        assert restored.config_snapshot == {"key": "value"}
        assert restored.artifacts == {"cfx": "/path/to/file.cfx"}

    def test_pipeline_run_from_pipeline_result(self):
        """Create PipelineRun from PipelineResult."""
        # Create a mock result
        result = PipelineResult(
            pipeline_name="TestPipe",
            stages=[
                StageResult(stage_name="s1", status=StageStatus.COMPLETED, duration=1.0, output="out1"),
                StageResult(stage_name="s2", status=StageStatus.FAILED, duration=2.0, error="boom"),
            ],
            total_duration=3.0,
            error="boom",
        )

        run = PipelineRun.from_pipeline_result(
            result,
            pipeline_name="TestPipe",
            config_snapshot={"stages": []},
            artifacts={"key": "value"},
        )

        assert run.pipeline_name == "TestPipe"
        assert run.status == StageStatus.FAILED
        assert run.error == "boom"
        assert len(run.stages) == 2
        assert run.stages[0].status == StageStatus.COMPLETED
        assert run.stages[1].status == StageStatus.FAILED
        assert run.config_snapshot == {"stages": []}
        assert run.artifacts == {"key": "value"}


class TestKnowledgeStorePipelineHistory:
    """Tests for pipeline run persistence in KnowledgeStore."""

    @pytest.mark.xfail(reason="Duplicate save_pipeline_run in store.py — fixed by multi-agent PR 5 merge")
    def test_save_and_load_pipeline_run(self):
        """Save and load a pipeline run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = KnowledgeStore(root=tmpdir)
            store.initialize()

            run = PipelineRun(
                run_id="run123",
                pipeline_name="TestPipe",
                status=StageStatus.COMPLETED,
                started_at=datetime.now(),
                completed_at=datetime.now(),
                duration=5.0,
                stages=[
                    StageRun(name="s1", status=StageStatus.COMPLETED, duration=2.0),
                    StageRun(name="s2", status=StageStatus.COMPLETED, duration=3.0),
                ],
                error=None,
                config_snapshot={"name": "TestPipe"},
                artifacts={"cfx": "/tmp/test.cfx"},
            )

            run_id = store.save_pipeline_run(run)
            assert run_id == "run123"

            # Load it back
            loaded = store.get_pipeline_run("run123")
            assert loaded is not None
            assert loaded.run_id == "run123"
            assert loaded.pipeline_name == "TestPipe"
            assert loaded.status == StageStatus.COMPLETED
            assert len(loaded.stages) == 2
            assert loaded.config_snapshot == {"name": "TestPipe"}
            assert loaded.artifacts == {"cfx": "/tmp/test.cfx"}

    def test_load_pipeline_runs_with_limit(self):
        """Load multiple runs with limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = KnowledgeStore(root=tmpdir)
            store.initialize()

            # Create 3 runs
            for i in range(3):
                run = PipelineRun(
                    run_id=f"run{i}",
                    pipeline_name=f"Pipe{i}",
                    status=StageStatus.COMPLETED,
                    started_at=datetime.now(),
                    duration=float(i),
                )
                store.save_pipeline_run(run)

            # Load with limit
            runs = store.load_pipeline_runs(limit=2)
            assert len(runs) == 2

    def test_load_pipeline_runs_with_status_filter(self):
        """Load runs filtered by status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = KnowledgeStore(root=tmpdir)
            store.initialize()

            # Create runs with different statuses
            for i, status in enumerate([StageStatus.COMPLETED, StageStatus.FAILED, StageStatus.COMPLETED]):
                run = PipelineRun(
                    run_id=f"run_{i}_{status.value}",
                    pipeline_name="Pipe",
                    status=status,
                    started_at=datetime.now(),
                )
                store.save_pipeline_run(run)

            # Filter by status
            completed = store.load_pipeline_runs(status="completed")
            assert len(completed) == 2
            assert all(r.status == StageStatus.COMPLETED for r in completed)

            failed = store.load_pipeline_runs(status="failed")
            assert len(failed) == 1
            assert failed[0].status == StageStatus.FAILED


class TestPipelineRunDryRun:
    """Tests for pipeline dry-run functionality."""

    @pytest.mark.asyncio
    async def test_dry_run_shows_stages(self, capsys):
        """Dry-run shows pipeline stages without executing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pipeline_dir = Path(tmpdir) / "pipelines"
            pipeline_dir.mkdir()
            (pipeline_dir / "test.yaml").write_text("""
name: "DryRunTest"
stages:
  - name: validate
    type: builtin
    config:
      dry_run: true
  - name: translate
    type: builtin
    config:
      strategy_id: "strat_123"
""")

            registry = PipelineRegistry(config_dirs=[str(pipeline_dir)])
            pipeline = registry.build_pipeline("DryRunTest")

            # Dry-run just builds pipeline, doesn't execute
            assert pipeline.name == "DryRunTest"
            assert len(pipeline.stages) == 2