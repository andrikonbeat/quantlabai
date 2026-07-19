"""HTML templates and CSS variables for report generation."""

# CSS Variables for theming (light + dark)
CSS_VARIABLES_TEMPLATE = """
    :root {{
        --color-equity-up: {equity_up};
        --color-equity-down: {equity_down};
        --color-equity-line: {equity_line};
        --color-drawdown-fill: {drawdown_fill};
        --color-drawdown-line: {drawdown_line};
        --color-trade-win: {trade_win};
        --color-trade-loss: {trade_loss};
        --color-benchmark-line: {benchmark_line};
        --color-grid: {grid};
        --color-background: {background};
        --color-text: {text};
    }}

    html.theme-dark {{
        --color-equity-up: #2A9D8F;
        --color-equity-down: #E63946;
        --color-equity-line: #48CAE4;
        --color-drawdown-fill: #E63946;
        --color-drawdown-line: #D62828;
        --color-trade-win: #2A9D8F;
        --color-trade-loss: #E63946;
        --color-benchmark-line: #F4A261;
        --color-grid: #0F3460;
        --color-background: #1A1A2E;
        --color-text: #EAEAEA;
    }}
"""

# Default HTML template with embedded Plotly.js and theming support
DEFAULT_TEMPLATE = """<!DOCTYPE html>
<html lang="en" class="theme-{theme_class}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
{css_vars}
{css_vars_dark}
        * {{
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: var(--color-background);
            color: var(--color-text);
            margin: 0;
            padding: 20px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            text-align: center;
            padding: 20px 0;
            border-bottom: 2px solid var(--color-grid);
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5rem;
            font-weight: 700;
        }}
        .header .meta {{
            color: var(--color-text);
            opacity: 0.7;
            margin-top: 10px;
            font-size: 1rem;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .card {{
            background: var(--color-background);
            border: 1px solid var(--color-grid);
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }}
        .card h2 {{
            margin: 0 0 15px 0;
            font-size: 1.25rem;
            font-weight: 600;
        }}
        .chart-container {{
            height: 350px;
            width: 100%;
        }}
        .chart-container.small {{
            height: 250px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid var(--color-grid);
        }}
        th {{
            background: var(--color-grid);
            font-weight: 600;
        }}
        tr:last-child td {{
            border-bottom: none;
        }}
        .positive {{ color: var(--color-equity-up); }}
        .negative {{ color: var(--color-equity-down); }}
        .warning {{
            color: #F4A261;
            text-align: center;
            padding: 20px;
            background: var(--color-grid);
            border-radius: 8px;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: var(--color-text);
            opacity: 0.6;
            font-size: 0.85rem;
            border-top: 1px solid var(--color-grid);
            margin-top: 30px;
        }}
        .section {{
            margin-bottom: 30px;
        }}
        .section h2 {{
            font-size: 1.5rem;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid var(--color-grid);
        }}
        .metrics-table {{
            width: 100%;
        }}
        .metrics-table th {{
            width: 50%;
        }}
        .chart-row {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        @media (max-width: 768px) {{
            .chart-row {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <h1>{title}</h1>
            <div class="meta">
                Campaign: {campaign_id} | Generated: {generated_at}
            </div>
        </header>

        <section class="section">
            <h2>Key Metrics</h2>
            <div class="grid">
                <div class="card">
                    <h2>Key Metrics</h2>
                    <table class="metrics-table">
                        {metrics_rows}
                    </table>
                </div>
                <div class="card">
                    <h2>Campaign Summary</h2>
                    <table class="metrics-table">
                        {summary_rows}
                    </table>
                </div>
            </div>
        </section>

        <section class="section">
            <h2>Equity Curve</h2>
            <div class="chart-container" id="plotly-equity_curve"></div>
        </section>

        <section class="section">
            <div class="chart-row">
                <div class="card">
                    <h2>Drawdown Underwater</h2>
                    <div id="plotly-drawdown_underwater" class="chart-container small"></div>
                </div>
                <div class="card">
                    <h2>Trade P&L Distribution</h2>
                    <div id="plotly-trade_scatter" class="chart-container small"></div>
                </div>
            </div>
        </section>

        <section class="section">
            <h2>Key Metrics Table</h2>
            <div class="card">
                <table class="metrics-table">
                    <tr><th>Metric</th><th>Value</th></tr>
                    {metrics_rows_detailed}
                </table>
            </div>
        </section>

        {phase_results_section}
        {executive_summary_section}
        {benchmark_section}
        {summary_section}

        <footer class="footer">
            Generated by QuantLab AI Reporting Module | Plotly: {plotly_status}
        </footer>
    </div>

    <script>
        const charts = {charts_json};
        Object.entries(charts).forEach(([id, data]) => {{
            const el = document.getElementById('plotly-' + id);
            if (el && data) {{
                Plotly.newPlot(el, JSON.parse(data).data, JSON.parse(data).layout, {{responsive: true}});
            }}
        }});
    </script>
</body>
</html>"""

# Light theme CSS variables (default)
CSS_VARIABLES_TEMPLATE_LIGHT = CSS_VARIABLES_TEMPLATE.format(
    equity_up="#2A9D8F",
    equity_down="#E63946",
    equity_line="#2E86AB",
    drawdown_fill="#E63946",
    drawdown_line="#A62836",
    trade_win="#2A9D8F",
    trade_loss="#E63946",
    benchmark_line="#F4A261",
    grid="#E0E0E0",
    background="#FFFFFF",
    text="#1A1A2E",
)

# Dark theme CSS variables (overrides via .theme-dark class)
CSS_VARIABLES_TEMPLATE_DARK = CSS_VARIABLES_TEMPLATE.format(
    equity_up="#2A9D8F",
    equity_down="#E63946",
    equity_line="#48CAE4",
    drawdown_fill="#E63946",
    drawdown_line="#D62828",
    trade_win="#2A9D8F",
    trade_loss="#E63946",
    benchmark_line="#F4A261",
    grid="#0F3460",
    background="#1A1A2E",
    text="#EAEAEA",
)