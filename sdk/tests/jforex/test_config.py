"""Tests for JForexCredentials model."""

from __future__ import annotations

from pydantic import ValidationError
import pytest

from quantlab.jforex.config import JForexCredentials


class TestJForexCredentials:
    """Test the JForexCredentials model."""

    def test_defaults(self):
        """Test that default values are applied correctly."""
        creds = JForexCredentials(username="user", password="pass")

        assert creds.username == "user"
        assert creds.password.get_secret_value() == "pass"
        assert creds.host == "127.0.0.1"
        assert creds.port == 11111
        assert creds.account_id is None

    def test_custom_values(self):
        """Test that custom values override defaults."""
        creds = JForexCredentials(
            username="trader",
            password="secret",
            host="jforex.example.com",
            port=22222,
            account_id="ACC-001",
        )

        assert creds.username == "trader"
        assert creds.password.get_secret_value() == "secret"
        assert creds.host == "jforex.example.com"
        assert creds.port == 22222
        assert creds.account_id == "ACC-001"

    def test_password_is_required(self):
        """Test that missing required fields raise validation errors."""
        with pytest.raises(ValidationError):
            JForexCredentials(username="user")

    def test_model_dump_excludes_secret(self):
        """Test that password is excluded from serialization."""
        creds = JForexCredentials(username="user", password="secret")
        data = creds.model_dump(exclude={"password"})

        assert "password" not in data
        assert data["username"] == "user"
