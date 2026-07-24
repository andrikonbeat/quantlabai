# Human Gates Guide

Guide to configuring and using human gate checkpoints in the Multi-Agent Research System.

## Overview

Human gates are intentional pause points in the research pipeline where human expertise is required to review progress, make decisions, or provide guidance before proceeding to the next phase. The Multi-Agent Research System includes 5 standard human gates that align with key decision points in the research workflow.

## Gate Philosophy

The system implements a "human-in-the-loop" approach where:
- Automation handles repetitive, data-intensive tasks
- Humans provide strategic oversight and domain expertise
- Gates ensure quality control at critical junctures
- Clear escalation paths prevent pipeline stagnation
- All gate interactions are recorded for audit and learning

## The 5 Standard Gates

The Multi-Agent Research System defines these standard gates:

| Gate ID | Position | Purpose | Typical Reviewers |
|---------|----------|---------|-------------------|
| `gate_research_complete` | After ResearchAgent | Validate research hypotheses | Quant Researchers |
| `gate_after_builder` | After BuilderAgent | Review compiled strategies | Strategy Developers |
| `gate_after_statistics` | After StatisticsAgent | Evaluate statistical validity | Quantitative Analysts |
| `gate_after_reviewer` | After ReviewerAgent | Assess overall strategy quality | Senior Researchers |
| `gate_pre_deployment` | After PortfolioAgent | Final pre-deployment check | Risk Managers & Traders |

## Gate Configuration

Gates are configured in the pipeline YAML under the `gates` section:

```yaml
gates:
  - id: gate_research_complete
    name: "Research Complete"
    description: "Review initial hypotheses before building strategies"
    timeout_hours: 24
    fallback: "continue"
    required_agents: [research-agent]
    notification:
      email: ["research-team@example.com"]
      slack: "#quant-research"
    approval_criteria:
      - "At least 3 testable hypotheses generated"
      - "Each hypothesis has clear entry/exit rules"
      - "No look-ahead bias detected"
```

### Gate Fields Explained

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique identifier (used in code callbacks) |
| `name` | string | yes | Display name for CLI and UI |
| `description` | string | no | Detailed purpose and context |
| `timeout_hours` | integer | yes | Hours before automatic fallback |
| `fallback` | string | yes | Action on timeout: `continue`, `abort`, `escalate` |
| `required_agents` | list | no | Agents that must finish before gate activates |
| `notification` | object | no | Alert configuration when gate activates |
| `approval_criteria` | list | no | Guidelines for human reviewers |

## Gate Lifecycle

### 1. Activation
A gate activates when:
- All `required_agents` have completed their stages
- The pipeline reaches the gate's position in the execution order
- No active gate is currently blocking the pipeline

### 2. Notification
When a gate activates:
- The pipeline pauses execution
- Configured notifications are sent (email, Slack, webhook)
- The gate appears in `quantlab pipeline list` output
- ResearchDirector logs the gate activation event

### 3. Human Review
Human reviewers should:
1. Examine the current pipeline state and outputs
2. Review any artifacts produced by preceding stages
3. Evaluate against the `approval_criteria` (if provided)
4. Make a decision: approve, request changes, or escalate

### 4. Resolution
Reviewers resolve the gate via:
- **CLI Approval**: `quantlab gate approve <gate-id> --comment "Looks good"`
- **CLI Rejection**: `quantlab gate reject <gate-id> --comment "Needs revision"`
- **API Call**: External systems can call the gate approval API
- **Automatic Timeout**: After `timeout_hours`, the `fallback` action executes

## Gate Actions

### Approve (`continue`)
- Pipeline resumes normal execution
- Decision recorded to Engram and Knowledge Lake
- Next stage begins processing
- Appropriate success logging occurs

### Request Changes (`revise`)
- Pipeline pauses for specified duration
- Feedback sent to relevant agents
- Affected stages may re-execute with new guidance
- Iteration counter increments

