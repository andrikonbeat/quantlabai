"""Tests for EvolutionConfig."""

import pytest
from pydantic import ValidationError

from quantlab.evolution.config import (
    EvolutionConfig,
    EvolutionMode,
    ConcurrencyConfig,
    ScheduleConfig,
    WeightProfile,
)


class TestEvolutionConfig:
    def test_default_config(self):
        config = EvolutionConfig()
        assert config.enabled is False
        assert config.mode == EvolutionMode.FULL
        assert config.schedule.interval_hours == 168
        assert config.concurrency.max_pool_size == 50
        assert config.candidate_ttl_days == 30

    def test_disabled_mode(self):
        config = EvolutionConfig(mode=EvolutionMode.DISABLED)
        assert config.mode == EvolutionMode.DISABLED

    def test_genetic_only(self):
        config = EvolutionConfig(mode=EvolutionMode.GENETIC_ONLY)
        assert config.mode == EvolutionMode.GENETIC_ONLY

    def test_custom_schedule(self):
        config = EvolutionConfig(
            schedule=ScheduleConfig(interval_hours=24, max_candidates_per_cycle=5)
        )
        assert config.schedule.interval_hours == 24
        assert config.schedule.max_candidates_per_cycle == 5

    def test_schedule_validation(self):
        with pytest.raises(ValidationError):
            ScheduleConfig(interval_hours=0)

    def test_custom_concurrency(self):
        config = EvolutionConfig(
            concurrency=ConcurrencyConfig(max_concurrent_evolutions=3, max_pool_size=100)
        )
        assert config.concurrency.max_concurrent_evolutions == 3
        assert config.concurrency.max_pool_size == 100

    def test_concurrency_validation(self):
        with pytest.raises(ValidationError):
            ConcurrencyConfig(max_concurrent_evolutions=0)

    def test_weight_profile_sum(self):
        profile = WeightProfile()
        total = sum(profile.as_dict().values())
        assert abs(total - 1.0) < 0.001  # Should sum to 1.0

    def test_custom_weight_profile(self):
        profile = WeightProfile(sharpe=0.5, profit_factor=0.5, sortino=0.0)
        weights = profile.as_dict()
        assert weights["sharpe"] == 0.5
        assert weights["profit_factor"] == 0.5
        assert weights["sortino"] == 0.0

    def test_mg_signal_priorities(self):
        config = EvolutionConfig()
        assert config.mg_signal_priorities["RETIRED"] == 100
        assert config.mg_signal_priorities["MONITORING"] == 30
