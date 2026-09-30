"""Tests for CrossChecks KB YAML schema completeness (PR1).

Strict TDD — RED phase: tests reference fields that do not exist yet
in the Cross checks YAML catalog. Expected failures: KeyError / AssertionError.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from quantlab.knowledge.kb.models import KbParameter
from quantlab.knowledge.kb.store import KbStore

_KNOWLEDGE_ROOT = Path("/home/ogzuz/Proyectos/QuantLab AI/knowledge/structured/sqx-kb/144.2953")
_PROJECT_ROOT = _KNOWLEDGE_ROOT.parent.parent.parent.parent
_CROSSCHECKS_DIR = _KNOWLEDGE_ROOT / "parameters" / "Cross checks"
_CFX_PATH = Path(
    "/home/ogzuz/Proyectos/QuantLab AI/sdk/assets/SQX_144_2953_linux_20260601"
    "/user/projects/sqx_4fdea2e7519c/project.cfx"
)
_TEMPLATE_PATH = Path(
    "/home/ogzuz/Proyectos/QuantLab AI/sdk/quantlab/sqx/templates/default-project.sqx-template"
)

# 8 robustness tabs extracted from CFX evidence (spec requirement)
_EXPECTED_TABS = {
    "RetestOnAdditionalMarkets",
    "WalkForwardOptimization",
    "RetestWithHigherPrecision",
    "MonteCarloRetest",
    "WalkForwardMatrix",
    "MonteCarloManipulation",
    "OptProfileSysParamPermutation",
    "WhatIf",
}


def _load_yaml(path: Path) -> dict:
    """Minimal YAML loader for catalog entries (no external deps)."""
    data: dict = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.rstrip("\n")
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        data[key] = value
    return data


def _extract_cfx_crosschecks() -> str:
    """Extract CrossChecks XML from the CFX archive."""
    import zipfile

    with zipfile.ZipFile(_CFX_PATH) as z:
        # The CFX stores CrossChecks in Build-Task1.xml, not config.xml
        xml = z.read("Build-Task1.xml").decode("utf-8", errors="replace")
    root = ET.fromstring(xml)
    cc = root.find(".//CrossChecks")
    assert cc is not None, "CFX evidence missing CrossChecks section"
    return ET.tostring(cc, encoding="unicode")


def _extract_template_crosschecks() -> str:
    """Extract CrossChecks XML from the default template."""
    import zipfile

    with zipfile.ZipFile(_TEMPLATE_PATH) as z:
        xml = z.read("Build-Task1.xml").decode("utf-8", errors="replace")
    root = ET.fromstring(xml)
    cc = root.find(".//CrossChecks")
    assert cc is not None, "Template missing CrossChecks section"
    return ET.tostring(cc, encoding="unicode")


# ── Schema completeness tests ──────────────────────────────────────────


class TestCrossChecksSchemaCompleteness:
    """Every CrossChecks YAML must carry the new evidence-first schema fields."""

    def test_every_yaml_has_xml_path_and_element_name(self):
        """GIVEN the Cross checks KB directory
        WHEN every YAML is loaded
        THEN each entry has xml_path and element_name.
        """
        yaml_files = sorted(_CROSSCHECKS_DIR.glob("*.yaml"))
        assert yaml_files, "No CrossChecks YAMLs found"

        for yaml_path in yaml_files:
            data = _load_yaml(yaml_path)
            assert "xml_path" in data, (
                f"{yaml_path.name} missing xml_path"
            )
            assert "element_name" in data, (
                f"{yaml_path.name} missing element_name"
            )

    def test_every_yaml_has_required_evidence_fields(self):
        """GIVEN the Cross checks KB directory
        WHEN every YAML is loaded
        THEN each entry has evidence_ref, type, range, and section.
        """
        yaml_files = sorted(_CROSSCHECKS_DIR.glob("*.yaml"))
        required = {"evidence_ref", "type", "range", "section"}

        for yaml_path in yaml_files:
            data = _load_yaml(yaml_path)
            missing = required - data.keys()
            assert not missing, (
                f"{yaml_path.name} missing fields: {missing}"
            )

    def test_evidence_refs_point_to_existing_files(self):
        """GIVEN every CrossChecks YAML
        WHEN evidence_ref is checked
        THEN the referenced file exists on disk.
        Anchors (#section) are stripped before existence check.
        """
        yaml_files = sorted(_CROSSCHECKS_DIR.glob("*.yaml"))

        for yaml_path in yaml_files:
            data = _load_yaml(yaml_path)
            ref = data.get("evidence_ref", "")
            assert ref, f"{yaml_path.name} has empty evidence_ref"
            # Strip anchor for file existence check
            ref_path = ref.split("#")[0]
            # evidence_ref may be relative to project root or absolute
            candidate = Path(ref_path)
            if not candidate.is_absolute():
                candidate = _PROJECT_ROOT / ref_path
            assert candidate.exists(), (
                f"{yaml_path.name} evidence_ref missing: {ref}"
            )

    def test_xml_paths_match_cfx_structure(self):
        """GIVEN every CrossChecks YAML xml_path
        WHEN checked against its cited CFX/template evidence
        THEN the path resolves to an actual element.
        Doc-gap entries and non-CFX evidence are skipped.
        """
        yaml_files = sorted(_CROSSCHECKS_DIR.glob("*.yaml"))

        for yaml_path in yaml_files:
            data = _load_yaml(yaml_path)
            xml_path = data.get("xml_path", "")
            assert xml_path, f"{yaml_path.name} missing xml_path"
            ref = data.get("evidence_ref", "")
            # Skip doc-gap entries whose evidence is not CFX/template XML
            if data.get("status") == "needs_review" and (
                ref.endswith(".md") or "#" in ref
            ):
                continue
            # Resolve the evidence file
            evidence_file = Path(ref)
            if not evidence_file.is_absolute():
                evidence_file = _PROJECT_ROOT / ref
            if not evidence_file.exists():
                continue
            # Extract CrossChecks XML from the evidence file
            import zipfile
            try:
                with zipfile.ZipFile(evidence_file) as z:
                    # Prefer Build-Task1.xml, fallback to config.xml
                    if "Build-Task1.xml" in z.namelist():
                        xml = z.read("Build-Task1.xml").decode("utf-8", errors="replace")
                    else:
                        xml = z.read("config.xml").decode("utf-8", errors="replace")
                root = ET.fromstring(xml)
                cc = root.find(".//CrossChecks")
                if cc is None:
                    continue
            except Exception:
                continue
            # Walk the path segments and verify each element exists
            parts = xml_path.split("/")
            current = cc
            for tag in parts[1:]:
                found = current.find(tag)
                assert found is not None, (
                    f"{yaml_path.name} xml_path invalid: {xml_path} "
                    f"(missing <{tag}> in evidence {evidence_file.name})"
                )
                current = found

    def test_all_eight_robustness_tabs_are_covered(self):
        """GIVEN the CFX CrossChecks evidence
        WHEN the KB catalog is inspected
        THEN all 8 robustness tabs have corresponding YAML entries.
        """
        cc_xml = _extract_cfx_crosschecks()
        root = ET.fromstring(cc_xml)
        present_tabs = {child.tag for child in root}
        assert _EXPECTED_TABS.issubset(present_tabs), (
            f"CFX evidence missing expected tabs: "
            f"{_EXPECTED_TABS - present_tabs}"
        )

        yaml_files = sorted(_CROSSCHECKS_DIR.glob("*.yaml"))
        cataloged_names = {
            _load_yaml(p).get("sqx_name", "").lower()
            for p in yaml_files
        }
        # Map CFX tag names to expected YAML sqx_name values
        expected_names = {
            "RetestOnAdditionalMarkets": "backtests on additional markets",
            "WalkForwardOptimization": "walk-forward optimization",
            "RetestWithHigherPrecision": "higher backtest precision",
            "MonteCarloRetest": "monte carlo retest methods",
            "WalkForwardMatrix": "walk-forward matrix",
            "MonteCarloManipulation": "monte carlo trades manipulation",
            "OptProfileSysParamPermutation": "opt. profile / sys. param. permutation",
            "WhatIf": "what if simulations",
        }
        missing = []
        for tag, name in expected_names.items():
            if name not in cataloged_names:
                missing.append(name)
        assert not missing, f"Missing YAML entries for tabs: {missing}"

    def test_needs_review_entries_have_doc_gap_markers(self):
        """GIVEN needs_review CrossChecks entries
        WHEN inspected
        THEN they carry explicit doc-gap markers, not invented content.
        """
        yaml_files = sorted(_CROSSCHECKS_DIR.glob("*.yaml"))

        for yaml_path in yaml_files:
            data = _load_yaml(yaml_path)
            status = data.get("status", "")
            if status == "needs_review":
                what = data.get("what_it_does", "")
                how = data.get("how_it_works_in_sqx", "")
                assert "doc gap" in what.lower() or "not documented" in what.lower(), (
                    f"{yaml_path.name} is needs_review but what_it_does lacks doc-gap marker"
                )
                assert "doc gap" in how.lower() or "not documented" in how.lower(), (
                    f"{yaml_path.name} is needs_review but how_it_works_in_sqx lacks doc-gap marker"
                )


class TestCrossChecksSchemaTriangulation:
    """Triangulation: specific YAML values match exact CFX evidence."""

    def test_walkforward_optimization_defaults_match_cfx(self):
        """GIVEN Walk-Forward Optimization YAML
        WHEN its default is compared to CFX evidence
        THEN the values match the actual CFX attributes.
        """
        yaml_path = _CROSSCHECKS_DIR / "Walk-Forward Optimization.yaml"
        data = _load_yaml(yaml_path)
        assert data["element_name"] == "WalkForwardOptimization"
        assert data["xml_path"] == "CrossChecks/WalkForwardOptimization"
        # CFX shows period="12" optimization="6"
        assert "period=12" in data["default"], data["default"]
        assert "optimization=6" in data["default"], data["default"]

    def test_montecarlo_retest_simulations_match_cfx(self):
        """GIVEN Monte Carlo retest methods YAML
        WHEN its default is compared to CFX evidence
        THEN simulation count matches the actual CFX NumberOfSimulations.
        """
        yaml_path = _CROSSCHECKS_DIR / "Monte Carlo retest methods.yaml"
        data = _load_yaml(yaml_path)
        assert data["element_name"] == "MonteCarloRetest"
        # CFX shows NumberOfSimulations=10
        assert "10 simulations" in data["default"], data["default"]

    def test_whatif_methods_exist_in_template(self):
        """GIVEN What If simulations YAML
        WHEN checked against template evidence
        THEN the WhatIf element with Methods exists.
        """
        import zipfile

        yaml_path = _CROSSCHECKS_DIR / "What If simulations.yaml"
        data = _load_yaml(yaml_path)
        assert data["element_name"] == "WhatIf"
        with zipfile.ZipFile(_TEMPLATE_PATH) as z:
            xml = z.read("Build-Task1.xml").decode("utf-8", errors="replace")
        root = ET.fromstring(xml)
        whatif = root.find(".//WhatIf")
        assert whatif is not None
        methods = whatif.find("Settings/Methods")
        assert methods is not None
        assert len(methods.findall("Method")) > 0


# ── Version drift (catalog invalidation, REQ-208) ───────────────────────────


def _seed_param(name: str, status: str) -> KbParameter:
    return KbParameter(
        name=name,
        sqx_name=name,
        tab="Cross checks",
        section="1. BASIC (FAST)",
        type="config",
        what_it_does="seeded for drift test",
        how_it_works_in_sqx="seeded for drift test",
        quant_trading_role="seeded for drift test",
        status=status,
        sqx_version="144.2953",
        evidence_ref="seeded",
    )


@pytest.fixture
def drift_store(tmp_path: Path) -> KbStore:
    store = KbStore(root=tmp_path)
    store.initialize()
    store.seed(
        [
            _seed_param("What If simulations", "verified"),
            _seed_param("Walk-Forward Optimization", "verified"),
        ]
    )
    return store


class TestVersionDriftInvalidation:
    """GIVEN a versioned catalog WHEN SQX drifts THEN entries become needs_review."""

    def test_drift_invalidates_verified_entries_to_needs_review(
        self, drift_store: KbStore
    ) -> None:
        """144.2953 -> 145.1 must invalidate, warn, and never block."""
        result = drift_store.invalidate_on_version_drift("145.1")

        assert result.drifted is True
        assert result.catalog_version == "144.2953"
        assert result.current_version == "145.1"
        assert result.invalidated == 2
        assert result.blocked is False
        statuses = {p.name: p.status for p in drift_store.list(tab="Cross checks")}
        assert statuses == {
            "What If simulations": "needs_review",
            "Walk-Forward Optimization": "needs_review",
        }

    def test_drift_emits_actionable_warning(self, drift_store: KbStore) -> None:
        result = drift_store.invalidate_on_version_drift("145.1")
        assert result.warnings, "version drift must warn consumers"
        assert any("144.2953" in w and "145.1" in w for w in result.warnings)

    def test_matching_version_is_a_no_op(self, drift_store: KbStore) -> None:
        """No drift means verified entries stay verified and nothing is warned."""
        result = drift_store.invalidate_on_version_drift("144.2953")

        assert result.drifted is False
        assert result.invalidated == 0
        assert result.warnings == []
        assert all(
            p.status == "verified" for p in drift_store.list(tab="Cross checks")
        )

    def test_drift_can_be_scoped_to_one_tab(self, drift_store: KbStore) -> None:
        """Tab scoping narrows which entries are demoted, not the drift verdict.

        Drift is a property of the two version strings, so it stays true; a tab
        with no entries is simply nothing to invalidate.
        """
        result = drift_store.invalidate_on_version_drift("145.1", tab="Cross checks")
        assert result.drifted is True
        assert result.invalidated == 2

        result = drift_store.invalidate_on_version_drift("145.2", tab="Ranking")
        assert result.drifted is True
        assert result.invalidated == 0

