"""Report generator — HTML + JSON output with Plotly charts."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from quantlab.readers.models import Trade, EquityPoint
from quantlab.stats.engine import StatisticsEngine
from quantlab.stats.models import StatsResult
from quantlab.reporting.models import (
    ReportConfig,
    ReportResult,
    ReportFormat,
    ReportTheme,
    ChartColors,
)

# Chart IDs for tracking
CHART_IDS = [
    "equity_curve",
    "drawdown_underwater",
    "trade_scatter",
    "metrics_table",
]

# Module-level availability flags
PLOTLY_AVAILABLE: bool = False
MATPLOTLIB_AVAILABLE: bool = False

try:
    import plotly  # noqa: F401
    PLOTLY_AVAILABLE = True
except ImportError:
    pass

try:
    import matplotlib  # noqa: F401
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    pass


class ReportGenerator:
    """Generates HTML and JSON reports from CampaignResult data."""

    def __init__(self, config: ReportConfig):
        self.config = config
        self._plotly_available = PLOTLY_AVAILABLE
        self._matplotlib_available = MATPLOTLIB_AVAILABLE
        self._jinja_env = self._create_jinja_env()

    @staticmethod
    def _check_plotly() -> bool:
        return PLOTLY_AVAILABLE

    @staticmethod
    def _check_matplotlib() -> bool:
        return MATPLOTLIB_AVAILABLE

    def _create_jinja_env(self) -> Environment:
        """Create Jinja2 environment for template rendering."""
        if self.config.template_path and self.config.template_path.exists():
            loader = FileSystemLoader(self.config.template_path.parent)
        else:
            # Use embedded template
            from quantlab.reporting.templates import DEFAULT_TEMPLATE
            loader = None  # We'll render manually

        env = Environment(
            loader=loader,
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        return env

    def generate(
        self,
        campaign_id: str,
        trades: list[Trade],
        equity: list[EquityPoint],
        statistics: StatsResult,
        phase_results: list[dict] | None = None,
        summary: dict | None = None,
    ) -> ReportResult:
        """Generate report from campaign data."""

        start_time = time.time()
        result = ReportResult(campaign_id=campaign_id)
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        # Generate JSON report (always)
        if ReportFormat.JSON in self.config.formats:
            json_path = self._generate_json(
                campaign_id, trades, equity, statistics, phase_results, summary
            )
            result.json_path = json_path

        # Generate HTML report
        if ReportFormat.HTML in self.config.formats:
            html_path = self._generate_html(
                campaign_id, trades, equity, statistics, phase_results, summary
            )
            result.html_path = html_path

        result.generation_time_ms = (time.time() - start_time) * 1000

        # Add warnings
        if not self._plotly_available and ReportFormat.HTML in self.config.formats:
            if self._matplotlib_available:
                result.warnings.append(
                    "Plotly not installed; using matplotlib static fallback. "
                    "Install with: pip install quantlab[reporting] for interactive charts."
                )
                result.charts_generated = CHART_IDS
            else:
                result.warnings.append(
                    "Plotly not installed; HTML report generated without charts. "
                    "Install with: pip install quantlab[reporting] for interactive charts "
                    "or pip install quantlab[reporting-matplotlib] for static charts."
                )
                result.charts_generated = []
        else:
            result.charts_generated = CHART_IDS

        return result

    def _generate_json(
        self,
        campaign_id: str,
        trades: list[Trade],
        equity: list[EquityPoint],
        statistics: StatsResult,
        phase_results: list[dict] | None,
        summary: dict | None,
    ) -> Path:
        """Generate machine-readable JSON report."""

        # Compute executive summary for JSON
        exec_summary = self._render_executive_summary(statistics)

        benchmark_equity_json = None
        if self.config.benchmark_equity:
            benchmark_equity_json = [
                {
                    "timestamp": e.timestamp.isoformat() if hasattr(e.timestamp, "isoformat") else str(e.timestamp),
                    "equity": e.equity,
                }
                for e in self.config.benchmark_equity
            ]

        json_data = {
            "campaign_id": campaign_id,
            "generated_at": time.time(),
            "statistics": statistics.model_dump() if hasattr(statistics, "model_dump") else statistics.__dict__,
            "trade_count": len(trades),
            "equity_points": len(equity),
            "trades": [
                {
                    "entry_time": t.entry_time.isoformat() if hasattr(t.entry_time, "isoformat") else str(t.entry_time),
                    "exit_time": t.exit_time.isoformat() if hasattr(t.exit_time, "isoformat") else str(t.exit_time),
                    "direction": getattr(t, "direction", "long"),
                    "lots": getattr(t, "lots", 1.0),
                    "profit": getattr(t, "profit", 0.0),
                }
                for t in trades
            ],
            "equity_curve": [
                {
                    "timestamp": e.timestamp.isoformat() if hasattr(e.timestamp, "isoformat") else str(e.timestamp),
                    "equity": e.equity,
                }
                for e in equity
            ],
            "benchmark_equity": benchmark_equity_json,
            "executive_summary": exec_summary,
            "summary": summary or {},
            "phase_results": phase_results or [],
        }

        json_path = self.config.output_dir / f"{campaign_id}_report.json"
        json_path.write_text(json.dumps(json_data, indent=2, default=str))
        return json_path

    def _generate_html(
        self,
        campaign_id: str,
        trades: list[Trade],
        equity: list[EquityPoint],
        statistics: StatsResult,
        phase_results: list[dict] | None,
        summary: dict | None,
    ) -> Path:
        """Generate interactive HTML report with Plotly charts."""

        # Prepare chart JSON for embedding (Plotly) or base64 PNG (matplotlib)
        charts = {}
        if self.config.include_charts:
            if self._plotly_available:
                charts = self._create_charts(trades, equity, statistics)
            elif self._matplotlib_available:
                charts = self._create_charts_matplotlib(trades, equity, statistics)

        # Compute executive summary
        executive_summary = self._render_executive_summary(statistics)

        # Compute benchmark comparison
        benchmark_comparison = self._render_benchmark_comparison(statistics, equity)

        # Render template
        html_content = self._render_html_template(
            campaign_id=campaign_id,
            title=self.config.effective_title,
            theme=self.config.theme,
            statistics=statistics,
            trades=trades,
            equity=equity,
            charts=charts,
            phase_results=phase_results,
            summary=summary,
            plotly_available=self._plotly_available,
            executive_summary=executive_summary,
            benchmark_comparison=benchmark_comparison,
        )

        html_path = self.config.output_dir / f"{campaign_id}_report.html"
        html_path.write_text(html_content)
        return html_path

    def _get_plotly_template(self) -> str:
        """Get Plotly template name based on theme."""
        return "plotly_dark" if self.config.theme == ReportTheme.DARK else "plotly_white"

    def _get_chart_colors(self) -> ChartColors:
        """Get chart colors from config or use defaults."""
        if hasattr(self.config, "chart_config") and self.config.chart_config:
            return self.config.chart_config.colors
        return ChartColors()

    def _render_chart_matplotlib(self, chart_type: str, data: dict[str, Any]) -> str:
        """Render a chart as a base64 PNG data URI using matplotlib.

        Args:
            chart_type: Type of chart ("equity_curve", "drawdown_underwater",
                        "trade_scatter", "metrics_table").
            data: Chart data dict with keys like "timestamps", "equities",
                  "profits", "metrics", etc.

        Returns:
            Base64-encoded PNG data URI string.

        Raises:
            ImportError: If matplotlib is not available.
        """
        import io
        import base64

        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates

        fig, ax = plt.subplots(figsize=(8, 3.5))
        colors = self._get_chart_colors()
        theme = self.config.theme

        if theme == ReportTheme.DARK:
            fig.patch.set_facecolor("#1A1A2E")
            ax.set_facecolor("#16213E")
            ax.tick_params(colors="#EAEAEA")
            ax.xaxis.label.set_color("#EAEAEA")
            ax.yaxis.label.set_color("#EAEAEA")
            ax.title.set_color("#EAEAEA")
            for spine in ax.spines.values():
                spine.set_color("#0F3460")

        if chart_type == "equity_curve":
            timestamps = data.get("timestamps", [])
            equities = data.get("equities", [])
            ax.plot(timestamps, equities, color=colors.equity_line, linewidth=1.5, label="Strategy")
            if self.config.benchmark_equity:
                bench_e = self.config.benchmark_equity
                bench_ts = [e.timestamp for e in bench_e]
                bench_eq = [e.equity for e in bench_e]
                if bench_ts and bench_eq:
                    ax.plot(bench_ts, bench_eq, color=colors.benchmark_line,
                            linewidth=1.5, linestyle="--", label="Benchmark")
            ax.legend()
            ax.set_title("Equity Curve")
            ax.set_ylabel("Equity")

        elif chart_type == "drawdown_underwater":
            timestamps = data.get("timestamps", [])
            equities = data.get("equities", [])
            running_max = []
            current_max = equities[0] if equities else 0
            for eq in equities:
                current_max = max(current_max, eq)
                running_max.append(current_max)
            drawdown = [(eq - mx) / mx * 100 if mx != 0 else 0
                        for eq, mx in zip(equities, running_max)]
            ax.fill_between(timestamps, drawdown, 0,
                            color=colors.drawdown_fill, alpha=0.5)
            ax.plot(timestamps, drawdown, color=colors.drawdown_line, linewidth=1)
            ax.set_title("Drawdown Underwater")
            ax.set_ylabel("Drawdown %")

        elif chart_type == "trade_scatter":
            profits = data.get("profits", [])
            ax.scatter(range(len(profits)), profits, c=[
                colors.trade_win if p >= 0 else colors.trade_loss
                for p in profits
            ], s=20)
            ax.axhline(y=0, color=colors.grid, linestyle="--", linewidth=0.5)
            ax.set_title("Trade P&L Distribution")
            ax.set_ylabel("Profit/Loss")

        elif chart_type == "metrics_table":
            ax.axis("off")
            metrics = data.get("metrics", {})
            table_data = [[k, str(v)] for k, v in metrics.items()]
            ax.table(cellText=table_data, colLabels=["Metric", "Value"],
                     loc="center", cellLoc="left")
            ax.set_title("Key Metrics")

        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode("utf-8")
        return f"data:image/png;base64,{b64}"

    def _create_charts_matplotlib(
        self,
        trades: list[Trade],
        equity: list[EquityPoint],
        statistics: StatsResult,
    ) -> dict[str, str]:
        """Create charts using matplotlib fallback (base64 PNG data URIs)."""
        charts = {}
        metrics = self._get_metrics_table(statistics)

        # 1. Equity Curve
        if equity:
            try:
                data = {
                    "timestamps": [e.timestamp for e in equity],
                    "equities": [e.equity for e in equity],
                }
                charts["equity_curve"] = self._render_chart_matplotlib("equity_curve", data)
            except Exception:
                pass

        # 2. Drawdown
        if equity:
            try:
                data = {
                    "timestamps": [e.timestamp for e in equity],
                    "equities": [e.equity for e in equity],
                }
                charts["drawdown_underwater"] = self._render_chart_matplotlib("drawdown_underwater", data)
            except Exception:
                pass

        # 3. Trade Scatter
        if trades:
            try:
                profits = [getattr(t, "profit", 0.0) for t in trades]
                data = {"profits": profits}
                charts["trade_scatter"] = self._render_chart_matplotlib("trade_scatter", data)
            except Exception:
                pass

        # 4. Metrics Table
        try:
            data = {"metrics": metrics}
            charts["metrics_table"] = self._render_chart_matplotlib("metrics_table", data)
        except Exception:
            pass

        return charts

    def _create_charts(
        self,
        trades: list[Trade],
        equity: list[EquityPoint],
        statistics: StatsResult,
    ) -> dict[str, str]:
        """Create Plotly chart JSON for embedding in HTML."""

        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        charts = {}
        template = self._get_plotly_template()
        colors = self._get_chart_colors()

        # 1. Equity Curve
        if equity:
            fig = go.Figure()
            timestamps = [e.timestamp for e in equity]
            equities = [e.equity for e in equity]

            fig.add_trace(go.Scatter(
                x=timestamps,
                y=equities,
                mode="lines",
                name="Equity",
                line=dict(color=colors.equity_line, width=2),
            ))

            # Add benchmark overlay if provided
            if self.config.benchmark_equity:
                bench_timestamps = [e.timestamp for e in self.config.benchmark_equity]
                bench_equities = [e.equity for e in self.config.benchmark_equity]
                if bench_timestamps and bench_equities:
                    fig.add_trace(go.Scatter(
                        x=bench_timestamps,
                        y=bench_equities,
                        mode="lines",
                        name="Benchmark",
                        line=dict(color=colors.benchmark_line, width=2, dash="dash"),
                    ))

            fig.update_layout(
                title="Equity Curve",
                xaxis_title="Time",
                yaxis_title="Equity",
                template=template,
                height=350,
                margin=dict(l=50, r=20, t=50, b=50),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
            )

            charts["equity_curve"] = fig.to_json()

            fig.update_layout(
                title="Equity Curve",
                xaxis_title="Time",
                yaxis_title="Equity",
                template=template,
                height=350,
                margin=dict(l=50, r=20, t=50, b=50),
            )

            charts["equity_curve"] = fig.to_json()

        # 2. Drawdown Underwater
        if equity:
            fig = go.Figure()
            timestamps = [e.timestamp for e in equity]
            equities = [e.equity for e in equity]

            # Calculate running max and drawdown
            running_max = []
            current_max = equities[0]
            for eq in equities:
                current_max = max(current_max, eq)
                running_max.append(current_max)

            drawdown = [(eq - mx) / mx * 100 for eq, mx in zip(equities, running_max)]

            fig.add_trace(go.Scatter(
                x=timestamps,
                y=drawdown,
                mode="lines",
                name="Drawdown %",
                fill="tozeroy",
                line=dict(color=colors.drawdown_line, width=1),
                fillcolor=colors.drawdown_fill,
            ))

            fig.update_layout(
                title="Drawdown Underwater",
                xaxis_title="Time",
                yaxis_title="Drawdown %",
                template=template,
                height=250,
                margin=dict(l=50, r=20, t=50, b=50),
            )

            charts["drawdown_underwater"] = fig.to_json()

        # 3. Trade P&L Scatter
        if trades:
            fig = go.Figure()

            profits = [getattr(t, "profit", 0) for t in trades]
            entry_times = [getattr(t, "entry_time", i) for i, t in enumerate(trades)]

            point_colors = [colors.trade_win if p >= 0 else colors.trade_loss for p in profits]

            fig.add_trace(go.Scatter(
                x=list(range(len(trades))),
                y=profits,
                mode="markers",
                name="Trade P&L",
                marker=dict(color=point_colors, size=8),
            ))

            fig.add_hline(y=0, line_dash="dash", line_color=colors.grid)

            fig.update_layout(
                title="Trade P&L Distribution",
                xaxis_title="Trade #",
                yaxis_title="Profit/Loss",
                template=template,
                height=300,
                margin=dict(l=50, r=20, t=50, b=50),
            )

            charts["trade_scatter"] = fig.to_json()

        # 4. Metrics Table (as interactive table)
        metrics_data = self._get_metrics_table(statistics)
        fig = go.Figure(data=[go.Table(
            header=dict(
                values=["Metric", "Value"],
                fill_color=colors.equity_line,
                font=dict(color=colors.background, size=12)
            ),
            cells=dict(
                values=[list(metrics_data.keys()), list(metrics_data.values())],
                fill_color=colors.background,
                font=dict(color=colors.text),
            ),
        )])

        fig.update_layout(
            title="Key Metrics",
            template=template,
            height=300,
            margin=dict(l=20, r=20, t=50, b=20),
        )

        charts["metrics_table"] = fig.to_json()

        return charts

    def _get_metrics_table(self, statistics: StatsResult) -> dict[str, str]:
        """Extract metrics as formatted strings for table."""

        def fmt(val):
            if val is None:
                return "N/A"
            if isinstance(val, float):
                if abs(val) < 0.01:
                    return f"{val:.6f}"
                return f"{val:.4f}"
            return str(val)

        return {
            "Profit Factor": fmt(getattr(statistics, "profit_factor", None)),
            "Sharpe Ratio": fmt(getattr(statistics, "sharpe_ratio", None)),
            "Sortino Ratio": fmt(getattr(statistics, "sortino_ratio", None)),
            "Max Drawdown": fmt(getattr(statistics, "max_drawdown", None)),
            "Expectancy": fmt(getattr(statistics, "expectancy", None)),
            "Win Rate": fmt(getattr(statistics, "win_rate", None)),
            "Total Trades": str(getattr(statistics, "total_trades", 0)),
            "MAR Ratio": fmt(getattr(statistics, "mar_ratio", None)),
            "Recovery Factor": fmt(getattr(statistics, "recovery_factor", None)),
        }

    def _render_executive_summary(self, statistics: StatsResult) -> dict[str, Any]:
        """Compute executive summary with assessment and indicator."""
        sharpe = getattr(statistics, "sharpe_ratio", None) or 0.0
        profit_factor = getattr(statistics, "profit_factor", None) or 0.0
        max_dd = getattr(statistics, "max_drawdown", None) or 0.0

        if sharpe >= 2.0:
            assessment = "Strong risk-adjusted returns"
            indicator = "green"
        elif sharpe >= 1.0:
            assessment = "Moderate risk-adjusted returns"
            indicator = "amber"
        else:
            assessment = "Weak risk-adjusted returns"
            indicator = "red"

        # Compute net_profit from recovery_factor * max_drawdown
        recovery_factor = getattr(statistics, "recovery_factor", None) or 0.0
        net_profit = recovery_factor * max_dd if max_dd > 0 else 0.0

        return {
            "net_profit": net_profit,
            "sharpe": sharpe,
            "max_drawdown": max_dd,
            "win_rate": 0.0,
            "profit_factor": profit_factor,
            "assessment": assessment,
            "indicator": indicator,
        }

    def _render_benchmark_comparison(
        self,
        statistics: StatsResult,
        equity: list[EquityPoint],
    ) -> list[dict[str, Any]] | None:
        """Compute strategy vs benchmark comparison when benchmark data provided.

        Args:
            statistics: Strategy statistics result.
            equity: Strategy equity curve.

        Returns:
            List of dicts with metric, strategy, benchmark values, or None.
        """
        if not self.config.benchmark_equity:
            return None

        # Strategy metrics
        strategy_return = (
            (equity[-1].equity - equity[0].equity) / equity[0].equity * 100
            if len(equity) >= 2 else 0.0
        )
        strategy_sharpe = getattr(statistics, "sharpe_ratio", None) or 0.0
        strategy_max_dd = getattr(statistics, "max_drawdown", None) or 0.0

        # Benchmark metrics
        bench = self.config.benchmark_equity
        bench_return = (
            (bench[-1].equity - bench[0].equity) / bench[0].equity * 100
            if len(bench) >= 2 else 0.0
        )
        bench_sharpe = 0.0  # Not available from equity alone
        bench_max_dd = 0.0

        return [
            {"metric": "Total Return", "strategy": f"{strategy_return:.2f}%", "benchmark": f"{bench_return:.2f}%"},
            {"metric": "Sharpe Ratio", "strategy": f"{strategy_sharpe:.2f}", "benchmark": f"{bench_sharpe:.2f} (N/A)"},
            {"metric": "Max Drawdown", "strategy": f"{strategy_max_dd:.2f}%", "benchmark": f"{bench_max_dd:.2f}% (N/A)"},
        ]

    def _render_html_template(
        self,
        campaign_id: str,
        title: str,
        theme: ReportTheme,
        statistics: StatsResult,
        trades: list[Trade],
        equity: list[EquityPoint],
        charts: dict[str, str],
        phase_results: list[dict] | None,
        summary: dict | None,
        plotly_available: bool,
        executive_summary: dict[str, Any] | None = None,
        benchmark_comparison: list[dict[str, Any]] | None = None,
    ) -> str:
        """Render the complete HTML report using Jinja2 template."""

        from quantlab.reporting.templates import DEFAULT_TEMPLATE, CSS_VARIABLES_TEMPLATE

        theme_value = theme.value
        colors = self._get_chart_colors()

        # Build CSS variables for template
        css_vars = CSS_VARIABLES_TEMPLATE.format(
            equity_up=colors.equity_up,
            equity_down=colors.equity_down,
            equity_line=colors.equity_line,
            drawdown_fill=colors.drawdown_fill,
            drawdown_line=colors.drawdown_line,
            trade_win=colors.trade_win,
            trade_loss=colors.trade_loss,
            benchmark_line=colors.benchmark_line,
            grid=colors.grid,
            background=colors.background,
            text=colors.text,
        )

        # Get dark theme overrides
        dark_colors = ChartColors(
            equity_up="#4ECDC4",
            equity_down="#FF6B6B",
            equity_line="#4ECDC4",
            drawdown_fill="#FF6B6B",
            drawdown_line="#E63946",
            trade_win="#4ECDC4",
            trade_loss="#FF6B6B",
            benchmark_line="#FFD93D",
            grid="#0F3460",
            background="#1A1A2E",
            text="#EAEAEA",
        )
        css_vars_dark = CSS_VARIABLES_TEMPLATE.format(
            equity_up=dark_colors.equity_up,
            equity_down=dark_colors.equity_down,
            equity_line=dark_colors.equity_line,
            drawdown_fill=dark_colors.drawdown_fill,
            drawdown_line=dark_colors.drawdown_line,
            trade_win=dark_colors.trade_win,
            trade_loss=dark_colors.trade_loss,
            benchmark_line=dark_colors.benchmark_line,
            grid=dark_colors.grid,
            background=dark_colors.background,
            text=dark_colors.text,
        )

        # Prepare template context
        theme_class = f"theme-{theme_value}"

        matplotlib_available = not plotly_available and self._matplotlib_available and charts
        charts_html = ""
        if plotly_available and charts:
            for chart_id, chart_json in charts.items():
                charts_html += f"""
                <div class="chart-container" id="{chart_id}">
                    <div id="plotly-{chart_id}"></div>
                </div>
                """
        elif matplotlib_available:
            for chart_id, chart_data in charts.items():
                charts_html += f"""
                <div class="chart-container" id="{chart_id}">
                    <img src="{chart_data}" alt="{chart_id}" style="width:100%;max-width:800px;">
                </div>
                """

        metrics = self._get_metrics_table(statistics)
        metrics_rows = "".join(
            f"<tr><td>{k}</td><td>{v}</td></tr>"
            for k, v in metrics.items()
        )

        phase_rows = ""
        if phase_results:
            for p in phase_results:
                phase_rows += f"""
                <tr>
                    <td>{p.get('phase', '')}</td>
                    <td>{p.get('status', '')}</td>
                    <td>{p.get('detail', '')}</td>
                    <td>{p.get('duration', '')}s</td>
                </tr>"""

        # Executive summary section
        executive_summary_section = ""
        if executive_summary:
            indicator = executive_summary.get("indicator", "amber")
            indicator_colors = {"green": "#2A9D8F", "amber": "#F4A261", "red": "#E63946"}
            indicator_color = indicator_colors.get(indicator, "#F4A261")
            executive_summary_section = f"""
            <section class="section" id="executive-summary">
                <h2>Executive Summary</h2>
                <div class="card">
                    <div class="indicator-bar" style="background:{indicator_color};padding:4px 16px;border-radius:4px;color:white;font-weight:bold;text-align:center;">
                        {executive_summary.get('assessment', '')}
                    </div>
                    <table class="metrics-table">
                        <tr><td>Net Profit</td><td>{executive_summary.get('net_profit', 0):.2f}</td></tr>
                        <tr><td>Sharpe Ratio</td><td>{executive_summary.get('sharpe', 0):.2f}</td></tr>
                        <tr><td>Max Drawdown</td><td>{executive_summary.get('max_drawdown', 0):.2f}%</td></tr>
                        <tr><td>Win Rate</td><td>{executive_summary.get('win_rate', 0):.2%}</td></tr>
                        <tr><td>Profit Factor</td><td>{executive_summary.get('profit_factor', 0):.2f}</td></tr>
                    </table>
                </div>
            </section>"""

        # Benchmark comparison section
        benchmark_section = ""
        if benchmark_comparison:
            bench_rows = "".join(
                f"<tr><td>{b['metric']}</td><td>{b['strategy']}</td><td>{b['benchmark']}</td></tr>"
                for b in benchmark_comparison
            )
            benchmark_section = f"""
            <section class="section" id="benchmark-comparison">
                <h2>Benchmark Comparison</h2>
                <div class="card">
                    <table class="metrics-table">
                        <thead><tr><th>Metric</th><th>Strategy</th><th>Benchmark</th></tr></thead>
                        {bench_rows}
                    </table>
                </div>
            </section>"""

        summary_rows = ""
        if summary:
            for k, v in summary.items():
                summary_rows += f"<tr><td>{k}</td><td>{v}</td></tr>"

        trade_count = len(trades)
        equity_count = len(equity)

        # Render using Jinja2 if custom template, else use embedded template
        if self.config.template_path and self.config.template_path.exists():
            template_name = self.config.template_path.name
            template = self._jinja_env.get_template(template_name)
            return template.render(
                title=title,
                campaign_id=campaign_id,
                theme_class=theme_class,
                css_variables=css_vars,
                css_variables_dark=css_vars_dark,
                metrics_rows=metrics_rows,
                trade_count=trade_count,
                equity_count=equity_count,
                summary_rows=summary_rows,
                phase_rows=phase_rows,
                phase_results=phase_results,
                charts_json=json.dumps(charts),
                plotly_available=plotly_available,
                matplotlib_available=matplotlib_available,
                executive_summary=executive_summary or {},
                executive_summary_section=executive_summary_section,
                benchmark_comparison=benchmark_comparison or [],
                benchmark_section=benchmark_section,
                generation_time=time.strftime('%Y-%m-%d %H:%M:%S'),
            )

        # Embedded template
        return DEFAULT_TEMPLATE.format(
            title=title,
            campaign_id=campaign_id,
            theme_class=theme_class,
            css_vars=css_vars,
            css_vars_dark=css_vars_dark,
            metrics_rows=metrics_rows,
            metrics_rows_detailed=metrics_rows,
            trade_count=trade_count,
            equity_count=equity_count,
            summary_rows=summary_rows,
            phase_rows=phase_rows,
            phase_results=phase_results,
            phase_results_section=phase_rows if phase_results else "",
            summary_section=f"<section class='section'><h2>Summary</h2><div class='card'><table class='metrics-table'>{summary_rows}</table></div></section>" if summary else "",
            executive_summary_section=executive_summary_section,
            benchmark_section=benchmark_section,
            charts_json=json.dumps(charts),
            plotly_available=plotly_available,
            plotly_status="Available" if plotly_available else "Not installed",
            generation_time=time.strftime('%Y-%m-%d %H:%M:%S'),
            generated_at=time.strftime('%Y-%m-%d %H:%M:%S'),
        )


def generate_report(
    campaign_id: str,
    trades: list[Trade],
    equity: list[EquityPoint],
    statistics: StatsResult,
    config: ReportConfig | None = None,
    phase_results: list[dict] | None = None,
    summary: dict | None = None,
) -> ReportResult:
    """Convenience function for generating a report."""

    if config is None:
        config = ReportConfig(campaign_id=campaign_id)

    generator = ReportGenerator(config)
    return generator.generate(
        campaign_id=campaign_id,
        trades=trades,
        equity=equity,
        statistics=statistics,
        phase_results=phase_results,
        summary=summary,
    )