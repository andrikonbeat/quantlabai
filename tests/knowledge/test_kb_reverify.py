"""Regression: XML anchors survive every store write (REQ-201 scenario 3).

Finding 0 — ``KbParameter`` omitted ``xml_path``/``element_name``, so pydantic's
``extra="ignore"`` dropped both on load and ``to_yaml``'s ``exclude_none=True``
never wrote them back. Every store write (verify / invalidate / drift demotion)
silently deleted the XML traceability pair from the catalog.

These tests pin the declared-schema contract: the pair is *declared*, not
accepted as an unknown key, and it survives a load -> mutate -> save -> reload
round trip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quantlab.knowledge.kb.models import KbParameter
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
