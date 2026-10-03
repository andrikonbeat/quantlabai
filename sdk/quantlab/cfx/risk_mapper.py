"""RiskConfigMapper: typed ``RiskConfig`` ⇄ CFX ``risk_money_mgmt`` bridge.

Serialises a typed :class:`quantlab.dsl.models.RiskConfig` into the
``RiskMoneyManagement`` ``SettingsSection`` of a ``BuildTask`` using the
existing flat ``key@value`` convention of the CFX writer, and reads it back.

Values are stored as ratios in their natural ``[0, 1]`` range and are
validated before serialisation: an out-of-range or non-numeric value raises
:class:`RiskConfigError` instead of producing a partial section.
"""

from __future__ import annotations

from typing import Any, NamedTuple

from quantlab.cfx.errors import VersionError
from quantlab.cfx.models import BuildTask, CfxConfig, SettingsSection
from quantlab.cfx.reader import _MAX_VERSION, _MIN_VERSION
from quantlab.dsl.models import RiskConfig
from quantlab.tools.exceptions import QuantLabError

#: Section name emitted for the ``risk_money_mgmt`` field of a ``BuildTask``.
RISK_SECTION_NAME = "RiskMoneyManagement"


class _Bound(NamedTuple):
    """Half-open/closed numeric range accepted for a single field."""

    low: float
    high: float
    low_inclusive: bool = True
    high_inclusive: bool = True

    def contains(self, value: float) -> bool:
        """Return whether ``value`` falls inside this range."""
        low_ok = value >= self.low if self.low_inclusive else value > self.low
        high_ok = value <= self.high if self.high_inclusive else value < self.high
        return low_ok and high_ok

    def __str__(self) -> str:
        left = "[" if self.low_inclusive else "("
        right = "]" if self.high_inclusive else ")"
        return f"{left}{self.low}, {self.high}{right}"


#: Accepted range per ``RiskConfig`` field, mirroring the constraints declared
#: on ``quantlab.dsl.models.RiskConfig``. The mapper must never accept a value
#: the model itself would reject, otherwise deserialisation would surface a
#: pydantic error instead of a ``RiskConfigError``.
_FIELD_BOUNDS: dict[str, _Bound] = {
    "max_portfolio_drawdown": _Bound(0.0, 1.0, low_inclusive=False),
    "max_strategy_correlation": _Bound(0.0, 1.0),
    "max_single_strategy_weight": _Bound(0.0, 1.0, low_inclusive=False),
    "kelly_fraction_cap": _Bound(0.0, 1.0, low_inclusive=False),
    "var_confidence": _Bound(0.0, 1.0, high_inclusive=False),
}

#: Accepted schema version range; mirrors the CFX reader's own range.
MIN_SCHEMA_VERSION = _MIN_VERSION
MAX_SCHEMA_VERSION = _MAX_VERSION


class RiskConfigError(QuantLabError):
    """Raised when a ``RiskConfig`` value cannot be mapped to or from CFX."""


def _parse_version(version: str) -> tuple[int, int]:
    """Parse a dotted schema version into a comparable ``(major, minor)`` pair."""
    try:
        parts = [int(part) for part in version.split(".")]
    except ValueError as exc:
        raise RiskConfigError(f"Invalid CFX schema version: {version!r}") from exc
    padded = parts + [0, 0]
    return padded[0], padded[1]


