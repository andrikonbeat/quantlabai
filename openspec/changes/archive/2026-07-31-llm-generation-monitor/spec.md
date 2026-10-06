# Delta: LLM Generation Monitor

Change: `llm-generation-monitor` | Affects: `llm-generation-monitor` (new), `campaign-monitor`, `sqx-cli-wrapper`

## llm-generation-monitor (New Capability — Full Spec)

### Purpose

An LLM-capable monitor that runs beside `CampaignMonitor` during generation, reasons over live status text + databank counts + baseline, and recommends `continue|stop` (Phase 1) so a doomed campaign (e.g. 58 generated, 0 accepted) can be stopped mid-run. Heuristics remain the always-on fallback.

### Requirement: LLM Verdict Polling

The system MUST run the LLM poll on a slow cadence — every N-th poll, with N configurable — while heuristics continue every poll. Each LLM poll SHALL build a compact prompt from: live status text, `-databank action=list` record counts, log tail (when present), and the campaign baseline (expected generations, population, timeframe, WF/MC, criteria).

#### Scenario: LLM polled on slow cadence, heuristics every poll

- GIVEN a running campaign with heuristics polling every 5s
- WHEN the monitor reaches the N-th poll
- THEN one LLM request is sent containing status text, databank counts, and baseline
- AND heuristic polling continues unchanged between LLM polls

### Requirement: Verdict Schema

The LLM SHALL return a strict JSON verdict: `{"assessment": str, "severity": str, "detected_issues": [str], "recommended_action": "continue"|"stop", "confidence": float, "reasoning": str}`. Invalid, missing, or malformed JSON SHALL dispatch no action and SHALL be treated as `continue` with a logged warning. Phase 1 accepts only `continue|stop`.

#### Scenario: Invalid verdict JSON treated as continue

- GIVEN an LLM response that is not valid JSON or lacks required fields
- WHEN the monitor parses the verdict
- THEN no action is dispatched
- AND the poll is treated as continue with a warning logged

### Requirement: ActionExecutor

The system MUST map `recommended_action: stop` to the existing cancel path (`monitor.cancel()` / `-project action=stop name=<campaign>`) and `continue` to a no-op. No other campaign mutation SHALL occur.

#### Scenario: Stop verdict uses the cancel path

- GIVEN an approved stop verdict
- WHEN ActionExecutor executes it
- THEN the same cancel/stop path used by CampaignMonitor is invoked
- AND no other campaign mutation occurs

#### Scenario: Continue verdict is a no-op

- GIVEN a continue verdict
- WHEN ActionExecutor executes it
- THEN no subprocess command is dispatched
- AND monitoring continues

### Requirement: Safety Rails

The system MUST gate every verdict on a confidence threshold: verdicts below the threshold SHALL NOT dispatch an action. A `stop` verdict SHALL require human confirmation before execution. The LLM SHALL run on a slow cadence and SHALL reuse the `LLMCircuitBreaker` pattern from `llm_research_agent`.

#### Scenario: Zero-acceptance campaign stops early after human confirm

- GIVEN a campaign generating strategies with 0 accepted and databank counts not growing
- WHEN the LLM recommends stop with confidence above the threshold
- THEN a stop confirmation prompt is shown
- AND on approval the campaign is stopped before the task ends

#### Scenario: Low-confidence verdict never dispatches

- GIVEN an LLM verdict with confidence below the threshold
- WHEN the monitor evaluates the verdict
- THEN no action is dispatched
- AND monitoring continues unchanged

### Requirement: Graceful Degradation

The system MUST fall back to heuristics on any LLM failure (API error, timeout, open circuit breaker). LLM failure SHALL NOT crash the campaign or the dispatch loop, and SHALL NOT alter `CampaignMonitor` behavior.

#### Scenario: LLM failure leaves heuristics running

- GIVEN the circuit breaker is open or the LLM API errors
- WHEN the monitor's LLM poll runs
- THEN no exception propagates to the dispatch loop
- AND CampaignMonitor heuristics continue polling normally

### Requirement: Defensive Parsing

The system MUST parse status text and databank counts defensively: both `Strategies generated  N` and `Strategies generated: N` variants SHALL be accepted, and any parse failure SHALL be tolerated (count treated as unknown, logged) rather than raising.

#### Scenario: Unknown databank format is tolerated

- GIVEN `-databank action=list` output in an unexpected format
- WHEN the monitor parses it
- THEN the failure is logged and counts are treated as unknown
- AND status text is still used in the verdict prompt

## campaign-monitor (Modified Capability — ADDED Requirements)

### Requirement: Databank Observability

The system MUST poll `-databank action=list` as part of monitor observability and SHALL surface record counts as a live zero-acceptance signal (counts not growing while generation count grows). Parse failure of databank output SHALL be tolerated. Existing heuristic events SHALL remain unchanged.

#### Scenario: Databank counts reveal zero-acceptance

- GIVEN a campaign whose record count does not grow while generation count increases
- WHEN the monitor polls databank counts
- THEN the counts are included in the monitor snapshot for the LLM monitor
- AND existing heuristic events are unchanged

#### Scenario: Databank parse failure tolerated

- GIVEN databank output that cannot be parsed
- WHEN the monitor polls it
- THEN the monitor continues without error
- AND heuristic polling is unaffected

## sqx-cli-wrapper (Modified Capability — ADDED Requirements)

### Requirement: Databank List Command

The CommandDispatcher MUST support `-databank action=list` and SHALL return per-databank record counts in a structured result.

#### Scenario: Databank list returns record counts

- GIVEN a running SQX project
- WHEN `-databank action=list` is dispatched
- THEN a structured result with per-databank record counts is returned

### Requirement: LLM Monitor Dispatch Hook

`dispatch_campaign` MUST accept an optional LLM-monitor hook mirroring `on_watcher_event`. The hook SHALL be opt-in and disabled by default; when not registered, `dispatch_campaign` SHALL behave exactly as before.

#### Scenario: Hook not registered preserves behavior

- GIVEN `dispatch_campaign` called without the LLM-monitor hook
- WHEN the campaign runs
- THEN the dispatch loop behaves exactly as before this change
- AND no LLM requests are made

#### Scenario: Registered hook receives verdicts

- GIVEN the LLM-monitor hook registered
- WHEN a verdict is produced
- THEN the hook is invoked with the verdict

## Acceptance Criteria

- [ ] Mocked zero-acceptance campaign triggers a `stop` recommendation before task end
- [ ] Low-confidence verdicts never dispatch an action
- [ ] LLM failure falls back to heuristics with zero disruption
- [ ] Existing 530+ tests pass; new tests cover verdict→action mapping
