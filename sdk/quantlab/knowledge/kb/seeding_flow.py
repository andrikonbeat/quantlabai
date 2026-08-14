"""SQX Parameter KB seeding flow (REQ-209, D1/D2).

``run_seed_flow`` is the full ``sqx kb seed`` pipeline: seed the curated
parameters from ``docs/sqx-builder-config/SQX Builder Config.md`` (REQ-203), bulk-verify
every parameter the real install can prove against ``CFX_EVIDENCE_MAP``
(promoting entries to ``verified`` with the real ``.cfx`` evidence path),
demote any remaining doc-only entries to ``needs_review`` (REQ-203 never
invents), rebuild the Knowledge Lake index (v4 with ``kb_parameters``,
REQ-403) and run the REQ-209 validation gate.

``CFX_EVIDENCE_MAP`` is a CURATED provenance table: parameter
``(tab, name)`` -> relative path of the real SQX Builder config that
evidences it. It was derived by scanning the pinned install for the
distinctive XML keys of each SEED_SPEC entry. Entries with NO config
evidence (Strategy style, Use, Number of Exit Types) are intentionally
absent: they stay ``needs_review`` instead of being invented (REQ-203).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from quantlab.knowledge.kb.models import SQX_VERSION
from quantlab.knowledge.kb.seeder import DEFAULT_DOC_PATH, seed_from_doc
from quantlab.knowledge.kb.store import KbParamNotFoundError, KbStore
from quantlab.knowledge.kb.validation import (
    SeedValidationReport,
    validate_seed,
)


CFX_EVIDENCE_MAP: dict[tuple[str, str], str] = {
    ('What to build', 'Strategy type'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('What to build', 'Trading directions'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('What to build', 'Build mode'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('What to build', 'Conditions in entry rule'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('What to build', 'Conditions in exit rule'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('What to build', 'Global Indicators period'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('What to build', 'Global Lookback period (Shift)'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('What to build', 'Stop Loss'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('What to build', 'Profit Target'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Genetic options', 'Max # of Generations'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Genetic options', 'Population Size (per island)'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Genetic options', 'Crossover Probability'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Genetic options', 'Mutation Probability'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Genetic options', 'Islands (separate evolution)'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Genetic options', 'Migrate every Xth generation, X ='): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Genetic options', 'Population migration rate'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Genetic options', 'Initial population size required'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Genetic options', 'Use strategies from Initial population databank as evolution start'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Genetic options', 'Generated decimation coefficient'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Genetic options', 'Profit factor > 1 (initial population filter)'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Genetic options', 'Detect same strategies in population and replace them with newly generated ones'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Genetic options', 'Replace % of weakest strategies with newly generated'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Genetic options', 'Every generation(s)'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Genetic options', 'Start again when finished (continuous repeating evolution)'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Genetic options', 'Restart evolution if fitness stagnates for X generation(s)'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Data', 'Engine'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Data', 'Symbol'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Data', 'Timeframe'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Data', 'Start day'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Data', 'End day'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Data', 'Precision'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Data', 'Commissions & swap'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Data', 'Spread'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Data', 'Slippage'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Data', 'Min. distance'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Trading options', "Don't trade on weekends"): 'assets/SQX_144_2953_linux_20260601/user/settings/Configs/DJ CFD H1.cfx',
    ('Trading options', 'Friday Close Time'): 'assets/SQX_144_2953_linux_20260601/user/settings/Configs/DJ CFD H1.cfx',
    ('Trading options', 'Sunday Open Time'): 'assets/SQX_144_2953_linux_20260601/user/settings/Configs/DJ CFD H1.cfx',
    ('Trading options', 'Exit At End Of Day'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Trading options', 'End Of Day Exit Time'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Trading options', 'Exit On Friday'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Trading options', 'Limit Time Range'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Trading options', 'Order Types To Close'): 'assets/SQX_144_2953_linux_20260601/user/settings/Configs/DJ CFD H1.cfx',
    ('Trading options', 'Max distance from market'): 'assets/SQX_144_2953_linux_20260601/user/settings/Configs/DJ CFD H1.cfx',
    ('Trading options', 'Maximum Trades Per Day'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Trading options', 'Minimum / Maximum SL'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Trading options', 'Minimum / Maximum PT'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Trading options', 'Realistic Gaps Handling'): 'assets/SQX_144_2953_linux_20260601/user/settings/Configs/DJ CFD H1.cfx',
    ('Trading options', 'Store Chart Data'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Building blocks', 'Signals (Predefined conditions)'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Building blocks', 'Indicators'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Building blocks', 'Stop/Limit entry blocks'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Building blocks', 'Order types'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Building blocks', 'Exit types'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Building blocks', 'Calibrate indicators'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Money management', 'Initial capital'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Money management', 'Choose Money Management method'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Money management', 'Order size'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Cross checks', 'What If simulations'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Cross checks', 'Monte Carlo trades manipulation'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Cross checks', 'Higher backtest precision'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Cross checks', 'Backtests on additional markets'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Cross checks', 'Monte Carlo retest methods'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Cross checks', 'Sequential Optimization'): 'assets/SQX_144_2953_linux_20260601/user/settings/Configs/DJ CFD H1.cfx',
    ('Cross checks', 'Opt. Profile / Sys. Param. Permutation'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Cross checks', 'Walk-Forward Optimization'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Cross checks', 'Walk-Forward Matrix'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Ranking', 'Maximum strategies to store in databank'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Ranking', 'Stop generation when'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Ranking', 'Compute from'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Ranking', 'Ranking Criterium'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Ranking', 'Custom filters'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Ranking', 'Dismiss strategies with these problems'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
    ('Ranking', 'Fit to existing portfolio filter'): 'assets/SQX_144_2953_linux_20260601/user/projects/Builder/project.cfx',
}


def _default_evidence_base(knowledge_root: str | Path) -> Path | None:
    """Project root when it carries an ``assets/`` install tree.

    Evidence paths in ``CFX_EVIDENCE_MAP`` are relative to the project
    root (the lake root's parent). Without an ``assets/`` tree (e.g. a
    staging checkout without the pinned install) verification is
    skipped — nothing is invented from a missing install.
    """
    root = Path(knowledge_root).resolve()
    return root.parent if (root.parent / "assets").is_dir() else None


def _bulk_verify(
    store: KbStore,
    evidence_base: Path | None,
    sqx_version: str,
    evidence_map: dict[tuple[str, str], str],
) -> int:
    """Promote mapped parameters whose real install file exists (D2).

    The stored ``evidence_ref`` is the map's RELATIVE path (portable
    goldens); the file is resolved against ``evidence_base`` for the
    existence check. Missing install files leave the parameter untouched
    (it becomes needs_review in the demote step).
    """
    if evidence_base is None:
        return 0
    count = 0
    for (tab, name), ref in evidence_map.items():
        if not (evidence_base / ref).is_file():
            continue
        try:
            store.verify(tab, name, evidence_ref=ref, sqx_version=sqx_version)
            count += 1
        except KbParamNotFoundError:
            continue  # param file absent — nothing to promote
    return count


def _demote_unverified(store: KbStore, sqx_version: str) -> int:
    """Downgrade leftover ``seeded`` entries to ``needs_review`` (D2).

    After bulk verification, any entry still ``seeded`` has doc-only
    evidence the install could not confirm. Per REQ-203 nothing is
    invented, so it must not be served as verified: it becomes
    ``needs_review`` (REQ-208 semantics).
    """
    count = 0
    for param in store.list(status="seeded", sqx_version=sqx_version):
        store.seed(
            [param.model_copy(update={"status": "needs_review"})],
            sqx_version=sqx_version,
        )
        count += 1
    return count


@dataclass
class SeedFlowResult:
    """Outcome of a full seed flow (seed + verify + index + gate)."""

    total: int
    verified: int
    needs_review: int
    seeded: int
    report: SeedValidationReport

    @property
    def ok(self) -> bool:
        return self.report.ok


def run_seed_flow(
    store: KbStore,
    doc_path: str | Path = DEFAULT_DOC_PATH,
    sqx_version: str | None = None,
    *,
    evidence_base: Path | None = None,
    evidence_map: dict[tuple[str, str], str] | None = None,
) -> SeedFlowResult:
    """Run the complete seed flow: seed -> bulk-verify -> demote -> index -> gate.

    Args:
        store: KbStore over the target Knowledge Lake.
        doc_path: source doc (defaults to ``docs/sqx-builder-config/SQX Builder Config.md``).
        sqx_version: target version bucket (defaults to pinned version).
        evidence_base: directory the map's relative evidence paths resolve
            against. Defaults to the project root when it has ``assets/``.
        evidence_map: provenance table (defaults to ``CFX_EVIDENCE_MAP``).

    Returns:
        SeedFlowResult with final distribution and the REQ-209 gate report.
        ``.ok`` is False when the gate fails (caller exits non-zero).
    """
    version = sqx_version or SQX_VERSION
    table = evidence_map if evidence_map is not None else CFX_EVIDENCE_MAP
    base = evidence_base if evidence_base is not None else _default_evidence_base(store.root)

    result = seed_from_doc(store, doc_path=doc_path, sqx_version=version)
    _bulk_verify(store, base, version, table)
    _demote_unverified(store, version)
    store.store.rebuild_index()

    report = validate_seed(store.root, sqx_version=version)
    return SeedFlowResult(
        total=result.total,
        verified=report.counts["verified"],
        needs_review=report.counts["needs_review"],
        seeded=report.counts["seeded"],
        report=report,
    )


__all__ = [
    "CFX_EVIDENCE_MAP",
    "SeedFlowResult",
    "run_seed_flow",
]
