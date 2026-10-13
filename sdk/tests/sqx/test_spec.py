"""Tests for spec parser/validator."""

import pytest

from quantlab.sqx.spec import parse_spec, SpecValidationError


class TestSpecParser:
    """Spec parser strictness."""

    def test_minimal_valid_spec(self):
        """Minimal valid spec with one Build task."""
        spec = {
            "tasks": [{
                "task": "Build",
                "base": "forex",
                "engine": "JForex",
                "symbol": "EURUSD_M1_dukas",
                "timeframe": "M15",
                "range": {"from": "2010-01-01", "to": "2024-10-30"},
            }]
        }
        # Should not raise
        spec = parse_spec('{"tasks":[{"task":"Build","base":"forex","engine":"JForex","symbol":"EURUSD_M1_dukas","timeframe":"M15","range":{"from":"2010-01-01","to":"2024-10-30"}}]}')
        assert spec["tasks"][0]["task"] == "Build"

    def test_rejects_unknown_top_key(self):
        """Unknown top-level key should fail."""
        bad = '{"tasks":[{}],"unknown":123}'
        with pytest.raises(Exception) as exc:
            parse_spec(bad)
        assert "unknown key" in str(exc.value).lower()

    def test_rejects_unknown_task_key(self):
        """Unknown task key should fail."""
        bad = '{"tasks":[{"task":"Build","unknown_key":123}]}'
        with pytest.raises(Exception) as exc:
            parse_spec(bad)
        assert "unknown key" in str(exc.value).lower()

    def test_rejects_invalid_symbol(self):
        """Invalid symbol format should fail."""
        bad = '{"tasks":[{"task":"Build","symbol":"EURUSD@123"}]}'
        with pytest.raises(Exception) as exc:
            parse_spec(bad)
        assert "symbol" in str(exc.value).lower()

    def test_rejects_invalid_timeframe(self):
        """Invalid timeframe should fail."""
        bad = '{"tasks":[{"task":"Build","symbol":"EURUSD","timeframe":"M99"}]}'
        with pytest.raises(Exception) as exc:
            parse_spec(bad)
        assert "timeframe" in str(exc.value).lower()

    def test_rejects_invalid_engine(self):
        """Invalid engine should fail."""
        bad = '{"tasks":[{"task":"Build","engine":"UnknownEngine"}]}'
        with pytest.raises(Exception) as exc:
            parse_spec(bad)
        assert "engine" in str(exc.value).lower()

    def test_rejects_invalid_stop_type(self):
        """Invalid stop type should fail."""
        bad = '{"tasks":[{"task":"Build","stop":{"type":"invalid"}}]}'
        with pytest.raises(Exception) as exc:
            parse_spec(bad)
        assert "stop" in str(exc.value).lower()

    def test_rejects_invalid_fitness(self):
        """Invalid fitness should fail."""
        bad = '{"tasks":[{"task":"Build","fitness":"InvalidFitness"}]}'
        with pytest.raises(Exception) as exc:
            parse_spec(bad)
        assert "fitness" in str(exc.value).lower()

    def test_rejects_invalid_base(self):
        """Invalid base should fail."""
        bad = '{"tasks":[{"task":"Build","base":"invalid"}]}'
        with pytest.raises(Exception) as exc:
            parse_spec(bad)
        assert "base" in str(exc.value).lower()

    def test_rejects_invalid_range(self):
        """Invalid range should fail."""
        bad = '{"tasks":[{"task":"Build","range":{"from":"2010-01-01"}}]}'
        with pytest.raises(Exception) as exc:
            parse_spec(bad)
        assert "range" in str(exc.value).lower()

    def test_rejects_invalid_oos_percent(self):
        """Invalid oos_percent should fail."""
        bad = '{"tasks":[{"task":"Build","oos_percent":150}]}'
        with pytest.raises(Exception) as exc:
            parse_spec(bad)
        assert "oos_percent" in str(exc.value).lower()

    def test_rejects_invalid_money_management_method(self):
        """Invalid MM method should fail."""
        bad = '{"tasks":[{"task":"Build","money_management":{"method":"InvalidMethod","size":0.01,"initial_capital":100}}]}'
        with pytest.raises(Exception) as exc:
            parse_spec(bad)
        assert "method" in str(exc.value).lower()

    def test_rejects_invalid_ranking_op(self):
        """Invalid ranking operator should fail."""
        # "!=" is actually VALID in SQX; use truly invalid operator
        bad = '{"tasks":[{"task":"Build","rankings":[{"column":"ProfitFactor","op":"invalid_op","value":1.2,"sample":"oos"}]}]}'
        with pytest.raises(Exception) as exc:
            parse_spec(bad)
        assert "op" in str(exc.value).lower()

    def test_rejects_missing_required_fields(self):
        """Missing required fields should fail."""
        bad = '{"tasks":[{}]}'
        with pytest.raises(Exception) as exc:
            parse_spec(bad)
        assert "missing required" in str(exc.value).lower()

    def test_rejects_invalid_cross_check_section(self):
        """Invalid cross-check section name should fail."""
        import json
        bad = json.dumps({"tasks":[{"task":"Build","cross_checks":{"InvalidSection":{"use":True}}}]})
        with pytest.raises(Exception) as exc:
            parse_spec(bad)
        assert "key" in str(exc.value).lower() or "unknown keys" in str(exc.value).lower() or "unknown keys" in str(exc.value).lower()

    def test_rejects_invalid_cross_check_key(self):
        """Invalid cross-check key should fail."""
        import json
        bad = json.dumps({"tasks":[{"task":"Build","cross_checks":{"RetestWithHigherPrecision":{"use":True,"invalid_key":123}}}]})
        with pytest.raises(Exception) as exc:
            parse_spec(bad)
        assert "unknown key" in str(exc.value).lower() or "unknown keys" in str(exc.value).lower()

    def test_rejects_cross_check_missing_use(self):
        """Cross-check section without 'use' should fail."""
        bad = '{"tasks":[{"task":"Build","cross_checks":{"RetestWithHigherPrecision":{"precision":2}}}]}'
        with pytest.raises(Exception) as exc:
            parse_spec(bad)
        assert "use" in str(exc.value).lower()

    def test_valid_complex_spec(self):
        """Complex valid spec should pass."""
        spec = {
            "edit": "Builder",
            "tasks": [{
                "task": "Build",
                "base": "forex",
                "engine": "JForex",
                "symbol": "EURUSD_M1_dukas",
                "timeframe": "M15",
                "range": {"from": "2010-01-01", "to": "2024-10-30"},
                "oos_percent": 30,
                "rankings": [
                    {"column": "ProfitFactor", "op": ">=", "value": 1.2, "sample": "oos"},
                    {"column": "NetProfit", "op": ">", "value": 0, "sample": "oos"}
                ],
                "max_strategies": 100,
                "stop": {"type": "passed-count", "count": 100},
                "cross_checks": {
                    "all": True,
                    "RetestWithHigherPrecision": {"use": True, "precision": 2, "spread": 5}
                },
                "money_management": {"method": "fixed_size", "size": 0.01, "initial_capital": 100, "max_drawdown": 20},
                "trading_options": {"exit_on_friday": True, "friday_exit_time": 74400, "max_trades_per_day": 2, "min_sl": 15, "max_sl": 25, "min_pt": 10, "max_pt": 60},
                "costs": {"spread": 5, "slippage": 1, "min_distance": 0},
                "fitness": "ReturnDDRatio",
                "what_to_build": {"market_sides": "both", "entry_symmetry": True, "exit_symmetry": True, "conditions": [1, 3], "exit_conditions": [0, 2], "period": [5, 100], "shift": [1, 2], "sl_required": True, "pt_required": True}
            }]
        }
        # Should not raise
        parsed = parse_spec(import_json_dumps(spec))
        assert parsed["edit"] == "Builder"
        assert parsed["tasks"][0]["task"] == "Build"

    def test_edit_mode_validation(self):
        """Edit mode should require tasks array."""
        bad = '{"edit":"Builder"}'
        with pytest.raises(Exception) as exc:
            parse_spec(bad)
        assert "edit" in str(exc.value).lower() or "tasks" in str(exc.value).lower()

    def test_empty_tasks_rejected(self):
        """Empty tasks array should be rejected."""
        bad = '{"tasks":[]}'
        with pytest.raises(Exception) as exc:
            parse_spec(bad)
        assert "tasks" in str(exc.value).lower()


def import_json_dumps(obj):
    import json
    return json.dumps(obj)
