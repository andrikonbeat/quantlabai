"""QuantLab Dashboard — Flask web UI for campaign visualization and monitoring.

This package provides:
- Flask app factory and DashboardServer lifecycle management
- API endpoints for campaigns, pipeline runs, statistics, and reports
- Jinja2 templates for campaign list, detail, pipeline monitor, and statistics views
- Static assets (CSS, Plotly-powered JavaScript)
"""

from quantlab.dashboard.app import DashboardServer, create_app

__all__ = ["DashboardServer", "create_app"]
__version__ = "0.1.0"