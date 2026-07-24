"""E2E Smoke test for Phase 5b-5e: Full pipeline → history → report → query flow."""

import csv
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import yaml


class TestPhase5bESmoke:
    """End-to-end smoke test for Phase 5b-5e."""

    @pytest.fixture
    def mock_campaign_data(self, tmp_path):
        """Create mock campaign data in the Knowledge Lake."""
        kl_root = tmp_path / "knowledge"
        kl_root.mkdir(parents=True)
        
        for dir_name in ["raw", "structured", "graph", "embeddings", "datasets", "pipeline-runs", "results", "stats", "campaigns"]:
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
        
        return tmp_path


    @pytest.mark.asyncio
    async def test_phase5b_e_smoke_full_pipeline(self, mock_campaign_data):
        """Full Phase 5b-5e smoke test: pipeline → history → report → query."""
        import sys
        
        kl_root = mock_campaign_data / "knowledge"
        
        # Set env var for Knowledge Lake root
        os.environ["QUANTLAB_KNOWLEDGE_ROOT"] = str(kl_root)
        
        # Import after setting env var
        from quantlab.cli.main import main
        from quantlab.cli.main import build_parser
        
        parser = build_parser()
        
        # 1. Pipeline dry-run
        print("\n=== Step 1: Pipeline dry-run ===")
        test_args = [
            "quantlab-cli", "pipeline", "run", "SQXCampaign",
            "--dry-run",
            "--knowledge-root", str(mock_campaign_data / "knowledge"),
            "--sqx-path", "/fake/sqx",
        ]
        
        args = build_parser().parse_args(test_args[1:])
        result = await args.func(args)
        
        assert result == 0, "Pipeline dry-run should succeed"
        
        # 2. Pipeline history
        print("\n=== Step 2: Pipeline history ===")
        test_args = [
            "quantlab-cli", "pipeline", "history",
            "--knowledge-root", str(mock_campaign_data / "knowledge"),
            "--json",
        ]
        
        args = build_parser().parse_args(test_args[1:])
        result = await args.func(args)
        
        assert result == 0, "Pipeline history should succeed"
        
        # 3. Generate report
        print("\n=== Step 3: Generate report ===")
        test_args = [
            "quantlab-cli", "report", "generate", "smoke_test_campaign",
            "--output-dir", "reports",
            "--knowledge-root", str(mock_campaign_data / "knowledge"),
            "--html", "--json", "--theme", "dark",
        ]
        
        args = build_parser().parse_args(test_args[1:])
        result = await args.func(args)
        
        assert result == 0, "Report generation should succeed"
        
        # Verify report files created
        report_files = list(Path("reports").glob("smoke_test_campaign*"))
        assert len(report_files) >= 2, f"Expected HTML and JSON reports, found: {report_files}"
        print(f"Reports generated: {report_files}")
        
        # 4. Knowledge query
        print("\n=== Step 4: Knowledge query ===")
        test_args = [
            "quantlab-cli", "knowledge", "query",
            "--knowledge-root", str(mock_campaign_data / "knowledge"),
            "--sharpe", ">1.0",
            "--json",
        ]
        
        args = build_parser().parse_args(test_args[1:])
        result = await args.func(args)
        
        assert result == 0, "Knowledge query should succeed"
        
        print("\n=== All steps passed! ===")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])