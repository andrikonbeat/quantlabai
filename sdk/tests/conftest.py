"""pytest configuration and shared fixtures.

Adds ``sdk/`` to ``sys.path`` so that ``from quantlab import ...``
works when running tests from the ``sdk/`` directory or project root.
"""

import sys
from pathlib import Path

# Ensure sdk/ is on the path so imports work from the project root
SDK_ROOT = Path(__file__).resolve().parent.parent
if str(SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(SDK_ROOT))
