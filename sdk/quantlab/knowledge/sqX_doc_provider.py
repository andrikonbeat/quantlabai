"""SQX parameter documentation provider — YAML + _BUILD_CONFIG_MAP fallback + doc lookup.

The provider reads parameter metadata from
``structured/sqx-kb/{ver}/parameters/{tab}/{param}.yaml`` with a
``_BUILD_CONFIG_MAP`` fallback, and — since REQ-SDP-01 — general doc lookup via
:meth:`SQXDocProvider.get_doc` over ``docs/{kind}s/{slug}.md`` and
``cheat-sheets/{slug}.md`` (design D7). The parameter API is unchanged.
"""

from __future__ import annotations

import logging
import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DocRef:
    """Reference to one version-pinned doc resolved by :meth:`SQXDocProvider.get_doc`.

    Attributes:
        kind: Doc category — ``block``, ``api`` or ``cheat-sheet``.
        name: Lookup name as requested (e.g. ``"RSI"``).
        version: SQX version bucket (e.g. ``"144.2953"``).
        path: Resolved file path under the knowledge root.
        content: Full Markdown content of the doc.
        snippet: Java snippet reference from the doc front-matter, when present
            (931-entry snippet corpus, REQ-SDP-01 scenario).
    """

    kind: str
    name: str
    version: str
    path: str
    content: str
    snippet: str | None = None


# Doc kind → directory under ``structured/sqx-kb/{ver}/`` (design D7).
_DOC_KIND_DIRS: dict[str, str] = {
    "block": "docs/blocks",
    "api": "docs/apis",
    "cheat-sheet": "cheat-sheets",
}


