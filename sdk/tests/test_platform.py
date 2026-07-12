"""Tests for cross-platform path resolution utilities.

NOTE: These tests mock platform.system() to avoid depending on the
actual host OS. Real cross-platform validation would run on each OS.
"""

from pathlib import Path
from unittest.mock import patch

from quantlab.tools.platform import (
    get_app_config_dir,
    get_app_data_dir,
    get_platform_name,
    get_sqcli_binary,
    normalize_path,
    resolve_sqcli_path,
)


class TestGetPlatformName:
    def test_when_windows(self) -> None:
        with patch("platform.system", return_value="Windows"):
            assert get_platform_name() == "windows"

    def test_when_linux(self) -> None:
        with patch("platform.system", return_value="Linux"):
            assert get_platform_name() == "linux"

    def test_when_darwin(self) -> None:
        with patch("platform.system", return_value="Darwin"):
            assert get_platform_name() == "darwin"


class TestGetSqcliBinary:
    def test_windows_returns_exe(self) -> None:
        with patch("quantlab.tools.platform.get_platform_name", return_value="windows"):
            assert get_sqcli_binary() == "sqcli.exe"

    def test_linux_returns_no_ext(self) -> None:
        with patch("quantlab.tools.platform.get_platform_name", return_value="linux"):
            assert get_sqcli_binary() == "sqcli"


class TestResolveSqcliPath:
    def test_custom_path_exists(self, tmp_path: Path) -> None:
        binary = tmp_path / "sqcli"
        binary.write_text("fake binary")
        result = resolve_sqcli_path(custom_path=str(binary))
        assert result is not None
        assert result.name == "sqcli"

    def test_custom_path_not_found(self) -> None:
        result = resolve_sqcli_path(custom_path="/nonexistent/sqcli")
        assert result is None

    def test_no_custom_and_not_windows_returns_none(self) -> None:
        with patch("quantlab.tools.platform.get_platform_name", return_value="linux"):
            result = resolve_sqcli_path()
            assert result is None


class TestAppDirs:
    def test_data_dir_returns_path(self) -> None:
        path = get_app_data_dir()
        assert isinstance(path, Path)

    def test_config_dir_returns_path(self) -> None:
        path = get_app_config_dir()
        assert isinstance(path, Path)


class TestNormalizePath:
    def test_resolves_to_absolute(self) -> None:
        result = normalize_path(".")
        assert result.is_absolute()
