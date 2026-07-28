"""GeneticOptimizer — CFX parameter mutation via pure Python GA operators and PipelineRunner backtesting."""

from __future__ import annotations

import logging
import random
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree

from quantlab.evolution.config import EvolutionConfig
from quantlab.evolution.fitness import FitnessFunction
from quantlab.evolution.models import CandidateStatus, EvolutionCandidate, EvolutionMode
from quantlab.pipeline.base import Pipeline, PipelineContext, Stage
from quantlab.pipeline.models import PipelineResult
from quantlab.pipeline.runner import PipelineRunner

logger = logging.getLogger(__name__)

# ── Fraction / Tolerances ───────────────────────────────────────────

SIGMA_FRAC = 3.0        # gaussian stddev = range / SIGMA_FRAC
BOUNDARY_FRAC = 0.2     # boundary reset clips at ±BOUNDARY_FRAC * range
BLEND_ALPHA = 0.5       # blend crossover interpolation factor
TOURNAMENT_SIZE = 3     # tournament selection participants
MUTATION_RATE = 0.3     # probability a given param is mutated


# ── Mutation Operators (pure functions, no side effects) ────────────


def gaussian_perturbation(value: float, lo: float, hi: float) -> float:
    """Add Gaussian noise clipped to [lo, hi].

    Noise scale = (hi - lo) / SIGMA_FRAC so that ~99.7 % of draws
    stay within the original range.
    """
    sigma = (hi - lo) / SIGMA_FRAC
    perturbed = value + random.gauss(0, sigma)
    return max(lo, min(hi, perturbed))


def boundary_reset(value: float, lo: float, hi: float) -> float:
    """Randomly jump within ±BOUNDARY_FRAC of the range.

    With 50 % probability resets to a random point near the lower
    boundary, otherwise near the upper boundary.
    """
    margin = (hi - lo) * BOUNDARY_FRAC
    if random.random() < 0.5:
        return lo + random.random() * margin
    else:
        return hi - random.random() * margin


def blend_crossover(a: float, b: float, lo: float, hi: float) -> Tuple[float, float]:
    """BLX-α crossover — two offspring from two parents.

    Each child is sampled from (min - α·d, max + α·d) where
    d = |a - b| and α = BLEND_ALPHA.
    """
    d = abs(a - b)
    low = min(a, b) - BLEND_ALPHA * d
    high = max(a, b) + BLEND_ALPHA * d
    c1 = low + random.random() * (high - low)
    c2 = low + random.random() * (high - low)
    return max(lo, min(hi, c1)), max(lo, min(hi, c2))


def single_point_crossover(parent_a: List[float], parent_b: List[float]) -> Tuple[List[float], List[float]]:
    """Single-point crossover on two parameter vectors of equal length."""
    if len(parent_a) != len(parent_b):
        raise ValueError("Parents must have equal length")
    if len(parent_a) < 2:
        return parent_a[:], parent_b[:]
    point = random.randint(1, len(parent_a) - 1)
    child_a = parent_a[:point] + parent_b[point:]
    child_b = parent_b[:point] + parent_a[point:]
    return child_a, child_b


def tournament_select(population: List[Dict[str, Any]], fitness_key: str = "fitness") -> Dict[str, Any]:
    """Tournament selection — pick the fittest from *k* random individuals."""
    candidates = random.choices(population, k=TOURNAMENT_SIZE)
    return max(candidates, key=lambda ind: ind.get(fitness_key, 0.0))


# ── CFX Parameter Extraction ─────────────────────────────────────────