### Escalate (`escalate`)
- Notification sent to escalation contacts
- Gate remains active until higher authority responds
- May trigger alternative workflow paths

### Abort (`abort`)
- Pipeline terminates immediately
- Cleanup procedures execute
- Failure recorded with reason
- Resources released for other workflows

### Continue (`continue` - timeout fallback)
- Pipeline proceeds despite lack of human input
- Warning logged to audit trail
- Used for low-risk gates or time-sensitive operations

## Gate Implementation

### ResearchDirector Integration
The ResearchDirector manages gate execution through:

1. **Gate Detection**: PipelineRunner identifies gate positions
2. **Activation**: ResearchDirector pauses pipeline and sends notifications
3. **Callback Execution**: Registered approval/rejection handlers execute
4. **State Persistence**: Gate decisions saved to Engram for audit
5. **Resumption**: Pipeline continues based on decision outcome

### Custom Gate Creation
To add custom gates:

1. **Define in YAML**: Add gate configuration to `gates` section
2. **Implement Callback**: Create async function handling decisions
3. **Register Callback**: Use `research_director.register_gate_callback(gate_id, callback)`
4. **Test Thoroughly**: Verify timeout, notification, and resume behavior

Example callback:
```python
async def my_gate_callback(context: dict, gate_id: str, decision: GateDecision) -> None:
    """Handle gate decision."""
    if decision.action == "approve":
        # Proceed with next steps
        await notify_team(f"Gate {gate_id} approved: {decision.reason}")
    elif decision.action == "revise":
        # Request changes
        await request_revisions(decision.feedback)
```

## Best Practices

### For Pipeline Designers
- Place gates after major milestones or before resource-intensive steps
- Keep gate criteria clear, objective, and measurable
- Set appropriate timeouts based on team responsiveness
- Use escalation paths for critical gates
- Document the rationale for each gate

### For Human Reviewers
- Review all `required_agents` outputs before deciding
- Focus on the `approval_criteria` if provided
- Consider both quantitative metrics and qualitative factors
- Provide specific, actionable feedback when requesting changes
- Escalate promptly if outside your expertise

### For Automation
- Design agents to gracefully handle pause/resume cycles
- Ensure deterministic behavior for identical inputs
- Clear temporary files during long pauses if needed
- Validate all inputs after resumption (system state may have changed)

## Gate Monitoring

### CLI Commands
```bash
# List all gates and their status
quantlab pipeline list --show-gates

# View details for a specific gate
quantlab pipeline list --show-gates

# Approve a gate (when notified)
quantlab gate approve gate_research_complete --comment "Approved 3 strong hypotheses"

# Reject a gate with feedback
quantlab gate reject gate_after_builder --comment "Strategy compilation failed - check SQX logs"
```

### API Endpoints
- `GET /api/v1/gates` - List all gate statuses
- `GET /api/v1/gates/{gate_id}` - Get specific gate details
- `POST /api/v1/gates/{gate_id}/approve` - Approve gate
- `POST /api/v1/gates/{gate_id}/reject` - Reject gate
- `POST /api/v1/gates/{gate_id}/escalate` - Escalate gate

### Monitoring Artifacts
Gate activities are recorded in:
- **Engram**: `gate/{gate_id}/{timestamp}` - Decision metadata
- **Knowledge Lake**: `gates/{gate_id}/` - Decision logs and feedback
- **Pipeline History**: Gate timestamps and decisions in run metadata
- **Audit Log**: All gate activities for compliance

## Integration with Research Workflow

### Typical Gate Usage

#### Gate 1: Research Complete (`gate_research_complete`)
**When**: After hypothesis generation, before strategy building
**Review**: 
- Are hypotheses novel and testable?
- Do they have clear economic rationale?
- Is there sufficient data to support investigation?
**Outcome**: Approved hypotheses proceed to builder; rejected ones are refined

