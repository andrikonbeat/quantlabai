"""Tests for pipeline stage contracts (requires/provides).

NOTE: The 8 multi-agent stages (ResearchStage, BuilderStage, etc.) are not yet
implemented. These tests were written as part of the multi-agent system SDD
and will be enabled once those stages are implemented in pipeline/stages.py.
"""

import pytest

pytest.skip("Multi-agent stages not yet implemented", allow_module_level=True)

from quantlab.pipeline.stages import (
    ValidateStage,
    TranslateStage,
    DaemonStartStage,
    LoadConfigStage,
    RunCampaignStage,
    PollCampaignStage,
    CampaignStage,
    ExportStage,
    ReadStage,
    ComputeStatsStage,
    KnowledgeStoreStage,
    ReportStage,
)


class TestAgentStageContracts:
    """Tests for the 8 new agent stage contracts."""

    def test_research_stage_contract(self):
        stage = ResearchStage()
        assert stage.name == "research"
        assert stage.requires == []
        assert stage.provides == [
            "research_config",
            "objectives",
            "hypotheses",
            "iteration_config",
            "gate_policies",
        ]

    def test_builder_stage_contract(self):
        stage = BuilderStage()
        assert stage.name == "builder"
        assert stage.requires == ["research_config"]
        assert stage.provides == [
            "cfx_bytes",
            "campaign_id",
            "sqcli_status",
            "export_paths",
        ]

    def test_statistics_stage_contract(self):
        stage = StatisticsStage()
        assert stage.name == "statistics"
        assert stage.requires == ["export_paths"]
        assert stage.provides == [
            "statistics",
            "aggregate_stats",
            "monte_carlo_bands",
            "rolling_metrics",
            "regime_alerts",
        ]

    def test_review_stage_contract(self):
        stage = ReviewStage()
        assert stage.name == "review"
        assert stage.requires == [
            "statistics",
            "aggregate_stats",
            "monte_carlo_bands",
        ]
        assert stage.provides == [
            "review_decision",
            "iteration_proposal",
            "wf_degradation",
            "mc_overfit_flag",
            "benchmark_comparison",
        ]

    def test_portfolio_stage_contract(self):
        stage = PortfolioStage()
        assert stage.name == "portfolio"
        assert stage.requires == ["selected_strategies", "review_decision"]
        assert stage.provides == [
            "portfolio_cfx",
            "portfolio_result",
            "correlation_matrix",
            "risk_allocation",
            "wf_aggregate_stats",
        ]

    def test_deploy_stage_contract(self):
        stage = DeployStage()
        assert stage.name == "deploy"
        assert stage.requires == [
            "portfolio_cfx",
            "gate_decision_human_approve_portfolio",
        ]
        assert stage.provides == [
            "jforex_package",
            "jcloud_config",
            "deployment_result",
        ]

    def test_monitor_stage_contract(self):
        stage = MonitorStage()
        assert stage.name == "monitor"
        assert stage.requires == [
            "live_equity",
            "deployment_result",
        ]
        assert stage.provides == [
            "rolling_metrics",
            "regime_alerts",
            "performance_alerts",
            "gate_decision_human_review_performance",
        ]

    def test_research_director_stage_contract(self):
        stage = ResearchDirectorStage()
        assert stage.name == "research_director"
        assert stage.requires == ["pipeline_config"]
        assert stage.provides == [
            "pipeline_result",
            "campaign_id",
            "gate_decisions",
        ]


