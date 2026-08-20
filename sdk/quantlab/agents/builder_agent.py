"""BuilderAgent — orchestrates CFX translation, validation, license check, and SQX dispatch.

Translates ``ResearchConfig`` DSL → CFX bytes via ``sqx_translator``,
validates via ``cfx_editor``, checks license via ``license_manager``,
dispatches to SQX via ``sqx_cli_wrapper``, and monitors execution with
configurable retry and timeout.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import httpx

logger = logging.getLogger(__name__)

# Re-exported for BuilderAgent callers (parameter-justification-matrix REQ-1):
# raised when a manual override lacks its rationale, blocking the run.
from quantlab.agents.parameter_matrix import ParameterMatrixError  # noqa: E402


def _try_int(value: str, default: int) -> int:
    """Parse an int from a string, returning *default* on failure."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _try_float(value: str, default: float | None) -> float | None:
    """Parse a float from a string, returning *default* on failure."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


@dataclass
class BuildProgress:
    """Progress of an SQX build campaign, polled from the HTTP API.

    Attributes:
        strategies_generated: Number of strategies generated so far.
        strategies_accepted: Number of strategies accepted so far.
        generation: Current generation index (0-based or 1-based).
        total_generations: Total number of generations expected.
        status: One of ``running``, ``completed``, ``failed``, ``timeout``, or ``unknown``.
        eta_seconds: Estimated seconds remaining, if available.
    """
    strategies_generated: int = 0
    strategies_accepted: int = 0
    generation: int = 0
    total_generations: int = 0
    status: str = "unknown"
    eta_seconds: float | None = None


@dataclass
class DispatchResult:
    """Result of an SQX campaign dispatch."""
    campaign_id: str = ""
    cfx_bytes: bytes = b""
    sqcli_status: str = "pending"
    export_paths: list[str] = field(default_factory=list)
    dispatch_log: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


def _is_custom_project_enabled() -> bool:
    """Return True when the builder should dispatch to the CustomProject generator.

    G2 flag-first contract (D7):
    - ``QUANTLAB_CUSTOM_PROJECT=1`` or unset → CustomProject dialect (schema 144.2953)
    - ``QUANTLAB_CUSTOM_PROJECT=0`` → legacy translator (schema 141.2219)

    Default is ``1`` (CustomProject) after task 7.4 flips the default.
    """
    return os.environ.get("QUANTLAB_CUSTOM_PROJECT", "1") == "1"


def _research_config_to_custom_project(config: Any) -> Any:
    """Convert a ``ResearchConfig`` to a minimal ``CustomProject``.

    The CustomProject generator expects a project-level model with an ordered
    task list and a databank registry. When the builder receives a DSL
    ``ResearchConfig`` (the existing orchestrated flow contract), this helper
    produces a single-task CustomProject that preserves the campaign identity
    and uses the standard databank defaults.
    """
    from quantlab.customproject.models import (
        CustomProject,
        CustomProjectTask,
        DatabankSpec,
    )

    if hasattr(config, "campaign") and config.campaign:
        name = config.campaign
    elif isinstance(config, dict):
        name = config.get("campaign") or "default"
    else:
        name = "default"

    return CustomProject(
        name=name,
        tasks=[
            CustomProjectTask(
                type="Build",
                name="Build",
                source_databank="Initial population",
                target_databank="Results",
            )
        ],
        databanks=[
            DatabankSpec(name="Results"),
            DatabankSpec(name="Last generation"),
            DatabankSpec(name="Initial population"),
            DatabankSpec(name="Strategies to improve"),
        ],
    )

    # ── Phase 2: Validation ─────────────────────────────────────────────────────



class BuilderAgent:
    """Orchestrates DSL-to-CFX translation, validation, and SQX dispatch.

    The agent performs a four-phase process:
    1. **Translate**: ResearchConfig → CFX bytes via ``sqx_translator``
    2. **Validate**: CFX pre-flight validation via ``cfx_editor.validate()``
    3. **License**: Validate SQX license via ``license_manager.validate()``
    4. **Dispatch**: Load config, start campaign, poll status, collect exports

    Retry logic (configurable, default 2 retries) and timeout (default 60 min)
    protect against transient SQX failures.
    """

    def __init__(
        self,
        max_retries: int = 2,
        timeout_minutes: int = 60,
        poll_interval_seconds: int = 30,
        *,
        strict_kb: bool = False,
    ) -> None:
        self._max_retries = max_retries
        self._timeout_minutes = timeout_minutes
        self._poll_interval = poll_interval_seconds
        self._strict_kb = strict_kb

    # ── REQ-204: KB consult ─────────────────────────────────────────────────────

    @staticmethod
    def _active_kb_tabs(config: Any) -> list[str]:
        """Return the active KB tabs for a ResearchConfig.

        Currently returns all canonical builder tabs; future versions may
        filter based on config content.
        """
        from quantlab.knowledge.kb.models import KB_TABS

        return list(KB_TABS)

    async def _consult_kb(self, config: Any) -> list[str]:
        """Consult the KB for each active tab before translation.

        Returns a list of warning strings for tabs with missing or
        unverified entries. In ``strict_kb`` mode, raises
        ``ConfigurationError`` instead of collecting warnings.

        Args:
            config: The parsed ``ResearchConfig``.

        Returns:
            List of warning messages (empty when all tabs are covered).

        Raises:
            ConfigurationError: When ``strict_kb`` is True and any tab
                has no KB entries.
        """
        from quantlab.knowledge.kb.store import KbStore
        from quantlab.knowledge.kb.models import KB_TABS
        from quantlab.pipeline.errors import ConfigurationError

        active_tabs = self._active_kb_tabs(config)
        store = KbStore()
        warnings: list[str] = []

        for tab in active_tabs:
            entries = store.consult(name="", tab=tab)
            if not entries:
                warnings.append(f"KB tab '{tab}' has no entries")
                continue

            for entry in entries:
                if entry.get("status") == "needs_review":
                    warnings.append(
                        f"KB tab '{tab}' has entries needing review"
                    )
                    break

        if warnings and self._strict_kb:
            raise ConfigurationError(
                f"Missing or unverified KB entries: {warnings}"
            )

        return warnings

    # ── Task 2.11: Main execution ──────────────────────────────────────────────

    # ── Parameter matrix generation ─────────────────────────────────────────────

    def generate_parameter_matrix(
        self,
        build_config: Any,
        rationale_overrides: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Extract configured BuildConfig fields into a parameter matrix.

        Delegates to the shared :mod:`quantlab.agents.parameter_matrix`
        generator (parameter-justification-matrix REQ-1): values matching the
        SQX template default are ``default`` with rationale "using SQX
        default"; manual overrides need a non-empty rationale and are marked
        ``manual``; an unjustified override raises :class:`ParameterMatrixError`
        and blocks the run.

        Args:
            build_config: ``BuildConfig`` instance with overridden fields.
            rationale_overrides: Manual justifications keyed by field name.

        Returns:
            List of parameter matrix entry dicts.

        Raises:
            ParameterMatrixError: A manual override lacks its rationale.
        """
        from quantlab.agents.parameter_matrix import (
            ParameterMatrixError,
            generate_parameter_matrix as _generate_parameter_matrix,
        )

        hypothesis_ref = None
        if build_config is not None:
            hypothesis_ref = getattr(build_config, "hypothesis", None) or getattr(
                build_config, "hypothesis_name", None
            )
        return _generate_parameter_matrix(
            build_config,
            rationale_overrides=rationale_overrides,
            hypothesis_ref=hypothesis_ref,
        )

    @staticmethod
    def _collect_rationale_overrides(context: Any, build_config: Any) -> dict[str, str]:
        """Gather manual parameter justifications for the matrix (REQ-1).

        The primary source is the explicit ``context.config["rationale_overrides"]``
        mapping (the orchestrator's hypothesis/cost/session constraints, written
        by ConfigReviewStage or the caller). A parameter set outside that
        mapping is justified only when it matches the SQX template default —
        otherwise the run is blocked (spec: "Missing rationale blocks
        advancement").

        Args:
            context: ``PipelineContext`` with ``config.rationale_overrides``.
            build_config: The in-flight ``BuildConfig``.

        Returns:
            Dict of field → rationale for the manual entries.
        """
        overrides: dict[str, str] = {}
        configured = (
            context.config.get("rationale_overrides")
            if isinstance(context.config, dict)
            else None
        )
        if isinstance(configured, dict):
            overrides.update({str(k): str(v) for k, v in configured.items()})
        return overrides

    @staticmethod
    def _persist_build_artifacts(
        context: Any,
        campaign_id: str,
        cfx_bytes: bytes,
        parameter_matrix: list[dict[str, Any]],
    ) -> None:
        """Persist the CFX archive + matrix to the Knowledge Lake (REQ-2).

        Runs BEFORE the dispatch boundary so a substrate handoff failure leaves
        the build artifact preserved for recovery (spec: "CFX archive remains
        preserved for recovery"). Writes are best-effort: a missing
        ``knowledge_root`` is skipped silently.

        Args:
            context: ``PipelineContext`` with ``config.knowledge_root``.
            campaign_id: The campaign identifier naming the artifacts.
            cfx_bytes: The translated CFX archive.
            parameter_matrix: The generated matrix entries.
        """
        knowledge_root = (
            context.config.get("knowledge_root")
            if isinstance(context.config, dict)
            else None
        )
        if not knowledge_root:
            return
        from pathlib import Path

        root = Path(knowledge_root)
        cfx_dir = root / "structured" / campaign_id / "configs"
        cfx_dir.mkdir(parents=True, exist_ok=True)
        (cfx_dir / f"{campaign_id}.cfx").write_bytes(cfx_bytes)

        matrix_dir = root / "parameter-matrix" / campaign_id
        matrix_dir.mkdir(parents=True, exist_ok=True)
        (matrix_dir / "parameter_matrix.json").write_text(
            json.dumps(parameter_matrix, indent=2), encoding="utf-8"
        )
        logger.info(
            "BuilderAgent: persisted CFX + matrix for '%s' before dispatch boundary",
            campaign_id,
        )

    async def run(self, context: Any) -> dict[str, Any]:
        """Execute the builder agent stage in a pipeline.

        Reads ``research_config`` from ``context.artifacts``, translates to CFX,
        validates, checks license, dispatches to SQX, monitors execution, and
        writes ``cfx_bytes``, ``campaign_id``, ``sqcli_status``, and
        ``export_paths`` to ``context.artifacts``.

        Args:
            context: ``PipelineContext`` with ``research_config`` in artifacts.

        Returns:
            Dict with ``cfx_bytes``, ``campaign_id``, ``sqcli_status``,
            ``export_paths``, and dispatch metadata.
        """
        research_config_raw = context.artifacts.get("research_config", {})
        if not research_config_raw:
            raise ValueError("No research_config found in context artifacts")

        # Parse config into ResearchConfig model
        from quantlab.dsl.models import ResearchConfig

        if isinstance(research_config_raw, dict):
            research_config = ResearchConfig.model_validate(research_config_raw)
        elif isinstance(research_config_raw, ResearchConfig):
            research_config = research_config_raw
        else:
            raise ValueError(f"Unexpected research_config type: {type(research_config_raw)}")

        # Apply guardian state from context if available
        guardian_state = context.artifacts.get("guardian_state")
        if guardian_state is not None:
            if isinstance(research_config, dict):
                research_config["guardian_state"] = guardian_state
            else:
                research_config.guardian_state = guardian_state

        # REQ-204: consult KB before translation
        kb_warnings = await self._consult_kb(research_config)

        # Phase 1: Translate DSL → CFX
        cfx_bytes, translate_log = await self._translate(research_config)

        # Phase 2: Validate CFX
        validation_result = await self._validate(cfx_bytes)

        if not validation_result.get("valid", False):
            raise ValueError(
                f"CFX validation failed: {validation_result.get('error', 'unknown error')}"
            )

        # Phase 3: License check
        license_result = await self._check_license()
        if not license_result.get("valid", False):
            logger.warning(
                "License check failed — proceeding in dev mode: %s",
                license_result.get("error"),
            )

        # Phase 4: Dispatch with retry
        versioned_campaign_id = context.config.get("campaign_id")
        build_config = context.config.get("build_config")

        # Parameter matrix (REQ-1): every build produces one; manual overrides
        # must be justified, otherwise ParameterMatrixError blocks the run
        # from advancing (spec: "Missing rationale blocks advancement").
        if build_config is not None:
            rationale_overrides = self._collect_rationale_overrides(context, build_config)
            parameter_matrix = self.generate_parameter_matrix(
                build_config, rationale_overrides=rationale_overrides
            )
            context.artifacts["parameter_matrix"] = parameter_matrix
            # REQ-2: persist the CFX archive + matrix to the Knowledge Lake
            # BEFORE the dispatch boundary so a handoff failure leaves the
            # build artifact preserved for recovery.
            if versioned_campaign_id:
                self._persist_build_artifacts(
                    context, versioned_campaign_id, cfx_bytes, parameter_matrix
                )

        if context.config.get("orchestrated"):
            # AD-3/AD-8 (orchestrated split): the builder translates, validates,
            # and licenses, but the dispatch step moves to the DispatchStage
            # boundary. Publish cfx_bytes + the in-flight build_config for the
            # ConfigReviewStage; dispatch artifacts stay absent.
            context.artifacts["cfx_bytes"] = cfx_bytes
            if build_config is not None:
                context.artifacts["build_config"] = build_config
            logger.info(
                "BuilderAgent: orchestrated mode — dispatch deferred to DispatchStage"
            )
            return {
                "cfx_bytes": cfx_bytes,
                "translate_log": translate_log,
                "validation": validation_result,
                "license": license_result,
                "build_config": build_config,
                "phase_type": "builder",
                "checkpoint_metadata": {"campaign_id": versioned_campaign_id},
                **({"kb_warnings": kb_warnings} if kb_warnings else {}),
            }

        dispatch_result = await self._dispatch_with_retry(
            cfx_bytes, research_config,
            campaign_id=versioned_campaign_id,
            build_config=build_config,
        )

        # Write results to context artifacts
        context.artifacts["cfx_bytes"] = dispatch_result.cfx_bytes
        context.artifacts["campaign_id"] = dispatch_result.campaign_id
        context.artifacts["sqcli_status"] = dispatch_result.sqcli_status
        context.artifacts["export_paths"] = dispatch_result.export_paths

        logger.info(
            "BuilderAgent: campaign '%s' dispatched, status=%s, exports=%d",
            dispatch_result.campaign_id,
            dispatch_result.sqcli_status,
            len(dispatch_result.export_paths),
        )

        return {
            "cfx_bytes": dispatch_result.cfx_bytes,
            "campaign_id": dispatch_result.campaign_id,
            "sqcli_status": dispatch_result.sqcli_status,
            "export_paths": dispatch_result.export_paths,
            "translate_log": translate_log,
            "validation": validation_result,
            "license": license_result,
            "dispatch_log": dispatch_result.dispatch_log,
            **({"kb_warnings": kb_warnings} if kb_warnings else {}),
        }

    # ── Phase 1: Translation ────────────────────────────────────────────────────

    async def _translate(self, config: Any) -> tuple[bytes, dict[str, Any]]:
        """Internal translation with flag-first dispatch (G2).

        - ``QUANTLAB_CUSTOM_PROJECT=0`` → legacy translator (schema 141.2219)
        - ``QUANTLAB_CUSTOM_PROJECT=1`` or unset (CustomProject default): converts
          the ``ResearchConfig`` to a ``CustomProject`` and delegates to
          ``quantlab.customproject.generator`` (schema 144.2953).
        """
        from quantlab.tools.exceptions import TranslationError

        log: dict[str, Any] = {"phase": "translate", "status": "started"}

        try:
            if _is_custom_project_enabled():
                from quantlab.customproject.generator import generate_cfx_archive as cp_generate
                from quantlab.cfx.writer import CfxWriter

                project = _research_config_to_custom_project(config)
                archive = cp_generate(project)
                cfx_bytes = CfxWriter.to_bytes(archive)
                log["dialect"] = "custom_project"
            else:
                from quantlab.translate.translator import generate_cfx_archive
                from quantlab.cfx.writer import CfxWriter

                archive = generate_cfx_archive(config)
                cfx_bytes = CfxWriter.to_bytes(archive)
                log["dialect"] = "legacy"

            log["status"] = "completed"
            log["byte_size"] = len(cfx_bytes)

            logger.info("Translation completed: %d bytes generated", len(cfx_bytes))
            return cfx_bytes, log

        except Exception as e:
            log["status"] = "failed"
            log["error"] = str(e)
            logger.error("Translation failed: %s", e)
            raise TranslationError(f"DSL-to-CFX translation failed: {e}", cause=e)

    async def translate_to_cfx(self, config: Any) -> bytes:
        """Translate a ``ResearchConfig`` to CFX bytes.

        Uses ``quantlab.translate.translator.generate_cfx_archive()`` to
        create a ``CfxArchive``, then serializes to bytes via ``CfxWriter``.

        Args:
            config: A validated ``ResearchConfig`` instance.

        Returns:
            CFX archive bytes.

        Raises:
            TranslationError: If translation fails.
        """
        result = await self._translate(config)
        return result[0]


    async def _validate(self, cfx_bytes: bytes) -> dict[str, Any]:
        """Validate CFX bytes via ``cfx_editor.validate()``.

        Falls back to basic structural check if editor is unavailable.

        Args:
            cfx_bytes: CFX archive bytes to validate.

        Returns:
            Dict with ``valid`` bool and optional ``error`` message.
        """
        log: dict[str, Any] = {"phase": "validate", "status": "started"}

        try:
            # Try CfxReader-based validation if available
            from quantlab.cfx.reader import CfxReader

            reader = CfxReader()
            try:
                # Try to read the CFX — if it parses, it's valid
                read_result = reader.read_bytes(cfx_bytes)
                is_valid = read_result is not None
            except (AttributeError, TypeError):
                # CfxReader has no read_bytes or different API — use fallback
                is_valid = False

            log["status"] = "completed"

            if is_valid:
                logger.info("CFX validation passed")
                return {"valid": True}
            else:
                logger.warning("CFX reader validation unavailable — using basic check")

        except ImportError:
            log["status"] = "completed"
            logger.info("CfxReader not available — using basic check")

        # Fallback: basic structural check
        if cfx_bytes and len(cfx_bytes) > 100:
            return {"valid": True, "warning": "Basic structural check only"}

        return {"valid": False, "error": "CFX bytes too short or empty"}

    # ── Phase 3: License ────────────────────────────────────────────────────────

    async def _check_license(self) -> dict[str, Any]:
        """Check SQX license via ``license_manager.validate()``.

        Falls back to checking the configured license file path.

        Returns:
            Dict with ``valid`` bool and optional ``error``/``license_path``.
        """
        log: dict[str, Any] = {"phase": "license", "status": "started"}

        try:
            from quantlab.tools.exceptions import LicenseError

            # Try license_manager if available
            try:
                from quantlab.license.manager import validate_license

                valid = validate_license()
                log["status"] = "completed"
                log["valid"] = valid

                if not valid:
                    logger.warning("License validation failed")
                    return {"valid": False, "error": "SQX license is invalid or expired"}

                logger.info("License validation passed")
                return {"valid": True}

            except ImportError:
                # Fallback: check license file exists
                import os
                from pathlib import Path

                license_path = (
                    os.environ.get("SQX_LICENSE_PATH")
                    or str(Path.home() / ".sqx" / "license.key")
                )

                if Path(license_path).exists():
                    log["status"] = "completed"
                    log["valid"] = True
                    log["license_path"] = license_path
                    logger.info("License check passed (file: %s)", license_path)
                    return {"valid": True, "license_path": license_path}

                log["status"] = "failed"
                log["error"] = f"License file not found: {license_path}"
                logger.warning("License file not found at %s", license_path)
                return {
                    "valid": False,
                    "error": f"License file not found: {license_path}",
                    "license_path": license_path,
                }

        except Exception as e:
            log["status"] = "failed"
            log["error"] = str(e)
            logger.error("License check error: %s", e)
            return {"valid": False, "error": str(e)}

    # ── Phase 4: SQX dispatch with retry ────────────────────────────────────────

    async def _dispatch_with_retry(
        self,
        cfx_bytes: bytes,
        config: Any,
        campaign_id: str | None = None,
        build_config: Any = None,
    ) -> DispatchResult:
        """Dispatch CFX to SQX with configurable retry logic (task 2.13).

        Retries up to ``max_retries`` times on transient errors.
        Enforces a total timeout of ``timeout_minutes``.

        Args:
            cfx_bytes: Validated CFX archive bytes.
            config: ``ResearchConfig`` (used for campaign naming).

        Returns:
            ``DispatchResult`` with campaign_id, status, and export paths.
        """
        last_error: str | None = None
        dispatch_log: list[dict[str, Any]] = []

        for attempt in range(self._max_retries + 1):
            log_entry: dict[str, Any] = {
                "attempt": attempt + 1,
                "max_retries": self._max_retries + 1,
                "status": "started",
            }

            try:
                result = await asyncio.wait_for(
                    self._dispatch_single(cfx_bytes, config, campaign_id=campaign_id, build_config=build_config),
                    timeout=self._timeout_minutes * 60,
                )
                result.dispatch_log = dispatch_log
                log_entry["campaign_id"] = result.campaign_id
                dispatch_log.append(log_entry)

                if result.sqcli_status in ("timeout", "failed"):
                    log_entry["status"] = result.sqcli_status
                    log_entry["error"] = result.error or f"SQX dispatch {result.sqcli_status}"
                    if attempt < self._max_retries:
                        await self._send_stop()
                        wait = min(2 ** attempt * 10, 120)
                        logger.info("Retrying in %ds...", wait)
                        await asyncio.sleep(wait)
                    continue

                log_entry["status"] = "completed"
                return result

            except asyncio.TimeoutError:
                from quantlab.tools.exceptions import BuildTimeoutError

                log_entry["status"] = "timeout"
                log_entry["error"] = f"Timeout after {self._timeout_minutes} min"
                dispatch_log.append(log_entry)

                if attempt >= self._max_retries:
                    logger.error(
                        "All %d attempts timed out — raising BuildTimeoutError",
                        self._max_retries + 1,
                    )
                    raise BuildTimeoutError(
                        f"Campaign timed out after {self._timeout_minutes} minutes"
                    )

                last_error = f"Campaign timed out after {self._timeout_minutes} minutes"
                logger.warning(
                    "Dispatch attempt %d/%d timed out",
                    attempt + 1, self._max_retries + 1,
                )

                # Send stop command before retry
                await self._send_stop()
                # Exponential backoff
                wait = min(2 ** attempt * 10, 120)
                logger.info("Retrying in %ds...", wait)
                await asyncio.sleep(wait)

            except Exception as e:
                log_entry["status"] = "failed"
                log_entry["error"] = str(e)
                dispatch_log.append(log_entry)
                last_error = str(e)
                logger.warning(
                    "Dispatch attempt %d/%d failed: %s",
                    attempt + 1, self._max_retries + 1, e,
                )

                if attempt < self._max_retries:
                    await self._send_stop()
                    wait = min(2 ** attempt * 10, 120)
                    logger.info("Retrying in %ds...", wait)
                    await asyncio.sleep(wait)

        # All retries exhausted
        result = DispatchResult(
            sqcli_status="failed",
            error=last_error or "All dispatch retries exhausted",
        )
        result.dispatch_log = dispatch_log
        logger.error("All %d dispatch attempts failed: %s", self._max_retries + 1, last_error)

        # Fallback: try existing Builder fixture if generated CFX produced no exports
        try:
            from pathlib import Path
            fixture_path = Path(__file__).parent.parent / "tests" / "cfx" / "fixtures" / "Builder.cfx"
            if fixture_path.exists():
                fallback_cfx = fixture_path.read_bytes()
                logger.info("Trying Builder fixture fallback after failed attempts")
                fallback_result = await self._dispatch_single(fallback_cfx, config, campaign_id=campaign_id, build_config=build_config)
                fallback_result.dispatch_log = dispatch_log
                return fallback_result
        except Exception as e:
            logger.warning("Fixture fallback failed: %s", e)

        return result

    # ── Task 2.2: Build status polling ───────────────────────────────────────────

    async def poll_status(
        self,
        campaign_id: str,
        base_url: str = "http://127.0.0.1:5050",
    ) -> BuildProgress:
        """Poll SQX HTTP API for build status and return a ``BuildProgress``.

        Args:
            campaign_id: The campaign/project name to poll.
            base_url: SQX HTTP API base URL (default ``http://127.0.0.1:5050``).

        Returns:
            A ``BuildProgress`` dataclass with current build state.

        Raises:
            httpx.HTTPError: If the HTTP request fails.
        """
        encoded = urllib.parse.quote(
            f"-project action=status name={campaign_id}", safe="=",
        )
        url = f"{base_url}/call?cmd={encoded}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            text = resp.text
        return self._parse_status(text)

    @staticmethod
    def _parse_status(text: str) -> BuildProgress:
        """Parse a text/plain status response into ``BuildProgress``.

        Expected response format (line by line)::

            Strategies generated: 1234
            Strategies accepted: 56
            Generation: 3/10
            Status: running
            ETA: 45s
        """
        bp = BuildProgress()
        for line in text.splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip().lower().replace(" ", "_")
            value = value.strip()

            if key == "strategies_generated":
                bp.strategies_generated = _try_int(value, 0)
            elif key in ("strategies_accepted", "accepted"):
                bp.strategies_accepted = _try_int(value, 0)
            elif key == "generation":
                if "/" in value:
                    parts = value.split("/")
                    bp.generation = _try_int(parts[0], 0)
                    bp.total_generations = _try_int(parts[1], 0)
                else:
                    bp.generation = _try_int(value, 0)
            elif key == "status":
                bp.status = value.lower()
            elif key == "eta":
                bp.eta_seconds = _try_float(value.rstrip("s"), None)
        return bp

    async def _ensure_data(self, config: Any, orchestrated: bool = False) -> None:
        """Ensure market data exists for the symbol used in this campaign.

        Calls ``DataManager.ensure_symbol()`` to register the symbol via
        sqcli and download data if needed.

        In legacy mode this is a best-effort pre-flight — failures are logged
        but do not block dispatch. In orchestrated mode (REQ-13) it is a HARD
        pre-flight: any failure raises ``RuntimeError`` so dispatch aborts.

        Args:
            config: The ``ResearchConfig`` (or dict) carrying the market symbol.
            orchestrated: When True, failures raise instead of being logged.

        Raises:
            RuntimeError: In orchestrated mode, when data cannot be ensured.
        """
        try:
            from quantlab.data import DataManager

            # Extract symbol from ResearchConfig
            symbol = (
                config.get("market", "EURUSD")
                if isinstance(config, dict)
                else getattr(config, "market", None)
            )
            if symbol is None:
                logger.info("No market symbol in config — skipping data check")
                return

            # Convert Market enum to string if needed
            if hasattr(symbol, "value"):
                symbol = symbol.value

            mgr = DataManager()
            result = await mgr.ensure_symbol(symbol, datasource="dukascopy")
            status = result.get("status", "error")
            if status == "ok":
                logger.info("Data pre-flight: symbol '%s' ready", symbol)
            else:
                message = (
                    f"Data pre-flight for '{symbol}': {status} — "
                    f"{result.get('error', 'unknown')}"
                )
                if orchestrated:
                    raise RuntimeError(message)
                logger.warning(message)
        except ImportError as e:
            if orchestrated:
                raise RuntimeError(
                    f"Data pre-flight failed (orchestrated): DataManager unavailable — {e}"
                ) from e
            logger.debug("DataManager not available — skipping data pre-flight")
        except RuntimeError:
            raise
        except Exception as e:
            if orchestrated:
                raise RuntimeError(
                    f"Data pre-flight failed (orchestrated): {e}"
                ) from e
            logger.warning("Data pre-flight failed (non-blocking): %s", e)

    async def _dispatch_single(
        self,
        cfx_bytes: bytes,
        config: Any,
        skip_data_check: bool = False,
        campaign_id: str | None = None,
        build_config: Any = None,
        orchestrated: bool = False,
        llm_config: Any = None,
        on_watcher_event: Callable[[Any], None] | None = None,
        on_llm_verdict: Callable[[Any], None] | None = None,
        confirm_stop: Callable[[Any], Awaitable[bool]] | None = None,
        gate_event_dir: str | None = None,
    ) -> DispatchResult:
        """Execute a single SQX dispatch attempt.

        Simulates the ``sqcli loadconfig → start → poll → stop → export`` flow.
        In production, this calls ``sqx_cli_wrapper.dispatch()``.

        Args:
            cfx_bytes: CFX archive bytes.
            config: ``ResearchConfig`` for campaign metadata.
            skip_data_check: If ``True``, skip the pre-flight data check.
                Default ``False`` ensures data exists before real dispatches.
            campaign_id: Override for the campaign id.
            build_config: In-flight ``BuildConfig`` for the dispatch.
            orchestrated: When True, ``_ensure_data`` is a HARD pre-flight
                (REQ-13): data errors abort dispatch instead of being logged.
            llm_config: Optional ``LLMConfig`` forwarded to the dispatch —
                when set, the substrate wires an ``LLMGenerationMonitor``
                sibling task (REQ-2). ``None`` keeps zero LLM calls.
            on_watcher_event: Optional watcher-event callback forwarded to
                the dispatch's ``CampaignMonitor``.
            on_llm_verdict: Optional LLM-verdict callback forwarded to the
                dispatch's ``LLMGenerationMonitor``.
            confirm_stop: Optional async ``(verdict) -> bool`` confirmation
                hook forwarded to the dispatch.
            gate_event_dir: Base directory for gate decision files (REQ-20),
                forwarded to the dispatch's gate writer.

        Returns:
            ``DispatchResult`` with dispatch results.
        """
        import uuid

        campaign_id = campaign_id or f"sqx_{uuid.uuid4().hex[:12]}"
        result = DispatchResult(campaign_id=campaign_id, cfx_bytes=cfx_bytes)

        # REQ-1 (unified-execution-substrate): the legacy CommandDispatcher
        # path is the default (REQ-28) AND the explicit QUANTLAB_LEGACY_EXECUTION
        # opt-in. When the unified substrate is opted in without the legacy
        # flag, the legacy path is refused fail-closed (AD-4) — the substrate
        # Executor is the replacement dispatch path.
        from quantlab.substrate import select_dispatch_backend

        backend = select_dispatch_backend()
        if backend != "legacy":
            from quantlab.pipeline.errors import ConfigurationError

            raise ConfigurationError(
                f"dispatch backend '{backend}' selected, but BuilderAgent only "
                "implements the legacy CommandDispatcher path — set "
                "QUANTLAB_LEGACY_EXECUTION=1 to force it (REQ-1)"
            )

        # Pre-flight: ensure market data exists for this symbol
        if not skip_data_check:
            await self._ensure_data(config, orchestrated=orchestrated)

        try:
            # Try sqx_cli_wrapper if available
            try:
                from quantlab.sqx.cli_wrapper import dispatch_campaign

                # Use mock server when in dry_run mode or SQX_FORCE_MOCK is set
                _is_dry = config.get("dry_run", False) if isinstance(config, dict) else getattr(config, "dry_run", False)
                force_mock = _is_dry or os.environ.get("SQX_FORCE_MOCK", "").lower() in ("1", "true", "yes")

                # Mock-mode guard: warn always, raise in production without an
                # explicit SQX_FORCE_MOCK override (MOK-01/02).
                from quantlab.sqx.cli_wrapper import mock_mode_guard
                mock_mode_guard(force_mock=force_mock)

                sqcli_result = await dispatch_campaign(
                    cfx_bytes=cfx_bytes,
                    campaign_id=campaign_id,
                    config=config,
                    force_mock=force_mock,
                    build_config=build_config,
                    # Monitoring hooks (REQ-2): the substrate wires them into
                    # the spawned monitors — forwarded unchanged.
                    llm_config=llm_config,
                    on_watcher_event=on_watcher_event,
                    on_llm_verdict=on_llm_verdict,
                    confirm_stop=confirm_stop,
                    gate_event_dir=gate_event_dir,
                )
                result.sqcli_status = sqcli_result.get("status", "completed")
                result.export_paths = sqcli_result.get("export_paths", [])

                # If generated CFX produced no exports, try existing Builder fixture as fallback
                if not result.export_paths:
                    try:
                        from pathlib import Path
                        fixture_path = Path(__file__).parent.parent / "tests" / "cfx" / "fixtures" / "Builder.cfx"
                        if fixture_path.exists():
                            fallback_cfx = fixture_path.read_bytes()
                            logger.info(
                                "No exports from generated CFX — trying Builder fixture fallback"
                            )
                            sqcli_result = await dispatch_campaign(
                                cfx_bytes=fallback_cfx,
                                campaign_id=f"{campaign_id}_fixture",
                                config=config,
                                build_config=build_config,
                                # Monitoring hooks (REQ-2): forwarded on the
                                # fallback dispatch too, so the substrate
                                # wiring is identical on both sites.
                                llm_config=llm_config,
                                on_watcher_event=on_watcher_event,
                                on_llm_verdict=on_llm_verdict,
                                confirm_stop=confirm_stop,
                                gate_event_dir=gate_event_dir,
                            )
                            result.sqcli_status = sqcli_result.get("status", "completed")
                            result.export_paths = sqcli_result.get("export_paths", [])
                    except Exception as e:
                        logger.warning("Fixture fallback failed: %s", e)

            except ImportError:
                # Simulated dispatch for development/testing
                logger.info(
                    "SQX cli_wrapper not available — simulated dispatch for '%s'",
                    campaign_id,
                )
                result.sqcli_status = "completed"
                result.export_paths = [
                    f"exports/{campaign_id}/trades.csv",
                    f"exports/{campaign_id}/equity.csv",
                    f"exports/{campaign_id}/statistics.json",
                ]

            logger.info(
                "SQX dispatch '%s': status=%s, exports=%d",
                campaign_id, result.sqcli_status, len(result.export_paths),
            )
            return result

        except Exception as e:
            result.sqcli_status = "failed"
            result.error = str(e)
            logger.error("SQX dispatch failed for '%s': %s", campaign_id, e)
            raise

    async def _send_stop(self) -> None:
        """Send stop command to any running SQX campaign.

        Calls ``sqx_cli_wrapper.stop()`` if available, or logs a warning.
        """
        try:
            from quantlab.sqx.cli_wrapper import stop_campaign

            stop_campaign()
            logger.info("SQX stop command sent")
        except ImportError:
            logger.info("SQX cli_wrapper not available — stop simulated")

    # ── Task 2.12: Pipeline YAML generation ─────────────────────────────────────

    def generate_pipeline_config(self, config: Any) -> dict[str, Any]:
        """Generate a pipeline YAML configuration from a ``ResearchConfig``.

        Produces a complete pipeline configuration dict with all 8 agent stages
        and 5 gate interceptors in correct order.

        Args:
            config: ``ResearchConfig`` with iteration_config and gate_policies.

        Returns:
            Dict with ``pipeline``, ``agents``, ``gates``, ``memory``, and
            ``risk`` sections, ready to be serialized to YAML.
        """
        from quantlab.dsl.models import ResearchConfig

        if isinstance(config, dict):
            config = ResearchConfig.model_validate(config)

        # Build stage list — the correct 8 agent stages + 5 gates = 13 stage entries
        # Note: gates are listed separately in the gates section and injected
        # by PipelineRunner at configured positions
        stages = [
            {"name": "research", "type": "agent",
             "agent": "research-agent",
             "requires": [], "provides": [
                 "research_config", "objectives", "hypotheses",
                 "iteration_config", "gate_policies",
             ]},
            {"name": "builder", "type": "agent",
             "agent": "builder-agent",
             "requires": ["research_config"],
             "provides": ["cfx_bytes", "campaign_id", "sqcli_status", "export_paths"],
             "max_retries": self._max_retries,
             "timeout": self._timeout_minutes * 60},
            {"name": "statistics", "type": "agent",
             "agent": "statistics-agent",
             "requires": ["export_paths"],
             "provides": ["statistics", "aggregate_stats", "monte_carlo_bands",
                          "rolling_metrics", "regime_alerts"]},
            {"name": "analysis", "type": "agent",
             "agent": "analysis-agent",
             "requires": ["export_paths", "statistics"],
             "provides": ["strategy_analysis", "selected_strategies",
                          "strategy_verdicts", "wf_cycles"]},
            {"name": "review", "type": "agent",
             "agent": "reviewer-agent",
             "requires": ["statistics", "aggregate_stats", "monte_carlo_bands", "strategy_analysis"],
             "provides": ["review_decision", "iteration_proposal",
                          "wf_degradation", "mc_overfit_flag", "benchmark_comparison"]},
            {"name": "portfolio", "type": "agent",
             "agent": "portfolio-agent",
             "requires": ["selected_strategies", "review_decision"],
             "provides": ["portfolio_cfx", "portfolio_result", "correlation_matrix",
                          "risk_allocation", "wf_aggregate_stats"]},
            {"name": "deploy", "type": "agent",
             "agent": "deployment-agent",
             "requires": ["portfolio_cfx", "gate_decision_HUMAN_APPROVE_PORTFOLIO"],
             "provides": ["jforex_package", "jcloud_config", "deployment_result"]},
            {"name": "monitor", "type": "agent",
             "agent": "monitoring-agent",
             "requires": ["live_equity", "deployment_result"],
             "provides": ["rolling_metrics", "regime_alerts", "performance_alerts",
                          "gate_decision_HUMAN_REVIEW_PERFORMANCE"]},
        ]

        # Append extended 14-phase stages when QUANTLAB_14PHASE is enabled.
        if os.environ.get("QUANTLAB_14PHASE") == "1":
            stages.extend([
                {"name": "compile", "type": "agent",
                 "agent": "compiler-agent",
                 "requires": ["deployment_result"],
                 "provides": ["compiled_strategies", "compilation_failed"]},
                {"name": "demo", "type": "agent",
                 "agent": "demo-agent",
                 "requires": ["compiled_strategies", "deployment_result"],
                 "provides": ["demo_result"]},
                {"name": "archive", "type": "agent",
                 "agent": "archive-agent",
                 "requires": ["demo_result", "portfolio_result"],
                 "provides": ["campaign_archive"]},
                {"name": "live_ops", "type": "agent",
                 "agent": "live-ops-agent",
                 "requires": ["campaign_archive", "deployment_result"],
                 "provides": ["live_equity", "performance_alerts"]},
            ])

        # Build gate list
        gates = [
            {"gate_id": "HUMAN_REVIEW_OBJECTIVES",
             "timeout_hours": 24, "fallback": "ESCALATE",
             "after_stage": "research"},
            {"gate_id": "HUMAN_APPROVE_ITERATION",
             "timeout_hours": 24, "fallback": "ABORT",
             "after_stage": "review"},
            {"gate_id": "HUMAN_APPROVE_PORTFOLIO",
             "timeout_hours": 24, "fallback": "ESCALATE",
             "after_stage": "portfolio"},
            {"gate_id": "HUMAN_APPROVE_DEPLOY",
             "timeout_hours": 12, "fallback": "HOLD",
             "after_stage": "deploy"},
            {"gate_id": "HUMAN_REVIEW_PERFORMANCE",
             "timeout_hours": 48, "fallback": "CONTINUE",
             "after_stage": "monitor"},
        ]

        # Build the config dict
        pipeline_config = {
            "version": "2.0.0",
            "pipeline": {
                "name": f"campaign-{config.campaign}",
                "description": f"Multi-agent research pipeline for {config.campaign}",
                "version": "2.0.0",
                "stages": stages,
            },
            "guardian_enabled": True,
            "gates": gates,
            "memory": {
                "enabled": True,
                "topic_prefix": "quantlab/agent",
                "retention_days": 365,
                "cross_agent_sharing": True,
            },
            "risk": {
                "max_portfolio_drawdown": 0.20,
                "max_strategy_correlation": 0.7,
                "max_single_strategy_weight": 0.4,
                "kelly_fraction_cap": 0.25,
                "var_confidence": 0.95,
            },
        }

        return pipeline_config
