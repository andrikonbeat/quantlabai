"""Tests for ParameterSpace and ParameterSpec."""

from __future__ import annotations

import pytest

from quantlab.optimization.space import (
    ParameterSpace,
    ParameterSpec,
    ParamType,
    ParameterConstraint,
    create_default_sqx_space,
)


class TestParameterSpec:
    """Tests for ParameterSpec validation and sampling."""

    def test_continuous_spec_validate(self):
        spec = ParameterSpec("lr", ParamType.CONTINUOUS, (0.0, 1.0), default=0.5)
        assert spec.validate(0.5) is True
        assert spec.validate(0.0) is True
        assert spec.validate(1.0) is True
        assert spec.validate(-0.1) is False
        assert spec.validate(1.1) is False
        assert spec.validate("invalid") is False

    def test_integer_spec_validate(self):
        spec = ParameterSpec("n", ParamType.INTEGER, (1, 10), default=5)
        assert spec.validate(5) is True
        assert spec.validate(1) is True
        assert spec.validate(10) is True
        assert spec.validate(0) is False
        assert spec.validate(11) is False
        assert spec.validate(5.5) is False

    def test_log_uniform_spec_validate(self):
        spec = ParameterSpec("lr", ParamType.LOG_UNIFORM, (-4, -1), default=0.001)
        assert spec.validate(0.001) is True
        assert spec.validate(0.1) is True
        assert spec.validate(0.0001) is True
        assert spec.validate(-0.001) is False
        assert spec.validate(0) is False

    def test_categorical_spec_validate(self):
        spec = ParameterSpec("opt", ParamType.CATEGORICAL, ["adam", "sgd", "rmsprop"], default="adam")
        assert spec.validate("adam") is True
        assert spec.validate("sgd") is True
        assert spec.validate("invalid") is False

    def test_sampling(self):
        spec = ParameterSpec("x", ParamType.CONTINUOUS, (0.0, 1.0))
        samples = [spec.sample() for _ in range(100)]
        assert all(0.0 <= s <= 1.0 for s in samples)

        spec_int = ParameterSpec("n", ParamType.INTEGER, (1, 10))
        samples_int = [spec_int.sample() for _ in range(100)]
        assert all(1 <= s <= 10 for s in samples_int)

        spec_cat = ParameterSpec("opt", ParamType.CATEGORICAL, ["a", "b", "c"])
        samples_cat = [spec_cat.sample() for _ in range(100)]
        assert all(s in ["a", "b", "c"] for s in samples_cat)

        spec_log = ParameterSpec("lr", ParamType.LOG_UNIFORM, (-4, -1))
        samples_log = [spec_log.sample() for _ in range(100)]
        assert all(0.0001 <= s <= 0.1 for s in samples_log)


class TestParameterSpace:
    """Tests for ParameterSpace functionality."""

    def test_add_and_get(self):
        space = ParameterSpace()
        spec = ParameterSpec("x", ParamType.CONTINUOUS, (0.0, 1.0))
        space.add(spec)
        assert space.get("x") is spec
        assert space.get("y") is None

    def test_names_and_bounds(self):
        space = ParameterSpace([
            ParameterSpec("a", ParamType.CONTINUOUS, (0.0, 1.0)),
            ParameterSpec("b", ParamType.INTEGER, (1, 5)),
            ParameterSpec("c", ParamType.CATEGORICAL, ["x", "y"]),
        ])
        assert space.names() == ["a", "b", "c"]
        bounds = space.bounds_array()
        assert len(bounds) == 3
        assert bounds[0] == (0.0, 1.0)
        assert bounds[1] == (1.0, 5.0)
        assert bounds[2] == (0.0, 1.0)  # categorical mapped to indices

    def test_param_types(self):
        space = ParameterSpace([
            ParameterSpec("a", ParamType.CONTINUOUS, (0.0, 1.0)),
            ParameterSpec("b", ParamType.INTEGER, (1, 5)),
            ParameterSpec("c", ParamType.CATEGORICAL, ["x", "y"]),
            ParameterSpec("d", ParamType.LOG_UNIFORM, (-3, 0)),
        ])
        types = space.param_types()
        assert types == [
            ParamType.CONTINUOUS,
            ParamType.INTEGER,
            ParamType.CATEGORICAL,
            ParamType.LOG_UNIFORM,
        ]

    def test_defaults(self):
        space = ParameterSpace([
            ParameterSpec("a", ParamType.CONTINUOUS, (0.0, 1.0), default=0.5),
            ParameterSpec("b", ParamType.INTEGER, (1, 5), default=3),
            ParameterSpec("c", ParamType.CATEGORICAL, ["x", "y"], default="x"),
        ])
        defaults = space.defaults()
        assert defaults == {"a": 0.5, "b": 3, "c": "x"}

    def test_validate_point(self):
        space = ParameterSpace([
            ParameterSpec("a", ParamType.CONTINUOUS, (0.0, 1.0)),
            ParameterSpec("b", ParamType.INTEGER, (1, 5)),
        ])
        valid, errors = space.validate_point({"a": 0.5, "b": 3})
        assert valid is True
        assert errors == []

        valid, errors = space.validate_point({"a": 1.5, "b": 3})
        assert valid is False
        assert "out of bounds" in errors[0]

        valid, errors = space.validate_point({"a": 0.5, "c": 1})
        assert valid is False
        assert "Unknown parameter" in errors[0]

    def test_to_from_vector(self):
        space = ParameterSpace([
            ParameterSpec("a", ParamType.CONTINUOUS, (0.0, 1.0)),
            ParameterSpec("b", ParamType.INTEGER, (1, 5)),
            ParameterSpec("c", ParamType.CATEGORICAL, ["x", "y", "z"]),
            ParameterSpec("d", ParamType.LOG_UNIFORM, (-3, 0)),
        ])
        point = {"a": 0.5, "b": 3, "c": "y", "d": 0.001}
        vec = space.to_vector(point)
        assert len(vec) == 4
        assert vec[0] == 0.5
        assert vec[1] == 3.0
        assert vec[2] == 1.0  # index of "y"
        assert vec[3] == 0.001

        # Round trip
        reconstructed = space.from_vector(vec)
        assert reconstructed["a"] == pytest.approx(0.5)
        assert reconstructed["b"] == 3
        assert reconstructed["c"] == "y"
        assert reconstructed["d"] == pytest.approx(0.001, rel=0.01)

    def test_constraints(self):
        space = ParameterSpace([
            ParameterSpec("a", ParamType.INTEGER, (1, 10)),
            ParameterSpec("b", ParamType.INTEGER, (1, 10)),
        ])
        space.constraints.append(ParameterConstraint(
            name="a_lt_b",
            constraint_type="lt",
            params={"left": "a", "right": "b"},
            message="a must be less than b",
        ))
        assert len(space.constraints) == 1

    def test_create_default_sqx_space(self):
        space = create_default_sqx_space()
        assert len(space.parameters) > 10
        names = space.names()
        assert "risk_per_trade_pct" in names
        assert "stop_loss_pips" in names
        assert "indicator_fast_period" in names
        assert "indicator_slow_period" in names
        assert len(space.constraints) >= 2


class TestParameterConstraint:
    """Tests for ParameterConstraint."""

    def test_constraint_creation(self):
        constraint = ParameterConstraint(
            name="test",
            constraint_type="lt",
            params={"left": "a", "right": "b"},
            message="a < b",
        )
        assert constraint.name == "test"
        assert constraint.constraint_type == "lt"
        assert constraint.params == {"left": "a", "right": "b"}
        assert constraint.message == "a < b"