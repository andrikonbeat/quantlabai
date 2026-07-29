"""Preset broker profiles with real-world cost parameters.

Provides ``BrokerProfile`` as a dataclass with factory methods for
Dukascopy, Interactive Brokers, and OANDA presets, plus override support
for customisation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from quantlab.costs.models import (
    CommissionSchema,
    MarketSession,
    SlippageProfile,
    SpreadConfig,
    SwapRule,
)


@dataclass
class BrokerProfile:
    """Complete broker cost profile with factory methods and override support.

    Use the factory methods (``dukascopy()``, ``interactive_brokers()``,
    ``oanda()``) for built-in presets, or ``with_overrides()`` to customise
    individual cost parameters.
    """

    name: str
    display_name: str
    commission: CommissionSchema
    swap: SwapRule
    slippage: SlippageProfile
    spread_config: SpreadConfig
    sessions: list[MarketSession] = field(default_factory=list)

    # ── Presets ─────────────────────────────────────────────────────────────────

    @classmethod
    def dukascopy(cls) -> BrokerProfile:
        """Dukascopy preset: tiered commission, tight spreads.

        Published schedule: EURUSD $3.0 per 100k, tiered to $2.0/100k
        above 100k. Spread 0.8 pips.
        """
        return cls(
            name="dukascopy",
            display_name="Dukascopy",
            commission=CommissionSchema(
                type="tiered",
                tiers=[
                    (0, 100_000, 3.0),
                    (100_000, 1_000_000_000, 2.0),
                ],
                currency="USD",
            ),
            swap=SwapRule(
                long_rate=-0.5,
                short_rate=-1.2,
                triple_day="Wednesday",
            ),
            slippage=SlippageProfile(mode="static", fixed_pips=0.5),
            spread_config=SpreadConfig(base_spread=0.8),
            sessions=[
                MarketSession(name="London", spread_multiplier=1.0),
                MarketSession(name="NewYork", spread_multiplier=1.2),
                MarketSession(name="Asia", spread_multiplier=1.5),
            ],
        )

    @classmethod
    def interactive_brokers(cls) -> BrokerProfile:
        """Interactive Brokers preset: tiered by volume, low spreads.

        Tiered pricing: $0.50/100k up to 50k, $0.30/100k up to 200k,
        $0.20/100k above. Spread 0.6 pips.
        """
        return cls(
            name="interactive_brokers",
            display_name="Interactive Brokers",
            commission=CommissionSchema(
                type="tiered",
                tiers=[
                    (0, 50_000, 0.50),
                    (50_000, 200_000, 0.30),
                    (200_000, 1_000_000_000, 0.20),
                ],
                currency="USD",
            ),
            swap=SwapRule(
                long_rate=-0.3,
                short_rate=-0.9,
                triple_day="Wednesday",
            ),
            slippage=SlippageProfile(mode="static", fixed_pips=0.3),
            spread_config=SpreadConfig(base_spread=0.6),
            sessions=[
                MarketSession(name="London", spread_multiplier=1.0),
                MarketSession(name="NewYork", spread_multiplier=1.1),
                MarketSession(name="Asia", spread_multiplier=1.3),
            ],
        )

    @classmethod
    def oanda(cls) -> BrokerProfile:
        """OANDA preset: spread-only pricing, wider spreads.

        OANDA charges no explicit commission — cost is embedded in the
        spread. Base spread 1.2 pips.
        """
        return cls(
            name="oanda",
            display_name="OANDA",
            commission=CommissionSchema(
                type="fixed",
                value=0.0,
                currency="USD",
            ),
            swap=SwapRule(
                long_rate=-0.4,
                short_rate=-1.0,
                triple_day="Wednesday",
            ),
            slippage=SlippageProfile(mode="static", fixed_pips=0.4),
            spread_config=SpreadConfig(base_spread=1.2),
            sessions=[
                MarketSession(name="London", spread_multiplier=1.0),
                MarketSession(name="NewYork", spread_multiplier=1.2),
                MarketSession(name="Asia", spread_multiplier=1.4),
            ],
        )

    # ── Override / customisation ────────────────────────────────────────────────

    def with_overrides(
        self,
        commission: CommissionSchema | None = None,
        swap: SwapRule | None = None,
        slippage: SlippageProfile | None = None,
        spread_config: SpreadConfig | None = None,
    ) -> BrokerProfile:
        """Create a new profile from this preset with selective overrides.

        Parameters
        ----------
        commission:
            Override the preset commission. ``None`` keeps the preset.
        swap:
            Override swap rules.
        slippage:
            Override slippage profile.
        spread_config:
            Override spread configuration.

        Returns
        -------
        BrokerProfile
            A **new** instance — the original preset is not mutated.
        """
        return BrokerProfile(
            name=self.name,
            display_name=self.display_name,
            commission=commission or self.commission,
            swap=swap or self.swap,
            slippage=slippage or self.slippage,
            spread_config=spread_config or self.spread_config,
            sessions=list(self.sessions),
        )
