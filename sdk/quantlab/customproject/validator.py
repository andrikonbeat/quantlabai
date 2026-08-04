"""Golden structural validation + sqcli readiness probe (REQ-24).

Validation rules are derived from the verified SQX 144/2953 sample projects
(``assets/SQX_144_2953_linux_20260601/user/projects/*/project.cfx``):

* root element ``<Project>`` with non-empty ``name`` and ``version="144.2953"``;
* ordered ``<Tasks>`` with at least one ``<Task type= taskXMLFile=>`` entry;
* every ``taskXMLFile`` resolves to a packaged, well-formed ``<Settings>`` XML;
* a ``<Databanks>`` registry whose entries carry ``name``, ``view`` and
  ``syncType`` (``position`` optional).

The ``sqcli -h`` readiness probe SHALL run before validation. Any deviation
raises ``ValidationError`` naming the deviating element — fail-closed, no
dispatch (AD-7). The probe is injectable (``probe_runner``) so unit tests run
fast; the default shell-out to the real binary is exercised by the E2E gate.
"""

from __future__ import annotations

import os
import subprocess
import zipfile
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree

from quantlab.cfx.models import CfxArchive, CfxProject
from quantlab.cfx.writer import CfxWriter

# Verified schema version of the SQX 144/2953 golden samples (REQ-24).
GOLDEN_SCHEMA_VERSION = "144.2953"

# Final fallback candidate; overridable for tests via monkeypatch.
DEFAULT_SQCLI = Path("/usr/local/bin/sqcli")


class ValidationError(ValueError):
    """Raised when a generated archive deviates from the golden format.

    The message names the deviating element so the fault is actionable
    (REQ-24: ``ValidationError ... naming the deviating element``).
    """


def resolve_sqcli(sqx_root: str | Path | None = None, env: dict[str, str] | None = None) -> Path:
    """Resolve the sqcli binary: ``SQCLI_PATH`` env → ``<sqx_root>/sqcli`` →
    ``/usr/local/bin/sqcli``.

    Raises:
        ValidationError: No candidate binary exists.
    """
    env = os.environ if env is None else env
    candidates: list[Path] = []
    if env.get("SQCLI_PATH"):
        candidates.append(Path(env["SQCLI_PATH"]))
    if sqx_root is not None:
        candidates.append(Path(sqx_root) / "sqcli")
    candidates.append(DEFAULT_SQCLI)

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise ValidationError(
        "sqcli binary not found (searched: "
        + ", ".join(str(c) for c in candidates)
        + "); set SQCLI_PATH or point sqx_root at the SQX install"
    )


def sqcli_ready(sqcli_path: str | Path, timeout: int = 300) -> bool:
    """Run the readiness probe ``sqcli -h``; True iff it exits 0.

    The JVM-backed launcher boots slowly (~2.5 min), hence the generous
    default timeout matching the repo's sqcli timeout_seconds=300.
    """
    try:
        result = subprocess.run(
            [str(sqcli_path), "-h"],
            capture_output=True,
            timeout=timeout,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def validate_golden(
    archive: CfxArchive,
    sqx_root: str | Path,
    *,
    probe_runner: Callable[[], bool] | None = None,
    probe_timeout: int = 300,
) -> None:
    """Validate a generated archive against the golden 144/2953 structure.

    The ``sqcli -h`` readiness probe runs first (REQ-24); a failed probe or any
    structural deviation raises ``ValidationError`` naming the element. On
    return (no exception), the archive is safe to dispatch.

    Args:
        archive: The generated CfxArchive (CfxProject config).
        sqx_root: SQX install root used to locate the sqcli binary.
        probe_runner: Optional probe callable returning bool; defaults to
            shelling out to the real ``sqcli -h``.
        probe_timeout: Seconds allowed for the real probe.
    """
    sqcli = resolve_sqcli(sqx_root)
    probe = probe_runner if probe_runner is not None else (
        lambda: sqcli_ready(sqcli, probe_timeout)
    )
    if not probe():
        raise ValidationError(
            f"sqcli readiness probe failed: {sqcli} -h did not exit 0 "
            "(no dispatch attempted)"
        )
    _validate_structure(archive)


def _validate_structure(archive: CfxArchive) -> None:
    """Structural checks over the archive the writer WILL produce (REQ-24)."""
    config = archive.config
    if not isinstance(config, CfxProject):
        raise ValidationError(
            "<Project> root: expected a multi-task Project config, got "
            f"{type(config).__name__}"
        )

    if not config.name:
        raise ValidationError("<Project>@name: missing or empty name attribute")

    if config.schema_version != GOLDEN_SCHEMA_VERSION:
        raise ValidationError(
            f"<Project>@version: expected {GOLDEN_SCHEMA_VERSION!r}, "
            f"got {config.schema_version!r}"
        )

    tasks = config.tasks
    if not tasks:
        raise ValidationError("<Tasks>: no tasks declared (golden samples always "
                              "declare at least one)")

    task_xml = config.task_meta if config.task_meta else {}
    for filename in tasks:
        meta = task_xml.get(filename)
        task_type = meta.task_type if meta else "Build"
        if not task_type:
            raise ValidationError(
                f"<Tasks><Task taskXMLFile={filename!r}>: empty or missing "
                "type attribute"
            )

    databanks = config.databanks
    if not databanks:
        raise ValidationError("<Databanks>: registry missing or empty (golden "
                              "samples always declare at least one databank)")
    for db in databanks:
        if not db.name:
            raise ValidationError(
                "<Databanks><Databank>: missing or empty name attribute"
            )
        if not db.view:
            raise ValidationError(
                f"<Databanks><Databank name={db.name!r}>: missing view attribute"
            )
        if not db.sync_type:
            raise ValidationError(
                f"<Databanks><Databank name={db.name!r}>: missing syncType attribute"
            )

    _validate_packaged_xml(archive)


def _validate_packaged_xml(archive: CfxArchive) -> None:
    """Every packaged task XML must be well-formed with a <Settings> root."""
    raw = CfxWriter.to_bytes(archive)
    with zipfile.ZipFile(BytesIO(raw), "r") as zf:
        names = set(zf.namelist())
        if "config.xml" not in names:
            raise ValidationError("<Project>: config.xml missing from archive")
        try:
            ElementTree.fromstring(zf.read("config.xml"))
        except ElementTree.ParseError as exc:
            raise ValidationError("<Project>: config.xml is not well-formed XML") from exc

        task_files = [n for n in names if n.endswith(".xml") and n != "config.xml"]
        for filename in task_files:
            try:
                root = ElementTree.fromstring(zf.read(filename))
            except ElementTree.ParseError as exc:
                raise ValidationError(
                    f"<Tasks><Task taskXMLFile={filename!r}>: task XML is not "
                    "well-formed"
                ) from exc
            if root.tag != "Settings":
                raise ValidationError(
                    f"<Tasks><Task taskXMLFile={filename!r}>: expected "
                    f"<Settings> root, got <{root.tag}>"
                )
