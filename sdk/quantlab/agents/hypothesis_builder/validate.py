"""BuildingBlockValidator — validates building blocks and strategies (RB-5).

Checks that:
- ``BuildingBlock.indicator.name`` is a known indicator.
- ``IndicatorConfig.params`` has the required keys for that indicator.
- ``EntryRule.conditions`` and ``ExitRule.conditions`` are non-empty.
- ``Strategy.building_blocks`` only reference existing block names.
- Building block names are unique within a batch.
"""

from __future__ import annotations

from quantlab.dsl.models import BuildingBlock, Strategy


class BuildingBlockValidator:
    """Validates building blocks and strategies per RB-5.

    Raises ``ValueError`` on the first validation failure.
    """

    # ── Known indicators and their required param keys ──────────────────────

    KNOWN_INDICATORS: dict[str, set[str]] = {
        "RSI": {"period"},
        "BB": {"period", "deviation"},
        "EMA": {"period"},
        "MACD": {"fast_period", "slow_period", "signal_period"},
        "ATR": {"period"},
        "Donchian": {"period"},
        "Volume": {"period"},
    }

    # ── Public API ──────────────────────────────────────────────────────────

    def validate(
        self,
        blocks: list[BuildingBlock],
        strategies: list[Strategy],
    ) -> None:
        """Validate a batch of building blocks and strategies (RB-5).

        Args:
            blocks: The building blocks to validate.
            strategies: The strategies referencing those blocks.

        Raises:
            ValueError: If any validation check fails.
        """
        self._validate_blocks(blocks)
        self._validate_strategies(blocks, strategies)

    # ── Internal checks ─────────────────────────────────────────────────────

    @classmethod
    def _validate_blocks(cls, blocks: list[BuildingBlock]) -> None:
        """Validate all building blocks.

        Checks:
        - Names are unique within the batch.
        - Indicator names are known.
        - Required params are present.
        - Entry/exit conditions are non-empty (when present).
        """
        seen_names: set[str] = set()

        for block in blocks:
            # Check unique name
            if block.name in seen_names:
                raise ValueError(
                    f"Duplicate building block name: '{block.name}'"
                )
            seen_names.add(block.name)

            # Check indicator name
            ind_name = block.indicator.name
            if ind_name not in cls.KNOWN_INDICATORS:
                raise ValueError(
                    f"Unknown indicator name '{ind_name}' in block "
                    f"'{block.name}'. Known: {', '.join(sorted(cls.KNOWN_INDICATORS))}"
                )

            # Check required params
            required = cls.KNOWN_INDICATORS[ind_name]
            missing = required - set(block.indicator.params.keys())
            if missing:
                raise ValueError(
                    f"Indicator '{ind_name}' in block '{block.name}' "
                    f"missing required params: {', '.join(sorted(missing))}"
                )

            # Check entry conditions
            if block.entry is not None and not block.entry.conditions:
                raise ValueError(
                    f"Block '{block.name}' has entry rule with empty conditions"
                )

            # Check exit conditions
            if block.exit is not None and not block.exit.conditions:
                raise ValueError(
                    f"Block '{block.name}' has exit rule with empty conditions"
                )

    @classmethod
    def _validate_strategies(
        cls,
        blocks: list[BuildingBlock],
        strategies: list[Strategy],
    ) -> None:
        """Validate all strategies.

        Checks:
        - Every block reference in a strategy exists in the blocks list.
        """
        block_names = {b.name for b in blocks}

        for strategy in strategies:
            for ref in strategy.building_blocks:
                if ref not in block_names:
                    raise ValueError(
                        f"Strategy '{strategy.name}' references unknown "
                        f"building block '{ref}'. "
                        f"Available blocks: {', '.join(sorted(block_names)) or '(none)'}"
                    )


__all__ = ["BuildingBlockValidator"]
