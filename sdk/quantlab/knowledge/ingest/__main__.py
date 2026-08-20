"""CLI entry point for the SQX/JForex knowledge ingestor.

Usage:
    python -m quantlab.knowledge.ingest ingest \\
        --source sqx-install \\
        --version 144.2953 \\
        --install-path /path/to/SQX_144_2953_linux_20260601
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from quantlab.knowledge.ingest import DocIndexer

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def cmd_ingest(args: argparse.Namespace) -> int:
    indexer = DocIndexer(
        knowledge_root=args.knowledge_root,
        install_path=args.install_path,
    )
    stats = indexer.ingest(version=args.version, source=args.source)
    logger.info(
        "Ingest complete: %d written, %d skipped, %d sources",
        stats.docs_written,
        stats.docs_skipped,
        stats.sources_processed,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m quantlab.knowledge.ingest",
        description="Ingest official SQX/JForex documentation into the Knowledge Lake.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Run ingestion for a specific SQX version")
    ingest.add_argument("--source", default="sqx-install", choices=["sqx-install"], help="Source selector")
    ingest.add_argument("--version", required=True, help="SQX version bucket (e.g. 144.2953)")
    ingest.add_argument("--install-path", required=True, type=Path, help="Path to the licensed SQX install")
    ingest.add_argument("--knowledge-root", default="knowledge", type=Path, help="Knowledge Lake root")
    ingest.set_defaults(func=cmd_ingest)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
