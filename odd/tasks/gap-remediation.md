# ODD Feature: Core Gap Remediation (10 gaps across config, verification, JForex deploy, 24/7 ops)

Read-only reconnaissance on 2026-02-XX verified 10 gaps in the QuantLab SDK. Each gap is fixed here as a
reviewable work unit on `feature/gap-remediation`. Gap 5 is already tracked in
`odd/tasks/jforex-bridge-architecture.md`; this document references that plan instead of duplicating it.

## Context

The pipeline research → hypothesis → config → review → dispatch → retest → optimize → portfolio → compile →
deploy → demo → archive → live-ops currently loses most of its own decisions before they reach StrategyQuant X,
verifies discrepancies with fabricated metrics, and ends at a deployment bridge that shells out to a binary
that does not exist. The reconnaissance below is the sole basis for the task list; nothing here is inferred
from the task description.

Two cross-cutting facts drive the ordering:

1. **The newest code path is worse than the oldest.** The production default is the Custom Project dialect
   (`sdk/quantlab/agents/builder_agent.py:482-493`, gated by `_is_custom_project_enabled()`), and it emits
   empty `Options`/`Data` sections (`sdk/quantlab/customproject/renderers.py:114-118`) while the legacy
   path at least wrote `RiskMoneyManagement` — hardcoded (`sdk/quantlab/translate/translator.py:176-184`:
   `AccountSize@value: 10000`, `RiskPercent@value: 2`, `MaxPositions@value: 1`). For a 100 USD portfolio
   neither path is correct: one says 10 000, the other says nothing.
2. **Verification cannot be trusted before serialization is fixed.** `ConfigReviewer` judges rules over
   parameters that never reach the `.cfx`, so the review phase validates paper, not reality.

## Specs

Requirement change protocol: a new or corrected requirement appends its verbatim `Log` entry, rewrites only the
affected `S#`, and reopens only its task.

### Configuration effect

> **S1** — "Es importante que se configure absolutamente todos los parámetros de cada task dentro del custom project."
> → Gap 1 · T3

> **S2** — "Se crea el artefacto para guiar la configuración del custom project, el artefacto debe contener la configuración de cada parámetro existente configurable de cada task dentro del custom project, estas configuraciones se realizan teniendo en cuenta el artefacto de desiciones durante la exploración."
> → Gap 1, Gap 9 · T3, T4

> **S3** — "es necesario que el modelo siempre configure los mismos parámetros (siempre o cuando no haya una actualización y se añadan más parámetros a SQX) pero variando la configuración en dependencia de la información del portfolio y de los artefactos de contrato creados previamente"
> → Gap 2 · T2

> **S4** — "dándole una indicación ejemplo: Comienza una campaña para un portafolio de 100 USD"
> → Gap 1 · T3

> **S5** — "El artefacto debe contener:
> - Capital
> - Mercado
> - Instrumentos
> - Temporalidad
> - Apalancamiento
> - Limitaciones de capital
> - Restricciones operativas
> - Gestión de riesgo
> - Gestión de dinero
> - Observaciones previas relacionadas
> - Ventaja estadística
> - Hipótesis a comprobar
> - Información actualizada del broker (Comisiones, Slippage, Spread, Swap, Rollovers, Triple swap)"
> → Gap 1 · T3

### Verification before spending compute

> **S6** — "4- Verificación de campaña. Se revisa todas las deciciones y configuraciones hasta el momento."
> → Gap 1, Gap 3 · T3, T6

> **S7** — "Creo que esto también es una tarea grande y ardua porque el LLM debe comprobar con evidencias si las deciciones y configuración establecida fueron la mejor ruta, si todo está correcto, pasa la verificación, en caso de encontrar problemas devuelve un resumen con la estrategia recomendada para corregir el problema se corrobora con el usuario y se corrige para continuar."
> → Gap 3, Gap 4 · T6, T7

> **S8** — "es preferible detectar un problema antes de comenzar un flujo de task de un Custom Project que tarde horas y realmente todo este mal."
> → Gap 1, Gap 3, Gap 4 · T3, T6, T7

### Run state, monitoring and mobile control

> **S9** — "Hasta el momento no se cómo se maneja el estado del custom project en ejecución, me imagino que SQX expone herramientas que a su vez exponen el estado actual de cada task en ejecución en el custom project, porque es necesario poder llevar un historial bien claro del proceso de generación de estrategias y demás procesos de otras task para que el modelo LLM pueda consultar ese historial y sacar conclusiones"
> → Gap 6, Gap 8 · T5, T8

> **S10** — "cualquier cosa mal configurada puede hacer que no se generen estrategias, o cualquier otro tipo de inconveniente durante la fase de ejecución de cada task y esto puede costar horas de cómputo y tiempo valioso en vano."
> → Gap 8 · T5

