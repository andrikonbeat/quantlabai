"""Tests for pipeline registry: StageRegistry and PipelineRegistry."""

import pytest
from pathlib import Path
from quantlab.pipeline.base import Stage, Pipeline
from quantlab.pipeline.registry import StageRegistry, PipelineRegistry
from quantlab.pipeline.config import PipelineConfig, StageConfig


class TestStageRegistry:
    """Tests for StageRegistry class."""

    def test_registry_initializes_with_all_stages(self):
        """Registry should contain all SQX + multi-agent stage types."""
        registry = StageRegistry()
        # Registry contains all SQX builtin + agent stages + gate + gate aliases + ...
        assert len(registry._stage_map) >= 25
        assert "research" in registry._stage_map
        assert "refutation" in registry._stage_map
        expected_stages = {
            "validate",
            "translate",
            "daemon_start",
            "load_config",
            "run_campaign",
            "poll_campaign",
            "export",
            "read",
            "compute_stats",
            "knowledge_store",
            "report",
            "research",
            "builder",
            "statistics",
            "review",
            "portfolio",
            "deploy",
            "monitor",
            "gate",
            "gate_human_review_objectives",
            "gate_human_approve_iteration",
            "gate_human_approve_portfolio",
            "gate_human_approve_deploy",
            "gate_human_review_performance",
            "campaign",
            "hypothesis_builder",
            "refutation",
            "research_llm",
            "guardian_evaluate",
            "monte_carlo",
            "cost_injection",
            # PR 3 orchestrated flow stages (REQ-17)
            "analysis",
            "config_review",
            "retester",
            "optimizer",
            "dispatch",
            # PR 6 post-optimize stages (REQ-01 phases 9-13)
            "compile",
            "demo",
            "archive",
        }
        assert set(registry._stage_map.keys()) == expected_stages

    def test_get_stage_class_returns_correct_class(self):
        """get_stage_class returns the correct SQX stage class for each name."""
        registry = StageRegistry()

        validate_cls = registry.get_stage_class("validate")
        assert validate_cls.__name__ == "SQXValidateStage"

        translate_cls = registry.get_stage_class("translate")
        assert translate_cls.__name__ == "SQXTranslateStage"

        compute_cls = registry.get_stage_class("compute_stats")
        assert compute_cls.__name__ == "SQXComputeStatsStage"

        knowledge_cls = registry.get_stage_class("knowledge_store")
        assert knowledge_cls.__name__ == "SQXKnowledgeStoreStage"

    def test_get_stage_class_returns_none_for_unknown(self, caplog):
        """get_stage_class returns None and logs warning for unknown stage."""
        registry = StageRegistry()

        result = registry.get_stage_class("unknown_stage")

        assert result is None
        assert "Unknown stage type 'unknown_stage'" in caplog.text

    def test_create_pipeline_builds_correct_pipeline(self):
        """create_pipeline builds Pipeline with all stages in order."""
        registry = StageRegistry()
        config = PipelineConfig(
            name="test_pipeline",
            description="Test",
            stages=[
                StageConfig(name="validate", type="builtin", config={"dry_run": True}),
                StageConfig(name="translate", type="builtin", config={}),
                StageConfig(name="export", type="builtin", config={}),
            ],
        )

        pipeline = registry.create_pipeline(config)

        assert pipeline.name == "test_pipeline"
        assert len(pipeline.stages) == 3
        assert pipeline.stages[0].name == "validate"
        assert pipeline.stages[1].name == "translate"
        assert pipeline.stages[2].name == "export"
        # Verify they are SQX concrete stages
        assert pipeline.stages[0].__class__.__name__ == "SQXValidateStage"
        assert pipeline.stages[1].__class__.__name__ == "SQXTranslateStage"
        assert pipeline.stages[2].__class__.__name__ == "SQXExportStage"

    def test_create_pipeline_raises_on_unknown_stage_type(self):
        """create_pipeline raises ValueError for non-builtin stage type."""
        registry = StageRegistry()
        config = PipelineConfig(
            name="test",
            stages=[StageConfig(name="validate", type="custom", config={})],
        )

        with pytest.raises(ValueError, match="Unknown stage type 'custom'"):
            registry.create_pipeline(config)

    def test_create_pipeline_raises_on_unknown_stage_name(self):
        """create_pipeline raises ValueError for unknown builtin stage name."""
        registry = StageRegistry()
        config = PipelineConfig(
            name="test",
            stages=[StageConfig(name="nonexistent", type="builtin", config={})],
        )

        with pytest.raises(ValueError, match="Unknown stage 'nonexistent'"):
            registry.create_pipeline(config)

    def test_create_pipeline_uses_stage_config(self):
        """Stage config dict is passed to stage constructor (if supported)."""
        registry = StageRegistry()
        config = PipelineConfig(
            name="test",
            stages=[
                StageConfig(name="validate", type="builtin", config={"dry_run": True}),
            ],
        )

        pipeline = registry.create_pipeline(config)
        stage = pipeline.stages[0]

        # SQXValidateStage should have been instantiated
        assert stage.__class__.__name__ == "SQXValidateStage"


