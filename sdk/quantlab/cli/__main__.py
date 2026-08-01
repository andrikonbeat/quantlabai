"""Module entry point — `python -m quantlab.cli` matches the console script."""

import sys

from quantlab.cli.main import main

if __name__ == "__main__":
    sys.exit(main())
