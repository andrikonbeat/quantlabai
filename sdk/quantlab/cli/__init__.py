"""QuantLab CLI — Phase 4 SQX Automation entry point."""

# CLI entry points are available via quantlab.cli.cli_entry / quantlab.cli.main
# Import at runtime to avoid circular import warning when run as module

from quantlab.cli.runner import CliResult, CliRunner, Executor, MockExecutor, RealExecutor

__all__ = [
    # Runner (legacy CLI wrapper)
    "CliResult",
    "CliRunner",
    "Executor",
    "MockExecutor",
    "RealExecutor",
]


def cli_entry() -> int:
    """Entry point for console scripts — calls main() with sys.argv."""
    from quantlab.cli.main import main
    import sys
    return main(sys.argv[1:])
