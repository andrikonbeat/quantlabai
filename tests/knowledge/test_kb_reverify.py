"""KB re-verification pipeline (REQ-201 scenario 3; kb-reverification 1–7).

Phase 2 (PR 1) — XML anchors must survive every store write. ``KbParameter``
omitted ``xml_path``/``element_name``, so pydantic's ``extra="ignore"`` dropped both on
load and ``to_yaml``'s ``exclude_none=True`` never wrote them back: every store write
(verify / invalidate / drift demotion) silently deleted the traceability pair.

Phase 3 (PR 2) — the pure decision module (D3): evidence loading, the structural
XML-anchored discriminator, and the four-outcome verdict table. All evidence comes from
the TRACKED ``sdk/quantlab/sqx/templates/default-project.sqx-template``; install assets
under ``assets/SQX_*`` are gitignored and never used.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

from quantlab.knowledge.kb.models import KbParameter
from quantlab.knowledge.kb.reverify import (
    EvidenceUnreadableError,
    UnknownVersionBucketError,
    Verdict,
    classify,
    is_xml_anchored,
    load_evidence,
    require_known_bucket,
)
from quantlab.knowledge.kb.store import KbStore

_XML_PATH = "CrossChecks/WhatIf"
_ELEMENT_NAME = "WhatIf"

# Field order/shape copied from the real catalog entry
# knowledge/structured/sqx-kb/144.2953/parameters/Cross checks/What If simulations.yaml
# Written as raw text on purpose: the production defect is a *load* defect, so
# the anchors must already exist on disk before any store call.
_CATALOG_YAML = f"""name: What If simulations
sqx_name: What If simulations
tab: Cross checks
section: 1. BASIC (FAST)
type: config
xml_path: {_XML_PATH}
element_name: {_ELEMENT_NAME}
default: 15 simulations, 3 filter conditions
range: 'Filters: Profit factor > 1.3 AND Ret/DD Ratio > 4'
what_it_does: Scenario tests to check profit dependence on isolated events.
how_it_works_in_sqx: What-If robustness simulations.
quant_trading_role: Detects event-dependent profitability.
status: verified
sqx_version: '144.2953'
evidence_ref: assets/project.cfx
"""


@pytest.fixture
def anchor_store(tmp_path: Path) -> KbStore:
    """A store whose lake already holds a ``Cross checks`` entry with both anchors."""
    store = KbStore(root=tmp_path)
    store.initialize()
    path = store._param_path("Cross checks", "What If simulations", "144.2953")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_CATALOG_YAML, encoding="utf-8")
    return store


def _anchors(path: Path) -> tuple[str | None, str | None]:
    """Read the anchor pair back through the declared model."""
    raw = path.read_text(encoding="utf-8")
    param = KbParameter.from_yaml(raw)
    return param.xml_path, param.element_name


class TestXmlAnchorsSurviveStoreWrites:
    """GIVEN a Cross checks entry with anchors WHEN the store writes it THEN both survive."""

    def test_xml_anchors_survive_a_verify_write(self, anchor_store: KbStore) -> None:
        """verify() is a promotion write: it must not strip the XML anchors."""
        path = anchor_store._param_path(
            "Cross checks", "What If simulations", "144.2953"
        )
        assert _anchors(path) == (_XML_PATH, _ELEMENT_NAME), "precondition"

        anchor_store.verify(
            "Cross checks", "What If simulations", "assets/project.cfx#WhatIf"
        )

        assert _anchors(path) == (_XML_PATH, _ELEMENT_NAME)
        on_disk = path.read_text(encoding="utf-8")
        assert f"xml_path: {_XML_PATH}" in on_disk
        assert f"element_name: {_ELEMENT_NAME}" in on_disk

    def test_xml_anchors_survive_a_drift_demotion(self, anchor_store: KbStore) -> None:
        """Version-drift demotion is also a write; REQ-201 lists it explicitly."""
        path = anchor_store._param_path(
            "Cross checks", "What If simulations", "144.2953"
        )

        anchor_store.invalidate_on_version_drift("145.1")

        assert _anchors(path) == (_XML_PATH, _ELEMENT_NAME)
        assert anchor_store.get("Cross checks", "What If simulations").status == (
            "needs_review"
        )


class TestAnchorsAreDeclaredSchemaFields:
    """D2: explicit optional fields — NOT ``ConfigDict(extra="allow")``."""

    def test_anchor_pair_is_declared_on_the_model(self) -> None:
        fields = KbParameter.model_fields
        assert "xml_path" in fields
        assert "element_name" in fields
        assert fields["xml_path"].annotation == (str | None)
        assert fields["element_name"].annotation == (str | None)

    def test_typo_in_an_anchor_key_is_not_persisted(self) -> None:
        """``extra="allow"`` would leak catalog typos into the YAML; keep ignoring.

        Pydantic's default ignores unknown keys silently, so the observable
        guard is that a misspelled anchor key never reaches ``to_yaml()``.
        """
        assert KbParameter.model_config.get("extra", "ignore") == "ignore"
        typo = KbParameter.from_yaml(
            _CATALOG_YAML.replace("element_name:", "elemen_name:")
        )
        assert "elemen_name" not in typo.to_yaml()
        assert "elemen_name" not in typo.model_dump()

    def test_to_yaml_is_deterministic_with_anchors_set(self) -> None:
        """Declared fields serialize in declaration order, keys not dropped."""
        param = KbParameter.from_yaml(_CATALOG_YAML)
        rendered = param.to_yaml()

        assert f"xml_path: {_XML_PATH}" in rendered
        assert f"element_name: {_ELEMENT_NAME}" in rendered
        assert rendered == param.to_yaml()


# ── Phase 3: pure evidence loader + verdict table (D3) ───────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_TRACKED_TEMPLATE = (
    _PROJECT_ROOT / "sdk/quantlab/sqx/templates/default-project.sqx-template"
)

# The one real documentation gap in the catalog (verbatim from the lake YAML).
_DOC_GAP_XML_PATH = "docs/sqx-builder-config/SQX Builder Config.md#Cross checks"

# Anchor pairs of all 10 real `Cross checks` entries, copied verbatim from
# knowledge/structured/sqx-kb/144.2953/parameters/Cross checks/*.yaml. Embedded
# instead of read from the lake so these tests never depend on a cross-worktree
# absolute path (the trap in test_crosschecks_schema.py).
_CROSSCHECKS_ANCHORS: tuple[tuple[str, str], ...] = (
    ("CrossChecks/RetestOnAdditionalMarkets", "RetestOnAdditionalMarkets"),
    (_DOC_GAP_XML_PATH, "Cross checks vs Retester"),
    ("CrossChecks/RetestWithHigherPrecision", "RetestWithHigherPrecision"),
    ("CrossChecks/MonteCarloRetest", "MonteCarloRetest"),
    ("CrossChecks/MonteCarloManipulation", "MonteCarloManipulation"),
    ("CrossChecks/OptProfileSysParamPermutation", "OptProfileSysParamPermutation"),
    ("CrossChecks/SequentialOptimization", "SequentialOptimization"),
    ("CrossChecks/WalkForwardMatrix", "WalkForwardMatrix"),
    ("CrossChecks/WalkForwardOptimization", "WalkForwardOptimization"),
    ("CrossChecks/WhatIf", "WhatIf"),
)


def _crosschecks_xml(*tabs: str) -> str:
    """Minimal SQX-shaped XML: CrossChecks nested under Settings (real shape)."""
    body = "".join(f"<{tab}/>" for tab in tabs)
    return f"<Settings><Project><CrossChecks>{body}</CrossChecks></Project></Settings>"


def _zip_with(tmp_path: Path, name: str, members: dict[str, str]) -> Path:
    """Write a ZIP artifact holding the given members."""
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as archive:
        for member, body in members.items():
            archive.writestr(member, body)
    return path


class TestLoadEvidence:
    """REQ: evidence loading — member preference, bare XML, unreadable is typed."""

    def test_load_tracked_template_loads_without_install_assets(self) -> None:
        """The tracked template is sufficient evidence; assets/ is never needed."""
        assert _TRACKED_TEMPLATE.is_file(), "precondition: tracked template exists"

        evidence = load_evidence(_TRACKED_TEMPLATE)

        # config.xml holds no CrossChecks at all, so a successful load with a
        # populated block also proves Build-Task1.xml was the member used.
        assert evidence.member == "Build-Task1.xml"
        assert evidence.crosschecks.find("WhatIf") is not None
        assert len(list(evidence.crosschecks)) == 8

    def test_load_prefers_build_task1_over_config_xml(self, tmp_path: Path) -> None:
        """Both members parse; only Build-Task1.xml carries the probed tab."""
        path = _zip_with(
            tmp_path,
            "project.cfx",
            {
                "Build-Task1.xml": _crosschecks_xml("WhatIf"),
                "config.xml": _crosschecks_xml("SequentialOptimization"),
            },
        )

        evidence = load_evidence(path)

        assert evidence.member == "Build-Task1.xml"
        assert evidence.crosschecks.find("WhatIf") is not None
        assert evidence.crosschecks.find("SequentialOptimization") is None

    def test_load_falls_back_to_config_xml_when_build_task1_is_absent(
        self, tmp_path: Path
    ) -> None:
        path = _zip_with(
            tmp_path, "config-only.cfx", {"config.xml": _crosschecks_xml("WhatIf")}
        )

        evidence = load_evidence(path)

        assert evidence.member == "config.xml"
        assert evidence.crosschecks.find("WhatIf") is not None

    def test_load_accepts_a_bare_xml_file(self, tmp_path: Path) -> None:
        path = tmp_path / "build.xml"
        path.write_text(_crosschecks_xml("WhatIf"), encoding="utf-8")

        evidence = load_evidence(path)

        assert evidence.member == "build.xml"
        assert evidence.crosschecks.find("WhatIf") is not None

    @pytest.mark.parametrize(
        "case", ["missing", "truncated", "text", "bad_xml", "no_crosschecks"]
    )
    def test_load_reports_unreadable_for_missing_truncated_and_non_archive_paths(
        self, tmp_path: Path, case: str
    ) -> None:
        if case == "missing":
            path = tmp_path / "absent.cfx"
        elif case == "truncated":
            path = tmp_path / "truncated.cfx"
            path.write_bytes(b"PK\x03\x04" + b"\x00" * 32)
        elif case == "text":
            path = tmp_path / "notes.txt"
            path.write_text("not an archive", encoding="utf-8")
        elif case == "bad_xml":
            path = _zip_with(
                tmp_path, "bad-xml.cfx", {"Build-Task1.xml": "<Settings><oops>"}
            )
        else:
            path = _zip_with(
                tmp_path,
                "no-cc.cfx",
                {"Build-Task1.xml": "<Settings><Project/></Settings>"},
            )

        with pytest.raises(EvidenceUnreadableError) as exc_info:
            load_evidence(path)

        assert exc_info.value.path == path


class TestIsXmlAnchored:
    """D5: the discriminator is STRUCTURAL — ``status`` is never consulted."""

    @pytest.mark.parametrize(
        "xml_path", ["CrossChecks/WhatIf", "CrossChecks/WhatIf/Settings"]
    )
    def test_xml_anchors_are_recognised(self, xml_path: str) -> None:
        assert is_xml_anchored(xml_path) is True

    @pytest.mark.parametrize(
        "xml_path",
        [
            # The real documentation gap: a '#anchor' into a Markdown file.
            _DOC_GAP_XML_PATH,
            # A doc gap stays one without its fragment — shape, not file suffix.
            "docs/sqx-builder-config/SQX Builder Config.md",
            "Other/Path",
            # The root segment is matched exactly, as the catalog spells it.
            "crosschecks/WhatIf",
            "",
            None,
        ],
    )
    def test_non_xml_anchors_are_rejected(self, xml_path: str | None) -> None:
        assert is_xml_anchored(xml_path) is False


class TestClassify:
    """D3 four-outcome table over the real tracked template."""

    @pytest.fixture
    def crosschecks(self) -> ET.Element:
        return load_evidence(_TRACKED_TEMPLATE).crosschecks

    def test_positive_resolution_is_verified(self, crosschecks) -> None:
        assert classify("CrossChecks/WhatIf", "WhatIf", crosschecks) is Verdict.VERIFIED

    def test_absent_element_is_terminal(self, crosschecks) -> None:
        # Real case: SQX's CrossChecks block has no SequentialOptimization tag
        # (the 8 tabs ship OptProfileSysParamPermutation instead).
        verdict = classify(
            "CrossChecks/SequentialOptimization",
            "SequentialOptimization",
            crosschecks,
        )

        assert verdict is Verdict.FIELD_ABSENT
        assert verdict.promotes is False

    def test_documentation_anchor_is_not_xml_backed_without_probing(
        self, crosschecks
    ) -> None:
        class _Tripwire:
            def find(self, tag: str) -> None:
                raise AssertionError(f"a doc gap must never be probed: {tag}")

        verdict = classify(_DOC_GAP_XML_PATH, "Cross checks vs Retester", _Tripwire())

        assert verdict is Verdict.NOT_XML_BACKED

    def test_absent_anchor_is_not_xml_backed(self, crosschecks) -> None:
        assert classify(None, None, crosschecks) is Verdict.NOT_XML_BACKED

    def test_multi_segment_path_resolves_to_the_named_leaf(self, crosschecks) -> None:
        """Real nested tab: CrossChecks/WhatIf/Settings exists in the template."""
        assert (
            classify("CrossChecks/WhatIf/Settings", "Settings", crosschecks)
            is Verdict.VERIFIED
        )

    def test_mismatched_element_name_does_not_promote(self, crosschecks) -> None:
        """The path resolves, but to a different element than the entry claims.

        Promoting here would write an ``evidence_ref`` anchored to an element that is
        not the one the catalog documents, so the pair is treated as not present.
        """
        verdict = classify("CrossChecks/WhatIf", "NotTheWhatIfElement", crosschecks)

        assert verdict is Verdict.FIELD_ABSENT
        assert verdict.promotes is False

    def test_mixed_population_yields_a_verdict_per_entry(self, crosschecks) -> None:
        verdicts = [
            classify(xml_path, element, crosschecks)
            for xml_path, element in _CROSSCHECKS_ANCHORS
        ]

        assert len(verdicts) == len(_CROSSCHECKS_ANCHORS) == 10
        assert verdicts.count(Verdict.VERIFIED) == 8
        assert verdicts.count(Verdict.FIELD_ABSENT) == 1
        assert verdicts.count(Verdict.NOT_XML_BACKED) == 1
        assert all(not v.promotes for v in verdicts if v is not Verdict.VERIFIED)


class TestUnknownVersionBucket:
    """REQ: an unknown version bucket is refused, never silently empty."""

    def test_known_bucket_resolves_to_itself(self) -> None:
        assert require_known_bucket("144.2953", ["144.2953", "145.1"]) == "144.2953"

    def test_unknown_version_bucket_is_refused(self) -> None:
        with pytest.raises(UnknownVersionBucketError) as exc_info:
            require_known_bucket("999.1", ["144.2953"])

        assert exc_info.value.sqx_version == "999.1"
