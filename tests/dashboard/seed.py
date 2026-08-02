"""Seeding helpers for dashboard API tests.

Write campaigns, export artifacts, and pipeline runs into a throwaway
KnowledgeStore so the API endpoints can be exercised against real lake
data without touching the repository's own ``knowledge/`` directory.
"""

import json

import yaml


def seed_campaign(
    store,
    campaign_id,
    *,
    market="EURUSD",
    timeframe="H1",
    status="completed",
    metrics=None,
    created="2026-01-01T00:00:00",
):
    """Write a campaign entry into the Knowledge Lake index (``results/``).

    Mirrors the enhanced-index shape the query layer reads: an entry under
    ``directories.results`` carrying ``path``, ``metrics``, ``market``,
    ``timeframe``, ``status``, ``tags``, and ``created``.

    Pass ``metrics=None`` for a campaign with no metric data at all; pass a
    dict to override (or supply the full set).
    """
    default_metrics = {
        "sharpe_ratio": 1.5,
        "profit_factor": 1.8,
        "win_rate": 0.55,
        "max_drawdown": -12.0,
        "total_trades": 120,
        "net_profit": 2500.0,
        "total_return": 0.18,
    }
    if metrics is None:
        metrics = default_metrics
    idx = store.read_index()
    idx.setdefault("directories", {}).setdefault("results", {})
    idx["directories"]["results"][f"results/{campaign_id}/stats.yaml"] = {
        "path": f"results/{campaign_id}",
        "metrics": metrics,
        "market": market,
        "timeframe": timeframe,
        "status": status,
        "tags": ["trend"],
        "created": created,
    }
    (store.root / "index.yaml").write_text(
        yaml.dump(idx, default_flow_style=False, sort_keys=False), encoding="utf-8"
    )


def seed_campaign_without_metrics(store, campaign_id, **metadata):
    """Seed a campaign entry carrying no metrics (empty-safe contract)."""
    seed_campaign(store, campaign_id, metrics={}, **metadata)


def seed_export_data(store, campaign_id, *, trades=None, equity=None, statistics=None):
    """Write real export artifacts under ``structured/{campaign_id}/``."""
    default_trades = [
        {
            "entry_time": "2026-01-01T10:00:00",
            "exit_time": "2026-01-01T11:00:00",
            "direction": "long",
            "lots": 1.0,
            "profit": 150.0,
        },
        {
            "entry_time": "2026-01-02T10:00:00",
            "exit_time": "2026-01-02T11:30:00",
            "direction": "short",
            "lots": 1.5,
            "profit": -60.0,
        },
    ]
    default_equity = [
        {"timestamp": "2026-01-01T00:00:00", "equity": 100000.0},
        {"timestamp": "2026-01-02T00:00:00", "equity": 100250.0},
    ]
    default_statistics = {
        "sharpe_ratio": 1.5,
        "profit_factor": 1.8,
        "win_rate": 0.55,
        "max_drawdown": -12.0,
        "total_trades": 120,
    }
    campaign_dir = store.root / "structured" / campaign_id
    campaign_dir.mkdir(parents=True, exist_ok=True)
    (campaign_dir / "trades.json").write_text(
        json.dumps(trades if trades is not None else default_trades), encoding="utf-8"
    )
    (campaign_dir / "equity.json").write_text(
        json.dumps(equity if equity is not None else default_equity), encoding="utf-8"
    )
    (campaign_dir / "statistics.json").write_text(
        json.dumps(statistics if statistics is not None else default_statistics),
        encoding="utf-8",
    )
