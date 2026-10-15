"""conftest.py for JForex Bridge tests — exports process manager fixtures."""

from test_fixtures import jforex_instance, jforex_session

# Export fixtures for all test modules in this package
__all__ = ["jforex_instance", "jforex_session"]