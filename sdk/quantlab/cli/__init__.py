"""QuantLab CLI — Phase 4 SQX Automation entry point."""

# CLI entry points are available via quantlab.cli.cli_entry / quantlab.cli.main
# Import at runtime to avoid circular import warning when run as module

from quantlab.cli.runner import CliResult, CliRunner, Executor, MockExecutor, RealExecutor

from quantlab.cli.daemon import DaemonContext, run_with_daemon

__all__ = [
    # Runner (legacy CLI wrapper)
    "CliResult",
    "CliRunner",
    "Executor",
    "MockExecutor",
    "RealExecutor",
    # Daemon Context (Phase 4+5)
    "DaemonContext",
    "run_with_daemon",
]


def cli_entry() -> int:
    """Entry point for console scripts — calls main() with sys.argv."""
    from quantlab.cli.main import main
    import sys
    return main(sys.argv[1:])