def extract_numeric_params(cfx_content: str) -> Dict[str, Tuple[float, float, float]]:
    """Extract numeric parameters and their ranges from CFX XML content.

    Uses ElementTree to parse the CFX XML, extracts numeric values
    from settings sections, and derives [lo, hi] bounds by ±20 % of
    the value.  Returns a dict mapping ``section/key`` → ``(default, lo, hi)``.

    When the CFX includes explicit ``OptimizationParameters`` the
    min/max/step from those definitions take precedence.
    """
    params: Dict[str, Tuple[float, float, float]] = {}

    def _try_float(v: str) -> Optional[float]:
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    try:
        root = ElementTree.fromstring(cfx_content)
    except ElementTree.ParseError:
        return params

    # Walk all elements and collect numeric attributes
    # CFX settings look like: <SectionName><SettingName value="42"/></SectionName>
    # Some also use: <SettingName>42</SettingName>
    for section_elem in root.iter():
        sectag = _normalise_tag(section_elem.tag)
        if sectag in ("buildtask", "task"):
            continue
        for setting_elem in section_elem:
            setting_tag = _normalise_tag(setting_elem.tag)
            # Check attribute-based values
            for attr_name in ("value",):
                raw = setting_elem.get(attr_name, "")
                value = _try_float(raw)
                if value is not None:
                    lo = value * 0.8
                    hi = value * 1.2
                    param_key = f"{sectag}/{setting_tag}@{attr_name}"
                    params[param_key] = (value, lo, hi)

            # Check text-based values
            text = (setting_elem.text or "").strip()
            value = _try_float(text)
            if value is not None:
                lo = value * 0.8
                hi = value * 1.2
                param_key = f"{sectag}/{setting_tag}#text"
                params[param_key] = (value, lo, hi)

    # Override with explicit OptimizationParameters when present
    for opt_param in root.iter("Parameter"):
        name = opt_param.get("name", "")
        lo = _try_float(opt_param.get("min", ""))
        hi = _try_float(opt_param.get("max", ""))
        step = _try_float(opt_param.get("step", ""))
        if lo is not None and hi is not None and name:
            default = step if step is not None else (lo + hi) / 2
            params[f"optimization/{name}"] = (default, lo, hi)

    return params


