"""Report configuration and result models."""

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ReportFormat(str, Enum):
    HTML = "html"
    JSON = "json"


class ReportTheme(str, Enum):
    LIGHT = "light"
    DARK = "dark"


class ChartColors(BaseModel):
    """Color palette for chart theming (11 colors)."""

    equity_up: str = "#2A9D8F"
    equity_down: str = "#E63946"
    equity_line: str = "#2E86AB"
    drawdown_fill: str = "#E63946"
    drawdown_line: str = "#A62836"
    trade_win: str = "#2A9D8F"
    trade_loss: str = "#E63946"
    benchmark_line: str = "#F4A261"
    grid: str = "#E0E0E0"
    background: str = "#FFFFFF"
    text: str = "#1A1A2E"

    def to_plotly_template(self, theme: "ReportTheme") -> dict:
        """Convert to Plotly template color overrides."""
        if theme == ReportTheme.DARK:
            return {
                "layout": {
                    "paper_bgcolor": "#1A1A2E",
                    "plot_bgcolor": "#16213E",
                    "font": {"color": "#EAEAEA"},
                    "xaxis": {"gridcolor": "#0F3460", "zerolinecolor": "#0F3460"},
                    "yaxis": {"gridcolor": "#0F3460", "zerolinecolor": "#0F3460"},
                    "colorway": [
                        self.equity_up,
                        self.equity_down,
                        self.equity_line,
                        self.drawdown_fill,
                        self.drawdown_line,
                        self.trade_win,
                        self.trade_loss,
                        self.benchmark_line,
                    ],
                }
            }
        return {
            "layout": {
                "paper_bgcolor": self.background,
                "plot_bgcolor": self.background,
                "font": {"color": self.text},
                "xaxis": {"gridcolor": self.grid, "zerolinecolor": self.grid},
                "yaxis": {"gridcolor": self.grid, "zerolinecolor": self.grid},
                "colorway": [
                    self.equity_up,
                    self.equity_down,
                    self.equity_line,
                    self.drawdown_fill,
                    self.drawdown_line,
                    self.trade_win,
                    self.trade_loss,
                    self.benchmark_line,
                ],
            }
        }


class ReportConfig(BaseModel):
    """Configuration for report generation."""

    campaign_id: str
    output_dir: Path = Path("reports")
    formats: list[ReportFormat] = Field(default_factory=lambda: [ReportFormat.HTML, ReportFormat.JSON])
    include_charts: bool = True
    theme: ReportTheme = ReportTheme.LIGHT
    template_path: Optional[Path] = None
    title: Optional[str] = None
    benchmark_equity: Optional[list] = None

    @property
    def effective_title(self) -> str:
        return self.title or f"Campaign Report: {self.campaign_id}"


class ReportResult(BaseModel):
    """Result of report generation."""

    campaign_id: str
    html_path: Optional[Path] = None
    json_path: Optional[Path] = None
    charts_generated: list[str] = Field(default_factory=list)
    generation_time_ms: float = 0.0
    warnings: list[str] = Field(default_factory=list)

    @field_validator("html_path", "json_path", mode="before")
    @classmethod
    def _ensure_path(cls, v):
        if isinstance(v, str):
            return Path(v)
        return v

    def is_successful(self) -> bool:
        return len(self.warnings) == 0 and (self.html_path or self.json_path)


class ChartConfig(BaseModel):
    """Configuration for individual chart generation."""

    chart_id: str
    title: str
    height: int = 400
    width: Optional[int] = None
    colors: ChartColors = Field(default_factory=ChartColors)