#### Gate 2: Post-Build Review (`gate_after_builder`)
**When**: After strategy compilation, before statistical analysis
**Review**:
- Did all strategies compile successfully?
- Are there any compilation warnings or errors?
- Do the compiled strategies match the intended logic?
**Outcome**: Successfully compiled strategies proceed; failed ones return to builder

#### Gate 3: Statistical Validation (`gate_after_statistics`)
**When**: After statistical analysis, before qualitative review
**Review**:
- Do results show statistical significance?
- Are confidence intervals reasonable?
- Any signs of overfitting or data mining bias?
**Outcome**: Statistically significant strategies proceed; others analyzed for flaws

#### Gate 4: Quality Review (`gate_after_reviewer`)
**When**: After statistical analysis, before portfolio construction
**Review**:
- Does strategy meet qualitative quality standards?
- Is it robust across different market regimes?
- Implementation complexity reasonable?
**Outcome**: High-quality strategies proceed to portfolio construction

#### Gate 5: Pre-Deployment (`gate_pre_deployment`)
**When**: After portfolio construction, before live deployment
**Review**:
- Does portfolio meet risk limits and constraints?
- Is capital allocation appropriate?
- Operational readiness confirmed?
**Outcome**: Approved portfolios proceed to deployment; others revised

## Custom Gate Examples

### Volatility Regime Gate
```yaml
gates:
  - id: gate_volatility_check
    name: "Volatility Regime Check"
    description: "Ensure strategy performs in current volatility regime"
    timeout_hours: 6
    fallback: "continue"
    required_agents: [statistics-agent, reviewer-agent]
    notification:
      email: ["risk-team@example.com"]
    approval_criteria:
      - "Strategy Sharpe > 1.0 in both high and low volatility periods"
      - "Max drawdown < 15% during volatility spikes"
```

### Compliance Check Gate
```yaml
gates:
  - id: gate_compliance_review
    name: "Compliance Review"
    description: "Verify strategy meets regulatory requirements"
    timeout_hours: 48
    fallback: "abort"
    required_agents: [portfolio-agent]
    notification:
      email: ["compliance@example.com"]
      escalation: ["chief-compliance-officer@example.com"]
    approval_criteria:
      - "No prohibited instruments or strategies"
      - "Position limits adhered to"
      - "Transaction costs modeled accurately"
      - "Reporting capabilities verified"
```

## Troubleshooting

### Gate Not Activating
**Symptoms**: Pipeline proceeds without pausing at expected gate
**Checks**:
1. Verify `required_agents` have actually completed
2. Check gate position in `stages` list matches expectation
3. Confirm gate `id` matches what ResearchDirector expects
4. Look for activation logs in ResearchDirector output

### No Notifications Received
**Symptoms**: Gate activates but team doesn't get alerts
**Checks**:
1. Verify notification configuration in YAML
2. Check email/SMS service connectivity
3. Validate webhook endpoints are reachable
4. Look for notification errors in ResearchDirector logs

### Gate Stuck in Pending State
**Symptoms**: Gate shows as active but no resolution possible
**Checks**:
1. Verify approval/rejection CLI commands target correct gate ID
2. Check if gate already timed out and fell back
3. Confirm ResearchDirector is still running (not crashed)
4. Examine Engram records for any decision attempts

## Security Considerations

### Access Control
- Gate decisions should be restricted to authorized personnel
- Consider implementing RBAC for gate operations
- Audit all gate actions for compliance
- Use secure channels for notification delivery

### Data Protection
- Gate feedback may contain sensitive strategy information
- Ensure approval/rejection channels are secure
- Consider encrypting highly sensitive gate communications
- Retention policies should align with data governance requirements

## See Also

- [Agent Reference](agents.md) - Understand what each stage produces
- [Pipeline Configuration Reference](pipeline.md) - Full YAML specification
- [Running Multi-Agent Campaigns](../guides/running-campaigns.md) - Execution procedures
- [Research Director API](../sdk/quantlab/agents/research_director.md) - Technical details