> **S11** — "consultas automáticas cada cierto tiempo que activen el LLM para que haga una evaluación de estado de todo el historial y decida si todo está bien, en caso de no estarlo necesitamos un sistema de notificaciones al móvil para alertar al usuario que debe revisar el estado del custom project"
> → Gap 8, Gap 7 · T5, T10

> **S12** — "hay que prestar especial atención al sistema y tecnología que se va a utilizar para controlar QuantLab-AI desde el dispositivo móvil porque además de notificaciones es necesario que el usuario pueda enviar ordenes desde el dispositivo móvil y que se ejecute en la máquina donde esté corriendo QuantLab"
> → Gap 7 · T10

> **S13** — "para esto habrá que diseñar un sistema de clasificación de veredicto porque el LLM es probabilístico y puede clasificar incorrectamente"
> → Gap 7 · T11

> **S14** — "el historial de resultado de cada campaña ya sea exitosa o fallida también debe formar parte del sistema de conocimiento de QuantLab que después se puede consumir en cualquier otra fase."
> → Gap 7 · T11

> **S15** — "Cuando el usuario de su veredicto, si el LLM considera que es importante recopilar alguna información del veredicto lo guarda en su sistema de conocimiento y aprendizaje con el objetivo de en futuras campañas cuando haya un historial de estados similar tratarlo como algo común y no molestar al usuario"
> → Gap 7 · T11

### JForex deployment layer

> **S16** — "se que es la capa de despliegue pero hay que instalar la plataforma de escritorio?, donde puedo ver reflejado las acciones que ejecuta QuantLab en Jforex?."
> → Gap 5, Gap 6 · T8, T9

> **S17** — "8- Selección de estrategias candidatas a demo. El usuario selecciona las estrategias candidatas y estas se mueven hacia la carpeta destino para que sean reconocidas dentro de J Forex 4 Desktop, se lanza un intento de compilación si da éxito se procede, si da error se lanza un sub-agente enfocado en corrección y compilado de las estrategias en Jforex 4. Se devuelve un reporte de los errores y correcciones y a la vez se guardan en la base de conocimiento de QuantLab para poder ser consumidos posteriormente y no volver a cometerlos."
> → Gap 5, Gap 10 · T1, T9

> **S18** — "9- Comparación entre backtest. Se lanza un backtest en Jforex 4 para comparar los resultados del motor de backtesting de Jforex con el resultado obtenido en el motor de backtesting de Strategy Quant X, si hay bastante similitud se procede a la siguiente fase, si hay discrepancias muy notables, se lanza un sub-agente dedicado a analizar las discrepancias que devuelve un resumen con recomendaciones y evidencias concretas verificables, se notifica al usuario para que tome una desición."
> → Gap 3, Gap 4 · T6, T7

> **S19** — "7- Analisis de resultados del Custom Project. Cuando el custom project termina activa al LLM que analiza el historial y el resultado, creando un resumen estructurado del resultado, con recomendaciones y enfocado específicamente en ayudar a decidir al usuario que estrategias deberían pasar a pruebas en cuentas demo de Jforex 4, con justificación y evidencias concretas. Luego que el resumen está listo manda una notificación al móvil del usuario."
> → Gap 4, Gap 7 · T7, T10

> **S20** — "5- Inicialización del Custom Project. Se inicia el custom project y se comprueba que este corriendo correctamente."
> → Gap 5 · T9

## Evidence

Every gap below was verified by reading the working tree; `path:line` is the citation, and each claim marked
*read-only* is a code-reading observation, not a runtime confirmation.

