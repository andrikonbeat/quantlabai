"""KB re-verification decision module (kb-reverification, D3).

Pure, read-only decision layer for re-verifying the SQX Parameter KB against an
operator-supplied build artifact. It owns three things and nothing else: loading
evidence, deciding one entry's verdict, and refusing unknown version buckets.

The non-promotion contract is the whole point of this module:

* Only :attr:`Verdict.VERIFIED` may mutate the store. ``field_absent`` is terminal —
  the entry stays ``needs_review`` — and ``not_xml_backed`` is skipped forever, whatever
  its ``status`` string says.
* ``evidence_unreadable`` is a *run-level* outcome: :func:`load_evidence` raises
  :class:`EvidenceUnreadableError` before any entry is classified, so no verdict is ever
  computed from evidence that was not fully parsed.
* Verdicts come from the *structural shape* of ``xml_path``, never from ``status``
  (:func:`is_xml_anchored`). A documentation anchor is not XML-backed because of how it
  is written, not because of where the entry sits in its lifecycle.

This module imports no store and no CLI: ``KbStore.reverify_against_build`` (PR 3) is a
thin wrapper over these functions, and the ``sqx kb reverify`` command (PR 4) only
renders the report. That keeps every decision testable without a Knowledge Lake.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Sequence

# The root segment the walker drops when it roots at ``.//CrossChecks``.
_CROSSCHECKS_ROOT = "CrossChecks"
# Member preference inside a SQX artifact: the build, else the project config.
_BUILD_TASK1_MEMBER = "Build-Task1.xml"
_CONFIG_MEMBER = "config.xml"


class EvidenceUnreadableError(Exception):
    """Raised when evidence cannot be read as SQX ``CrossChecks`` XML.

    This is the run-level ``evidence_unreadable`` outcome (spec). Callers MUST write
    nothing and exit non-zero: because it is raised during loading, no entry verdict is
    ever computed against a half-parsed artifact.
    """

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(f"Unreadable evidence {path}: {reason}")
        self.path = path
        self.reason = reason


class UnknownVersionBucketError(ValueError):
    """Raised when re-verification targets a version bucket the lake does not hold."""

    def __init__(self, sqx_version: str, known: Sequence[str]) -> None:
        available = ", ".join(sorted(known)) or "none"
        super().__init__(
            f"Unknown SQX version bucket: {sqx_version} (available: {available})"
        )
        self.sqx_version = sqx_version


@dataclass(frozen=True)
class EvidenceXml:
    """Parsed SQX evidence: which member was used and its ``CrossChecks`` block."""

    path: Path
    member: str
    crosschecks: ET.Element


class Verdict(str, Enum):
    """The four-outcome verdict contract; every entry receives exactly one."""

    VERIFIED = "verified"
    FIELD_ABSENT = "field_absent"
    NOT_XML_BACKED = "not_xml_backed"
    EVIDENCE_UNREADABLE = "evidence_unreadable"

    @property
    def promotes(self) -> bool:
        """True only for ``VERIFIED`` — the sole outcome allowed to write."""
        return self is Verdict.VERIFIED


def is_xml_anchored(xml_path: str | None) -> bool:
    """True when ``xml_path`` is an XML anchor rather than a documentation anchor.

    The discriminator is structural and MUST NOT read ``status`` (spec, D5). A path is
    XML-anchored iff it is non-empty, carries no ``#`` fragment, does not end in ``.md``
    (case-insensitive), and its first segment is the ``CrossChecks`` root — the segment
    the walker drops once it has rooted at ``.//CrossChecks``.

    Args:
        xml_path: The entry's declared anchor, or ``None`` when it has none.

    Returns:
        True only for anchors that can be resolved against evidence XML.
    """
    if not xml_path or "#" in xml_path:
        return False
    if xml_path.lower().endswith(".md"):
        return False
    return xml_path.split("/")[0] == _CROSSCHECKS_ROOT


def _select_member(path: Path) -> tuple[str, bytes] | None:
    """Pick the member holding ``CrossChecks`` XML: Build-Task1.xml, else config.xml.

    A ZIP prefers the build member and falls back to the config member (spec: member
    preference). A path that is not a ZIP is returned verbatim so a bare XML file is
    accepted as evidence too.

    Returns:
        ``(member, raw_bytes)``, or ``None`` when a ZIP holds neither member.
    """
    if not zipfile.is_zipfile(path):
        return path.name, path.read_bytes()
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        for member in (_BUILD_TASK1_MEMBER, _CONFIG_MEMBER):
            if member in names:
                return member, archive.read(member)
    return None


def load_evidence(path: str | Path) -> EvidenceXml:
    """Load operator-supplied SQX evidence into its ``CrossChecks`` block.

    Evidence is always explicit — nothing here discovers artifacts on its own (spec).

    Args:
        path: Archive (``.cfx`` / ``.sqx-template``) or bare XML file to load.

    Returns:
        EvidenceXml carrying the member actually parsed and the ``CrossChecks`` element.

    Raises:
        EvidenceUnreadableError: when the path is missing, unreadable, holds neither
            CrossChecks member, or its XML does not parse. The run MUST then write
            nothing and exit non-zero.
    """
    target = Path(path)
    if not target.is_file():
        raise EvidenceUnreadableError(target, "file does not exist")

    try:
        selected = _select_member(target)
    except (OSError, zipfile.BadZipFile) as exc:
        raise EvidenceUnreadableError(target, f"cannot read archive: {exc}") from exc
    if selected is None:
        raise EvidenceUnreadableError(
            target,
            f"archive holds neither {_BUILD_TASK1_MEMBER} nor {_CONFIG_MEMBER}",
        )
    member, raw = selected

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise EvidenceUnreadableError(
            target, f"{member} is not valid XML: {exc}"
        ) from exc

    crosschecks = root.find(f".//{_CROSSCHECKS_ROOT}")
    if crosschecks is None:
        raise EvidenceUnreadableError(target, f"{member} has no <{_CROSSCHECKS_ROOT}>")
    return EvidenceXml(path=target, member=member, crosschecks=crosschecks)


def classify(
    xml_path: str | None,
    element_name: str | None,
    crosschecks: ET.Element,
) -> Verdict:
    """Decide one entry's verdict from its XML anchor against loaded evidence.

    Pure: no store access, no writes, no status lookup.

    Args:
        xml_path: The entry's ``xml_path`` anchor, or ``None`` when it has none.
        element_name: The element the entry claims to point at.
        crosschecks: The evidence's ``CrossChecks`` element.

    Returns:
        ``VERIFIED`` when the path root and every segment resolve and the resolved leaf
        is the element the entry names, ``FIELD_ABSENT`` when the block resolves but the
        named element is missing (terminal), or ``NOT_XML_BACKED`` for documentation
        anchors — which are never probed and never promoted.
        ``EVIDENCE_UNREADABLE`` is never returned here: :func:`load_evidence` raises
        before classification begins.
    """
    if xml_path is None or not is_xml_anchored(xml_path):
        return Verdict.NOT_XML_BACKED

    node = crosschecks
    for tag in xml_path.split("/")[1:]:
        found = node.find(tag)
        if found is None:
            return Verdict.FIELD_ABSENT
        node = found
    if element_name and node.tag != element_name:
        return Verdict.FIELD_ABSENT
    return Verdict.VERIFIED


@dataclass(frozen=True)
class EntryVerdict:
    """One catalog entry's verdict together with the identity a report prints."""

    tab: str
    name: str
    xml_path: str | None
    verdict: Verdict

    @property
    def promotes(self) -> bool:
        """True when this entry may be promoted (delegates to its verdict)."""
        return self.verdict.promotes

    @property
    def reason(self) -> str:
        """Why this entry drew its verdict, in the operator's terms."""
        if self.verdict is Verdict.VERIFIED:
            return f"{self.xml_path} resolves in the evidence CrossChecks block"
        if self.verdict is Verdict.FIELD_ABSENT:
            return f"{self.xml_path} does not resolve in the evidence CrossChecks block"
        if self.verdict is Verdict.EVIDENCE_UNREADABLE:
            return "evidence could not be read; no entry was probed"
        if self.xml_path is None:
            return "no xml_path declared, so the entry is not XML-backed"
        return f"{self.xml_path} is a documentation anchor, not an XML anchor"


