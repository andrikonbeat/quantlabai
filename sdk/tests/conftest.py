"""pytest configuration and shared fixtures.

Adds ``sdk/`` to ``sys.path`` so that ``from quantlab import ...``
works when running tests from the ``sdk/`` directory or project root.
"""

import sys
import zipfile
from pathlib import Path
from typing import Callable

import pytest

# Ensure sdk/ is on the path so imports work from the project root
SDK_ROOT = Path(__file__).resolve().parent.parent
if str(SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(SDK_ROOT))

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def make_cfx(dest_dir: str | Path, name: str = "config_mini.cfx") -> Path:
    """Build a minimal real ``.cfx`` ZIP from the committed config fixture.

    ``.cfx`` files are ZIP containers holding the builder config XML. This
    helper packages the committed ``config_mini.xml`` fixture (T-2.2, AD-9)
    into a real ZIP at ``dest_dir`` so evidence/verification tests get a
    realistic config artifact without a real SQX install. Importable
    directly (``from conftest import make_cfx``) and exposed as a pytest
    fixture of the same name.
    """
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    xml_path = FIXTURES_DIR / "config_mini.xml"
    if not xml_path.is_file():
        raise FileNotFoundError(f"missing config fixture: {xml_path}")
    cfx_path = dest / name
    with zipfile.ZipFile(cfx_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Config.xml", xml_path.read_text(encoding="utf-8"))
    return cfx_path


@pytest.fixture(name="make_cfx")
def _make_cfx_fixture() -> Callable[[str | Path, str], Path]:
    """Return the ``.cfx`` ZIP builder for evidence tests (T-2.2)."""
    return make_cfx