| Gap | Finding | Evidence |
|-----|---------|----------|
| 1 | Renderers read only 3 params; `render_build` emits empty `Options`/`Data`; `map_exploration_to_task_params` returns `{}` | `sdk/quantlab/customproject/renderers.py:86-96,114-118`; `sdk/quantlab/exploration/params_schema.py:1001-1011`; write site `sdk/quantlab/customproject/param_mapper.py:81` |
| 1 | Legacy path hardcodes `AccountSize=10000`; Custom Project path writes no money management at all | `sdk/quantlab/translate/translator.py:176-184`; `grep -rn 'money\|Money' sdk/quantlab/customproject/` → 0 matches |
| 1 | Production default is the Custom Project dialect | `sdk/quantlab/agents/builder_agent.py:482-493` |
| 2 | Schema covers 14 task types vs 21 in the catalog. The 7 types with no schema are `ApplyMassConfig`, `CallExternalScript`, `ClearDatabanks`, `DeleteFile`, `NeuralNetworkTrainer`, `Notification`, `StopAndStart` | `sdk/quantlab/customproject/catalog.py:35` (`CATALOG_TYPES` = 21); `sdk/quantlab/exploration/params_schema.py:148-164` |
| 2 | The `TASK_PARAM_SCHEMAS` dict literal declares 23 keys but the runtime dict has 14 entries: 9 keys are repeated verbatim, so the later definition silently overwrites the earlier one for those 9 types | `sdk/quantlab/exploration/params_schema.py:173+`; measured via `ast` (23 literal keys, 9 repeated) and `len(TASK_PARAM_SCHEMAS)` == 14 |
| 2 | No drift test: nothing under `tests/` imports `params_schema`; only count invariant is `assert len(RENDERERS) == 21` | `sdk/quantlab/customproject/renderers.py:438` |
| 3 | Dead `async def execute` calls undefined `self._compare_results`; overriding `execute` returns hardcoded `{"similar": True, "correlation": 0.98}`; `phase_id` outside `PHASES` | `sdk/quantlab/pipeline/stages/backtest_comparator_stage.py:65,79,113,121,130,138` |
| 4 | `backtest_analyzer` exists only as a prompt; no stage implementation; no `knowledge/structured/backtest_discrepancies/` | `ai/opencode/agents/backtest_analyzer.md`; `backtest_comparator_stage.py:131` |
| 5 | Python bridge runs `[jforex, "deploy"\|"start"\|"stop", …]` against a fictional binary; README documents a `bridge_jar` param the class does not accept | `sdk/quantlab/jforex/strategy_bridge.py:62-112`; `odd/tasks/jforex-bridge-architecture.md`; `strategies/jforex-templates/README.md` |
| 6 | No `/orders` or `/positions` handler despite the ODD checklist marking them `[x]` | `grep -rn 'positions\|/orders\|IOrder\|submitOrder' sdk/quantlab/jforex_bridge/**/*.java` → no matches |
| 7 | No inbound channel (no Telegram `getUpdates`, no webhook receiver, no MQTT); only inbound is filesystem polling of `decision.json`; the REQ-36 ops surface is duck-typed against a test double | `sdk/quantlab/gates/callbacks.py:189,280`; `sdk/quantlab/agents/autonomous_monitor.py:437,585-591,637-639`; `sdk/quantlab/guardian/agent.py:129-134`; `sdk/tests/test_guardian/test_guardian_agent.py:85,90` |
| 8 | LLM monitor exists but `_spawn_llm_monitor` returns `None` without `llm_config`, and `run-flow` never sets it | `sdk/quantlab/sqx/llm_generation_monitor.py:386,389`; `sdk/quantlab/cli/campaign_commands.py:338-346` |
| 9 | `ConfigBuilderStage` is registered in no pipeline and calls `generate_cfx_archive(base_project, cfx_path)` (2 args) against a 1-arg definition | `sdk/quantlab/pipeline/stages/config_builder_stage.py:137`; `sdk/quantlab/customproject/generator.py:55` |
| 10 | `_write_to_kb` uses `logger.warning` with no `logging` import and no module logger | `sdk/quantlab/pipeline/stages/jforex_deploy_stage.py:107-112` |

Gap 6 also blocks S9: without orders and positions, an LLM status summary can report that a campaign ran but
not what it did. Gap 4 is inert without Gap 3: there is nothing to classify while the comparator is constant.

## Tasks

Branch: `feature/gap-remediation` (created from `c02e103`; T12 landed on it as `0848c61`). The 275-entry
in-flight WIP that was sitting on the working tree has since been committed as 21 path-scoped checkpoints on
this same branch (L14), so a task's commit is no longer entangled with unrelated work. Only T9's two RED test
files stay untracked, by design. Test-first policy applies: each task observes RED before its fix.

