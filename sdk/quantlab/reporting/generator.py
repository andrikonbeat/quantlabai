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


class ReportGenerator:
    """Generates HTML and JSON reports from CampaignResult data."""

    def __init__(self, config: ReportConfig):
        self.config = config
        self._plotly_available = self._check_plotly()
        self._jinja_env = self._create_jinja_env()

    @staticmethod
    def _check_plotly() -> bool:
        try:
            import plotly  # noqa: F401
            return True
        except ImportError:
            return False

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
            result.warnings.append(
                "Plotly not installed; HTML report generated without interactive charts. "
                "Install with: pip install quantlab[reporting]"
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

        # Prepare chart JSON for embedding
        charts = {}
        if self._plotly_available and self.config.include_charts:
            charts = self._create_charts(trades, equity, statistics)

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

        charts_html = ""
        if plotly_available and charts:
            for chart_id, chart_json in charts.items():
                charts_html += f"""
                <div class="chart-container" id="{chart_id}">
                    <div id="plotly-{chart_id}"></div>
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