def _normalise_tag(tag: str) -> str:
    """Strip XML namespace from a tag name, if present."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def apply_params_to_cfx(cfx_content: str, param_values: Dict[str, float]) -> str:
    """Write mutated parameter values into a CFX XML string.

    Parses the XML, applies the changes, and returns the modified XML.
    """
    try:
        root = ElementTree.fromstring(cfx_content)
    except ElementTree.ParseError:
        return cfx_content

    for param_key, value in param_values.items():
        if "/" not in param_key:
            continue
        section_name, remainder = param_key.split("/", 1)

        # Parse the remainder: setting_tag@attr or setting_tag#text
        if "@" in remainder:
            setting_tag, attr_name = remainder.split("@", 1)
        elif "#" in remainder:
            setting_tag = remainder.split("#", 1)[0]
            attr_name = None
        else:
            setting_tag = remainder
            attr_name = None

        # Format the value
        formatted = str(int(value)) if value == int(value) else f"{value:.4f}"

        # Find the element in the XML tree
        _apply_param_value(root, section_name, setting_tag, attr_name, formatted)

    return ElementTree.tostring(root, encoding="unicode")


def _apply_param_value(
    root: ElementTree.Element,
    section_name: str,
    setting_tag: str,
    attr_name: Optional[str],
    formatted: str,
) -> None:
    """Apply a single parameter value into the XML tree."""
    for section_elem in root.iter():
        if _normalise_tag(section_elem.tag).lower() == section_name.lower():
            for setting_elem in section_elem:
                if _normalise_tag(setting_elem.tag).lower() == setting_tag.lower():
                    if attr_name:
                        setting_elem.set(attr_name, formatted)
                    else:
                        setting_elem.text = formatted
                    return


def cfx_content_to_archive(cfx_content: str) -> Optional[bool]:
    """Validate that CFX content is parseable XML.

    Returns True if valid, None on parse failure.  (Named for backward
    compatibility — we don't need the full CfxArchive for GA work.)
    """
    try:
        ElementTree.fromstring(cfx_content)
        return True
    except ElementTree.ParseError as exc:
        logger.warning("Failed to parse CFX content: %s", exc)
        return None


# ── Evolution Pipeline Builders ─────────────────────────────────────


def _build_evolution_pipeline(stages: Optional[List[str]] = None) -> Pipeline:
    """Build a lightweight pipeline for evolution backtests.

    Default stages: daemon_start → load_cfx → run_backtest → compute_stats → export.
    Falls back to a minimal no-op pipeline if the registry lacks
    concrete SQX stages (e.g. in test environments).
    """
    from quantlab.pipeline.registry import StageRegistry

    registry = StageRegistry()
    pipeline = Pipeline(name="evolution-backtest")

    stage_names = stages or ["daemon_start", "load_cfx", "run_backtest",
                              "compute_stats", "export"]

    for name in stage_names:
        stage_class = registry.get_stage_class(name)
        if stage_class is None:
            logger.debug("Stage '%s' not registered — using no-op fallback", name)
            stage = _NoopStage(name=name)
        else:
            stage = stage_class()
        pipeline.stages.append(stage)

    return pipeline


class _NoopStage(Stage):
    """Fallback stage that does nothing — used when SQX stages aren't available."""

    def __init__(self, name: str = "noop") -> None:
        self.name = name
        self.requires: List[str] = []
        self.provides: List[str] = []

    async def execute(self, ctx: PipelineContext) -> Dict[str, Any]:
        logger.debug("No-op stage '%s' executed", self.name)
        return {"status": "noop", "stage": self.name}


# ── GeneticOptimizer ─────────────────────────────────────────────────


class GeneticOptimizer:
    """Evolves strategies via genetic parameter mutation.

    Parses existing CFX configurations, extracts numeric parameters,
    applies GA operators (gaussian, boundary, blend crossover,
    single-point crossover), delegates backtest via PipelineRunner,
    and scores results using the FitnessFunction.
    """

    def __init__(
        self,
        config: EvolutionConfig,
        fitness: FitnessFunction,
        runner: Optional[PipelineRunner] = None,
    ) -> None:
        """Initialize the genetic optimizer.

        Args:
            config: Evolution configuration.
            fitness: Fitness function for scoring.
            runner: Optional PipelineRunner (creates a default one).
        """
        self._config = config
        self._fitness = fitness
        self._runner = runner or PipelineRunner()

    async def optimize(
        self,
        strategy_id: str,
        cfx_content: str,
        parent_candidate_id: Optional[str] = None,
    ) -> List[EvolutionCandidate]:
        """Run a genetic optimization cycle on a strategy's CFX.

        Args:
            strategy_id: Target strategy identifier.
            cfx_content: Current CFX configuration XML.
            parent_candidate_id: Optional parent candidate ID.

        Returns:
            List of candidate strategies.
        """
        if not cfx_content or not cfx_content.strip():
            logger.info("Empty or invalid CFX content for %s — returning no candidates", strategy_id)
            return []

        # 1. Parse CFX → extract parameters
        if cfx_content_to_archive(cfx_content) is None:
            logger.warning("Could not parse CFX for %s — returning no candidates", strategy_id)
            return []

        params = extract_numeric_params(cfx_content)
        if not params:
            logger.info("No mutable parameters found in CFX for %s", strategy_id)
            return []

        param_names = list(params.keys())
        # (default, lo, hi)
        param_ranges = [params[name] for name in param_names]
        param_defaults = [r[0] for r in param_ranges]
        param_los = [r[1] for r in param_ranges]
        param_his = [r[2] for r in param_ranges]

        # 2. Build population from mutated parameter vectors
        population_size = min(
            self._config.schedule.max_candidates_per_cycle,
            len(param_names) * 2,  # at least 2x params
        )
        population_size = max(population_size, 2)  # min 2 for crossover

        individuals: List[Dict[str, Any]] = []
        for i in range(population_size):
            # Copy defaults and mutate
            vector = list(param_defaults)
            # Apply random mutations to some params
            for j in range(len(vector)):
                if random.random() < MUTATION_RATE:
                    if random.random() < 0.5:
                        vector[j] = gaussian_perturbation(vector[j], param_los[j], param_his[j])
                    else:
                        vector[j] = boundary_reset(vector[j], param_los[j], param_his[j])
            individuals.append({
                "vector": vector,
                "fitness": 0.0,
                "mutated": True,
            })

        # 3. Crossover — blend first half with second half
        half = len(individuals) // 2
        for i in range(half):
            j = i + half
            if j >= len(individuals):
                break
            va = individuals[i]["vector"]
            vb = individuals[j]["vector"]
            for k in range(len(va)):
                va[k], vb[k] = blend_crossover(va[k], vb[k], param_los[k], param_his[k])
            individuals[i]["crossover"] = True
            individuals[j]["crossover"] = True

        # 4. For each individual, create CFX and run backtest
        candidates: List[EvolutionCandidate] = []
        pipeline = _build_evolution_pipeline()

        for idx, ind in enumerate(individuals):
            param_values = dict(zip(param_names, ind["vector"]))
            mutated_cfx = apply_params_to_cfx(cfx_content, param_values)

            candidate_id = f"gen-{uuid.uuid4().hex[:12]}"

            # Run backtest via PipelineRunner
            pipeline_ctx = PipelineContext(
                config={"strategy_id": strategy_id, "candidate_id": candidate_id},
                artifacts={
                    "cfx_content": mutated_cfx,
                    "candidate_id": candidate_id,
                    "strategy_id": strategy_id,
                },
            )

            try:
                pipeline_result = await self._runner.run(pipeline, pipeline_ctx)
                fitness_score = self._score_from_pipeline(pipeline_result)
            except Exception as exc:
                logger.warning("Pipeline backtest failed for candidate %s: %s", candidate_id, exc)
                fitness_score = 0.0

            ind["fitness"] = fitness_score

            candidate = EvolutionCandidate(
                candidate_id=candidate_id,
                strategy_id=strategy_id,
                mode=EvolutionMode.GENETIC_ONLY,
                cfx_content=mutated_cfx,
                parent_candidate_id=parent_candidate_id,
                fitness_score=fitness_score,
                status=CandidateStatus.PENDING,
                validation_results={
                    "genesis": "genetic_optimizer",
                    "mutation_operators": self._describe_operators(ind),
                    "pipeline_result": self._summarize_pipeline(pipeline_result)
                    if "pipeline_result" in dir()
                    else {},
                    "param_changes": {
                        n: {"from": param_defaults[i], "to": ind["vector"][i]}
                        for i, n in enumerate(param_names)
                        if abs(param_defaults[i] - ind["vector"][i]) > 1e-6
                    },
                },
            )
            candidates.append(candidate)

        logger.info(
            "GeneticOptimizer: generated %d candidates for %s",
            len(candidates), strategy_id,
        )
        return candidates

    def _score_from_pipeline(self, pipeline_result: PipelineResult) -> float:
        """Derive a fitness score from pipeline results.

        If the pipeline completed and produced statistics, delegate
        to FitnessFunction. Otherwise return a default score.
        """
        if pipeline_result.is_successful:
            # Extract stats from the last stage's output
            for stage in reversed(pipeline_result.stages):
                if stage.output and isinstance(stage.output, dict):
                    stats = stage.output.get("statistics") or stage.output.get("stats")
                    if stats is not None:
                        try:
                            from quantlab.stats.models import StatsResult
                            if isinstance(stats, dict):
                                stats_obj = StatsResult(**stats)
                            else:
                                stats_obj = stats
                            return self._fitness.evaluate(stats_obj)
                        except Exception:
                            pass
            # Fallback: score based on completion and number of stages passed
            completed = sum(1 for s in pipeline_result.stages if s.status.value == "completed")
            total = len(pipeline_result.stages) or 1
            return (completed / total) * 50.0  # max 50 for partial data
        return 0.0

    @staticmethod
    def _describe_operators(ind: Dict[str, Any]) -> List[str]:
        ops = []
        if ind.get("mutated"):
            ops.append("gaussian_perturbation")
            ops.append("boundary_reset")
        if ind.get("crossover"):
            ops.append("blend_crossover")
        return ops or ["none"]

    @staticmethod
    def _summarize_pipeline(result: PipelineResult) -> Dict[str, Any]:
        return {
            "stages": len(result.stages),
            "successful": result.is_successful,
            "error": result.error,
        }

    async def _mutate_cfx(self, cfx_content: str) -> List[str]:
        """Generate mutated CFX variants (legacy compatibility wrapper).

        Args:
            cfx_content: Original CFX content.

        Returns:
            List of mutated CFX strings.
        """
        if cfx_content_to_archive(cfx_content) is None:
            return [cfx_content]

        params = extract_numeric_params(cfx_content)
        if not params:
            return [cfx_content]

        variants: List[str] = []
        for _ in range(min(3, len(params) * 2)):
            param_values = {}
            for key, (default, lo, hi) in params.items():
                if random.random() < MUTATION_RATE:
                    param_values[key] = gaussian_perturbation(default, lo, hi)
            variants.append(apply_params_to_cfx(cfx_content, param_values))

        return variants or [cfx_content]
