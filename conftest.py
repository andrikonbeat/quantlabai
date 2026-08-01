"""Root pytest configuration — makes `sdk/` importable from the project root.

Lets `from quantlab import ...` resolve when running the canonical root
suite (`testpaths = tests sdk/tests`), independent of the working directory.
"""

import sys
from pathlib import Path

# Ensure sdk/ is on the path so imports work from the project root
SDK_ROOT = Path(__file__).resolve().parent / "sdk"
if str(SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(SDK_ROOT))