| ID | Task | Spec | Route | Commit |
|----|------|------|-------|--------|
| T0 | Create this feature document and task breakdown | — | inline | — |
| T1 | Define the module logger in the JForex deploy stage KB write path (Gap 10) | S17 | inline | landed in `1168916` (checkpoint C07 of the WIP split — the logger and the KB write path it serves are one file and cannot be separated) |
| T2 | Complete `TASK_PARAM_SCHEMAS` to all 21 catalog task types, remove the 9 repeated keys that shadow 9 types, add a schema-vs-catalog drift test (Gap 2) | S3 | worker + verify | landed in `92c04e9` (`feat(config): complete task param schema for all 21 catalog types`) — TaskType 21/21, literal keys 21 with 0 duplicates, 88 parameters; focused 384 passed, gate 72 → 64 with 0 new failures (L17) |
| T3 | Serialize the full mapped parameter set into the task CFX (money management, capital, SL/PT, sessions, complexity, broker) (Gap 1) | S1, S2, S4, S5, S6, S8 | worker + verify | `feat(customproject): serialize full param set into task CFX` |
| T4 | Align `generate_cfx_archive` arity and either register the stage or delete it (Gap 9) | S2 | inline | `fix(pipeline): align config builder stage with generator signature` |
| T5 | Wire `llm_config` into `campaign run-flow` so the LLM generation monitor actually runs (Gap 8) | S9, S10, S11 | worker + verify | landed in `f7b2247` (`feat(campaign): wire LLM generation monitor into run-flow`) — independent chain trace verified, gate certified against L15 |
| T6 | Replace the stubbed comparator with a real SQX-vs-JForex backtest comparison and a valid `phase_id` (Gap 3) | S6, S7, S8, S18 | worker + verify | `feat(pipeline): implement real backtest comparator` |
| T7 | Implement `BacktestAnalyzerStage` behind the existing analyzer prompt (Gap 4) | S7, S8, S18, S19 | worker + verify | `feat(pipeline): add backtest discrepancy analyzer stage` |
| T8 | Expose `/orders` and `/positions` on the JForex bridge and consume them on the Python side (Gap 6) | S9, S16 | worker + verify | `feat(jforex-bridge): expose orders and positions endpoints` |
| T9 | Drive deploy/start/stop through the real `QuantLabBridge` subprocess and retire the fictional CLI path (Gap 5) — recover the frozen implementation if it is intact, never rewrite from scratch by default | S16, S17, S20 | worker + verify | `feat(jforex): drive deploy through QuantLabBridge subprocess` |
| T10 | Implement an authenticated inbound control channel and a real ops surface (Gap 7) | S11, S12, S19 | worker + security review | `feat(ops): add authenticated inbound control channel` |
| T11 | Add verdict classification and campaign-outcome knowledge ingestion (Gap 7) | S13, S14, S15 | worker + verify | `feat(knowledge): add verdict classifier and outcome ingestion` |
| T12 | Restore full-suite collection: package `sdk/tests/sqx/` and resolve the duplicate test module basenames the in-flight WIP introduced (acceptance criterion 5) | — | inline (landed first, prerequisite) | `test: restore full-suite collection` — `0848c61` — **done**, verified at 4704 collected / 2 errors (T9's RED imports) |

T9 defers its Java-side tasks to `odd/tasks/jforex-bridge-architecture.md` (tasks 3-9 pending) and owns only the
Python-side rewiring plus the README correction for the nonexistent `bridge_jar` parameter.

## Risk classification

Risk items follow the orchestrator's high-risk list (1 data/irreversible, 2 security, 3 consumed contracts,
4 concurrency, 5 delivery/environment, 6 no test would catch a regression).

| Task | Risk | Reason |
|------|------|--------|
| T1 | none | Adds a logger; no behavior change beyond removing a `NameError`. |
| T2 | 3, 6 | The schema is the contract every mapper and validator reads. |
| T3 | 1, 3 | Changes the `.cfx` byte content SQX consumes; wrong values are hard to detect downstream. |
| T4 | 6 | Touches the CFX build path that no test currently exercises. |
| T5 | 6 | Enables LLM calls inside the production loop; a regression is invisible without a test. |
| T6 | 1, 6 | A wrong "similar" verdict is silent and sends unvalidated strategies to demo. |
| T7 | 6 | Introduces LLM judgement into a decision that gates deployment. |
| T8 | 2, 6 | Exposes account and order data over the bridge REST surface. |
| T9 | 5 | Changes how artifacts are delivered to the JForex deployment target. |
| T10 | 2 | Creates a remote channel able to execute commands on the QuantLab host. |
| T11 | 6 | Probabilistic classification writes into the knowledge base the user flagged as unreliable. |
| T12 | 6 | Touches the test infrastructure that gates every other task; a wrong fix makes the suite silently collect fewer tests. |

## Acceptance criteria (all tasks)

1. Each fixed behavior has one RED test per `S#` it covers, asserting the rule's observable effects, and one test proving the previously existing behavior still holds for each command or option touched.
2. Tests exercise the public interface only, never internal storage; mutating tests run against isolated state.
3. No task closes while its focused tests fail, and no task may raise the full-suite failure count above the baseline recorded in L15. A green suite is not achievable yet: the in-flight WIP arrives with 72 pre-existing failures. The gate is therefore "no new failures and no lost collection", reported as an explicit delta.
4. Help text and docs describing any changed command, option, or message are updated in the same commit.
5. `SQX_FORCE_MOCK=1 python3 -m pytest -q` closes every task with the collection-blocking files ignored, and is reported as a delta against the L15 baseline (`72 failed, 4543 passed, 60 skipped`; 4704 collected). T12 restored collection, so the only ignored files until T9 lands are T9's two RED modules. Never report the suite as green while that baseline is red.

## Rollback

Each task is a single path-scoped commit on `feature/gap-remediation`, revertible independently with
`git revert <commit>` without touching unrelated work. T3 and T6 are the only tasks whose revert changes
generated artifacts: T3 changes `.cfx` output and T6 changes comparison verdicts, so both are reverted behind
their own focused tests. No task in this feature mutates stored data, so no data rollback is required.

