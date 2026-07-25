"""Demo: multi-agent pipeline con gates interactivos."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from quantlab.pipeline.config.models import MultiAgentPipelineConfig
from quantlab.pipeline.registry import StageRegistry
from quantlab.pipeline.runner import PipelineRunner
from quantlab.pipeline.base import Pipeline, PipelineContext
from quantlab.pipeline.stages.gate_interceptor import (
    GateInterceptorStage,
    GateContext,
    GateDecision,
    GateAction,
    FallbackPolicy,
)

CONFIG_PATH = "examples/pipeline.yaml"


async def human_gate_callback(ctx: GateContext) -> GateDecision:
    """Callback interactivo: muestra el contexto del gate y espera y/n/hold."""
    print(f"\n{'='*70}")
    print(f"🚦 GATE: {ctx.gate_id}")
    print(f"   Pipeline: {ctx.pipeline_name}")
    print(f"   Triggered after stage: {ctx.stage_name}")
    print(f"   Timeout: {ctx.timeout_hours}h | Fallback: {ctx.fallback.value}")
    print(f"{'='*70}")

    print("\n📦 Artifacts disponibles hasta este punto:")
    shown = 0
    for key, value in ctx.context_artifacts.items():
        if key.startswith("gate_decision_"):
            continue
        if key == "export_paths" and value:
            print(f"  • {key}: {len(value)} archivos generados")
            for ep in value[:3]:
                print(f"       {ep}")
            if len(value) > 3:
                print(f"       ... y {len(value) - 3} más")
            shown += 1
            continue
        # Acortar valores largos para legibilidad
        val = str(value)
        if len(val) > 120:
            val = val[:120] + "..."
        print(f"  • {key}: {val}")
        shown += 1

    if shown == 0:
        print("  (sin artifacts relevantes)")

    # Auto-aprobar para demo sin intervención manual
    print("\n✅ Auto-aprobado para demo.")
    return GateDecision(
        gate_id=ctx.gate_id,
        action=GateAction.APPROVED,
        reason="Auto-aprobado en demo",
        decided_by="system",
    )


async def main() -> None:
    # 1. Cargar config
    config = MultiAgentPipelineConfig.load(CONFIG_PATH)
    print(f"\n📋 Pipeline: {config.name}")
    print(f"   Versión: {config.version}")
    print(f"   Descripción: {config.description}\n")

    # 2. Mostrar stages y gates
    print(f"🎯 Stages ({len(config.stages)}):")
    for i, stage in enumerate(config.stages, 1):
        req = ", ".join(stage.requires) if stage.requires else "-"
        prov = ", ".join(stage.provides) if stage.provides else "-"
        print(f"  {i:2d}. {stage.name:20s}  requires: {req:35s}  provides: {prov}")

    print(f"\n🚦 Gates ({len(config.gates)}):")
    for gate in config.gates:
        print(f"  • {gate.gate_id:30s}  after: {gate.after_stage:15s}  fallback: {gate.fallback}")

    # 3. Build pipeline
    pipeline = Pipeline("demo-multi-agent")
    runner = PipelineRunner(max_retries=1, retry_delay=0.1)

    # Usar el registry para obtener las clases concretas de agentes
    registry = StageRegistry()
    for stage_cfg in config.stages:
        cls = registry.get_stage_class(stage_cfg.name)
        if cls is None:
            print(f"  ⚠ Stage '{stage_cfg.name}' no encontrado en registry, salteando")
            continue
        stage = cls()
        stage.name = stage_cfg.name
        stage.requires = stage_cfg.requires
        stage.provides = stage_cfg.provides
        pipeline.stages.append(stage)

        # Inyectar gate después de este stage
        matching_gates = [g for g in config.gates if g.after_stage == stage_cfg.name]
        for gate_cfg in matching_gates:
            gate = GateInterceptorStage()
            gate.name = f"gate_{gate_cfg.gate_id}"
            gate.gate_id = gate_cfg.gate_id
            gate.timeout_hours = gate_cfg.timeout_hours
            try:
                gate.fallback = FallbackPolicy(gate_cfg.fallback)
            except ValueError:
                gate.fallback = FallbackPolicy.CONTINUE
            gate.set_callback(human_gate_callback)
            runner.register_gate(stage_cfg.name, gate)

    print(f"\n🔨 Pipeline: {len(pipeline.stages)} stages + {len(config.gates)} gates registrados")

    # 4. Ejecutar
    print("\n" + "=" * 70)
    print("EJECUTANDO PIPELINE — modo interactivo")
    print("(cada gate te va a pedir aprobación por consola)")
    print("=" * 70 + "\n")

    ctx = PipelineContext(config={
        "dry_run": True,
        "campaign_name": config.name,
        "sqx_install_path": "assets/SQX_144_2953_linux_20260601",
        "objectives": ["Mean reversion strategy for EURUSD H1"],
        "market_context": {"market": "EURUSD", "timeframe": "H1"},
    })

    ctx.artifacts.setdefault("live_equity", {})
    for gate_id in (
        "HUMAN_APPROVE_PORTFOLIO",
        "HUMAN_APPROVE_DEPLOY",
        "HUMAN_REVIEW_PERFORMANCE",
    ):
        ctx.artifacts.setdefault(f"gate_decision_{gate_id}", {"status": "pending"})

    result = await runner.run_with_gates(pipeline, ctx)

    export_paths = ctx.artifacts.get("export_paths", [])
    if not export_paths:
        print("\n⚠️  Advertencia: No se encontraron export_paths después del builder.")
        print("   El pipeline continuará con estadísticas vacías.\n")

    # 5. Report
    print("\n" + "=" * 70)
    print("RESULTADO FINAL")
    print("=" * 70)
    print(f"  Exitosa:       {result.is_successful}")
    print(f"  Duración:      {result.total_duration:.2f}s")
    print(f"  Error:         {result.error or 'none'}")
    print(f"\n  Stages ejecutados:")

    for stage_result in result.stages:
        icon = {
            "completed": "✅",
            "failed": "❌",
            "skipped": "⏭️",
            "retrying": "🔄",
            "running": "▶️",
        }.get(stage_result.status.value, "❓")

        print(f"    {icon} {stage_result.stage_name:30s} {stage_result.status.value:12s} {stage_result.duration:.2f}s")
        if stage_result.error:
            err = str(stage_result.error)
            if len(err) > 80:
                err = err[:80] + "..."
            print(f"       └─ {err}")

    print()


if __name__ == "__main__":
    asyncio.run(main())
