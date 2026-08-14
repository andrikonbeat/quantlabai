"""Run the full multi-agent campaign against real SQX CLI with live progress."""

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

# Resolve SQX install path: SQX_PATH env var wins, fall back to repo-relative assets
_DEFAULT_SQX = str(Path(__file__).resolve().parent / "assets" / "SQX_144_2953_linux_20260601")
SQX_PATH = str(Path(os.environ.get("SQX_PATH", _DEFAULT_SQX)).resolve())
os.environ.setdefault("SQX_INSTALL_PATH", SQX_PATH)
os.environ.setdefault("JAVA_HOME", f"{SQX_PATH}/j64")

# Enable verbose logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)

# Quiet down noisy libs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("oshi").setLevel(logging.WARNING)

from quantlab.dsl.parser import parse_yaml
from quantlab.agents.research_director import ResearchDirector


async def run_campaign():
    print(f"\n{'='*60}", flush=True)
    print(f"QUANTLAB AI — FULL MULTI-AGENT CAMPAIGN (REAL SQCLI)", flush=True)
    print(f"SQX: {SQX_PATH}", flush=True)
    print(f"{'='*60}\n", flush=True)

    # Parse config
    print("📋 Loading research config...", flush=True)
    config = parse_yaml("examples/research-config.yaml")
    print(f"   Campaign: {config.campaign}", flush=True)
    print(f"   Market:   {config.market}", flush=True)
    print(f"   Hypotheses: {len(config.hypotheses)}", flush=True)
    print(f"   Max iterations: {config.iteration_config.max_iterations}", flush=True)
    print(f"   Gate policies: {len(config.gate_policies)}\n", flush=True)

    # Create director with progress callback
    print("🚀 Creating ResearchDirector...\n", flush=True)
    director = ResearchDirector(knowledge_root="/tmp/quantlab-knowledge")

    # Run campaign
    print(f"{'─'*60}", flush=True)
    print(f"🏁 STARTING CAMPAIGN...", flush=True)
    print(f"{'─'*60}\n", flush=True)

    start_time = time.time()
    try:
        result = await director.execute_campaign(config)
        duration = time.time() - start_time

        print(f"\n{'='*60}", flush=True)
        print(f"✅ CAMPAIGN COMPLETE", flush=True)
        print(f"{'='*60}", flush=True)
        print(f"  Campaign ID:  {result.campaign_id}", flush=True)
        print(f"  State:        {result.state.value}", flush=True)
        print(f"  Iterations:   {result.current_iteration}", flush=True)
        print(f"  Duration:     {duration:.1f}s ({duration/60:.1f}m)", flush=True)
        if result.error:
            print(f"  Error:        {result.error}", flush=True)

        # Show pipeline results per iteration
        if hasattr(result, 'result') and result.result is not None:
            pr = result.result
            print(f"\n  Pipeline: {pr.pipeline_name}", flush=True)
            print(f"  Stages: {len(pr.stages)}", flush=True)
            for s in pr.stages:
                icon = "✅" if s.status.value == "completed" else "❌" if s.status.value == "failed" else "⏭️" if s.status.value == "skipped" else "⏳"
                dur = f"{s.duration:.1f}s" if s.duration else "?"
                err = f" — {s.error[:80]}" if s.error else ""
                print(f"    {icon} {s.stage_name} ({dur}){err}", flush=True)
            if pr.error:
                print(f"  Pipeline error: {pr.error}", flush=True)

        return result

    except Exception as e:
        duration = time.time() - start_time
        print(f"\n❌ CAMPAIGN FAILED after {duration:.1f}s", flush=True)
        print(f"   {type(e).__name__}: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    result = asyncio.run(run_campaign())
    sys.exit(0 if result and result.state.value in ("completed", "converged") else 1)