@dataclass(frozen=True)
class ReverifyReport:
    """Run-level report: per-entry verdicts plus per-outcome counts (D7).

    The report is the pipeline's only surface — stdout prints ``counts``, and a caller
    promotes exactly the entries whose ``verdict`` promotes.

    ``evidence_ok`` carries the run-level ``evidence_unreadable`` outcome: when it is
    ``False`` nothing was classified or written, and ``unreadable_reason`` says why.
    ``counts`` still reports that outcome once, so the four-outcome contract stays whole.
    """

    artifact: str
    entries: tuple[EntryVerdict, ...] = ()
    evidence_ok: bool = True
    unreadable_reason: str = ""

    @classmethod
    def from_entries(
        cls, artifact: str, entries: Sequence[EntryVerdict]
    ) -> ReverifyReport:
        """Build a report from per-entry verdicts."""
        return cls(artifact=artifact, entries=tuple(entries))

    @classmethod
    def unreadable(cls, artifact: str, reason: str) -> ReverifyReport:
        """Build the run-level report for evidence that could not be read."""
        return cls(artifact=artifact, evidence_ok=False, unreadable_reason=reason)

    @property
    def counts(self) -> dict[str, int]:
        """Per-outcome counts (D7), always reporting all four outcomes."""
        counts = {
            outcome.value: sum(1 for e in self.entries if e.verdict is outcome)
            for outcome in Verdict
        }
        if not self.evidence_ok:
            counts[Verdict.EVIDENCE_UNREADABLE.value] = 1
        return counts

    @property
    def promotable(self) -> tuple[EntryVerdict, ...]:
        """The entries a caller may promote — ``VERIFIED`` only."""
        return tuple(entry for entry in self.entries if entry.promotes)


def require_known_bucket(sqx_version: str, known: Sequence[str]) -> str:
    """Return ``sqx_version`` when the lake holds that bucket, else refuse it.

    ``KbStore.list`` answers an unknown bucket with an empty list, which would make a
    mistyped bucket look like a clean run with nothing to re-verify. This guard turns
    that silent empty into an explicit refusal (spec).

    Args:
        sqx_version: The requested version bucket.
        known: Buckets the lake actually holds.

    Returns:
        The resolved bucket name, unchanged.

    Raises:
        UnknownVersionBucketError: when the bucket is not among ``known``.
    """
    if sqx_version not in known:
        raise UnknownVersionBucketError(sqx_version, known)
    return sqx_version


__all__ = [
    "EntryVerdict",
    "EvidenceUnreadableError",
    "EvidenceXml",
    "ReverifyReport",
    "UnknownVersionBucketError",
    "Verdict",
    "classify",
    "is_xml_anchored",
    "load_evidence",
    "require_known_bucket",
]