## Log

**L1** — User's original request for this feature, verbatim:

> "Arma el documento ODD para todos los gaps que encontraste vamos a corregirlos todos."

**L2** — Requirement source. The 20 specs above are quoted verbatim from the campaign specification the user
supplied earlier in the same session (installer flow, exploration pipeline, configuration and deployment
pipeline). No requirement was added from the task description.

**L3** — User decision preceding L1: the user asked "Explicame los 10 gaps como nos benefician." and then
authorized remediation of all ten. The benefit framing that informed the ordering was accepted as the basis
for this plan; prioritization (T1 → T5 → T2+T3 → T6+T7 → T10 → T8+T9 → T4) is recorded in `## Tasks`.

**L4** — Evidence, read-only reconnaissance (parent, same session). Verified by reading the working tree, not by
executing code: the 10 gaps in `## Evidence`, the discovery that the legacy path hardcodes `AccountSize=10000`
while the default Custom Project path writes no money management, and the observation that
`ConfigBuilderStage` has no production call site. Observations marked *read-only* must be confirmed at runtime
during their task.

**L5** — Environment decision (parent). Reconnaissance found 119 in-flight entries (18 modified, 101 untracked;
1088 insertions) on `feature/installer-block-a`, including uncommitted edits to two files this feature also
touches (`sdk/quantlab/pipeline/stages/jforex_deploy_stage.py`, `sdk/quantlab/sqx/cli_wrapper.py`). Decision:
create `feature/gap-remediation` from `c02e103` carrying that WIP untouched and commit only the paths each task
owns. No stash, no reset, and no reordering of the user's uncommitted work.

