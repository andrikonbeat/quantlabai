"""SQX Parameter KB models (REQ-201, D7).

Each parameter is a 22-field pydantic model persisted as YAML at
``structured/sqx-kb/{sqx_version}/parameters/{tab}/{param}.yaml``.

WU4 (REQ-302): ``SQX_VERSION`` resolves through ``PINNED_SQX_VERSION`` from
``quantlab.versioning`` — the single source of truth for the pinned SQX
build. This module is the KB's only import site for the pinned version.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from quantlab.versioning import PINNED_SQX_VERSION

# Pinned SQX build for this KB slice (D8/REQ-302). Consumers resolve
# through this constant; changing the pin propagates everywhere.
SQX_VERSION = PINNED_SQX_VERSION

# The 8 documented builder tabs (REQ-202). ``Tab`` mirrors this tuple.
KB_TABS: tuple[str, ...] = (
    "What to build",
    "Genetic options",
    "Data",
    "Trading options",
    "Building blocks",
    "Money management",
    "Cross checks",
    "Ranking",
)

Tab = Literal[
    "What to build",
    "Genetic options",
    "Data",
    "Trading options",
    "Building blocks",
    "Money management",
    "Cross checks",
    "Ranking",
]

# Status lifecycle: seeded (from doc) → verified (real config evidence) →
# needs_review (doc gap or invalidated on version drift, REQ-208).
Status = Literal["seeded", "verified", "needs_review"]


class SmallAccountRecommendation(BaseModel):
    """Nano-capital guidance for a parameter (REQ-206).

    ``recommended_value`` is what QuantLab recommends for a small account
    (e.g. $100), ``default_value`` is the SQX default, ``reason`` explains
    the tradeoff.
    """

    recommended_value: Any
    default_value: Any
    reason: str


class KbParameter(BaseModel):
    """A single SQX builder parameter (REQ-201, 22 fields).

    ``what_it_does`` is required: a KB YAML missing it MUST fail validation
    naming the field. ``default``/``range`` are free-form (scalar or string
    range). ``status`` defaults to ``seeded``; ``sqx_version`` defaults to the
    pinned version for this slice.
    """

    # Identity and placement
    name: str
    sqx_name: str
    tab: Tab
    section: str
    type: str
    # Documented values
    default: Any = None
    range: Any = None
    # Semantics (required — a stored entry without these is not usable)
    what_it_does: str
    how_it_works_in_sqx: str
    quant_trading_role: str
    # Research/edge context (optional)
    hypothesis_relation: str | None = None
    edge_relation: str | None = None
    # Small-account guidance (REQ-206)
    small_account_recommendation: SmallAccountRecommendation | None = None
    why_choose: str | None = None
    when_choose: str | None = None
    related_parameters: list[str] | None = None
    # Provenance / lifecycle
    status: Status = "seeded"
    sqx_version: str = SQX_VERSION
    evidence_ref: str | None = None

    @property
    def is_usable(self) -> bool:
        """True when the entry can guide configuration (verified or seeded)."""
        return self.status in ("seeded", "verified")

    def to_yaml(self) -> str:
        """Serialize to YAML, omitting empty fields."""
        import yaml

        return yaml.safe_dump(
            self.model_dump(exclude_none=True),
            default_flow_style=False,
            sort_keys=False,
        )

    @classmethod
    def from_yaml(cls, raw: str) -> "KbParameter":
        """Parse and validate a KB YAML document (REQ-201 loader)."""
        import yaml

        data = yaml.safe_load(raw)
        if not isinstance(data, dict):
            raise ValueError("KB YAML must contain a mapping")
        return cls.model_validate(data)
