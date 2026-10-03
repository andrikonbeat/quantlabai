"""CFX archive reader — opens .cfx ZIP archives and returns typed CfxArchive.

Supports both single-task config archives (<Task> root) and multi-file
projects (<Project> root). Validates ZIP paths against directory traversal
attacks and enforces a supported schema version range.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree

from quantlab.cfx.errors import (
    CfxCorruptError,
    CfxNotFoundError,
    CfxParseError,
    VersionError,
)
from quantlab.cfx.models import (
    DATA_RANGE_PART_TAGS,
    AdvancedRankingCondition,
    AdvancedRankingsConfig,
    AtmConfig,
    AutomaticPortfolioBuilderConfig,
    BlockConfig,
    BuildTask,
    CfxArchive,
    CfxConfig,
    CfxProject,
    ColumnValue,
    CrossChecksConfig,
    DataBankConfig,
    DatabanksConfig,
    DataRangeParts,
    OptimizationConfig,
    OptimizationParametersConfig,
    PortfolioSettingsConfig,
    RankingsConfig,
    RawXmlSection,
    ResourceConfig,
    RetesterDataConfig,
    SettingsSection,
    WalkForwardConfig,
)

# Minimum schema version accepted — based on SQX 144.2953 real-world files.
_MIN_VERSION = "130.0"
_MAX_VERSION = "146.0"

# Elements that should be parsed as simple key-value settings sections.
_SETTINGS_SECTIONS = frozenset({
    "Options",
    "RiskMoneyManagement",
    "WhatToBuild",
    "Data",
    "PartsToImprove",
    "Notes",
})

# Elements that are parsed as typed complex sections.
_COMPLEX_SECTIONS = frozenset({
    "Blocks",
    "ATMs",
    "DataBanks",
    "Resources",
    # Phase 4 complex sections
    "AutomaticPortfolioBuilder",
    "PortfolioSettings",
    "Optimization",
    "OptimizationParameters",
    "WalkForward",
    "Databanks",
    "Rankings",
    "CrossChecks",
    "RetesterData",
})

# ``<Data>`` children that no lane owns, so they are excluded from the flat lane
# and parked verbatim in ``DataRangeParts.raw_xml`` instead. Real SQX writes
# ``<Setups>`` and ``<OutOfSample>`` here and they have no typed field.
_DATA_PASSTHROUGH_TAGS: frozenset[str] = frozenset({"Setups", "OutOfSample"})

# The tags a sibling ``<Data>`` lane claims: the typed sub-ranges plus the
# passthrough subtrees above.
_DATA_OWNED_TAGS: frozenset[str] = DATA_RANGE_PART_TAGS | _DATA_PASSTHROUGH_TAGS


class CfxReader:
    """Reads .cfx archives and returns typed CfxArchive models."""

    @staticmethod
    def read(path: str | Path) -> CfxArchive:
        """Open a .cfx ZIP archive and parse it into a CfxArchive model.

        Args:
            path: Filesystem path to the .cfx file.

        Returns:
            A CfxArchive populated with the parsed contents.

        Raises:
            CfxNotFoundError: The file does not exist.
            CfxCorruptError: The file is not a valid ZIP or contains
                invalid XML.
            CfxParseError: The XML structure does not match the CFX
                schema.
            VersionError: The schema version is not supported.
        """
        path = Path(path)

        if not path.exists():
            raise CfxNotFoundError(f"CFX file not found: {path}")

        try:
            zf = zipfile.ZipFile(path, "r")
        except zipfile.BadZipFile as exc:
            raise CfxCorruptError(f"Not a valid CFX archive: {path}") from exc

        # ── ZIP traversal defense ────────────────────────────────
        _validate_zip_paths(zf)

        # ── Determine type & parse ───────────────────────────────
        names = zf.namelist()
        task_files = [n for n in names if n.endswith(".xml")]

        if not task_files:
            raise CfxParseError("CFX archive contains no XML files")

        # Read config.xml (single-task archives have it inline; projects
        # always have it).
        raw_config = _read_entry(zf, "config.xml", task_files)

        root = _parse_xml(raw_config, filename="config.xml")
        _validate_schema_version(root)

        if root.tag == "Task":
            return CfxReader._parse_config(zf, root, path)
        elif root.tag == "Project":
            return CfxReader._parse_project(zf, root, task_files, path)
        else:
            raise CfxParseError(
                f"Unexpected root element <{root.tag}> in config.xml"
            )

    # ── Phase 4: Portfolio / Optimizer / Retester CFX Readers ─────────

    @staticmethod
    def read_portfolio_cfx(path: str | Path) -> CfxArchive:
        """Read a Portfolio Master CFX archive.

        Args:
            path: Path to .cfx file.

        Returns:
            CfxArchive with Portfolio Master task.
        """
        return CfxReader.read(path)

    @staticmethod
    def read_optimizer_cfx(path: str | Path) -> CfxArchive:
        """Read an Optimizer CFX archive.

        Args:
            path: Path to .cfx file.

        Returns:
            CfxArchive with Optimizer task.
        """
        return CfxReader.read(path)

    @staticmethod
    def read_retester_cfx(path: str | Path) -> CfxArchive:
        """Read a Retester CFX archive.

        Args:
            path: Path to .cfx file.

        Returns:
            CfxArchive with Retester task.
        """
        return CfxReader.read(path)

    # ── Single-file Config ───────────────────────────────────────

    @staticmethod
    def _parse_config(
        zf: zipfile.ZipFile,
        root: ElementTree.Element,
        path: Path,
    ) -> CfxArchive:
        version = root.get("version", "0")
        task_xml_file = root.get("taskXMLFile", "")

        # Settings may be inline inside the <Task> element or in a
        # separate XML file referenced by taskXMLFile.
        settings_el = root.find("Settings")
        if settings_el is not None:
            task = _parse_settings_element_tree(settings_el)
        elif task_xml_file:
            task = _parse_settings_xml(zf, task_xml_file)
        else:
            task = BuildTask()

        config = CfxConfig(task=task, schema_version=version)
        return CfxArchive(config=config, task_files={task_xml_file: task} if task_xml_file else {})

    # ── Multi-file Project ───────────────────────────────────────

    @staticmethod
    def _parse_project(
        zf: zipfile.ZipFile,
        root: ElementTree.Element,
        task_files: list[str],
        path: Path,
    ) -> CfxArchive:
        version = root.get("version", "0")
        name = root.get("name", "")

        tasks_el = root.find("Tasks")
        task_mapping: dict[str, BuildTask] = {}

        if tasks_el is not None:
            for task_el in tasks_el.findall("Task"):
                xml_file = task_el.get("taskXMLFile", "")
                if xml_file and xml_file in task_files:
                    task = _parse_settings_xml(zf, xml_file)
                    task_mapping[xml_file] = task

        metadata: dict[str, str] = {}
        metadata_el = root.find("Metadata")
        if metadata_el is not None:
            for entry in metadata_el.findall("Entry"):
                key = entry.get("key")
                if key is not None:
                    metadata[key] = entry.get("value", "")

        project = CfxProject(
            name=name,
            tasks=task_mapping,
            schema_version=version,
            metadata=metadata or None,
        )
        return CfxArchive(config=project, task_files=task_mapping)


# ── Helpers ──────────────────────────────────────────────────────────


def _validate_zip_paths(zf: zipfile.ZipFile) -> None:
    """Reject ZIP entries containing path traversal or absolute paths."""
    for name in zf.namelist():
        # Normalise to POSIX separators for consistent checking.
        normalised = name.replace("\\", "/")
        if normalised.startswith("/") or normalised.startswith(".."):
            raise CfxCorruptError(
                f"Path traversal detected in archive entry: {name!r}"
            )
        # Deeply nested ".." also rejected.
        parts = normalised.split("/")
        for part in parts:
            if part == "..":
                raise CfxCorruptError(
                    f"Path traversal detected in archive entry: {name!r}"
                )


def _read_entry(
    zf: zipfile.ZipFile, name: str, available: list[str]
) -> str:
    """Read an XML entry, raising CfxCorruptError on failure."""
    if name not in available:
        raise CfxParseError(f"Required entry {name!r} not found in archive")
    try:
        return zf.read(name).decode("utf-8")
    except (KeyError, UnicodeDecodeError) as exc:
        raise CfxCorruptError(f"Failed to read {name!r}: {exc}") from exc


def _parse_xml(raw: str, *, filename: str = "") -> ElementTree.Element:
    """Parse raw XML, raising CfxCorruptError on parse failure."""
    try:
        return ElementTree.fromstring(raw)
    except ElementTree.ParseError as exc:
        ctx = f" in {filename}" if filename else ""
        raise CfxCorruptError(f"Invalid XML{ctx}: {exc}") from exc


def _validate_schema_version(root: ElementTree.Element) -> None:
    """Raise VersionError if the schema version is outside the supported range."""
    version = root.get("version")
    if version is None and root.tag == "Task":
        version = root.get("version", "0")
    if version is None:
        raise CfxParseError("Missing version attribute on root element")

    # Simple tuple-based comparison on dotted version strings.
    try:
        parts = [int(x) for x in version.split(".")]
        min_parts = [int(x) for x in _MIN_VERSION.split(".")]
        max_parts = [int(x) for x in _MAX_VERSION.split(".")]
    except ValueError as exc:
        raise CfxParseError(f"Invalid version format: {version!r}") from exc

    min_ver = tuple(parts[:2])
    min_allowed = tuple(min_parts[:2])
    max_allowed = tuple(max_parts[:2])

    if min_ver < min_allowed or min_ver > max_allowed:
        raise VersionError(
            f"Unsupported CFX schema version {version} "
            f"(supported: {_MIN_VERSION} – {_MAX_VERSION})"
        )


def _parse_settings_xml(
    zf: zipfile.ZipFile, filename: str
) -> BuildTask:
    """Parse a task-XML file (e.g. Build-Task1.xml) into a BuildTask model."""
    names = zf.namelist()
    raw = _read_entry(zf, filename, names)
    root = _parse_xml(raw, filename=filename)

    if root.tag != "Settings":
        raise CfxParseError(
            f"Expected <Settings> root in {filename!r}, got <{root.tag}>"
        )

    return _parse_settings_element_tree(root)


def _parse_settings_element_tree(root: ElementTree.Element) -> BuildTask:
    """Parse a <Settings> ElementTree element into a BuildTask model."""
    sections: dict[str, SettingsSection | None] = {}
    complex_sections: dict[
        str,
        BlockConfig
        | AtmConfig
        | DataBankConfig
        | ResourceConfig
        | AutomaticPortfolioBuilderConfig
        | PortfolioSettingsConfig
        | OptimizationConfig
        | OptimizationParametersConfig
        | WalkForwardConfig
        | DatabanksConfig
        | RankingsConfig
        | CrossChecksConfig
        | RetesterDataConfig
        | None,
    ] = {}
    unknown: list[RawXmlSection] = []
    data_el: ElementTree.Element | None = None
    rankings_el: ElementTree.Element | None = None

    for child in root:
        tag = child.tag
        if tag in _SETTINGS_SECTIONS:
            if tag == "Data":
                # <Data> feeds two lanes: the flat key-value section and the
                # typed sub-range model. `_DATA_OWNED_TAGS` keeps them disjoint
                # — admitting the whole subtree would copy every typed
                # sub-range into the flat lane as well, and the writer merges
                # both lanes back, so the section would grow on every cycle.
                sections[tag] = _parse_settings_element(
                    child, exclude_tags=_DATA_OWNED_TAGS
                )
                data_el = child
            else:
                sections[tag] = _parse_settings_element(child)
        elif tag in _COMPLEX_SECTIONS:
            raw_xml = ElementTree.tostring(child, encoding="unicode")
            complex_sections[tag] = _make_complex_section(tag, raw_xml)
            if tag == "Rankings":
                rankings_el = child
        else:
            raw_xml = ElementTree.tostring(child, encoding="unicode")
            unknown.append(RawXmlSection(name=tag, raw_xml=raw_xml))

    return BuildTask(
        options=sections.get("Options"),
        what_to_build=sections.get("WhatToBuild"),
        risk_money_mgmt=sections.get("RiskMoneyManagement"),
        data=sections.get("Data"),
        rankings=sections.get("Rankings"),
        parts_to_improve=sections.get("PartsToImprove"),
        cross_checks=sections.get("CrossChecks"),
        notes=sections.get("Notes"),
        blocks=complex_sections.get("Blocks"),
        atms=complex_sections.get("ATMs"),
        databanks=complex_sections.get("DataBanks"),
        resources=complex_sections.get("Resources"),
        automatic_portfolio_builder=complex_sections.get("AutomaticPortfolioBuilder"),
        portfolio_settings=complex_sections.get("PortfolioSettings"),
        optimization=complex_sections.get("Optimization"),
        optimization_parameters=complex_sections.get("OptimizationParameters"),
        walk_forward=complex_sections.get("WalkForward"),
        databanks_section=complex_sections.get("Databanks"),
        rankings_section=complex_sections.get("Rankings"),
        cross_checks_section=complex_sections.get("CrossChecks"),
        retester_data=complex_sections.get("RetesterData"),
        data_range_parts=_parse_data_range_parts(data_el),
        advanced_rankings=_parse_advanced_rankings(
            rankings_el, complex_sections.get("Rankings")
        ),
        unknown_sections=unknown,
    )


def _is_flat_lane_child(
    child: ElementTree.Element, exclude: frozenset[str]
) -> bool:
    """True when ``child`` belongs to a flat section's key-value lane.

    Both halves of the test matter: a child must be a **leaf**, so a nested
    subtree such as ``<Setups><Setup dateFrom=.../></Setups>`` cannot be
    rewritten as key-value pairs, and its tag must be unclaimed by a sibling
    lane in ``exclude``, so the typed sub-ranges and the passthrough subtrees
    of ``<Data>`` stay out of it.

    This is the *single* flat-lane predicate. ``_parse_settings_element`` calls
    it to **admit** a child and ``_parse_data_range_parts`` calls it to
    **strip** one; the two must agree, or a section is captured by both lanes,
    the writer merges both copies back, and the section grows on every
    read/write cycle. Re-implementing the rule at either call site reintroduces
    exactly that duplication, so both call this function instead.
    """
    return len(child) == 0 and child.tag not in exclude


def _parse_settings_element(
    el: ElementTree.Element, *, exclude_tags: frozenset[str] = frozenset()
) -> SettingsSection:
    """Convert a flat section element to a key-value SettingsSection.

    The section's *children* are flattened with an empty prefix, so no key ever
    carries the section tag: ``<WhatToBuild><BuildType value="genetic"/>`` yields
    ``BuildType@value``, never ``WhatToBuild.BuildType@value``. The writer
    inverts this by grouping ``Tag@attr`` keys back into one element per tag.

    A leaf ``<Setting key="K" value="V"/>`` becomes **one** entry
    ``settings[K] = V`` rather than two entries keyed by the literal strings
    ``Setting@key`` and ``Setting@value``; the pairing survives in the dict and
    the writer's grouping re-emits it. Any other admitted leaf reuses
    ``_flatten_element`` unchanged and becomes ``Tag@attr``.

    ``exclude_tags`` names the tags a sibling lane owns — see
    ``_is_flat_lane_child``. ``<Data>`` passes ``_DATA_OWNED_TAGS`` so its flat
    and typed lanes stay disjoint; every other flat section passes the empty set.
    """
    settings: dict[str, str] = {}
    for child in el:
        if not _is_flat_lane_child(child, exclude_tags):
            continue
        if child.tag == "Setting" and "key" in child.attrib:
            settings[child.get("key", "")] = child.get("value", "")
            continue
        _flatten_element(child, settings, prefix="")
    return SettingsSection(name=el.tag, settings=settings)


def _flatten_element(
    el: ElementTree.Element,
    acc: dict[str, str],
    prefix: str,
) -> None:
    """Recursively flatten an XML element tree into key-value pairs."""
    tag = el.tag
    full_key = f"{prefix}.{tag}" if prefix else tag

    # Include attributes.
    for attr_key, attr_val in el.attrib.items():
        acc[f"{full_key}@{attr_key}"] = attr_val

    # Include text content for leaf elements.
    text = (el.text or "").strip()
    if text and len(el) == 0:
        acc[full_key] = text

    # Recurse into children.
    for child in el:
        _flatten_element(child, acc, full_key)


def _parse_advanced_rankings(
    el: ElementTree.Element | None,
    section: RankingsConfig | None,
) -> AdvancedRankingsConfig | None:
    """Build the typed advanced-conditions lane from a ``<Rankings>`` element.

    Returns ``None`` when the element is absent or carries no ``<Conditions>``
    block, so the pre-existing simple ``<Rankings>`` (flat ``Criterion*``
    settings only) is reported as having no advanced lane rather than as an
    empty one.

    ``section`` must be the :class:`RankingsConfig` built from the very same
    ``el``; its ``raw_xml`` is passed through verbatim, not re-rendered. The
    real SQX ``<Condition>`` also holds ``<Left-Side>``/``<Comparator>``/
    ``<Right-Side>`` content that has no typed field here, and re-rendering
    would drop it.
    """
    if el is None or section is None:
        return None
    conditions_el = el.find("Conditions")
    if conditions_el is None:
        return None

    conditions = [
        _parse_advanced_condition(cond_el)
        for cond_el in conditions_el.findall("Condition")
    ]
    if not conditions:
        return None
    return AdvancedRankingsConfig(conditions=conditions, raw_xml=section.raw_xml)


def _parse_advanced_condition(cond_el: ElementTree.Element) -> AdvancedRankingCondition:
    """Parse one ``<Condition>`` element, in either SQX dialect."""
    use_raw = cond_el.get("use", "true").strip().lower()
    columns = [_parse_column_value(cv) for cv in _column_value_elements(cond_el)]
    return AdvancedRankingCondition(
        use=use_raw in ("true", "1"),
        result_type=cond_el.get("resultType", "main"),
        sample_type=cond_el.get("sampleType", "127"),
        direction=cond_el.get("direction", "0"),
        pct_ratio=cond_el.get("pctRatio", "0"),
        confidence_level=cond_el.get("confidenceLevel", "50"),
        market=cond_el.get("market", "1"),
        pl_type=cond_el.get("plType", "10"),
        subresult=cond_el.get("subresult", "30"),
        class_=cond_el.get("class"),
        name=cond_el.get("name"),
        column_values=columns,
    )


def _column_value_elements(cond_el: ElementTree.Element) -> list[ElementTree.Element]:
    """Return the ``<Column-Value>`` descendants of a ``<Condition>``.

    Real SQX wraps the filter in ``<Left-Side valueType="column">``; QuantLab's
    own ``build_conditions_xml`` writes it as a direct child. Both dialects
    occur in the wild, so both are accepted — reading only one of them makes
    the reader report zero conditions for a perfectly valid CFX.
    """
    direct = cond_el.findall("Column-Value")
    if direct:
        return direct
    left_side = cond_el.find("Left-Side")
    if left_side is None:
        return []
    return left_side.findall("Column-Value")


def _parse_column_value(cv_el: ElementTree.Element) -> ColumnValue:
    """Parse one ``<Column-Value>`` element into its typed model."""
    return ColumnValue(
        column=cv_el.get("column", ""),
        column_type=cv_el.get("columnType", "0"),
        format=cv_el.get("format", ""),
        result_type=cv_el.get("resultType", "main"),
        direction=cv_el.get("direction", "0"),
        sample_type=cv_el.get("sampleType", "127"),
        pl_type=cv_el.get("plType", "10"),
        confidence_level=cv_el.get("confidenceLevel", "50"),
        market=cv_el.get("market", "1"),
        subresult=cv_el.get("subresult", "30"),
        pct_ratio=cv_el.get("pctRatio", "0"),
        class_=cv_el.get("class", ""),
        name=cv_el.get("name"),
    )


def _parse_data_range_parts(el: ElementTree.Element | None) -> DataRangeParts | None:
    """Build the typed ``<Data>`` sub-range lane.

    Delegates to :meth:`DataRangeParts.from_xml`, which parks every unmodelled
    sibling in ``raw_xml`` — the real SQX ``<Data>`` holds ``<Setups>`` and
    ``<OutOfSample>``, which have no typed field but must not be lost.

    Flat-lane children are stripped first, using the *same*
    ``_is_flat_lane_child`` predicate that admitted them: parking a second copy
    in ``raw_xml`` would make the writer emit each of them twice.
    """
    if el is None:
        return None
    payload = ElementTree.fromstring(ElementTree.tostring(el, encoding="unicode"))
    for child in [c for c in payload if _is_flat_lane_child(c, _DATA_OWNED_TAGS)]:
        payload.remove(child)
    return DataRangeParts.from_xml(ElementTree.tostring(payload, encoding="unicode"))


def _make_complex_section(
    tag: str, raw_xml: str
) -> (
    BlockConfig
    | AtmConfig
    | DataBankConfig
    | ResourceConfig
    | AutomaticPortfolioBuilderConfig
    | PortfolioSettingsConfig
    | OptimizationConfig
    | OptimizationParametersConfig
    | WalkForwardConfig
    | DatabanksConfig
    | RankingsConfig
    | CrossChecksConfig
    | RetesterDataConfig
):
    """Create the appropriate typed config model for a complex section."""
    mapping = {
        "Blocks": BlockConfig,
        "ATMs": AtmConfig,
        "DataBanks": DataBankConfig,
        "Resources": ResourceConfig,
        "AutomaticPortfolioBuilder": AutomaticPortfolioBuilderConfig,
        "PortfolioSettings": PortfolioSettingsConfig,
        "Optimization": OptimizationConfig,
        "OptimizationParameters": OptimizationParametersConfig,
        "WalkForward": WalkForwardConfig,
        "Databanks": DatabanksConfig,
        "Rankings": RankingsConfig,
        "CrossChecks": CrossChecksConfig,
        "RetesterData": RetesterDataConfig,
    }
    cls = mapping.get(tag)
    if cls is None:
        raise CfxParseError(f"Unknown complex section: {tag}")
    if cls is CrossChecksConfig:
        # CrossChecks is a dual-dialect typed model: parse into dialect +
        # typed sections so consumers read fields instead of raw XML.
        return CrossChecksConfig.from_xml(raw_xml)
    return cls(raw_xml=raw_xml)
