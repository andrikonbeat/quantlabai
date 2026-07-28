"""Build SQX project directories from DSL config using a clean template."""

from __future__ import annotations

import logging
import re
import shutil
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_DEFAULT_TEMPLATE = _TEMPLATE_DIR / "default-project.sqx-template"

# Default JForex Dukascopy broker settings
_JFOREX_COMMISSION = 3.5       # USD per lot (standard Dukascopy)
_JFOREX_SLIPPAGE = 1           # pips
_JFOREX_SPREAD = 3             # pips base
_JFOREX_ENGINE = "Dukascopy"


def _template_path() -> Path:
    return _DEFAULT_TEMPLATE


def create_project(
    sqx_install_path: str,
    campaign_id: str,
    *,
    symbol: str = "EURUSD",
    timeframe: str = "H1",
    date_from: str = "2020.1.1",
    date_to: str = "2024.12.31",
    generations: int = 80,
    population: int = 200,
    crossover: float = 0.8,
    mutation: float = 0.15,
    slippage: int = _JFOREX_SLIPPAGE,
    spread: int = _JFOREX_SPREAD,
    commission: float = _JFOREX_COMMISSION,
    engine: str = _JFOREX_ENGINE,
    rankings_min_profit_factor: float = 1.3,
    rankings_min_sharpe: float = 0.8,
    rankings_max_drawdown: float = 0.25,
    rankings_min_win_rate: float = 0.3,
) -> str:
    """Create a campaign project directory from the template.

    Returns the path to the created project.cfx.
    """
    sqx_path = Path(sqx_install_path).resolve()
    project_dir = sqx_path / "user" / "projects" / campaign_id
    dest_cfx = project_dir / "project.cfx"

    # Remove if exists
    if project_dir.exists():
        shutil.rmtree(project_dir)

    # Create databank directories (SQX expects these)
    databanks = [
        "Results", "Last generation", "Initial population",
        "Strategies to improve", "Existing portfolio",
    ]
    for db in databanks:
        (project_dir / "databanks" / db).mkdir(parents=True, exist_ok=True)

    # Read template
    template_path = _template_path()
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    with zipfile.ZipFile(template_path, "r") as z:
        config_xml = z.read("config.xml").decode("utf-8")
        task_xml = z.read("Build-Task1.xml").decode("utf-8")

    # ── config.xml: replace project name ──
    config_xml = re.sub(
        r'name="[^"]*"',
        f'name="{campaign_id}"',
        config_xml,
        count=1,
    )

    # ── Build-Task1.xml modifications ──

    # 1. Data section: symbol, timeframe, date range
    # SQX symbol naming: {SYMBOL}_{TIMEFRAME}_dukas for Dukascopy engine
    if engine.lower() == "dukascopy":
        chart_symbol = f"{symbol}_{timeframe.upper()}_dukas"
    else:
        chart_symbol = f"{symbol}_{timeframe.lower()}"

    chart_old = re.search(
        r'<Chart symbol="[^"]*" timeframe="[^"]*" spread="\d+"',
        task_xml,
    )
    if chart_old:
        task_xml = task_xml.replace(
            chart_old.group(),
            f'<Chart symbol="{chart_symbol}" timeframe="{timeframe}" spread="{spread}"',
        )

    # 2. Setup: date range, slippage, engine
    setup_old = re.search(
        r'dateFrom="[^"]*" dateTo="[^"]*"[^>]*slippage="\d+"[^>]*engine="[^"]*"',
        task_xml,
    )
    if setup_old:
        task_xml = task_xml.replace(
            setup_old.group(),
            f'dateFrom="{date_from}" dateTo="{date_to}" '
            f'testPrecision="1" session="No Session" '
            f'slippage="{slippage}" minDist="0" engine="{engine}"',
        )

    # 3. Commissions: switch to Money-based for Dukascopy
    commission_block = (
        "<Commissions>\n"
        '          <Method type="Money" use="true">\n'
        "            <Params>\n"
        '              <Param name="CommissionType" value="PerLot"/>\n'
        f'              <Param name="Commission" value="{commission}"/>\n'
        '              <Param name="CommissionCurrency" value="USD"/>\n'
        '              <Param name="CommissionPerSide" value="true"/>\n'
        "            </Params>\n"
        "          </Method>\n"
        "        </Commissions>"
    )
    task_xml = re.sub(
        r'<Commissions>\s*<Method[^>]*>\s*<Params\s*/>\s*</Method>\s*</Commissions>',
        commission_block,
        task_xml,
        flags=re.DOTALL,
    )

    # 4. Genetic settings
    task_xml = re.sub(
        r'<PopulationSize>\d+</PopulationSize>',
        f'<PopulationSize>{population}</PopulationSize>',
        task_xml,
    )
    task_xml = re.sub(
        r'<MaxGenerations>\d+</MaxGenerations>',
        f'<MaxGenerations>{generations}</MaxGenerations>',
        task_xml,
    )
    task_xml = re.sub(
        r'<CrossoverProbability>[0-9.]+</CrossoverProbability>',
        f'<CrossoverProbability>{crossover}</CrossoverProbability>',
        task_xml,
    )
    task_xml = re.sub(
        r'<MutationProbability>[0-9.]+</MutationProbability>',
        f'<MutationProbability>{mutation}</MutationProbability>',
        task_xml,
    )

    # 5. Rankings: enable and set acceptance criteria
    # Change type="never" to something that applies
    task_xml = re.sub(
        r'<Rankings type="never">',
        '<Rankings type="always">',
        task_xml,
    )

    # Modify Conditions in Rankings
    # Find ProfitFactor condition and set minValue
    task_xml = re.sub(
        r'(<Column-Value column="ProfitFactor"[^>]*minValue=")[^"]*(")',
        f'\\g<1>{rankings_min_profit_factor}\\2',
        task_xml,
    )
    task_xml = re.sub(
        r'(<Column-Value column="SharpeRatio"[^>]*minValue=")[^"]*(")',
        f'\\g<1>{rankings_min_sharpe}\\2',
        task_xml,
    )
    task_xml = re.sub(
        r'(<Column-Value column="MaxDrawdown"[^>]*maxValue=")[^"]*(")',
        f'\\g<1>{rankings_max_drawdown}\\2',
        task_xml,
    )
    task_xml = re.sub(
        r'(<Column-Value column="WinRate"[^>]*minValue=")[^"]*(")',
        f'\\g<1>{rankings_min_win_rate}\\2',
        task_xml,
    )

    # 6. CrossChecks: enable Walk-Forward + Monte Carlo
    task_xml = re.sub(
        r'<WalkForwardOptimization use="false">',
        '<WalkForwardOptimization use="true">',
        task_xml,
    )
    task_xml = re.sub(
        r'<MonteCarloRetest use="false">',
        '<MonteCarloRetest use="true">',
        task_xml,
    )
    # Set realistic walk-forward params
    task_xml = re.sub(
        r'<WalkForward type="1" period="\d+" optimization="\d+">',
        '<WalkForward type="1" period="12" optimization="6">',
        task_xml,
    )

    # 7. RetestOnAdditionalMarkets: optionally enable
    task_xml = re.sub(
        r'<RetestOnAdditionalMarkets use="false">',
        '<RetestOnAdditionalMarkets use="false">',  # keep disabled for speed
        task_xml,
    )

    # Write new project.cfx
    with zipfile.ZipFile(dest_cfx, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("config.xml", config_xml.encode("utf-8"))
        zf.writestr("Build-Task1.xml", task_xml.encode("utf-8"))

    logger.info(
        "Created project '%s' at %s (%s %s, %d gen, %d pop, %s engine)",
        campaign_id, dest_cfx, symbol, timeframe,
        generations, population, engine,
    )
    return str(dest_cfx)


def remove_project(sqx_install_path: str, campaign_id: str) -> bool:
    """Remove a campaign project directory."""
    project_dir = Path(sqx_install_path) / "user" / "projects" / campaign_id
    if project_dir.exists():
        shutil.rmtree(project_dir)
        logger.info("Removed project '%s'", campaign_id)
        return True
    return False
