"""Flask application for the QuantLab Dashboard."""

from __future__ import annotations

import os
import sys
import json
import signal
import statistics as py_stats
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from flask import Flask, jsonify, render_template, request

from quantlab.cli.runner import CliRunner, MockExecutor
from quantlab.knowledge.store import KnowledgeStore
from quantlab.readers.models import Trade, EquityPoint
from quantlab.reporting.generator import ReportGenerator, ReportConfig, ReportFormat, ReportTheme
from quantlab.stats.models import StatsResult
from quantlab.tools.platform import get_sqcli_binary, resolve_sqcli_path

# Documented default SQX install path (no machine-specific paths).
DEFAULT_SQX_INSTALL_PATH = "assets/SQX_144_2953_linux_20260601"


# ─── Configuration ────────────────────────────────────────────────────────────

class ServerConfig:
    """Configuration for the dashboard server."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        debug: bool = False,
        sqx_install_path: Optional[str] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.debug = debug
        self.sqx_install_path = sqx_install_path


def resolve_sqcli_binary(config: Optional[ServerConfig] = None) -> Optional[str]:
    """Resolve the sqcli binary by precedence (DSH-01).

    Chain: config → ``SQX_INSTALL_PATH`` env → documented default.
    Returns the binary path when resolvable, ``None`` otherwise (the
    caller reports a clear "sqcli unavailable" error instead of crashing).
    """
    candidates: list[str] = []
    if config and getattr(config, "sqx_install_path", None):
        candidates.append(config.sqx_install_path)
    env_path = os.environ.get("SQX_INSTALL_PATH")
    if env_path:
        candidates.append(env_path)
    candidates.append(DEFAULT_SQX_INSTALL_PATH)

    binary_name = get_sqcli_binary()
    for install_path in candidates:
        binary = resolve_sqcli_path(Path(install_path) / binary_name)
        if binary is not None:
            return str(binary)
    return None


def _knowledge_store() -> KnowledgeStore:
    """Build the KnowledgeStore rooted at the repository ``knowledge/`` lake."""
    # app.py lives at sdk/quantlab/dashboard/app.py → repo root is 4 levels up.
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    return KnowledgeStore(root=repo_root / "knowledge")


def _load_campaign_export_data(
    store: KnowledgeStore, campaign_id: str
) -> tuple[list, list, dict]:
    """Load real campaign export data from the Knowledge Lake (T24).

    Returns ``(trades, equity, statistics)`` — empty-safe when the lake
    holds no artifacts for the campaign, so report generation never fails
    on missing data.
    """
    trades: list = []
    equity: list = []
    statistics: dict = {}

    structured_dir = store.root / "structured"
    if not structured_dir.is_dir():
        return trades, equity, statistics

    # structured/{campaign_id}/{trades,equity,statistics}.json
    campaign_dir = structured_dir / campaign_id
    if campaign_dir.is_dir():
        for name, target in (("trades", trades), ("equity", equity), ("statistics", statistics)):
            f = campaign_dir / f"{name}.json"
            if f.is_file():
                try:
                    payload = json.loads(f.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
                if name == "statistics" and isinstance(payload, dict):
                    statistics = payload
                elif isinstance(payload, list):
                    target.extend(payload)

    # structured/{campaign_id}.json (single-file fallback)
    single = structured_dir / f"{campaign_id}.json"
    if single.is_file():
        try:
            payload = json.loads(single.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            payload = None
        if isinstance(payload, dict):
            if isinstance(payload.get("trades"), list):
                trades = payload["trades"]
            if isinstance(payload.get("equity"), list):
                equity = payload["equity"]
            if isinstance(payload.get("statistics"), dict):
                statistics = payload["statistics"]

    return trades, equity, statistics


def _campaign_entry(c: Any) -> dict:
    """Build the campaign API entry carrying the DSH-MOD spec field contract.

    Spec: each entry SHALL carry ``campaign_id, market, timeframe, sharpe,
    profit_factor, win_rate, status, total_return``. The extra ``name`` /
    ``metrics`` / ``tags`` / ``created`` / ``path`` fields are additive.
    ``market`` / ``timeframe`` / ``status`` surface from stored campaign
    metadata (index entry ``market``/``symbol``/``timeframe``/``status``) and
    are ``None`` when the lake does not carry them — no data is invented.
    ``total_return`` surfaces from stored metrics when present.
    """
    metrics = c.metrics
    return {
        "campaign_id": c.campaign_id,
        "name": c.name,
        "market": c.market,
        "timeframe": c.timeframe,
        "sharpe": metrics.sharpe_ratio if metrics else None,
        "profit_factor": metrics.profit_factor if metrics else None,
        "win_rate": metrics.win_rate if metrics else None,
        "status": c.status,
        "total_return": metrics.total_return if metrics else None,
        "metrics": (
            {
                "sharpe_ratio": metrics.sharpe_ratio,
                "profit_factor": metrics.profit_factor,
                "win_rate": metrics.win_rate,
                "max_drawdown": metrics.max_drawdown,
                "total_trades": metrics.total_trades,
                "net_profit": metrics.net_profit,
            }
            if metrics
            else None
        ),
        "tags": c.tags,
        "created": c.created.isoformat() if c.created else None,
        "path": str(c.path) if c.path else None,
    }


def _campaign_exists(store: KnowledgeStore, campaign_id: str) -> bool:
    """Return True when the campaign is known to the Knowledge Lake.

    A campaign exists when the store index resolves it or when export
    artifacts are present under ``structured/{campaign_id}``. Genuinely
    absent ids report 404 instead of generating empty reports.
    """
    result = store.query().filter_by_campaign(campaign_id).execute()
    if result.campaigns:
        return True
    structured = store.root / "structured"
    return (structured / campaign_id).is_dir() or (structured / f"{campaign_id}.json").is_file()


def _as_typed_export(trades: list, equity: list, statistics: dict):
    """Convert raw lake JSON export data into the typed models the
    ReportGenerator expects, falling back to the raw dicts when a payload
    does not match the model shape (the generator is attribute-tolerant).

    The dashboard JSON endpoints keep the raw lake data; only the report
    generator consumes typed ``Trade`` / ``EquityPoint`` / ``StatsResult``.
    """
    typed_trades: list = []
    for item in trades:
        if isinstance(item, dict):
            try:
                typed_trades.append(Trade(**item))
            except Exception:
                typed_trades.append(item)
        else:
            typed_trades.append(item)

    typed_equity: list = []
    for item in equity:
        if isinstance(item, dict):
            try:
                typed_equity.append(EquityPoint(**item))
            except Exception:
                typed_equity.append(item)
        else:
            typed_equity.append(item)

    typed_stats: dict | StatsResult = statistics
    if isinstance(statistics, dict) and statistics:
        try:
            typed_stats = StatsResult(**statistics)
        except Exception:
            typed_stats = statistics

    return typed_trades, typed_equity, typed_stats

    # structured/{campaign_id}/{trades,equity,statistics}.json
    campaign_dir = structured_dir / campaign_id
    if campaign_dir.is_dir():
        for name, target in (("trades", trades), ("equity", equity), ("statistics", statistics)):
            f = campaign_dir / f"{name}.json"
            if f.is_file():
                try:
                    payload = json.loads(f.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
                if name == "statistics" and isinstance(payload, dict):
                    statistics = payload
                elif isinstance(payload, list):
                    target.extend(payload)

    # structured/{campaign_id}.json (single-file fallback)
    single = structured_dir / f"{campaign_id}.json"
    if single.is_file():
        try:
            payload = json.loads(single.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            payload = None
        if isinstance(payload, dict):
            if isinstance(payload.get("trades"), list):
                trades = payload["trades"]
            if isinstance(payload.get("equity"), list):
                equity = payload["equity"]
            if isinstance(payload.get("statistics"), dict):
                statistics = payload["statistics"]

    return trades, equity, statistics


# ─── Helper: JSON error envelope ──────────────────────────────────────────────

def error_response(code: str, message: str, status: int = 500):
    """Return a standardized error JSON response."""
    return jsonify({"success": False, "error": {"code": code, "message": message}}), status


def success_response(data: Any, status: int = 200):
    """Return a standardized success JSON response."""
    return jsonify({"success": True, "data": data}), status


# ─── Flask App Factory ────────────────────────────────────────────────────────

def create_app(config: Optional[ServerConfig] = None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Set template and static folders
    base_dir = Path(__file__).parent
    app.template_folder = str(base_dir / "templates")
    app.static_folder = str(base_dir / "static")

    # Store config in app
    app.config["DASHBOARD_CONFIG"] = config or ServerConfig()

    # Initialize KnowledgeStore (data source for API endpoints)
    app.config["KNOWLEDGE_STORE"] = _knowledge_store()

    # Initialize CLI runner with a resolvable sqcli binary (DSH-01).
    # When unresolvable, report a clear error instead of crashing.
    sqcli_path = resolve_sqcli_binary(config)
    if sqcli_path:
        app.config["SQCLI_PATH"] = sqcli_path
        app.config["CLI_RUNNER"] = CliRunner(sqcli_path=sqcli_path)
    else:
        app.config["SQCLI_PATH"] = None
        app.config["CLI_RUNNER"] = None
        app.config["SQCLI_UNAVAILABLE"] = (
            "sqcli unavailable: set SQX_INSTALL_PATH or configure "
            "ServerConfig.sqx_install_path to a valid SQX installation"
        )

    # ─── Health endpoint ────────────────────────────────────────────────────
    @app.route("/api/health")
    def health():
        return success_response({"status": "ok", "version": "0.1.0"})

    # ─── Campaign endpoints ─────────────────────────────────────────────────
    @app.route("/api/campaigns")
    def list_campaigns():
        try:
            store: KnowledgeStore = app.config["KNOWLEDGE_STORE"]
            result = store.query().execute()
            campaigns = [_campaign_entry(c) for c in result.campaigns]
            return success_response(campaigns)
        except Exception as e:
            return error_response("INTERNAL_ERROR", str(e))

    @app.route("/api/campaigns/<campaign_id>")
    def get_campaign(campaign_id: str):
        try:
            store: KnowledgeStore = app.config["KNOWLEDGE_STORE"]
            result = store.query().filter_by_campaign(campaign_id).execute()
            if not result.campaigns:
                return error_response("CAMPAIGN_NOT_FOUND", f"Campaign '{campaign_id}' not found", 404)

            c = result.campaigns[0]
            # Real export data from the lake, empty-safe when absent.
            trades, equity, statistics = _load_campaign_export_data(store, campaign_id)
            campaign = _campaign_entry(c)
            campaign["equity_curve"] = equity
            campaign["trades"] = trades
            campaign["statistics"] = statistics
            # No phase-result artifact exists in the Knowledge Lake yet.
            campaign["phases"] = []
            return success_response(campaign)
        except Exception as e:
            return error_response("INTERNAL_ERROR", str(e))

    # ─── Pipeline endpoints ─────────────────────────────────────────────────
    @app.route("/api/pipeline")
    def list_pipeline_runs():
        try:
            store: KnowledgeStore = app.config["KNOWLEDGE_STORE"]
            runs = [r.to_dict() for r in store.load_pipeline_runs()]
            return success_response(runs)
        except Exception as e:
            return error_response("INTERNAL_ERROR", str(e))

    @app.route("/api/pipeline/<run_id>")
    def get_pipeline_run(run_id: str):
        try:
            store: KnowledgeStore = app.config["KNOWLEDGE_STORE"]
            run = store.get_pipeline_run(run_id)
            if run is None:
                return error_response("PIPELINE_NOT_FOUND", f"Pipeline run '{run_id}' not found", 404)
            return success_response(run.to_dict())
        except Exception as e:
            return error_response("INTERNAL_ERROR", str(e))

    # ─── Statistics endpoint ────────────────────────────────────────────────
    @app.route("/api/stats")
    def get_stats():
        try:
            store: KnowledgeStore = app.config["KNOWLEDGE_STORE"]
            campaigns = store.query().execute()

            def metric_values(attr: str) -> list[float]:
                return [
                    getattr(c.metrics, attr)
                    for c in campaigns.campaigns
                    if c.metrics and getattr(c.metrics, attr) is not None
                ]

            def mean_or_zero(values: list[float]) -> float:
                return py_stats.mean(values) if values else 0.0

            sharpes = metric_values("sharpe_ratio")
            max_dds = metric_values("max_drawdown")
            win_rates = metric_values("win_rate")
            total_trades = sum(metric_values("total_trades"))

            stats = {
                # DSH-MOD spec aggregate fields, computed from real stored
                # campaigns; empty-safe (zeros) when no campaigns exist.
                "sharpe_mean": mean_or_zero(sharpes),
                "sharpe_std": py_stats.stdev(sharpes) if len(sharpes) >= 2 else 0.0,
                "max_drawdown_pct": mean_or_zero(max_dds),
                "win_rate_mean": mean_or_zero(win_rates),
                "total_trades": total_trades,
                # No benchmark data source in the Knowledge Lake — empty.
                "benchmark_comparison": None,
                "total_campaigns": campaigns.total_count,
                "total_pipeline_runs": len(store.load_pipeline_runs()),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            return success_response(stats)
        except Exception as e:
            return error_response("INTERNAL_ERROR", str(e))

    # ─── Report generation endpoint ─────────────────────────────────────────
    @app.route("/api/reports/generate", methods=["POST"])
    def generate_report():
        try:
            data = request.get_json()
            if not data:
                return error_response("BAD_REQUEST", "JSON body required", 400)

            campaign_id = data.get("campaign_id")
            if not campaign_id:
                return error_response("BAD_REQUEST", "campaign_id is required", 400)

            store: KnowledgeStore = app.config["KNOWLEDGE_STORE"]
            # Missing campaign -> 404 with the error envelope, based on the
            # store index and the lake export artifacts (no sentinel strings).
            if not _campaign_exists(store, campaign_id):
                return error_response(
                    "CAMPAIGN_NOT_FOUND",
                    f"Campaign '{campaign_id}' not found",
                    404,
                )

            # Build report config
            config = ReportConfig(
                campaign_id=campaign_id,
                theme=ReportTheme(data.get("theme", "light")),
                formats=[ReportFormat(f) for f in data.get("formats", ["html"])],
                benchmark=data.get("benchmark"),
                template=data.get("template"),
                title=data.get("title"),
            )

            # Load REAL export data for the campaign (empty-safe fallback).
            trades, equity, statistics = _load_campaign_export_data(store, campaign_id)
            trades, equity, statistics = _as_typed_export(trades, equity, statistics)

            # Generate report
            generator = ReportGenerator(config)
            result = generator.generate(
                campaign_id=campaign_id,
                trades=trades,
                equity=equity,
                statistics=statistics,
                phase_results=None,
                summary=None,
                agent_decisions=None,
                comparison_campaigns=None,
            )

            # Pydantic v2: model_dump(mode="json") serializes Path -> str.
            return success_response(result.model_dump(mode="json"))

        except ValueError as e:
            return error_response("BAD_REQUEST", str(e), 400)
        except Exception as e:
            return error_response("INTERNAL_ERROR", str(e))

    # ─── HTML Template Routes ──────────────────────────────────────────────
    @app.route("/")
    def index():
        return render_template("campaign_list.html")

    @app.route("/campaigns")
    def campaigns():
        return render_template("campaign_list.html")

    @app.route("/campaigns/<campaign_id>")
    def campaign_detail(campaign_id: str):
        return render_template("campaign_detail.html", campaign_id=campaign_id)

    @app.route("/pipeline")
    def pipeline():
        return render_template("pipeline_monitor.html")

    @app.route("/stats")
    def stats():
        return render_template("stats_dashboard.html")

    return app


# ─── Dashboard Server ────────────────────────────────────────────────────────

class DashboardServer:
    """Manages the dashboard server lifecycle."""

    def __init__(self, config: ServerConfig) -> None:
        self.config = config
        self._app: Flask = create_app(config)
        self._server_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        self._is_running = False

    @property
    def url(self) -> str:
        return f"http://{self.config.host}:{self.config.port}"

    @property
    def is_running(self) -> bool:
        return self._is_running

    def start(self) -> None:
        """Start the dashboard server in a background thread."""
        if self._is_running:
            return

        self._is_running = True
        self._shutdown_event.clear()

        self._server_thread = threading.Thread(
            target=self._run_server,
            daemon=True,
        )
        self._server_thread.start()

    def _run_server(self) -> None:
        """Run the Flask server."""
        self._app.run(
            host=self.config.host,
            port=self.config.port,
            debug=self.config.debug,
            use_reloader=False,
        )

    def stop(self) -> None:
        """Stop the dashboard server."""
        if not self._is_running:
            return

        # Flask doesn't provide a clean shutdown in another thread
        # For now, we rely on the thread being daemon
        self._is_running = False
        self._shutdown_event.set()

    def wait(self, timeout: Optional[float] = None) -> None:
        """Wait for the server thread to finish."""
        if self._server_thread:
            self._server_thread.join(timeout=timeout)