class TestPipelineConfig:
    """Tests for PipelineConfig model."""

    def test_load_from_yaml(self, tmp_path):
        """PipelineConfig.from_yaml loads YAML file correctly."""
        yaml_content = """
name: "TestPipeline"
description: "A test pipeline"
stages:
  - name: validate
    type: builtin
    config:
      dry_run: true
  - name: translate
    type: builtin
    config: {}
"""
        yaml_path = tmp_path / "test_pipeline.yaml"
        yaml_path.write_text(yaml_content.strip())

        config = PipelineConfig.from_yaml(yaml_path)

        assert config.name == "TestPipeline"
        assert config.description == "A test pipeline"
        assert len(config.stages) == 2
        assert config.stages[0].name == "validate"
        assert config.stages[0].type == "builtin"
        assert config.stages[0].config == {"dry_run": True}
        assert config.stages[1].name == "translate"
        assert config.stages[1].type == "builtin"
        assert config.stages[1].config == {}

    def test_from_yaml_uses_filename_as_name_if_missing(self, tmp_path):
        """from_yaml uses file stem as name if not in YAML."""
        yaml_content = """
description: "No name in yaml"
stages:
  - name: validate
    type: builtin
    config: {}
"""
        yaml_path = tmp_path / "my_pipeline.yaml"
        yaml_path.write_text(yaml_content.strip())

        config = PipelineConfig.from_yaml(yaml_path)

        assert config.name == "my_pipeline"

    def test_to_dict_roundtrip(self):
        """to_dict and from_yaml preserve data."""
        config = PipelineConfig(
            name="RoundTrip",
            description="Test",
            stages=[
                StageConfig(name="validate", type="builtin", config={"a": 1}),
                StageConfig(name="translate", type="builtin", config={}),
            ],
        )
        data = config.to_dict()

        assert data["name"] == "RoundTrip"
        assert data["description"] == "Test"
        assert len(data["stages"]) == 2
        assert data["stages"][0]["config"] == {"a": 1}

    def test_save_and_load_roundtrip(self, tmp_path):
        """save() then from_yaml() preserves config."""
        config = PipelineConfig(
            name="SavedPipeline",
            description="Saved",
            stages=[
                StageConfig(name="validate", type="builtin", config={"dry_run": False}),
            ],
        )
        path = tmp_path / "saved.yaml"
        config.save(path)

        loaded = PipelineConfig.from_yaml(path)

        assert loaded.name == "SavedPipeline"
        assert loaded.description == "Saved"
        assert len(loaded.stages) == 1
        assert loaded.stages[0].config == {"dry_run": False}


class TestPipelineSummary:
    """Tests for PipelineSummary model."""

    def test_summary_has_required_fields(self):
        """PipelineSummary has name, stage_count, description."""
        from quantlab.pipeline.config import PipelineSummary

        summary = PipelineSummary(name="Test", stage_count=5, description="Desc")

        assert summary.name == "Test"
        assert summary.stage_count == 5
        assert summary.description == "Desc"