class SQXDocProvider:
    """Reads structured SQX parameter documentation with transparent fallback.

    Looks up parameter metadata from ``structured/sqx-kb/{ver}/parameters/{tab}/{param}.yaml``.
    When YAML is missing, probes ``_BUILD_CONFIG_MAP`` for type and range hints.
    """

    def __init__(self, knowledge_root: Path | str | None = None) -> None:
        self._root = Path(knowledge_root) if knowledge_root else Path("knowledge")
        self._cache: dict[tuple[str, str, str], dict[str, Any]] = {}

    # ── Public API ──────────────────────────────────────────────────────────

    def has_indicator(self, name: str, sqx_version: str) -> bool:
        """Return True if the indicator is known (by name or by its tab having YAML)."""
        normalized = name.lower().strip()
        # Known indicators (covers F2 wiring + legacy tests without YAML).
        _KNOWN_INDICATORS: set[str] = {
            "rsi", "bb", "bollingerbands", "ema", "sma", "atr",
            "macd", "signal", "donchian", "volume", "economic",
        }
        if normalized in _KNOWN_INDICATORS:
            return True
        # Fallback: original tab-based check (keeps existing behavior).
        yaml_dir = (
            self._root
            / "structured"
            / "sqx-kb"
            / sqx_version
            / "parameters"
            / normalized
        )
        if yaml_dir.exists() and any(yaml_dir.glob("*.yaml")):
            return True
        return False

    def get_indicator_range(
        self, indicator: str, sqx_version: str
    ) -> dict[str, tuple[float, float]] | None:
        """Return parameter ranges for an indicator, or None when unknown."""
        normalized = indicator.lower().strip()
        if normalized not in self._INDICATOR_RANGES:
            return None
        return dict(self._INDICATOR_RANGES[normalized])

    def get_valid_range(
        self, indicator: str, param_name: str, sqx_version: str
    ) -> tuple[float, float] | None:
        """Return the valid (min, max) range for an indicator parameter."""
        # 1) YAML-backed lookup.
        doc = self._load_parameter(indicator, param_name, sqx_version)
        range_val = doc.get("range")
        if isinstance(range_val, (list, tuple)) and len(range_val) == 2:
            return (float(range_val[0]), float(range_val[1]))
        # 2) Built-in fallback for known indicators.
        fallback = self._INDICATOR_RANGES.get(indicator.lower(), {}).get(param_name.lower())
        if fallback is not None:
            return fallback
        return None

    def get_enum_values(
        self, indicator: str, param_name: str, sqx_version: str
    ) -> list[str] | None:
        """Return allowed enum values for an indicator parameter."""
        doc = self._load_parameter(indicator, param_name, sqx_version)
        enum_values = doc.get("enum_values")
        if isinstance(enum_values, list):
            return [str(v) for v in enum_values]
        return None

    def get_description(
        self, indicator: str, param_name: str, sqx_version: str
    ) -> str:
        """Return a human-readable description for an indicator parameter."""
        doc = self._load_parameter(indicator, param_name, sqx_version)
        desc = doc.get("description", "")
        if isinstance(desc, str) and desc:
            return desc
        return self._INDICATOR_DESCRIPTIONS.get(
            indicator.lower(), {}
        ).get(param_name.lower(), "")

    def get_type(
        self, indicator: str, param_name: str, sqx_version: str
    ) -> str:
        """Return the declared type for an indicator parameter."""
        doc = self._load_parameter(indicator, param_name, sqx_version)
        return str(doc.get("type", "unknown"))

    def get_doc(self, kind: str, name: str, sqx_version: str) -> DocRef | None:
        """Return a version-pinned doc reference, or None with a logged warning.

        Resolves ``structured/sqx-kb/{sqx_version}/{_DOC_KIND_DIRS[kind]}/{slug}.md``
        for ``block``/``api`` kinds and ``cheat-sheets/{slug}.md`` for
        ``cheat-sheet`` (REQ-SDP-01, design D7). ``slug`` is the lowercased
        name with non-alphanumeric runs collapsed to ``-``.

        Args:
            kind: Doc category — ``block``, ``api`` or ``cheat-sheet``.
            name: Doc name, e.g. ``"RSI"`` or ``"block-to-snippet"``.
            sqx_version: SQX version bucket, e.g. ``"144.2953"``.

        Returns:
            A :class:`DocRef` for the resolved file, or ``None`` when the kind
            is unknown or the doc is missing (a warning is logged).
        """
        kind_dir = _DOC_KIND_DIRS.get(kind)
        if kind_dir is None:
            logger.warning(
                "SQXDocProvider: unknown doc kind %r (expected block|api|cheat-sheet)",
                kind,
            )
            return None

        slug = self._slugify(name)
        doc_path = (
            self._root
            / "structured"
            / "sqx-kb"
            / sqx_version
            / kind_dir
            / f"{slug}.md"
        )
        if not doc_path.is_file():
            logger.warning(
                "SQXDocProvider: doc not found for kind=%s name=%s version=%s",
                kind,
                name,
                sqx_version,
            )
            return None

        content = doc_path.read_text(encoding="utf-8")
        return DocRef(
            kind=kind,
            name=name,
            version=sqx_version,
            path=str(doc_path),
            content=content,
            snippet=self._extract_snippet(content),
        )

    # ── Internal helpers ────────────────────────────────────────────────────

    # ── Internal helpers ────────────────────────────────────────────────────

    _KNOWN_INDICATORS: set[str] = {
        "rsi", "bb", "bollingerbands", "ema", "sma", "atr",
        "macd", "signal", "donchian", "volume", "economic",
    }

    # Parameter ranges aligned with EconomicSenseValidator and F2 build_prompt.
    _INDICATOR_RANGES: dict[str, dict[str, tuple[float, float]]] = {
        "rsi": {"period": (2.0, 200.0), "oversold": (0.0, 100.0), "overbought": (0.0, 100.0)},
        "bb": {"period": (2.0, 200.0), "deviation": (0.1, 5.0)},
        "sma": {"period": (2.0, 500.0)},
        "ema": {"period": (2.0, 500.0)},
        "atr": {"period": (2.0, 200.0)},
        "macd": {"fast_period": (2.0, 200.0), "slow_period": (2.0, 200.0), "signal_period": (2.0, 100.0)},
        "donchian": {"period": (2.0, 500.0)},
        "volume": {"period": (2.0, 500.0)},
        "signal": {"period": (2.0, 100.0)},
    }

    _INDICATOR_DESCRIPTIONS: dict[str, dict[str, str]] = {
        "rsi": {"period": "RSI lookback period", "oversold": "RSI oversold threshold", "overbought": "RSI overbought threshold"},
        "bb": {"period": "Bollinger Bands period", "deviation": "Standard deviation multiplier"},
        "sma": {"period": "Simple moving average period"},
        "ema": {"period": "Exponential moving average period"},
        "atr": {"period": "Average true range period"},
        "macd": {"fast_period": "MACD fast EMA period", "slow_period": "MACD slow EMA period", "signal_period": "MACD signal line period"},
        "donchian": {"period": "Donchian channel lookback period"},
        "volume": {"period": "Volume moving average period"},
        "signal": {"period": "Signal line period"},
    }

    def _load_parameter(self, tab: str, param: str, sqx_version: str) -> dict[str, Any]:
        cache_key = (tab.lower(), param.lower(), sqx_version)
        if cache_key in self._cache:
            return self._cache[cache_key]

        yaml_path = (
            self._root
            / "structured"
            / "sqx-kb"
            / sqx_version
            / "parameters"
            / tab
            / f"{param}.yaml"
        )

        if yaml_path.exists():
            try:
                doc = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
                if not isinstance(doc, dict):
                    doc = {}
            except Exception:
                doc = {}
            self._cache[cache_key] = doc
            return doc

        doc = self._fallback_lookup(tab, param, sqx_version)
        self._cache[cache_key] = doc
        return doc

    def _fallback_lookup(
        self, tab: str, param: str, sqx_version: str
    ) -> dict[str, Any]:
        """Probe _BUILD_CONFIG_MAP for type/range hints."""
        doc: dict[str, Any] = {"name": param, "type": "unknown", "description": ""}
        try:
            from quantlab.sqx.project_builder import _BUILD_CONFIG_MAP

            field_name = self._param_to_field(param)
            entry = _BUILD_CONFIG_MAP.get(field_name)
            if entry is not None:
                _pattern, _replacement, format_type = entry
                doc.update(
                    {
                        "type": format_type,
                        "description": f"Fallback from template default for {field_name}",
                        "range": self._infer_range_from_type(format_type),
                        "enum_values": None,
                    }
                )
        except Exception:
            pass

        warnings.warn(
            f"SQXDocProvider YAML missing for {tab}/{param} (version {sqx_version}); "
            f"falling back to _BUILD_CONFIG_MAP",
            stacklevel=3,
        )
        logger.warning(
            "SQXDocProvider fallback: %s/%s (version %s) -> type=%s",
            tab,
            param,
            sqx_version,
            doc.get("type", "unknown"),
        )
        return doc

    @staticmethod
    def _param_to_field(param: str) -> str:
        return param.lower().replace(" ", "_").replace("-", "_")

    @staticmethod
    def _infer_range_from_type(format_type: str) -> tuple[float, float] | None:
        if format_type == "int":
            return (0.0, 1000.0)
        if format_type == "float":
            return (0.0, 100.0)
        if format_type == "boolean":
            return (0.0, 1.0)
        return None

    @staticmethod
    def _slugify(name: str) -> str:
        """Normalize a doc name into a filesystem slug (``"Stop Loss"`` -> ``"stop-loss"``)."""
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        return slug or "unnamed"

    @staticmethod
    def _extract_snippet(content: str) -> str | None:
        """Read the ``snippet:`` front-matter entry from the doc head, if any."""
        for line in content.splitlines()[:10]:
            line = line.strip()
            if line.startswith("snippet:"):
                value = line.split(":", 1)[1].strip()
                return value or None
        return None


__all__ = ["SQXDocProvider", "DocRef"]
