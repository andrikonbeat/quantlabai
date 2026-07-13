"""CFX archive writer — XML-to-ZIP packaging for StrategyQuant X.

Wraps the generated CFX XML into a ZIP archive with ``.cfx`` extension,
or writes raw XML during dry-run mode.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from pydantic import BaseModel, Field

from quantlab.dsl.models import ResearchConfig
from quantlab.translate.translator import generate_cfx_xml

#: Default output subdirectory used by both normal and dry-run modes.
DEFAULT_OUTPUT_DIR = "_output"


class CfxResult(BaseModel):
    """Structured result from a CFX archive operation.

    Attributes:
        xml_content: The generated XML string.
        path:       Filesystem path to the written artifact (ZIP or raw XML).
    """

    xml_content: str | None = None
    path: Path | None = None


def _sanitize_filename(campaign: str) -> str:
    """Replace non-alphanumeric characters with underscores."""
    sanitized = re.sub(r"[^\w\-.]", "_", campaign)
    # Collapse multiple underscores
    sanitized = re.sub(r"_+", "_", sanitized)
    # Strip leading/trailing underscores
    return sanitized.strip("_")


def _dry_run_output_dir(output_dir: str | Path) -> Path:
    """Derive the dry-run output directory from a normal output dir.

    If *output_dir* is a custom path (not the default), dry-run files are
    written to a sibling ``_output/`` directory so they do not pollute the
    real output location.  When the default output dir is used, dry-run
    writes to the default ``_output/``.
    """
    out = Path(output_dir)
    if out.resolve() == Path(DEFAULT_OUTPUT_DIR).resolve():
        # Using the default — stay in _output/
        return out
    # Custom output_dir — write to a sibling _output/
    return out.parent / DEFAULT_OUTPUT_DIR


class CfxArchive:
    """Factory for creating CFX archive files from ``ResearchConfig`` models.

    Usage::

        result = CfxArchive.from_model(config, dry_run=True)
        print(result.xml_content)
    """

    @staticmethod
    def from_model(
        config: ResearchConfig,
        output_dir: str | None = None,
        dry_run: bool = False,
    ) -> CfxResult:
        """Translate a ``ResearchConfig`` and write the result to disk.

        Args:
            config:     A validated ``ResearchConfig`` instance.
            output_dir: Directory for the output file(s).
                        Defaults to ``_output/`` in the current working directory.
            dry_run:    When True, writes raw XML to ``_output/`` instead of
                        creating a ZIP archive.

        Returns:
            A ``CfxResult`` containing the XML content and the output path.
        """
        # Resolve output directory
        out_dir = Path(output_dir) if output_dir is not None else Path(DEFAULT_OUTPUT_DIR)

        # Generate XML content
        xml_str = generate_cfx_xml(config)

        # Build a safe filename from the campaign name
        safe_name = _sanitize_filename(config.campaign) or "campaign"

        if dry_run:
            # Write raw XML to _output/ (or sibling _output/)
            dst_dir = _dry_run_output_dir(out_dir)
            dst_dir.mkdir(parents=True, exist_ok=True)
            dst_path = dst_dir / f"{safe_name}.cfx.xml"
            dst_path.write_text(xml_str, encoding="utf-8")
            return CfxResult(xml_content=xml_str, path=dst_path)

        # Normal mode: create a ZIP archive with .cfx extension
        dst_dir = out_dir
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst_path = (dst_dir / safe_name).with_suffix(".cfx")

        with zipfile.ZipFile(dst_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"{safe_name}.cfx", xml_str)

        return CfxResult(xml_content=xml_str, path=dst_path)
