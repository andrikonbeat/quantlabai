"""QuantLab Bayesian Optimization Package.

Provides Bayesian optimization capabilities for strategy parameter tuning
with Gaussian Process surrogates and Expected Improvement acquisition.
Integrates with Knowledge Lake for persistence and session continuity.

Main Components:
- BayesianOptimizer: Core optimization engine
- ParameterSpace: Search space definition
- Surrogate models: GaussianProcess, RandomForest
- Acquisition functions: EI, UCB, PI, Thompson Sampling
- Convergence monitoring: Multiple stopping criteria
- History buffer: Persistence to Knowledge Lake

Example:
    >>> from quantlab.optimization import create_bayesian_optimizer, create_default_sqx_space
    >>> space = create_default_sqx_space()
    >>> optimizer = create_bayesian_optimizer(parameter_space=space, max_iterations=50)
    >>> result = optimizer.optimize(objective_function)
    >>> print(result.best_parameters)
"""

from quantlab.optimization.acquisition import (
    AcquisitionFunction,
    ConstrainedExpectedImprovement,
    ExpectedImprovement,
    ExpectedImprovementPerSecond,
    ProbabilityOfImprovement,
    ThompsonSampling,
    UpperConfidenceBound,
    create_acquisition,
)
from quantlab.optimization.bayesian_optimizer import (
    BayesianOptimizer,
    BayesianOptimizerConfig,
    OptimizationResult,
    create_bayesian_optimizer,
)
from quantlab.optimization.convergence import (
    ConvergenceMonitor,
    ConvergenceReason,
    ConvergenceState,
    CompositeConvergenceCriterion,
    DivergenceCriterion,
    EIThresholdCriterion,
    MaxIterationsCriterion,
    PatienceCriterion,
    TargetValueCriterion,
    create_default_monitor,
)
from quantlab.optimization.history import (
    HistoryBuffer,
    OptimizationStep,
    create_history_from_exploration,
    load_history,
)
from quantlab.optimization.space import (
    ParameterSpace,
    ParameterSpec,
    ParamType,
    ParameterConstraint,
    create_default_sqx_space,
)
from quantlab.optimization.surrogate import (
    GaussianProcessSurrogate,
    RandomForestSurrogate,
    SurrogateModel,
    SurrogatePrediction,
    create_surrogate,
)

__all__ = [
    # Core optimizer
    "BayesianOptimizer",
    "BayesianOptimizerConfig",
    "OptimizationResult",
    "create_bayesian_optimizer",
    # Parameter space
    "ParameterSpace",
    "ParameterSpec",
    "ParamType",
    "ParameterConstraint",
    "create_default_sqx_space",
    # Surrogate models
    "SurrogateModel",
    "GaussianProcessSurrogate",
    "RandomForestSurrogate",
    "SurrogatePrediction",
    "create_surrogate",
    # Acquisition functions
    "AcquisitionFunction",
    "ExpectedImprovement",
    "UpperConfidenceBound",
    "ProbabilityOfImprovement",
    "ThompsonSampling",
    "ExpectedImprovementPerSecond",
    "ConstrainedExpectedImprovement",
    "create_acquisition",
    # Convergence
    "ConvergenceMonitor",
    "ConvergenceState",
    "ConvergenceReason",
    "MaxIterationsCriterion",
    "EIThresholdCriterion",
    "PatienceCriterion",
    "TargetValueCriterion",
    "DivergenceCriterion",
    "CompositeConvergenceCriterion",
    "create_default_monitor",
    # History
    "HistoryBuffer",
    "OptimizationStep",
    "load_history",
    "create_history_from_exploration",
]

# Version
__version__ = "0.1.0"