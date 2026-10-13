"""Tests for templates loader."""

import pytest
from xml.etree import ElementTree as ET

from quantlab.sqx.templates import load_defaults, available_types, get_install_root


class TestTemplates:
    """Template loader tests."""

    def test_load_defaults_build_forex(self):
        """Load Build task defaults for forex base."""
        settings = load_defaults("Build", "forex")
        assert settings is not None
        # Should have Options/BuildTradingOptions/Params
        params = settings.find("Options/BuildTradingOptions/Params")
        assert params is not None
        # Should have some Params
        params_list = list(params.findall("Param"))
        assert len(params_list) > 0

    def test_load_defaults_build_futures(self):
        """Load Build task defaults for futures base."""
        settings = load_defaults("Build", "futures")
        assert settings is not None

    def test_load_defaults_build_stockpicker(self):
        """Load Build task defaults for stockpicker base."""
        settings = load_defaults("Build", "stockpicker")
        assert settings is not None

    def test_load_defaults_retest(self):
        """Load Retest task defaults."""
        settings = load_defaults("Retest")
        assert settings is not None

    def test_load_defaults_optimizer(self):
        """Load Optimize task defaults."""
        settings = load_defaults("Optimize")
        assert settings is not None

    def test_load_defaults_filtering(self):
        """Load Filtering task defaults."""
        settings = load_defaults("Filtering")
        assert settings is not None

    def test_rejects_unknown_task_type(self):
        """Unknown task type should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_defaults("UnknownTask")

    def test_available_types(self):
        """Available types should include known task types."""
        types = available_types()
        assert "Build" in types
        assert "Retest" in types
        assert "Optimize" in types

    def test_load_defaults_returns_copy(self):
        """Each call should return a fresh copy for safe mutation."""
        s1 = load_defaults("Build", "forex")
        s2 = load_defaults("Build", "forex")
        # Should be different objects
        assert s1 is not s2
        # But have same structure
        assert ET.tostring(s1) == ET.tostring(s2)

    def test_load_defaults_caches(self):
        """Repeated loads should be cached."""
        from quantlab.sqx.templates import _TEMPLATE_CACHE
        # Clear cache
        from quantlab.sqx.templates import _TEMPLATE_CACHE as cache
        cache.clear()
        load_defaults("Build", "forex")
        assert len(cache) == 1
        load_defaults("Build", "forex")
        assert len(cache) == 1  # Still 1, cached


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
