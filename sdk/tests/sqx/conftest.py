"""conftest.py for SQX tests — exports process manager fixtures."""

import sys
from pathlib import Path

# Add the tests directory to path for local imports
TESTS_DIR = Path(__file__).parent
sys.path.insert(0, str(TESTS_DIR))

from test_process_manager_fixtures import sqx_instance, sqx_session

# Export fixtures for all test modules in this package
__all__ = ["sqx_instance", "sqx_session"]