class TestPipelineRegistry:
    """Tests for PipelineRegistry class."""

    def test_discover_finds_pipeline_yaml(self, tmp_path):
        """discover() finds pipeline YAML files in config dirs."""
        # Create test pipeline YAML
        yaml_content = """
name: "DiscoveredPipeline"
description: "Found by registry"
stages:
  - name: validate
    type: builtin
    config: {}
"""
        pipeline_dir = tmp_path / "pipelines"
        pipeline_dir.mkdir()
        (pipeline_dir / "test.yaml").write_text(yaml_content.strip())

        registry = PipelineRegistry(config_dirs=[str(pipeline_dir)])
        summaries = registry.discover()

        assert len(summaries) == 1
        assert summaries[0].name == "DiscoveredPipeline"
        assert summaries[0].stage_count == 1
        assert summaries[0].description == "Found by registry"

    def test_discover_ignores_missing_directories(self):
        """discover() logs debug and continues if dir doesn't exist."""
        registry = PipelineRegistry(config_dirs=["/nonexistent/path"])
        summaries = registry.discover()

        assert summaries == []

    def test_get_returns_full_config(self, tmp_path):
        """get(name) returns full PipelineConfig."""
        yaml_content = """
name: "GetPipeline"
description: "Full config"
stages:
  - name: validate
    type: builtin
    config:
      dry_run: false
  - name: translate
    type: builtin
    config: {}
"""
        pipeline_dir = tmp_path / "pipelines"
        pipeline_dir.mkdir()
        (pipeline_dir / "get.yaml").write_text(yaml_content.strip())

        registry = PipelineRegistry(config_dirs=[str(pipeline_dir)])
        config = registry.get("GetPipeline")

        assert config.name == "GetPipeline"
        assert len(config.stages) == 2
        assert config.stages[0].config == {"dry_run": False}

    def test_get_raises_keyerror_for_missing(self, tmp_path):
        """get() raises KeyError with available names for unknown pipeline."""
        pipeline_dir = tmp_path / "pipelines"
        pipeline_dir.mkdir()
        (pipeline_dir / "exists.yaml").write_text("name: 'Exists'\nstages: []")

        registry = PipelineRegistry(config_dirs=[str(pipeline_dir)])

        with pytest.raises(KeyError, match="Pipeline 'Missing' not found"):
            registry.get("Missing")

    def test_list_returns_all_summaries(self, tmp_path):
        """list() returns summaries for all discovered pipelines."""
        yaml1 = """
name: "Pipe1"
description: "First"
stages:
  - name: validate
    type: builtin
    config: {}
"""
        yaml2 = """
name: "Pipe2"
description: "Second"
stages:
  - name: validate
    type: builtin
    config: {}
  - name: translate
    type: builtin
    config: {}
"""
        pipeline_dir = tmp_path / "pipelines"
        pipeline_dir.mkdir()
        (pipeline_dir / "pipe1.yaml").write_text(yaml1.strip())
        (pipeline_dir / "pipe2.yaml").write_text(yaml2.strip())

        registry = PipelineRegistry(config_dirs=[str(pipeline_dir)])
        summaries = registry.list()

        assert len(summaries) == 2
        names = {s.name for s in summaries}
        assert names == {"Pipe1", "Pipe2"}

    def test_names_returns_sorted_names(self, tmp_path):
        """names() returns alphabetically sorted pipeline names."""
        yaml1 = "name: 'Zebra'\nstages: []"
        yaml2 = "name: 'Alpha'\nstages: []"
        pipeline_dir = tmp_path / "pipelines"
        pipeline_dir.mkdir()
        (pipeline_dir / "z.yaml").write_text(yaml1)
        (pipeline_dir / "a.yaml").write_text(yaml2)

        registry = PipelineRegistry(config_dirs=[str(pipeline_dir)])
        names = registry.names()

        assert names == ["Alpha", "Zebra"]

    def test_reload_forces_rediscovery(self, tmp_path):
        """reload() clears cache and re-discovers."""
        pipeline_dir = tmp_path / "pipelines"
        pipeline_dir.mkdir()
        (pipeline_dir / "first.yaml").write_text("name: 'First'\nstages: []")

        registry = PipelineRegistry(config_dirs=[str(pipeline_dir)])
        assert registry.names() == ["First"]

        # Add second file
        (pipeline_dir / "second.yaml").write_text("name: 'Second'\nstages: []")

        # Without reload, still only first
        assert registry.names() == ["First"]

        # With reload, both
        registry.reload()
        assert set(registry.names()) == {"First", "Second"}

    def test_build_pipeline_creates_runnable_pipeline(self, tmp_path):
        """build_pipeline() returns Pipeline with SQX stages."""
        yaml_content = """
name: "BuildTest"
stages:
  - name: validate
    type: builtin
    config: {}
  - name: translate
    type: builtin
    config: {}
"""
        pipeline_dir = tmp_path / "pipelines"
        pipeline_dir.mkdir()
        (pipeline_dir / "build.yaml").write_text(yaml_content.strip())

        registry = PipelineRegistry(config_dirs=[str(pipeline_dir)])
        pipeline = registry.build_pipeline("BuildTest")

        assert pipeline.name == "BuildTest"
        assert len(pipeline.stages) == 2
        assert pipeline.stages[0].__class__.__name__ == "SQXValidateStage"
        assert pipeline.stages[1].__class__.__name__ == "SQXTranslateStage"

    def test_build_pipeline_raises_for_unknown(self, tmp_path):
        """build_pipeline() raises KeyError for unknown pipeline."""
        pipeline_dir = tmp_path / "pipelines"
        pipeline_dir.mkdir()

        registry = PipelineRegistry(config_dirs=[str(pipeline_dir)])

        with pytest.raises(KeyError):
            registry.build_pipeline("Unknown")