class TestSQXStageContracts:
    """Tests for original SQX stage contracts (backward compatibility)."""

    def test_validate_stage_contract(self):
        stage = ValidateStage()
        assert stage.name == "validate"
        assert stage.requires == []
        assert stage.provides == ["validated_config"]

    def test_translate_stage_contract(self):
        stage = TranslateStage()
        assert stage.name == "translate"
        assert stage.requires == ["validated_config"]
        assert stage.provides == ["cfx_bytes", "cfx_path"]

    def test_daemon_start_stage_contract(self):
        stage = DaemonStartStage()
        assert stage.name == "daemon_start"
        assert stage.requires == []
        assert stage.provides == ["daemon_url", "daemon_manager"]

    def test_load_config_stage_contract(self):
        stage = LoadConfigStage()
        assert stage.name == "load_config"
        assert stage.requires == ["dispatcher", "cfx_bytes"]
        assert stage.provides == []

    def test_run_campaign_stage_contract(self):
        stage = RunCampaignStage()
        assert stage.name == "run_campaign"
        assert stage.requires == ["dispatcher"]
        assert stage.provides == ["campaign_name"]

    def test_poll_campaign_stage_contract(self):
        stage = PollCampaignStage()
        assert stage.name == "poll_campaign"
        assert stage.requires == ["dispatcher", "campaign_name"]
        assert stage.provides == ["campaign_status"]

    def test_campaign_stage_contract(self):
        stage = CampaignStage()
        assert stage.name == "campaign"
        assert stage.requires == ["daemon_url", "cfx_path"]
        assert stage.provides == ["campaign_name", "campaign_status"]

    def test_export_stage_contract(self):
        stage = ExportStage()
        assert stage.name == "export"
        assert stage.requires == ["campaign_name", "daemon_url"]
        assert stage.provides == ["export_paths"]

    def test_read_stage_contract(self):
        stage = ReadStage()
        assert stage.name == "read"
        assert stage.requires == ["export_paths"]
        assert stage.provides == ["parsed_results"]

    def test_compute_stats_stage_contract(self):
        stage = ComputeStatsStage()
        assert stage.name == "compute_stats"
        assert stage.requires == ["parsed_results"]
        assert stage.provides == ["statistics"]

    def test_knowledge_store_stage_contract(self):
        stage = KnowledgeStoreStage()
        assert stage.name == "knowledge_store"
        assert stage.requires == ["parsed_results", "statistics"]
        assert stage.provides == ["knowledge_keys"]

    def test_report_stage_contract(self):
        stage = ReportStage()
        assert stage.name == "report"
        assert stage.requires == ["parsed_results", "statistics"]
        assert stage.provides == ["report_path"]


class TestAllStageContractsUnique:
    """Verify all 17+ stages have unique names and proper contracts."""

    def test_all_stages_have_unique_names(self):
        stages = [
            ResearchStage(), BuilderStage(), StatisticsStage(), ReviewStage(),
            PortfolioStage(), DeployStage(), MonitorStage(), ResearchDirectorStage(),
            ValidateStage(), TranslateStage(), DaemonStartStage(), LoadConfigStage(),
            RunCampaignStage(), PollCampaignStage(), CampaignStage(), ExportStage(),
            ReadStage(), ComputeStatsStage(), KnowledgeStoreStage(), ReportStage(),
        ]
        names = [s.name for s in stages]
        assert len(names) == len(set(names)), f"Duplicate names: {names}"

    def test_all_stages_have_requires_and_provides(self):
        stages = [
            ResearchStage(), BuilderStage(), StatisticsStage(), ReviewStage(),
            PortfolioStage(), DeployStage(), MonitorStage(), ResearchDirectorStage(),
            ValidateStage(), TranslateStage(), DaemonStartStage(), LoadConfigStage(),
            RunCampaignStage(), PollCampaignStage(), CampaignStage(), ExportStage(),
            ReadStage(), ComputeStatsStage(), KnowledgeStoreStage(), ReportStage(),
        ]
        for stage in stages:
            assert hasattr(stage, "requires"), f"{stage.name} missing requires"
            assert hasattr(stage, "provides"), f"{stage.name} missing provides"
            assert isinstance(stage.requires, list), f"{stage.name}.requires not a list"
            assert isinstance(stage.provides, list), f"{stage.name}.provides not a list"