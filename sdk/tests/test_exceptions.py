"""Tests for the QuantLab error hierarchy."""

from quantlab.tools.exceptions import (
    InsufficientDataError,
    ParseError,
    QuantLabError,
    SQXNotFoundError,
    TimeoutError,
    TranslationError,
    ValidationError,
)


class TestQuantLabError:
    """Base error class tests."""

    def test_base_error_has_detail(self) -> None:
        err = QuantLabError("something broke")
        assert err.detail == "something broke"

    def test_base_error_str(self) -> None:
        err = QuantLabError("fail")
        assert str(err) == "fail"

    def test_base_error_with_cause(self) -> None:
        cause = ValueError("inner")
        err = QuantLabError("outer", cause=cause)
        assert "outer" in str(err)
        assert "inner" in str(err)


class TestErrorSubclasses:
    """All error subclasses are catchable as QuantLabError."""

    def test_parse_error(self) -> None:
        err = ParseError("cannot parse YAML")
        assert isinstance(err, QuantLabError)
        assert err.detail == "cannot parse YAML"

    def test_validation_error(self) -> None:
        err = ValidationError("unknown market")
        assert isinstance(err, QuantLabError)
        assert err.detail == "unknown market"

    def test_translation_error(self) -> None:
        err = TranslationError("translation failed")
        assert isinstance(err, QuantLabError)

    def test_sqx_not_found_error(self) -> None:
        err = SQXNotFoundError("sqcli not found")
        assert isinstance(err, QuantLabError)

    def test_timeout_error(self) -> None:
        err = TimeoutError("command timed out")
        assert isinstance(err, QuantLabError)

    def test_insufficient_data_error(self) -> None:
        err = InsufficientDataError("empty trade list")
        assert isinstance(err, QuantLabError)