class TestIntegration:
    """Integration tests combining registry and config."""

    def test_full_flow_yaml_to_pipeline(self, tmp_path):
        """Complete flow: YAML -> PipelineRegistry -> Pipeline -> run."""
        yaml_content = """
name: "IntegrationTest"
description: "Full integration"
stages:
  - name: validate
    type: builtin
    config:
      dry_run: true
  - name: translate
    type: builtin
    config: {}
  - name: export
    type: builtin
    config: {}
"""
        pipeline_dir = tmp_path / "pipelines"
        pipeline_dir.mkdir()
        (pipeline_dir / "integration.yaml").write_text(yaml_content.strip())

        registry = PipelineRegistry(config_dirs=[str(pipeline_dir)])

        # Discover
        summaries = registry.discover()
        assert len(summaries) == 1
        assert summaries[0].name == "IntegrationTest"

        # Get config
        config = registry.get("IntegrationTest")
        assert len(config.stages) == 3

        # Build pipeline
        pipeline = registry.build_pipeline("IntegrationTest")
        assert pipeline.name == "IntegrationTest"
        assert len(pipeline.stages) == 3

        # Verify stage types
        stage_names = [s.name for s in pipeline.stages]
        assert stage_names == ["validate", "translate", "export"]
        stage_classes = [s.__class__.__name__ for s in pipeline.stages]
        assert stage_classes == [
            "SQXValidateStage",
            "SQXTranslateStage",
            "SQXExportStage",
        ]

    def test_all_11_stage_types_resolvable(self):
        """All 11 SQX stage types can be resolved and instantiated."""
        registry = StageRegistry()

        all_stage_names = [
            "validate",
            "translate",
            "daemon_start",
            "load_config",
            "run_campaign",
            "poll_campaign",
            "export",
            "read",
            "compute_stats",
            "knowledge_store",
            "report",
        ]

        for name in all_stage_names:
            stage_class = registry.get_stage_class(name)
            assert stage_class is not None, f"Stage {name} not registered"
            instance = stage_class()
            assert instance is not None
            assert instance.name == name


if __name__ == "__main__":
    pytest.main([__file__, "-v"])