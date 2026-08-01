"""Shared pytest fixtures for dashboard tests."""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_cli_runner():
    """Create a mock CliRunner that returns serializable results."""
    runner = MagicMock()

    def make_result(*args, **kwargs):
        result = MagicMock()
        # Return 404 for nonexistent IDs
        if args and isinstance(args[0], list) and len(args[0]) > 0:
            cmd = args[0]
            if "nonexistent" in cmd or "missing" in cmd:
                result.exit_code = 1
                result.stdout = ""
                result.stderr = "Not found"
                return result
        result.exit_code = 0
        result.stdout = "[]"
        result.stderr = ""
        return result

    runner.execute.side_effect = make_result
    return runner


@pytest.fixture
def client(mock_cli_runner):
    """Flask test client with mocked CLI runner."""
    with patch("sdk.quantlab.dashboard.app.CliRunner", return_value=mock_cli_runner):
        from sdk.quantlab.dashboard.app import create_app

        app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client