class RiskConfigMapper:
    """Maps a typed ``RiskConfig`` to and from the CFX ``risk_money_mgmt`` section.

    The mapper is stateless; use it as a class-level singleton or instantiate
    it freely. Every ``RiskConfig`` field is mapped 1:1, so
    ``from_cfx(to_cfx(config)) == config`` holds for any valid config.
    """

    #: ``RiskConfig`` field name → CFX ``SettingsSection`` key.
    CFX_KEYS: dict[str, str] = {
        "max_portfolio_drawdown": "MaxPortfolioDrawdown@value",
        "max_strategy_correlation": "MaxStrategyCorrelation@value",
        "max_single_strategy_weight": "MaxStrategyWeight@value",
        "kelly_fraction_cap": "KellyFractionCap@value",
        "var_confidence": "VaRConfidence@value",
    }

    def to_cfx(self, config: RiskConfig) -> SettingsSection:
        """Serialise a typed ``RiskConfig`` into a CFX settings section.

        Args:
            config: Typed risk limits to serialise.

        Returns:
            A ``SettingsSection`` named ``RiskMoneyManagement`` whose settings
            use the known SQX keys and plain ratio strings.

        Raises:
            RiskConfigError: If any field is missing, non-numeric, or outside
                its valid range. Nothing is serialised in that case.
        """
        settings: dict[str, str] = {}
        for field, key in self.CFX_KEYS.items():
            settings[key] = self._format_value(config, field)
        return SettingsSection(name=RISK_SECTION_NAME, settings=settings)

    def from_cfx(self, source: SettingsSection | BuildTask | CfxConfig) -> RiskConfig:
        """Deserialise a CFX ``risk_money_mgmt`` section into a ``RiskConfig``.

        Args:
            source: The settings section itself, a ``BuildTask`` carrying one,
                or a whole ``CfxConfig`` (whose schema version is validated).

        Returns:
            A typed ``RiskConfig`` with every mapped field populated.

        Raises:
            RiskConfigError: If the section is missing, or a value cannot be
                parsed into a valid ratio.
            VersionError: If a ``CfxConfig`` declares an unsupported schema
                version. No partial ``RiskConfig`` is produced.
        """
        section = self._resolve_section(source)
        if section is None:
            raise RiskConfigError(
                "CFX source has no RiskMoneyManagement section to map"
            )

        values: dict[str, float] = {}
        for field, key in self.CFX_KEYS.items():
            raw = section.settings.get(key)
            if raw is None:
                raise RiskConfigError(
                    f"RiskMoneyManagement section is missing required key {key!r}"
                )
            values[field] = self._coerce(raw, field)
        return RiskConfig(**values)

    # ── Internals ──────────────────────────────────────────────────────────────

    def _format_value(self, config: RiskConfig, field: str) -> str:
        """Validate a single field and render it as a CFX string value."""
        value = getattr(config, field, None)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RiskConfigError(
                f"RiskConfig.{field} must be a real number; got {value!r}"
            )
        self._assert_in_range(field, float(value))
        return str(value)

    def _coerce(self, raw: str, field: str) -> float:
        """Parse a CFX string value into a validated ratio."""
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise RiskConfigError(
                f"RiskConfig.{field} value {raw!r} is not a number"
            ) from exc
        self._assert_in_range(field, value)
        return value

    def _assert_in_range(self, field: str, value: float) -> None:
        """Reject values outside the field's accepted range."""
        bound = _FIELD_BOUNDS[field]
        if not bound.contains(value):
            raise RiskConfigError(
                f"RiskConfig.{field} must be within {bound}; got {value}"
            )

    def _resolve_section(
        self, source: SettingsSection | BuildTask | CfxConfig
    ) -> SettingsSection | None:
        """Extract the risk section, validating the schema version when present."""
        if isinstance(source, SettingsSection):
            return source
        if isinstance(source, CfxConfig):
            self._assert_supported_version(source.schema_version)
            return source.task.risk_money_mgmt
        if isinstance(source, BuildTask):
            return source.risk_money_mgmt
        raise RiskConfigError(
            "from_cfx expects a SettingsSection, BuildTask, or CfxConfig; "
            f"got {type(source).__name__}"
        )

    @staticmethod
    def _assert_supported_version(version: Any) -> None:
        """Reject schema versions outside the supported range."""
        if version is None:
            raise RiskConfigError("Missing CFX schema version")
        parsed = _parse_version(str(version))
        low = _parse_version(MIN_SCHEMA_VERSION)
        high = _parse_version(MAX_SCHEMA_VERSION)
        if not low <= parsed <= high:
            raise VersionError(
                f"Unsupported CFX schema version {version} "
                f"(supported: {MIN_SCHEMA_VERSION} – {MAX_SCHEMA_VERSION})"
            )
