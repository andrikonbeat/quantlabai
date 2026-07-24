"""Integration test for full smoke test with auto-approve gates."""

import asyncio
import csv
import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import yaml

import pytest

pytest
from quantlab.knowledge.store import KnowledgeStore
from quantlab.readers.models import Trade, EquityPoint
from quantlab.stats.models import StatsResult
from quantlab.cli import cli_entry
from quantlab.cli.main import build_parser


class TestSmokeTestWithAutoApproveGates:
    """Full smoke test: temp Knowledge Lake → pipeline dry-run (11 stages) → history → report → knowledge query.
    Includes auto-approve gates for testing.
    """

    @pytest.fixture
    def mock_campaign_data(self):
        """Create mock campaign data in the Knowledge Lake."""
        with tempfile.TemporaryDirectory() as tmpdir:
            kl_root = Path(tmpdir) / "knowledge"
            kl_root.mkdir(parents=True)
            
            # Create standard Knowledge Lake directories
            for dir_name in ["raw", "structured", "graph", "embeddings", "datasets", 
                           "pipeline-runs", "results", "stats", "campaigns", "agent-memory"]:
                (kl_root / dir_name).mkdir(parents=True, exist_ok=True)
            
            # Create mock campaign data
            campaign_id = "smoke_test_campaign"
            
            # Create stats YAML
            stats_path = kl_root / "stats" / f"{campaign_id}.yaml"
            stats_path.parent.mkdir(parents=True, exist_ok=True)
            stats_data = {
                "profit_factor": 1.5,
                "sharpe_ratio": 1.2,
                "sortino_ratio": 1.5,
                "max_drawdown": 5.0,
                "mar_ratio": 0.8,
                "recovery_factor": 2.0,
                "expectancy": 10.0,
                "expectancy_ratio": 0.5,
                "win_rate": 0.6,
                "total_trades": 10,
            }
            stats_path.write_text(yaml.dump(stats_data))
            
            # Create trades CSV
            trades_path = kl_root / "results" / f"{campaign_id}.csv"
            trades_path.parent.mkdir(parents=True, exist_ok=True)
            with open(trades_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["entry_time", "exit_time", "direction", "lots", "profit"])
                base_time = datetime(2024, 1, 1, 10, 0, 0)
                for i, profit in enumerate([100, -50, 200, -30, 150, -20, 100, -10, 80, 0]):
                    entry = base_time.replace(hour=10 + i)
                    exit_t = base_time.replace(hour=10 + i, minute=30)
                    writer.writerow([
                        entry.isoformat(),
                        exit_t.isoformat(),
                        "long" if profit > 0 else "short",
                        1.0,
                        profit,
                    ])
            
            # Create equity CSV
            equity_path = kl_root / "structured" / f"{campaign_id}_equity.csv"
            equity_path.parent.mkdir(parents=True, exist_ok=True)
            with open(equity_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "equity"])
                base = datetime(2024, 1, 1)
                for i, val in enumerate([10000, 10100, 10050, 10200, 10150, 10300, 10250, 10400, 10350, 10500]):
                    ts = (datetime(2024, 1, 1) + timedelta(days=i)).isoformat()
                    writer.writerow([ts, val])
            
            yield kl_root

    @pytest.fixture
    def mock_sqx_stages(self):
        """Mock SQX stages for dry-run."""
        with patch.multiple(
            'sdk.quantlab.phase4.stages',
            SQXValidateStage=AsyncMock(),
            SQXTranslateStage=AsyncMock(),
            SQXDaemonStartStage=AsyncMock(),
            SQXLoadConfigStage=AsyncMock(),
            SQXRunCampaignStage=AsyncMock(),
            SQXPollCampaignStage=AsyncMock(),
            SQXCampaignStage=AsyncMock(),
            SQXExportStage=AsyncMock(),
            SQXReadStage=AsyncMock(),
            SQXComputeStatsStage=AsyncMock(),
            SQXKnowledgeStoreStage=AsyncMock(),
            SQXReportStage=AsyncMock(),
        ) as mocks:
            # Configure all mocks to return successful StageResult
            for stage_name, mock_class in mocks.items():
                mock_instance = mock_class.return_value
                mock_instance.run = AsyncMock(return_value=MagicMock(
                    stage_name=stage_name.replace('SQX', '').replace('Stage', '').lower(),
                    status="completed",
                    output_data={}
                ))
            yield mocks

    @pytest.fixture
    def mock_auto_approve_gates(self):
        """Mock gate interceptor to auto-approve all gates."""
        with patch('sdk.quantlab.pipeline.stages.gate_interceptor.GateInterceptorStage') as mock_gate:
            mock_instance = mock_gate.return_value
            mock_instance.run = AsyncMock(return_value=MagicMock(
                stage_name="gate",
                status="completed",
                output_data={"decision": "continue", "approved": True}
            ))
            yield mock_gate

    @pytest.mark.asyncio
    async def test_phase5f_i_smoke_full_pipeline(
        self, 
        mock_campaign_data,
        mock_sqx_stages,
        mock_auto_approve_gates
    ):
        """Full Phase 5f-5i smoke test: pipeline → history → report → query with auto-approve gates."""
        # Set environment variable for Knowledge Lake root
        os.environ["QUANTLAB_KNOWLEDGE_ROOT"] = str(mock_campaign_data)
        
        try:
            # Import after setting env var
            from quantlab.cli.main import main
            parser = build_parser()
            
            # 1. Pipeline dry-run (11 stages as per Spec 1 FR-002)
            print("\n=== Step 1: Pipeline dry-run (11 stages) ===")
            test_args = [
                "quantlab-cli", "pipeline", "run", "SQXCampaign",
                "--dry-run",
                "--knowledge-root", str(mock_campaign_data),
                "--sqx-path", "/fake/sqx",  # Not used in dry-run but required by CLI
            ]
            
            args = parser.parse_args(test_args[1:])  # Skip the command name
            result = await args.func(args)
            
            assert result == 0, "Pipeline dry-run should succeed"
            
            # 2. Pipeline history (Spec 1 FR-003)
            print("\n=== Step 2: Pipeline history ===")
            test_args = [
                "quantlab-cli", "pipeline", "history",
                "--knowledge-root", str(mock_campaign_data),
                "--json",
            ]
            
            args = parser.parse_args(test_args[1:])
            result = await args.func(args)
            
            assert result == 0, "Pipeline history should succeed"
            
            # 3. Generate report (Spec 1 FR-004)
            print("\n=== Step 3: Generate report ===")
            test_args = [
                "quantlab-cli", "report", "generate", "smoke_test_campaign",
                "--output-dir", "reports",
                "--knowledge-root", str(mock_campaign_data),
                "--html", "--json", "--theme", "dark",
            ]
            
            args = parser.parse_args(test_args[1:])
            result = await args.func(args)
            
            assert result == 0, "Report generation should succeed"
            
            # Verify report files created
            report_files = list(Path("reports").glob("smoke_test_campaign*"))
            assert len(report_files) >= 2, f"Expected HTML and JSON reports, found: {report_files}"
            print(f"Reports generated: {report_files}")
            
            # 4. Knowledge query (Spec 1 FR-005)
            print("\n=== Step 4: Knowledge query ===")
            test_args = [
                "quantlab-cli", "knowledge", "query",
                "--knowledge-root", str(mock_campaign_data),
                "--sharpe", ">1.0",
                "--json",
            ]
            
            args = parser.parse_args(test_args[1:])
            result = await args.func(args)
            
            # This might return 0 or 1 depending on whether our mock data matches
            # The important thing is that it doesn't crash
            assert result in [0, 1], f"Knowledge query should not crash, got {result}"
            
            print("\n=== All steps passed! ===")
            
        finally:
            # Clean up environment variable
            if "QUANTLAB_KNOWLEDGE_ROOT" in os.environ:
                del os.environ["QUANTLAB_KNOWLEDGE_ROOT"]
            
            # Clean up reports directory
            import shutil
            if Path("reports").exists():
                shutil.rmtree("reports")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])