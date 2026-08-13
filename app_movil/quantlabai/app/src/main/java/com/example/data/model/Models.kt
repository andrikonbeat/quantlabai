package com.example.data.model

data class SystemHealth(
    val openCodeOnline: Boolean = true,
    val orchestratorRunning: Boolean = true,
    val sqxOnline: Boolean = true,
    val dataPipelineOnline: Boolean = true,
    val databaseOnline: Boolean = true,
    val activeWorkers: Int = 8,
    val totalWorkers: Int = 10,
    val cpuUsagePct: Int = 42,
    val ramUsagePct: Int = 61,
    val storageUsagePct: Int = 73,
    val apiHealthy: Boolean = true
) {
    val totalOperational: Int
        get() = (if (openCodeOnline) 1 else 0) +
                (if (orchestratorRunning) 1 else 0) +
                (if (sqxOnline) 1 else 0) +
                (if (dataPipelineOnline) 1 else 0) +
                (if (databaseOnline) 1 else 0)
}

enum class CampaignStatus {
    ACTIVE, COMPLETED, PAUSED, ATTENTION, FAILED, ARCHIVED
}

enum class PipelineStage {
    HYPOTHESIS, RESEARCH, DATA, GENERATION, ROBUSTNESS, PORTFOLIO, APPROVAL
}

data class Campaign(
    val id: String,
    val name: String,
    val asset: String,
    val timeframe: String,
    val objective: String,
    val hypothesis: String,
    val progressPct: Int,
    val currentStage: PipelineStage,
    val activeAgents: Int,
    val waitingAgents: Int,
    val generatedCount: Int,
    val passedFiltersCount: Int,
    val status: CampaignStatus,
    val lastEvent: String,
    val updatedAt: String
)

enum class AgentStatus {
    RUNNING, WAITING, IDLE, ERROR, PAUSED
}

enum class LogLevel {
    INFO, EXEC, WARN, ERROR, SUCCESS
}

data class AgentLogEntry(
    val id: String,
    val timestamp: String,
    val level: LogLevel,
    val message: String,
    val stepName: String? = null,
    val details: String? = null
)

data class Agent(
    val id: String,
    val name: String,
    val role: String,
    val status: AgentStatus,
    val currentTask: String,
    val campaignName: String,
    val runtime: String,
    val lastEvent: String,
    val currentInstruction: String,
    val generatedCount: Int = 0,
    val passedCount: Int = 0,
    val progressPct: Int = 0,
    val logs: List<AgentLogEntry> = emptyList()
)

enum class StrategyStatus {
    CANDIDATE, VALIDATED, REJECTED, LIVE, DEGRADED, REPLACEMENT_READY
}

data class Strategy(
    val id: String,
    val codeNumber: String,
    val asset: String,
    val timeframe: String,
    val score: Int,
    val status: StrategyStatus,
    val netProfit: String,
    val profitFactor: Float,
    val maxDrawdownPct: Float,
    val recoveryFactor: Float,
    val sharpeRatio: Float,
    val walkForwardPass: Boolean,
    val monteCarloPass: Boolean,
    val parameterStabilityPass: Boolean,
    val marketRegimePass: Boolean,
    val correlationStatus: String,
    val exposureStatus: String,
    val campaignId: String,
    val rejectionReason: String? = null
)

enum class ApprovalType {
    PORTFOLIO_INCLUSION, LIVE_DEPLOYMENT, STRATEGY_REPLACEMENT, PARAMETER_OVERRIDE, CAMPAIGN_ESCALATION
}

enum class ApprovalStatus {
    PENDING, APPROVED, REJECTED
}

data class ApprovalItem(
    val id: String,
    val strategyId: String,
    val title: String,
    val requestType: ApprovalType,
    val reason: String,
    val metricsSummary: String,
    val riskImpact: String,
    val recommendedAction: String,
    val status: ApprovalStatus = ApprovalStatus.PENDING,
    val timestamp: String
)

data class ActivityEvent(
    val id: String,
    val timestamp: String,
    val category: String, // Research, Agent, Strategy, Validation, Portfolio, Infrastructure, Human Decision, Error
    val source: String,
    val message: String,
    val context: String
)

enum class ChatSender {
    USER, AI, SYSTEM
}

enum class ChatContextType {
    GLOBAL, CAMPAIGN, AGENT, OPENCODE
}

data class ChatMessage(
    val id: String,
    val sender: ChatSender,
    val authorName: String,
    val content: String,
    val timestamp: String,
    val contextType: ChatContextType = ChatContextType.GLOBAL,
    val contextName: String = "Orchestrator",
    val strategyCardId: String? = null,
    val approvalCardId: String? = null,
    val actionText: String? = null,
    val actionType: String? = null
)

data class AutonomyPolicy(
    val researchAuto: Boolean = true,
    val generationAuto: Boolean = true,
    val validationAuto: Boolean = true,
    val replacementSearchAuto: Boolean = true,
    val portfolioInclusionApproval: Boolean = true,
    val liveDeploymentApproval: Boolean = true,
    val strategyDeletionApproval: Boolean = true
)

data class PipelineRun(
    val runId: String,
    val pipelineName: String,
    val status: String,
    val startedAt: String,
    val completedAt: String?,
    val duration: Double,
    val error: String?
)

data class Stats(
    val sharpeMean: Double,
    val sharpeStd: Double,
    val maxDrawdownPct: Double,
    val winRateMean: Double,
    val totalTrades: Int,
    val benchmarkComparison: String?,
    val totalCampaigns: Int,
    val totalPipelineRuns: Int,
    val generatedAt: String
)