**L6** — Known overlap (parent). Gap 5 is already planned as tasks 3-9 of `odd/tasks/jforex-bridge-architecture.md`
(its task 5, "Rewrite `sdk/quantlab/jforex/strategy_bridge.py` to call bridge subprocess", is the same work as
T9's Python half). T9 references that document and must not re-plan its Java tasks; task 2 of that document
remains in progress and is not claimed here.

**L7** — Repository condition (parent). `git checkout` prints a Git LFS hook failure (`git-lfs` not on PATH)
and exits non-zero while still switching branches. This is pre-existing repository configuration, unrelated to
this feature; branch switches must be verified with `git branch --show-current` rather than the exit code.

**L8** — Blocker discovered while closing T1 (parent). The full suite cannot collect at all on the current
working tree: `SQX_FORCE_MOCK=1 python3 -m pytest -q` interrupts with 4 collection errors.

- `sdk/tests/sqx/test_http_client.py` and `sdk/tests/sqx/test_templates.py` are new *untracked* files whose
  bare module names collide with the tracked `tests/phase4/test_http_client.py` and
  `tests/phase4/test_templates.py` (`sdk/tests/sqx/` has no `__init__.py`, while `tests/sqx/` does).
- `sdk/tests/quantlab/jforex/test_strategy_bridge.py` and `.../test_strategy_bridge_integration.py` are also
  new *untracked* files and fail with `ImportError: cannot import name 'BridgeError' from
  'quantlab.jforex.strategy_bridge'`.

This is introduced by the in-flight WIP, not by this feature. Verified by inspection that no *tracked* pair of
test files collides under bare-module naming, so `HEAD` collects cleanly. Consequence: acceptance criterion 5
was unachievable as originally written and has been reworded, and T12 was added as a prerequisite for the
suite gate. The 2 `BridgeError` errors are not a separate defect — they are the RED tests for T9.

**L9** — Recovery lead for T9 (parent). `sdk/quantlab/jforex/strategy_bridge.py` is tracked and clean at `HEAD`
and is 114 lines long, delegating to the fictional `{jforex_home}/bin/jforex` CLI (Gap 5). Two frozen native
review candidate trees exist under `.git/gentle-ai/candidate-views/` and both differ from `HEAD`:

- `2ed16832-4737-4842-b343-816e3929b386` — 31 paths; its `sdk/quantlab/jforex/strategy_bridge.py` is 276 lines
  and contains `class BridgeError(RuntimeError)`, a `bridge_jar` constructor argument, and subprocess
  delegation to the QuantLabBridge fat-jar (JForex API 2.13.99 / DDS2 3.6.51). It also modifies
  `sdd/specs/jforex4-integration/spec.md`, `docs/runbooks/jforex-demo.md`, `sdk/quantlab/phase4/http_client.py`
  and `sdk/tests/jforex/test_jforex_integration.py`, and deletes `sdk/tests/jforex/test_strategy_bridge.py`.
- `ace0cff7-2749-4079-85bf-18f45440b0d3` — 17 paths, all installer consolidation (deletes
  `installer/internal/tools/opencode.go`, `installer/internal/opencode/managed.go`,
  `installer/internal/tui/screens/*`).

These are snapshots of *candidate* trees from earlier native reviews, not commits and not authority. T9 must
treat the first view as a reference implementation to recover and verify, not as approved code: the view is a
working-tree snapshot whose provenance beyond the review that froze it is not established. No such view is
mutated by this feature.

**L10** — Baseline for acceptance criterion 5 (parent). Full suite with the collection-blocking files ignored;
the recorded figure is the delta baseline every later task is compared against. Two attempts were discarded:
a first run interrupted at collection by the 4 errors below (before T12), and a second started in parallel with
an orphaned run from the previous turn (two overlapping suites in one tree is not reliable evidence). The
recorded measurement is a single clean run on the tree after T12, with only T9's two RED files ignored.

**L11** — T12 landed (commit `0848c61`, `test(tests): package new test dirs to restore full-suite collection`).
Symptom: `SQX_FORCE_MOCK=1 python3 -m pytest -q` interrupted with 4 collection errors — three `import file
mismatch` plus one `ImportError: cannot import name 'BridgeError'`. Root cause of the mismatches: `sdk/tests/sqx/`
(tracked, 3 test files) and the new `sdk/tests/quantlab/jforex/` were not Python packages, so their modules
imported under bare basenames colliding with `tests/phase4/test_http_client.py`, `tests/phase4/test_templates.py`
and `sdk/tests/jforex/test_strategy_bridge.py`. Fix: three 0-byte `__init__.py` markers so module names are
path-qualified. They were deliberately **not** added to `sdk/tests/jforex_bridge/`, `sdk/tests/exploration/` or
`sdk/tests/optimization/`: their basenames are unique, and packaging `jforex_bridge/` would remove that directory
from `sys.path` and break its `from test_fixtures import ...` sibling import. Evidence: `pytest --collect-only -q`
went from 4 errors / 4673 collected to 2 errors / 4704 collected; the delta is exactly +21 from
`sdk/tests/sqx/test_http_client.py` and +10 from `sdk/tests/sqx/test_templates.py`, with zero test ids lost
(`comm` of the two collection lists by id). The 2 remaining errors are T9's RED `BridgeError` imports, untouched
by T12; until T9 lands, the suite gate records runs with those 2 files ignored.

**L12** — Defect discovered while running the gate (parent, not fixed here; different path and concern). The
in-flight WIP added to `pytest.ini` an `env = SQX_FORCE_MOCK / QUANTLAB_SQX_USE_HTTP / QUANTLAB_JFOREX_BRIDGE`
block commented as "Default to HTTP API for tests (feature flag)", but `pytest-env` is neither installed locally
nor declared in `sdk/pyproject.toml`, so pytest reports `PytestConfigWarning: Unknown config option: env` and the
three variables are never set by a plain `pytest` invocation. Only the shell prefix (`SQX_FORCE_MOCK=1 pytest`),
which the gate command and CI both use, actually forces the mock. Consequence: the block is dead config that
reads as protection it does not provide — a plain `pytest` run would not force the mock. Reported to the user for
a decision (declare `pytest-env` in the `dev` extra, or drop the block); no task claims it yet.

**L13** — T1 evidence (parent, pending its suite gate). Gap 10's fix and its RED tests are in the working tree:
`sdk/quantlab/pipeline/stages/jforex_deploy_stage.py` gains `import logging`, a module-level
`logger = logging.getLogger(__name__)`, the `_write_to_kb` Knowledge Lake write of deployment failures, and the
call site that writes them under `deployment_failures`. RED observed by removing only the
`logger = logging.getLogger(__name__)` line: `test_knowledge_lake_write_failure_is_logged_not_raised` fails
(1 failed) because the `logger.warning` in the `except` block raises with no module logger, which is exactly the
pre-fix state the gap recorded. GREEN after restoring the line: `sdk/tests/pipeline/test_jforex_pipeline_e2e.py`
13 passed, covering the four pre-existing deploy behaviours plus the two Gap 10 behaviours. The commit for T1
necessarily carries the whole `jforex_deploy_stage.py` path, including the Knowledge Lake write that arrived with
the in-flight WIP; the two cannot be separated because the logger only exists to serve that write path. After the split (L14) that commit is `1168916`.

**L14** — In-flight WIP split, executed (user decision, parent). The user chose thematic checkpoints plus one
labeled snapshot commit over a single rescue commit. Executed in three steps.

1. Safety net first, verified rather than declared: annotated tag `wip-snapshot-20261013-040034` on `0848c61`
   (the pre-split HEAD), a full-tree archive `.git/wip-backups/wip-20261013-040034.tar.gz` (378 MiB, 29 385
   entries) and a manifest of 267 paths with one `sha256` each. Verification extracted all 267 files from the
   archive and compared them hash by hash against the working tree: 267/267 identical, and all 267 still present.
   The archive lives under `.git/`, so `git status` never sees it. `.gitignore` does not delete files; nothing was
   deleted by this work.
2. Every path assigned before anything was committed: 275 entries (256 untracked + 19 modified) sorted into 19
   checkpoint groups with zero unassigned paths (`split-plan.txt` and `split-paths.txt` sit in the same backup
   directory).
3. 21 path-scoped commits on `feature/gap-remediation`, each staged with explicit paths and each verified by
   comparing `HEAD` before and after. Order: C01 installer → C02/C03/C04 sqx → C05 exploration → C06
   customproject → C07 pipeline → C08 optimization → C09 analysis → C10 agents → C11/C12 `jforex_bridge` →
   C13 bridge (QuantLabBridge) → C14 strategies → C15 cli → C17 odd docs → C16a/b/c CI, pytest config and docs →
   C-LAST labeled snapshot → this document. Commits: `b13b598`, `9f3f31d`, `60a27a3`, `80e9cd0`, `05ca0e9`,
   `5e1cc61`, `1168916`, `fb0bb13`, `5083569`, `122b597`, `855a4bb`, `fa163d1`, `874c794`, `a84bd5b`, `725f2c6`,
   `738bce5`, `8431fbb`, `7faa206`, `57c31de`, `0006134`, `72361bc`.

Where the doubtful artifacts went: `knowledge/deployment_failures/*` and `knowledge/structured/bayesopt_*/*`
(135 of the 275 paths) landed in the single labeled commit `0006134 chore(repo): snapshot runtime artifacts,
third-party metadata and tooling`, together with `bridge-jars/` (extracted Dukascopy JAR metadata) and `tools/`
(TUI logo generators). Evidence that these are runtime output rather than authored work: new files appeared in
those directories with 08:01-08:02 timestamps *after* the safety-net archive was taken, written by this session's
suite runs. Nothing was discarded and nothing was mixed into a code checkpoint. Git emitted a CRLF
normalization warning for three `bridge-jars` files as they were committed; the exact original bytes are
preserved in the archive.

Left untracked on purpose: `sdk/tests/quantlab/jforex/test_strategy_bridge.py` and
`test_strategy_bridge_integration.py` — T9's RED tests, which must arrive with T9's implementation.

Branch placement: the checkpoints landed on `feature/gap-remediation` itself, on top of `0848c61`, rather than on
`feature/installer-block-a`. That keeps one linear history and removes the rebase step the plan originally
carried (old T16, dropped). Consequence: the branch name no longer describes its whole content, and
`feature/installer-block-a` still sits at `c02e103` while its WIP now lives one branch over. Renaming or
re-splitting that arrangement is left to the user. State after the split: working tree clean except T9's two RED
files; `import quantlab...` OK; collection unchanged at 4704 collected / 2 errors.

**L15** — Full-suite baseline for acceptance criteria 3 and 5 (parent). One clean run on the post-T12 tree with
`-p no:randomly --tb=no -rf` and T9's two RED files ignored: `72 failed, 4543 passed, 60 skipped, 56 warnings in
588.67s`. Distribution of the 72: `tests/test_orchestrator_prompt.py` 24 (phase-agent registration in
`opencode.json`), `sdk/tests/optimization/` 15 (surrogate and bayesian optimiser), `tests/compiler/` 9,
`tests/substrate/` 9, `sdk/tests/test_kb.py` 8, `sdk/tests/test_version.py` 3, `tests/phase4/test_cli_main.py` 2,
`tests/knowledge/test_kb_reverify_cli.py` 2, `tests/dashboard/test_api.py` 1,
`tests/pipeline/test_stage_io_contracts.py` 1, `sdk/tests/test_cli.py` 1. These are pre-existing failures in the
in-flight WIP rather than regressions from this feature, and no task claims them yet; the 24 registration
failures are consistent with the WIP adding agents that `opencode.json` does not register. Raw output:
`/tmp/gentle-jobs-y1bZMg/baseline-suite.txt`. Criteria 3 and 5 were reworded to a delta gate against this figure
for that reason.

**L16** — T5 landed (commit `f7b2247`, `feat(campaign): wire LLM generation monitor into run-flow`). The single
broken link was the CLI: `cmd_campaign_run_flow` built `ctx.config` without `llm_config` while
`ResearchConfig.llm_config`, `DispatchStage`, `BuilderAgent._dispatch_single`, `dispatch_campaign` and
`_spawn_llm_monitor` already accepted it end to end. The fix seeds the key only when the config declares it, so a
config without the block spawns no LLM calls and stays byte-identical to the orchestrated default. RED was
observed first (`tests/campaign/test_run_flow_llm_wiring.py`: 1 passed / 1 failed), then GREEN (2 passed); 54
focused tests passed in total. Independent verification by `gentle-ai-verify` traced all eight links with
`path:line` evidence, found no regression (nothing serialises, hashes, snapshots or freezes the `ctx.config` key
set, and every consumer reads it with `.get`), and confirmed the new test is a genuine regression guard; it also
surfaced the pre-existing contract guard `tests/builder/test_dispatch_hooks.py`. Gate against L15, invoked
identically: `65 failed, 4583 passed, 60 skipped`. The failure-set diff by node id is exactly `72 - 7 + 0 new`:
seven baseline failures, all in `tests/substrate/`, now pass, and no baseline failure regressed. The cause of
those seven is not established here — they exercise the mock/substrate parity path the in-flight WIP touches, and
the WIP split is the only tree change between the two runs. Collection grew from 4675 to 4708 with T12's
collection fix; `60 skipped` is unchanged.

**L16a** — Gate instrumentation defect (parent, corrected in process). The first gate run (`job-6`, `64 failed,
4584 passed`) was captured with `| tail -50`, so only 49 of its `FAILED` lines survived and the comparison was
unprovable; `.pytest_cache/v/cache/lastfailed` is not a substitute because it is a historical union (283 entries,
including collection errors from a dead run — a sampled entry passed 10/10 on re-run). Re-running with a full-file
capture (`job-7`, `/tmp/gentle-jobs-y1bZMg/suite-t5-full.log`) produced the certified diff above. A one-test
difference between the two identical runs (64 vs 65 failures) is a pre-existing flaky baseline failure rather than
a T5 regression: both failure sets are subsets of L15. Rule adopted for every later gate: capture the suite to a
file, never through `tail`, and diff failure sets by node id.

**L17** — T2 closed (Gap 2, commit `92c04e9`). The assigned worker timed out after extending `TaskType` from 14 to 21
members but before touching a single schema, leaving no report and no evidence; the parent completed the unit
inline over the worker's own (good) drift test, which is why the route column still reads worker + verify: the
worker's RED and its test survived, the parent wrote the fix. Measured before the fix: `TASK_PARAM_SCHEMAS`
declared 23 literal keys but only 14 reached runtime because 9 keys were repeated verbatim, so the later
definition shadowed the earlier one, and 7 of the 21 catalog types had no schema at all. Now: `TaskType` = 21
members, literal keys = 21 with 0 duplicates, 88 parameters. Method worth reusing: the duplicate block was
deleted only after confirming the two blocks were byte-identical in content, and the **first** block was kept
because re-assigning an existing dict key preserves its insertion position, so the runtime key order is unchanged;
keeping the second block instead would have silently moved those 9 keys. The independent verifier re-derived all
of this against `HEAD` and confirmed the order claim, that the 9 previously shadowed types keep their parameter
sets (Build 54, Filtering 1, Retest 2, GoToTask 2, Optimize 2), that no consumer assumes a non-empty schema — two
entries are now legitimately empty — and that the drift test genuinely fails on a removed entry or a re-added
duplicate key rather than being a tautology. The 7 new entries are evidence-backed for CallExternalScript
(`file`, `params`, `type`, `waitfor`, `hours`, `minutes`), ClearDatabanks (`databank`), DeleteFile (`file`),
Notification (`type`, `email`, `wait`) and StopAndStart (`startAnother`, `projectName`, `skipToFirstProject`),
extracted from the SQX 144/2953 install (`internal/plugins/<Task>/task.xml` default settings plus the
`simpleSettings.html` UI bindings). ApplyMassConfig and NeuralNetworkTrainer are declared empty with an explicit
TODO naming the task JARs, because their settings are compiled and no readable source names their parameters;
the rule that no parameter may be invented is enforced by a test, not by a comment. Two facts to keep:
`sdd/specs/custom-project-generator/spec.md:76` already required all 21 catalog types, so this closed a
code-vs-spec drift rather than changing a requirement; and `ruff` on the touched module improved from 7 findings
at `HEAD` to 4, the remaining 4 being pre-existing (`F401` at :21, `F841` at :952, :1024, :1025 — the last two
sitting in the still-dead `map_exploration_to_task_params` body that T3 has to bring to life). RED/GREEN: the
drift test failed 2 of its 4 cases before the change and passes 7 of 7 after, with focused suites at 384 passed /
23 skipped. Gate (`job-8`, `/tmp/gentle-jobs-y1bZMg/suite-t2-full.log`): 64 failed / 4591 passed / 60 skipped,
nodeid-set diff against L15 = 72 − 8 + 0, 0 new failures, 8 recoveries all in `tests/substrate/` (the same flaky
family L16 recorded), collection 4675 → 4715 with the 7 new drift tests among the additions.
