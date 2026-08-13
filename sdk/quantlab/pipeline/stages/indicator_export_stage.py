"""IndicatorExportStage — injects the indicator export helper into .jfx archives.

Post-compile stage (Ciclo 4, T4.3): every compiled strategy ``.jfx`` gains the
``IndicatorExporter.java`` helper plus an ``indicator_export.manifest.json``
pointing at the strategy's canonical export path (REQ-05). The stage then
provides ``indicator_export_paths`` (strategy -> export JSON path) so
downstream LLM agents can locate and read the exports.

Fail-closed: a missing ``.jfx`` raises — no partial packaging.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from quantlab.pipeline.base import PipelineContext, Stage

#: Injectable injector: (jfx_path, strategy) -> modified jfx path.
InjectFn = Callable[[str | Path, str], Path]


class IndicatorExportStage(Stage):
    """Inject indicator export support into each compiled .jfx (REQ-05).

    **Requires**: compiled_strategies
    **Provides**: indicator_export_paths
    """

    name: str = "indicator_export"
    requires: list[str] = ["compiled_strategies"]
    provides: list[str] = ["indicator_export_paths"]

    def __init__(
        self,
        inject_fn: InjectFn | None = None,
        *,
        export_dir: str | Path | None = None,
    ) -> None:
        # Injectable for tests; the default resolves the real injector lazily
        # so registry instantiation stays side-effect free.
        self._inject_fn = inject_fn
        self._export_dir = export_dir

    async def execute(self, ctx: PipelineContext) -> dict[str, Any]:
        """Inject the helper into every compiled strategy and map export paths.

        Args:
            ctx: Pipeline context with ``compiled_strategies`` — either a list
                of .jfx paths/JfxArtifact objects or a dict of
                ``strategy_id -> .jfx path``.

        Returns:
            Dict with ``indicator_export_paths`` mapping strategy id to the
            canonical export JSON path.
        """
        compiled = ctx.artifacts.get("compiled_strategies") or {}
        if isinstance(compiled, dict):
            items = list(compiled.items())
        else:
            items = [(self._strategy_name(a), a) for a in compiled]

        inject = self._inject_fn or self._default_inject()
        exports: dict[str, Path] = {}
        for strategy_id, artifact in items:
            jfx_path = self._resolve_jfx_path(artifact)
            inject(jfx_path, strategy_id)
            exports[strategy_id] = self._export_path(strategy_id)

        ctx.artifacts["indicator_export_paths"] = exports
        return {"indicator_export_paths": exports}

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _default_inject(self) -> InjectFn:
        """Lazily import the exporter injector (keeps imports side-effect free)."""
        from quantlab.jforex.exporter import inject_indicator_exporter

        def inject(jfx_path: str | Path, strategy_id: str) -> Path:
            return inject_indicator_exporter(
                jfx_path, strategy_id, export_dir=self._export_dir
            )

        return inject

    def _export_path(self, strategy_id: str) -> Path:
        from quantlab.jforex.exporter import indicator_export_path

        return indicator_export_path(strategy_id, export_dir=self._export_dir)

    @staticmethod
    def _resolve_jfx_path(artifact: Any) -> Path:
        """Unwrap a .jfx path from JfxArtifact objects or paths."""
        if hasattr(artifact, "path"):
            return Path(artifact.path)
        return Path(artifact)

    @staticmethod
    def _strategy_name(artifact: Any) -> str:
        """Derive the strategy id from a list entry (stem of the .jfx)."""
        return IndicatorExportStage._resolve_jfx_path(artifact).stem