"""SQX KB educational table + shared dataset generator (parameter-educational-table spec).

The generator reads the seeded KB plus the SQX builder template
(``tpl_build.xml``) and emits:

1. A parameter-by-parameter markdown table in the REQ-205 shape (headers from
   ``teaching.TABLE_HEADERS``), and
2. A shared machine-readable educational dataset (one record per seeded
   parameter) consumed by ``parameter-justification-matrix`` as its rationale
   source (D2 connected decision).

Parsing uses stdlib ``xml.etree.ElementTree`` only; regeneration is
deterministic and idempotent. Parameters absent from the template are flagged
``template-missing`` and retain their KB status.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Literal, Sequence

from pydantic import BaseModel

from quantlab.knowledge.kb.models import KbParameter, SQX_VERSION
from quantlab.knowledge.kb.teaching import TABLE_HEADERS

# Spanish-doc / KB name → tpl_build.xml camelCase key mapping. Curated against
# the REAL pinned template (assets/SQX_144_2953_linux_20260601/internal/web/
# BUILDER/templates/tpl_build.xml, 104 parseable keys). Each value was verified
# to exist verbatim in that file; keys are the exact KB param names. Unmapped
# params render ⚠ template-missing retaining their KB status (design AD-6) —
# no invented values (verify WARNING 1 remediation).
TPL_KEY_MAP: dict[str, str] = {
    # Money management
    "Initial capital": "InitialCapital",
    "Order size": "Size",
    # Trading options
    "Maximum Trades Per Day": "MaxTradesPerDay",
    "Exit At End Of Day": "ExitAtEndOfDay",
    "Exit On Friday": "ExitOnFriday",
    "Limit Time Range": "LimitTimeRange",
    "Store Chart Data": "StoreChartData",
    "Stop Loss": "StopLoss",
    "End Of Day Exit Time": "EODExitTime",
    "Friday Close Time": "FridayExitTime",
    # Genetic options
    "Crossover Probability": "CrossoverProbability",
    "Mutation Probability": "MutationProbability",
    "Max # of Generations": "MaxGenerations",
    "Population Size (per island)": "PopulationSize",
    "Islands (separate evolution)": "Islands",
    "Migrate every Xth generation, X =": "MigrationModulo",
    "Population migration rate": "MigrationRate",
    "Generated decimation coefficient": "DecimationCoef",
    # Ranking
    "Maximum strategies to store in databank": "MaxStrategies",
}

TemplateStatus = Literal["matched", "template-missing"]

EMPTY_TABLE_NOTE = "No KB parameters to teach."


class EducationalRecord(BaseModel):
    """One educational dataset record (15-field contract per spec).

    ``chosen_config`` and ``template_status`` are generator-derived extras:
    the table's "Chosen config" column and the template cross-reference flag.
    """

    name: str
    sqx_name: str
    tab: str
    section: str
    type: str
    default: Any = None
    range: Any = None
    what_it_does: str
    how_it_works_in_sqx: str
    quant_trading_role: str
    small_account_recommendation: str | None = None
    why_choose: str | None = None
    when_choose: str | None = None
    status: str
    evidence_ref: str | None = None
    # Generator-derived (not part of the 15-field contract, but present in the
    # emitted dataset so consumers and the table share one source of truth).
    chosen_config: str | None = None
    template_status: TemplateStatus = "template-missing"


def parse_tpl_build(path: str | Path) -> dict[str, dict[str, Any]]:
    """Parse ``tpl_build.xml`` into ``{tpl_key: {name,type,min,max,default,...}}``.

    A single pass over the XML collects:

    - ``<Param key="..." className="...">value</Param>`` entries, and
    - scalar builder tags (``<MaxGenerations>50</MaxGenerations>``).

    Args:
        path: Path to the template XML.

    Returns:
        Mapping of template key → extracted attributes (``name``/``type``/
        ``min``/``max``/``default``/``className`` where present).
    """
    tree = ET.parse(path)
    data: dict[str, dict[str, Any]] = {}

    for elem in tree.iter():
        tag = elem.tag
        if not isinstance(tag, str):
            continue
        if tag == "Param":
            key = elem.get("key")
            if not key:
                continue
            entry: dict[str, Any] = {
                "name": elem.get("name", key),
                "className": elem.get("className"),
                "default": _normalize_text(elem.text),
            }
            for attr in ("type", "minValue", "maxValue"):
                val = elem.get(attr)
                if val is not None:
                    entry[attr] = val
            data[key] = entry
        elif tag == "Settings":
            continue
        elif elem.text is not None and elem.text.strip() and not list(elem):
            # Scalar leaf tag: <MaximumTradesPerDay>3</MaximumTradesPerDay>
            key = elem.tag
            if key not in data:
                data[key] = {"name": key, "default": _normalize_text(elem.text)}

    return data


def _normalize_text(text: str | None) -> str | None:
    """Normalize XML text content (strip whitespace; empty → None)."""
    if text is None:
        return None
    stripped = text.strip()
    return stripped or None


def _template_lookup(
    param: KbParameter, tpl: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any] | None, TemplateStatus]:
    """Resolve a KB parameter against the template map.

    Tries the curated ``TPL_KEY_MAP`` translation first, then exact
    ``sqx_name`` and ``name`` matches. Returns ``(template_entry, status)``.
    """
    candidates = [
        TPL_KEY_MAP.get(param.name),
        TPL_KEY_MAP.get(param.sqx_name),
        param.sqx_name,
        param.name,
    ]
    for candidate in candidates:
        if candidate and candidate in tpl:
            return tpl[candidate], "matched"
    return None, "template-missing"


def _small_account_text(param: KbParameter) -> str | None:
    """Render the small-account recommendation as a single string, if any."""
    rec = param.small_account_recommendation
    if rec is None:
        return None
    return f"{rec.recommended_value} (default {rec.default_value}): {rec.reason}"


def build_educational_dataset(
    params: Sequence[KbParameter],
    *,
    tpl: dict[str, dict[str, Any]],
    tpl_key_map: dict[str, str] | None = None,
) -> list[EducationalRecord]:
    """Build one :class:`EducationalRecord` per KB parameter.

    Args:
        params: Seeded/verified KB parameters.
        tpl: Template map from :func:`parse_tpl_build`.
        tpl_key_map: Optional override for the curated key map.

    Returns:
        Dataset records (deterministic; input params are not mutated).
    """
    global TPL_KEY_MAP
    key_map = tpl_key_map if tpl_key_map is not None else TPL_KEY_MAP
    records: list[EducationalRecord] = []
    for param in params:
        entry, status = _template_lookup(param, tpl)
        chosen = None
        if entry is not None:
            chosen = str(entry.get("default") or "")
        records.append(
            EducationalRecord(
                name=param.name,
                sqx_name=param.sqx_name,
                tab=param.tab,
                section=param.section,
                type=param.type,
                default=param.default,
                range=param.range,
                what_it_does=param.what_it_does,
                how_it_works_in_sqx=param.how_it_works_in_sqx,
                quant_trading_role=param.quant_trading_role,
                small_account_recommendation=_small_account_text(param),
                why_choose=param.why_choose,
                when_choose=param.when_choose,
                status=param.status,
                evidence_ref=param.evidence_ref,
                chosen_config=chosen,
                template_status=status,
            )
        )
    return records


def _cell(value: object) -> str:
    """Normalize a table cell, escaping pipes for markdown."""
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def load_educational_dataset(
    root: str | Path = "knowledge",
    sqx_version: str | None = None,
) -> list[EducationalRecord]:
    """Lazily load the shared educational dataset from the KB lake (REQ-205).

    Reads ``structured/sqx-kb/{sqx_version}/educational/educational-dataset.yaml``
    using :class:`~quantlab.knowledge.kb.store.KbStore` root resolution. The
    dataset is loaded at runtime from the lake — it is never imported as a
    static list. Returns ``[]`` when the file is missing or unreadable, so
    consumers (``parameter-justification-matrix``) fall back to their
    existing rationale sources; nothing is invented from a missing dataset.

    Args:
        root: Knowledge Lake root (default ``"knowledge"``).
        sqx_version: SQX version bucket (default: the pinned version).

    Returns:
        Parsed :class:`EducationalRecord` list (possibly empty).
    """
    from quantlab.knowledge.kb.store import KbStore

    store = KbStore(root)
    version = sqx_version or SQX_VERSION
    path = (
        store.root
        / "structured"
        / "sqx-kb"
        / version
        / "educational"
        / "educational-dataset.yaml"
    )
    if not path.is_file():
        return []
    try:
        import yaml

        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        return [EducationalRecord.model_validate(rec) for rec in raw]
    except Exception:
        return []


def build_educational_table(records: Sequence[EducationalRecord]) -> str:
    """Render the markdown educational table (REQ-205 shape).

    Args:
        records: Dataset records (or empty sequence for the placeholder).

    Returns:
        A markdown table with the REQ-205 headers and one row per record.
    """
    if not records:
        return EMPTY_TABLE_NOTE

    lines = [
        "| " + " | ".join(TABLE_HEADERS) + " |",
        "|" + "---|" * len(TABLE_HEADERS),
    ]
    for rec in records:
        marker = "⚠ " if rec.template_status == "template-missing" else ""
        row = (
            f"{rec.tab} / {rec.section}",
            marker + rec.name,
            rec.what_it_does,
            rec.how_it_works_in_sqx,
            rec.quant_trading_role,
            rec.chosen_config or "",
            rec.why_choose or "",
            rec.when_choose or "",
        )
        lines.append("| " + " | ".join(_cell(value) for value in row) + " |")
    return "\n".join(lines)
