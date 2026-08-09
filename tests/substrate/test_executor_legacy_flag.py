"""F3: QUANTLAB_LEGACY_EXECUTION flag routes dispatch to the legacy path.

Spec (unified-execution-substrate REQ-1 scenario, GIVEN clause authoritative):
- GIVEN QUANTLAB_LEGACY_EXECUTION=true THEN the legacy CommandDispatcher path
  is used (the legacy flag OVERRIDES the unified substrate opt-in).
- Default/unset keeps the substrate decision (REQ-28 parity: legacy is the
  fallback, substrate is the opt-in).

Strict TDD: written first — RED until the legacy flag selectors exist.
"""

from __future__ import annotations

from quantlab.substrate import (
    is_legacy_execution_enabled,
    is_unified_substrate_enabled,
    select_dispatch_backend,
)


class TestIsLegacyExecutionEnabled:
    """QUANTLAB_LEGACY_EXECUTION truthiness."""

    def test_true_when_flag_is_1(self) -> None:
        assert is_legacy_execution_enabled({"QUANTLAB_LEGACY_EXECUTION": "1"}) is True

    def test_true_when_flag_is_true(self) -> None:
        assert is_legacy_execution_enabled({"QUANTLAB_LEGACY_EXECUTION": "true"}) is True

    def test_true_when_flag_is_yes(self) -> None:
        assert is_legacy_execution_enabled({"QUANTLAB_LEGACY_EXECUTION": "yes"}) is True

    def test_false_when_unset(self) -> None:
        assert is_legacy_execution_enabled({}) is False

    def test_false_when_flag_is_0(self) -> None:
        assert is_legacy_execution_enabled({"QUANTLAB_LEGACY_EXECUTION": "0"}) is False


class TestSelectDispatchBackend:
    """Backend selection honours the legacy override (REQ-1 GIVEN)."""

    def test_legacy_when_flag_set(self) -> None:
        assert select_dispatch_backend({"QUANTLAB_LEGACY_EXECUTION": "true"}) == "legacy"

    def test_substrate_when_unified_opted_in(self) -> None:
        assert select_dispatch_backend({"QUANTLAB_UNIFIED_SUBSTRATE": "1"}) == "substrate"

    def test_legacy_by_default(self) -> None:
        """GIVEN no flags THEN the default keeps legacy operational (REQ-28)."""
        assert select_dispatch_backend({}) == "legacy"

    def test_legacy_overrides_unified(self) -> None:
        """GIVEN both flags set THEN the legacy path wins (REQ-1 scenario)."""
        env = {"QUANTLAB_LEGACY_EXECUTION": "1", "QUANTLAB_UNIFIED_SUBSTRATE": "1"}
        assert select_dispatch_backend(env) == "legacy"


class TestUnifiedFlagUnchanged:
    """The existing opt-in flag semantics are untouched (REQ-28 parity)."""

    def test_unified_enabled_when_1(self) -> None:
        assert is_unified_substrate_enabled({"QUANTLAB_UNIFIED_SUBSTRATE": "1"}) is True

    def test_unified_disabled_by_default(self) -> None:
        assert is_unified_substrate_enabled({}) is False

    def test_unified_disabled_when_0(self) -> None:
        assert is_unified_substrate_enabled({"QUANTLAB_UNIFIED_SUBSTRATE": "0"}) is False
