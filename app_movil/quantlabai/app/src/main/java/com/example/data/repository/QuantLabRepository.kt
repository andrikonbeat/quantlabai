package com.example.data.repository

import com.example.data.local.CampaignEntity
import com.example.data.local.HealthEntity
import com.example.data.local.PipelineRunEntity
import com.example.data.local.QuantLabDatabase
import com.example.data.local.StatsEntity
import com.example.data.model.*
import com.example.data.remote.ApiService
import com.example.data.remote.NetworkModule
import com.example.data.remote.model.ApiCampaign
import com.example.data.remote.model.ApiCampaignDetail
import com.example.data.remote.model.ApiEnvelope
import com.example.data.remote.model.ApiHealth
import com.example.data.remote.model.ApiPipelineRun
import com.example.data.remote.model.ApiStats
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.withContext
import java.io.IOException
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class QuantLabRepository internal constructor(
    private val apiService: ApiService = NetworkModule.apiService,
    private val databaseProvider: (() -> QuantLabDatabase?)? = null
) {

    private val database: QuantLabDatabase? get() = databaseProvider?.invoke()

    private val _systemHealth = MutableStateFlow(SystemHealth())
    val systemHealth: StateFlow<SystemHealth> = _systemHealth.asStateFlow()

    private val _campaigns = MutableStateFlow(initialCampaigns())
    val campaigns: StateFlow<List<Campaign>> = _campaigns.asStateFlow()

    private val _agents = MutableStateFlow(initialAgents())
    val agents: StateFlow<List<Agent>> = _agents.asStateFlow()

    private val _strategies = MutableStateFlow(initialStrategies())
    val strategies: StateFlow<List<Strategy>> = _strategies.asStateFlow()

    private val _approvals = MutableStateFlow(initialApprovals())
    val approvals: StateFlow<List<ApprovalItem>> = _approvals.asStateFlow()

    private val _activityEvents = MutableStateFlow(initialActivityEvents())
    val activityEvents: StateFlow<List<ActivityEvent>> = _activityEvents.asStateFlow()

    private val _chatMessages = MutableStateFlow(initialChatMessages())
    val chatMessages: StateFlow<List<ChatMessage>> = _chatMessages.asStateFlow()

    private val _autonomyPolicy = MutableStateFlow(AutonomyPolicy())
    val autonomyPolicy: StateFlow<AutonomyPolicy> = _autonomyPolicy.asStateFlow()

    private val _systemHealthUiState = MutableStateFlow<UiState<SystemHealth>>(UiState.Loading)
    private val _campaignsUiState = MutableStateFlow<UiState<List<Campaign>>>(UiState.Loading)
    private val _pipelineRunsUiState = MutableStateFlow<UiState<List<PipelineRun>>>(UiState.Loading)
    private val _statsUiState = MutableStateFlow<UiState<Stats>>(UiState.Loading)
    private val _lastRefreshed = MutableStateFlow<String>("")

    val systemHealthUiState: StateFlow<UiState<SystemHealth>> = _systemHealthUiState.asStateFlow()
    val campaignsUiState: StateFlow<UiState<List<Campaign>>> = _campaignsUiState.asStateFlow()
    val pipelineRunsUiState: StateFlow<UiState<List<PipelineRun>>> = _pipelineRunsUiState.asStateFlow()
    val statsUiState: StateFlow<UiState<Stats>> = _statsUiState.asStateFlow()
    val lastRefreshed: StateFlow<String> = _lastRefreshed.asStateFlow()

    suspend fun getSystemHealth(): UiState<SystemHealth> {
        val result = fetchWithCache(
            apiCall = { apiService.getHealth() },
            mapper = { it: ApiHealth -> it.toDomain() },
            cacheWriter = { health -> database?.healthDao()?.insert(health.toEntity()) },
            cacheReader = { database?.healthDao()?.getLatest()?.toDomain() }
        )
        if (result is UiState.Success) {
            _systemHealth.value = result.data
        }
        return result
    }

    suspend fun getCampaigns(): UiState<List<Campaign>> {
        val result = fetchWithCacheList(
            apiCall = { apiService.getCampaigns() },
            mapper = { list: List<ApiCampaign> -> list.map { api: ApiCampaign -> api.toDomain() } },
            cacheWriter = { campaigns -> database?.campaignDao()?.insertAll(campaigns.map { it.toEntity() }) },
            cacheReader = { database?.campaignDao()?.getAll()?.first()?.map { it.toDomain() } ?: emptyList() }
        )
        if (result is UiState.Success) {
            _campaigns.value = result.data
        }
        return result
    }

    suspend fun getCampaign(id: String): UiState<Campaign> {
        return fetchWithCacheSingle(
            apiCall = { apiService.getCampaign(id) },
            mapper = { it: ApiCampaignDetail -> it.toDomain() },
            cacheWriter = {},
            cacheReader = { database?.campaignDao()?.getById(id)?.toDomain() }
        )
    }

    suspend fun getPipelineRuns(): UiState<List<PipelineRun>> {
        return fetchWithCacheList(
            apiCall = { apiService.getPipelineRuns() },
            mapper = { list: List<ApiPipelineRun> -> list.map { api: ApiPipelineRun -> api.toDomain() } },
            cacheWriter = { runs -> database?.pipelineDao()?.insertAll(runs.map { it.toEntity() }) },
            cacheReader = { database?.pipelineDao()?.getAll()?.first()?.map { it.toDomain() } ?: emptyList() }
        )
    }

    suspend fun getStats(): UiState<Stats> {
        return fetchWithCacheSingle(
            apiCall = { apiService.getStats() },
            mapper = { it: ApiStats -> it.toDomain() },
            cacheWriter = { database?.statsDao()?.insert(it.toEntity()) },
            cacheReader = { database?.statsDao()?.getLatest()?.toDomain() }
        )
    }

    suspend fun refreshFromBackend() {
        refreshSystemHealth()
        refreshCampaigns()
    }

    suspend fun refreshSystemHealth() {
        _systemHealthUiState.value = UiState.Loading
        val result = getSystemHealth()
        _systemHealthUiState.value = result
    }

    suspend fun refreshCampaigns() {
        _campaignsUiState.value = UiState.Loading
        val result = getCampaigns()
        _campaignsUiState.value = result
    }

    suspend fun refreshPipelineRuns() {
        _pipelineRunsUiState.value = UiState.Loading
        val result = getPipelineRuns()
        _pipelineRunsUiState.value = result
    }

    suspend fun refreshStats() {
        _statsUiState.value = UiState.Loading
        val result = getStats()
        _statsUiState.value = result
    }

    suspend fun refreshData() {
        refreshSystemHealth()
        refreshCampaigns()
        refreshStats()
        refreshPipelineRuns()
        updateLastRefreshed()
    }

    fun updateLastRefreshed() {
        _lastRefreshed.value = SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(Date())
    }

    private suspend fun <T, R> fetchWithCache(
        apiCall: suspend () -> retrofit2.Response<ApiEnvelope<T>>,
        mapper: (T) -> R,
        cacheWriter: suspend (R) -> Unit,
        cacheReader: suspend () -> R?
    ): UiState<R> {
        return try {
            val response = apiCall()
            if (response.isSuccessful) {
                val body = response.body()?.data
                if (body != null) {
                    val result = mapper(body)
                    cacheWriter(result)
                    return UiState.Success(result)
                }
            }
            UiState.Error("Invalid server response")
        } catch (e: Exception) {
            val cached = cacheReader()
            if (cached != null) {
                return UiState.Success(cached)
            } else {
                UiState.Error("No cached data available")
            }
        }
    }

    private suspend fun <T, R> fetchWithCacheList(
        apiCall: suspend () -> retrofit2.Response<ApiEnvelope<List<T>>>,
        mapper: (List<T>) -> List<R>,
        cacheWriter: suspend (List<R>) -> Unit,
        cacheReader: suspend () -> List<R>?
    ): UiState<List<R>> {
        return try {
            val response = apiCall()
            if (response.isSuccessful) {
                val body = response.body()?.data
                if (body != null) {
                    val result = mapper(body)
                    cacheWriter(result)
                    return UiState.Success(result)
                }
            }
            UiState.Error("Invalid server response")
        } catch (e: Exception) {
            val cached = cacheReader()
            if (cached != null && cached.isNotEmpty()) {
                UiState.Success(cached)
            } else {
                UiState.Error("No cached data available")
            }
        }
    }

    private suspend fun <T, R> fetchWithCacheSingle(
        apiCall: suspend () -> retrofit2.Response<ApiEnvelope<T>>,
        mapper: (T) -> R,
        cacheWriter: suspend (R) -> Unit,
        cacheReader: suspend () -> R?
    ): UiState<R> {
        return try {
            val response = apiCall()
            if (response.isSuccessful) {
                val body = response.body()?.data
                if (body != null) {
                    val result = mapper(body)
                    cacheWriter(result)
                    return UiState.Success(result)
                }
            }
            UiState.Error("Invalid server response")
        } catch (e: Exception) {
            val cached = cacheReader()
            if (cached != null) {
                return UiState.Success(cached)
            } else {
                UiState.Error("No cached data available")
            }
        }
    }

    // Actions
    fun approveItem(approvalId: String) {
        _approvals.update { list ->
            list.map { item ->
                if (item.id == approvalId) item.copy(status = ApprovalStatus.APPROVED) else item
            }
        }
        val app = _approvals.value.find { it.id == approvalId }
        app?.let { approval ->
            _strategies.update { strats ->
                strats.map { s ->
                    if (s.id == approval.strategyId) s.copy(status = StrategyStatus.LIVE) else s
                }
            }
            addActivityEvent(
                category = "Human Decision",
                source = "Operator",
                message = "Approved ${approval.title}",
                context = approval.strategyId
            )
        }
    }

    fun rejectItem(approvalId: String) {
        _approvals.update { list ->
            list.map { item ->
                if (item.id == approvalId) item.copy(status = ApprovalStatus.REJECTED) else item
            }
        }
        val app = _approvals.value.find { it.id == approvalId }
        app?.let { approval ->
            _strategies.update { strats ->
                strats.map { s ->
                    if (s.id == approval.strategyId) s.copy(status = StrategyStatus.REJECTED, rejectionReason = "Human operator rejected portfolio inclusion") else s
                }
            }
            addActivityEvent(
                category = "Human Decision",
                source = "Operator",
                message = "Rejected ${approval.title}",
                context = approval.strategyId
            )
        }
    }

    fun updateCampaignStatus(campaignId: String, newStatus: CampaignStatus) {
        _campaigns.update { list ->
            list.map { if (it.id == campaignId) it.copy(status = newStatus) else it }
        }
        addActivityEvent(
            category = "Agent",
            source = "Orchestrator",
            message = "Campaign $campaignId updated to $newStatus",
            context = campaignId
        )
    }

    fun toggleAgentStatus(agentId: String) {
        _agents.update { list ->
            list.map { agent ->
                if (agent.id == agentId) {
                    val nextStatus = if (agent.status == AgentStatus.RUNNING) AgentStatus.PAUSED else AgentStatus.RUNNING
                    agent.copy(status = nextStatus)
                } else agent
            }
        }
    }

    fun sendChatMessage(
        content: String,
        contextType: ChatContextType = ChatContextType.GLOBAL,
        contextName: String = "Orchestrator"
    ) {
        val userMsg = ChatMessage(
            id = "msg_${System.currentTimeMillis()}",
            sender = ChatSender.USER,
            authorName = "elBoni",
            content = content,
            timestamp = "Just now",
            contextType = contextType,
            contextName = contextName
        )
        _chatMessages.update { it + userMsg }

        val aiResponseContent = when {
            content.contains("H-042", ignoreCase = true) || content.contains("continue", ignoreCase = true) ->
                "Understood. Starting strategy generation with SQX Agent for hypothesis H-042 prioritizing robustness over raw returns. 5,000 candidate building blocks loaded."
            content.contains("status", ignoreCase = true) || content.contains("health", ignoreCase = true) ->
                "QuantLab AI Control Plane operational: 5/5 services online. 4 campaigns running, 17 candidate strategies passed robust Monte Carlo checks. No system errors detected."
            content.contains("pause", ignoreCase = true) ->
                "Received request. Pausing execution pipeline for selected scope. Agents entering graceful wait state."
            else ->
                "Request received by Orchestrator. Evaluating constraints across research, SQX, and portfolio validation agents. Operational state is currently HEALTHY."
        }

        val aiMsg = ChatMessage(
            id = "msg_${System.currentTimeMillis() + 1}",
            sender = ChatSender.AI,
            authorName = "QuantLab Agent",
            content = aiResponseContent,
            timestamp = "Just now",
            contextType = contextType,
            contextName = contextName
        )
        _chatMessages.update { it + aiMsg }
    }

    fun createCampaign(
        name: String,
        asset: String,
        timeframe: String,
        objective: String,
        hypothesis: String
    ) {
        val newCamp = Campaign(
            id = "CAMP-${System.currentTimeMillis() % 10000}",
            name = name,
            asset = asset,
            timeframe = timeframe,
            objective = objective,
            hypothesis = hypothesis,
            progressPct = 5,
            currentStage = PipelineStage.HYPOTHESIS,
            activeAgents = 2,
            waitingAgents = 0,
            generatedCount = 0,
            passedFiltersCount = 0,
            status = CampaignStatus.ACTIVE,
            lastEvent = "Campaign initialized by operator",
            updatedAt = "Just now"
        )
        _campaigns.update { listOf(newCamp) + it }
        addActivityEvent(
            category = "Research",
            source = "Operator",
            message = "Created new research campaign: $name ($asset $timeframe)",
            context = newCamp.id
        )
    }

    fun replaceStrategy(degradedStrategyId: String, candidateStrategyId: String) {
        _strategies.update { list ->
            list.map { s ->
                when (s.id) {
                    degradedStrategyId -> s.copy(status = StrategyStatus.REJECTED, rejectionReason = "Replaced by candidate $candidateStrategyId due to alpha decay")
                    candidateStrategyId -> s.copy(status = StrategyStatus.LIVE)
                    else -> s
                }
            }
        }
        addActivityEvent(
            category = "Replacement",
            source = "Replacement Engine",
            message = "Replaced degraded strategy $degradedStrategyId with candidate $candidateStrategyId",
            context = candidateStrategyId
        )
    }

    fun updateAutonomyPolicy(policy: AutonomyPolicy) {
        _autonomyPolicy.value = policy
        addActivityEvent(
            category = "Human Decision",
            source = "Operator",
            message = "Autonomy matrix updated",
            context = "Settings"
        )
    }

    private fun addActivityEvent(category: String, source: String, message: String, context: String) {
        val event = ActivityEvent(
            id = "act_${System.currentTimeMillis()}",
            timestamp = "Just now",
            category = category,
            source = source,
            message = message,
            context = context
        )
        _activityEvents.update { listOf(event) + it }
    }

    private fun ApiHealth.toDomain(): SystemHealth = SystemHealth(
        openCodeOnline = status == "ok",
        orchestratorRunning = status == "ok",
        sqxOnline = status == "ok",
        dataPipelineOnline = status == "ok",
        databaseOnline = status == "ok",
        activeWorkers = 8,
        totalWorkers = 10,
        cpuUsagePct = 42,
        ramUsagePct = 61,
        storageUsagePct = 73,
        apiHealthy = status == "ok"
    )

    private fun ApiCampaign.toDomain(): Campaign {
        val mappedStatus = try {
            CampaignStatus.valueOf(status.uppercase())
        } catch (e: IllegalArgumentException) {
            CampaignStatus.ATTENTION
        }
        return Campaign(
            id = campaignId,
            name = name,
            asset = market,
            timeframe = timeframe,
            objective = "",
            hypothesis = "",
            progressPct = 0,
            currentStage = PipelineStage.HYPOTHESIS,
            activeAgents = 0,
            waitingAgents = 0,
            generatedCount = 0,
            passedFiltersCount = 0,
            status = mappedStatus,
            lastEvent = "",
            updatedAt = created ?: ""
        )
    }

    private fun ApiCampaignDetail.toDomain(): Campaign {
        val mappedStatus = try {
            CampaignStatus.valueOf(status.uppercase())
        } catch (e: IllegalArgumentException) {
            CampaignStatus.ATTENTION
        }
        return Campaign(
            id = campaignId,
            name = name,
            asset = market,
            timeframe = timeframe,
            objective = "",
            hypothesis = "",
            progressPct = 0,
            currentStage = PipelineStage.HYPOTHESIS,
            activeAgents = 0,
            waitingAgents = 0,
            generatedCount = 0,
            passedFiltersCount = 0,
            status = mappedStatus,
            lastEvent = "",
            updatedAt = created ?: ""
        )
    }

    private fun ApiPipelineRun.toDomain(): PipelineRun = PipelineRun(
        runId = runId,
        pipelineName = pipelineName,
        status = status,
        startedAt = startedAt,
        completedAt = completedAt,
        duration = duration,
        error = error
    )

    private fun ApiStats.toDomain(): Stats = Stats(
        sharpeMean = sharpeMean,
        sharpeStd = sharpeStd,
        maxDrawdownPct = maxDrawdownPct,
        winRateMean = winRateMean,
        totalTrades = totalTrades,
        benchmarkComparison = benchmarkComparison as? String,
        totalCampaigns = totalCampaigns,
        totalPipelineRuns = totalPipelineRuns,
        generatedAt = generatedAt
    )

    private fun Campaign.toEntity(): CampaignEntity = CampaignEntity(
        id = id,
        name = name,
        asset = asset,
        timeframe = timeframe,
        objective = objective,
        hypothesis = hypothesis,
        progressPct = progressPct,
        currentStage = currentStage.name,
        activeAgents = activeAgents,
        waitingAgents = waitingAgents,
        generatedCount = generatedCount,
        passedFiltersCount = passedFiltersCount,
        status = status.name,
        lastEvent = lastEvent,
        updatedAt = updatedAt,
        fetchedAt = System.currentTimeMillis()
    )

    private fun PipelineRun.toEntity(): PipelineRunEntity = PipelineRunEntity(
        runId = runId,
        pipelineName = pipelineName,
        status = status,
        startedAt = startedAt,
        completedAt = completedAt,
        duration = duration,
        error = error,
        fetchedAt = System.currentTimeMillis()
    )

    private fun Stats.toEntity(): StatsEntity = StatsEntity(
        sharpeMean = sharpeMean,
        sharpeStd = sharpeStd,
        maxDrawdownPct = maxDrawdownPct,
        winRateMean = winRateMean,
        totalTrades = totalTrades,
        benchmarkComparison = benchmarkComparison,
        totalCampaigns = totalCampaigns,
        totalPipelineRuns = totalPipelineRuns,
        generatedAt = generatedAt,
        fetchedAt = System.currentTimeMillis()
    )

    private fun HealthEntity.toDomain(): SystemHealth = SystemHealth(
        openCodeOnline = status == "ok",
        orchestratorRunning = status == "ok",
        sqxOnline = status == "ok",
        dataPipelineOnline = status == "ok",
        databaseOnline = status == "ok",
        activeWorkers = 8,
        totalWorkers = 10,
        cpuUsagePct = 42,
        ramUsagePct = 61,
        storageUsagePct = 73,
        apiHealthy = status == "ok"
    )

    private fun CampaignEntity.toDomain(): Campaign = Campaign(
        id = id,
        name = name,
        asset = asset,
        timeframe = timeframe,
        objective = objective,
        hypothesis = hypothesis,
        progressPct = progressPct,
        currentStage = try { PipelineStage.valueOf(currentStage) } catch (e: IllegalArgumentException) { PipelineStage.HYPOTHESIS },
        activeAgents = activeAgents,
        waitingAgents = waitingAgents,
        generatedCount = generatedCount,
        passedFiltersCount = passedFiltersCount,
        status = try { CampaignStatus.valueOf(status) } catch (e: IllegalArgumentException) { CampaignStatus.ATTENTION },
        lastEvent = lastEvent,
        updatedAt = updatedAt
    )

    private fun PipelineRunEntity.toDomain(): PipelineRun = PipelineRun(
        runId = runId,
        pipelineName = pipelineName,
        status = status,
        startedAt = startedAt,
        completedAt = completedAt,
        duration = duration,
        error = error
    )

    private fun StatsEntity.toDomain(): Stats = Stats(
        sharpeMean = sharpeMean,
        sharpeStd = sharpeStd,
        maxDrawdownPct = maxDrawdownPct,
        winRateMean = winRateMean,
        totalTrades = totalTrades,
        benchmarkComparison = benchmarkComparison,
        totalCampaigns = totalCampaigns,
        totalPipelineRuns = totalPipelineRuns,
        generatedAt = generatedAt
    )

    private fun SystemHealth.toEntity(): HealthEntity = HealthEntity(
        status = if (apiHealthy) "ok" else "error",
        version = "cached",
        fetchedAt = System.currentTimeMillis()
    )

    companion object {
        val instance: QuantLabRepository by lazy {
            QuantLabRepository(
                apiService = NetworkModule.apiService,
                databaseProvider = { DatabaseProvider.database }
            )
        }

        private fun initialCampaigns() = listOf(
            Campaign(
                id = "CAMP-027",
                name = "EURUSD H1 Mean Reversion Research",
                asset = "EURUSD",
                timeframe = "H1",
                objective = "Find robust mean reversion strategies during quiet Asian & London overlap regimes.",
                hypothesis = "H-042: RSI(14) divergence with Bollinger Band squeeze on H1.",
                progressPct = 78,
                currentStage = PipelineStage.GENERATION,
                activeAgents = 4,
                waitingAgents = 1,
                generatedCount = 184,
                passedFiltersCount = 17,
                status = CampaignStatus.ACTIVE,
                lastEvent = "SQX Agent generated 250 new candidates",
                updatedAt = "13:39"
            ),
            Campaign(
                id = "CAMP-028",
                name = "GBPUSD M30 Breakout Hypothesis",
                asset = "GBPUSD",
                timeframe = "M30",
                objective = "Capture volatile volatility expansions following high-impact UK economic releases.",
                hypothesis = "H-019: Keltner Channel expansion with volume spike verification.",
                progressPct = 43,
                currentStage = PipelineStage.ROBUSTNESS,
                activeAgents = 2,
                waitingAgents = 0,
                generatedCount = 92,
                passedFiltersCount = 8,
                status = CampaignStatus.ACTIVE,
                lastEvent = "Validation Agent running 1,000 Monte Carlo permutations",
                updatedAt = "13:31"
            ),
            Campaign(
                id = "CAMP-025",
                name = "USDJPY H4 Trend Following Alpha",
                asset = "USDJPY",
                timeframe = "H4",
                objective = "Macro interest rate differential trend continuation filter.",
                hypothesis = "H-008: Dual EMA crossover with yield spread momentum.",
                progressPct = 100,
                currentStage = PipelineStage.APPROVAL,
                activeAgents = 0,
                waitingAgents = 1,
                generatedCount = 412,
                passedFiltersCount = 31,
                status = CampaignStatus.ATTENTION,
                lastEvent = "Portfolio Agent passed correlation check. Awaiting human approval.",
                updatedAt = "12:15"
            )
        )

        private fun initialAgents() = listOf(
            Agent(
                id = "agent_research",
                name = "Research Agent",
                role = "Macro & Sentiment Scraper",
                status = AgentStatus.RUNNING,
                currentTask = "Analyzing ECB rate policy statements and CFTC commitment reports",
                campaignName = "EURUSD H1",
                runtime = "3h 24m",
                lastEvent = "Completed macro research report",
                currentInstruction = "Filter macro signals for EURUSD directional bias",
                progressPct = 90,
                logs = listOf(
                    AgentLogEntry("log_r1", "00:14:10", LogLevel.INFO, "Scraper connected to ECB RSS feeds and ForexFactory API", "InitScraper", "200 OK - Latency: 42ms"),
                    AgentLogEntry("log_r2", "00:14:22", LogLevel.EXEC, "Parsing latest ECB press release on interest rate expectations", "NLP_Parser", "Extracted hawkish sentiment score: +0.68"),
                    AgentLogEntry("log_r3", "00:14:35", LogLevel.WARN, "High volatility alert: US CPI release scheduled in 2h 15m", "RiskAlert", "Threshold: >0.4% MoM expected"),
                    AgentLogEntry("log_r4", "00:15:01", LogLevel.SUCCESS, "Macro research report #EURUSD-99 compiled successfully", "ReportGen", "Output size: 24KB, Bias: Bullish EUR")
                )
            ),
            Agent(
                id = "agent_hypothesis",
                name = "Hypothesis Agent",
                role = "Quantitative Rule Generator",
                status = AgentStatus.RUNNING,
                currentTask = "Formulating entry/exit triggers for H-042 mean reversion",
                campaignName = "EURUSD H1",
                runtime = "2h 10m",
                lastEvent = "Validated hypothesis H-042 mathematically",
                currentInstruction = "Translate RSI divergence into StrategyQuant X building blocks",
                progressPct = 85,
                logs = listOf(
                    AgentLogEntry("log_h1", "00:12:00", LogLevel.INFO, "Loading historical tick data for EURUSD H1 (2018-2026)", "DataLoader", "1,240,000 bars loaded"),
                    AgentLogEntry("log_h2", "00:13:15", LogLevel.EXEC, "Testing 14-period RSI divergence against Bollinger Bands 2.0 SD", "HypothesisTester", "Sample size: 3,420 trades"),
                    AgentLogEntry("log_h3", "00:13:40", LogLevel.SUCCESS, "Hypothesis H-042 passed chi-square significance test (p < 0.01)", "MathValidator", "Win rate expectation: 58.4%"),
                    AgentLogEntry("log_h4", "00:14:50", LogLevel.INFO, "Constructing SQX building block XML payload", "SQXBuilder", "Target engine: SQX v138.2")
                )
            ),
            Agent(
                id = "agent_sqx",
                name = "SQX Agent",
                role = "StrategyQuant X Engine",
                status = AgentStatus.RUNNING,
                currentTask = "Genetic strategy evolution (5,000 target strategies)",
                campaignName = "EURUSD H1",
                runtime = "1h 14m",
                lastEvent = "Generated 250 new candidates",
                currentInstruction = "Evolve building blocks with maximum Sharpe > 1.8",
                generatedCount = 4820,
                passedCount = 214,
                progressPct = 82,
                logs = listOf(
                    AgentLogEntry("log_s1", "00:10:00", LogLevel.INFO, "Genetic Evolution Engine initialized (Population size: 500)", "EvoInit", "Threads: 16 cores assigned"),
                    AgentLogEntry("log_s2", "00:11:30", LogLevel.EXEC, "Generation #42 completed: 500 candidates evaluated", "GenEval", "Best Profit Factor: 2.14, Max DD: 6.8%"),
                    AgentLogEntry("log_s3", "00:12:45", LogLevel.EXEC, "Crossover mutation batch #89 applied to top 10% performers", "Mutation", "New building block: Keltner Channel Breakout"),
                    AgentLogEntry("log_s4", "00:14:10", LogLevel.WARN, "Filtered 86 strategies due to excessive trade count (>2000 trades/yr)", "OverfitFilter", "Reason: High transaction cost decay"),
                    AgentLogEntry("log_s5", "00:14:55", LogLevel.SUCCESS, "Candidate STRAT-8421 passed initial backtest filter", "CandidatePool", "Sharpe: 2.1, Recovery Factor: 8.4")
                )
            ),
            Agent(
                id = "agent_validation",
                name = "Validation Agent",
                role = "Walk-Forward & Monte Carlo Tester",
                status = AgentStatus.WAITING,
                currentTask = "Awaiting Monte Carlo cluster compute slot",
                campaignName = "GBPUSD M30",
                runtime = "45m",
                lastEvent = "Rejected 63 overfitted strategies",
                currentInstruction = "Apply 30% parameter variation matrix",
                progressPct = 40,
                logs = listOf(
                    AgentLogEntry("log_v1", "00:08:10", LogLevel.INFO, "Walk-Forward Analysis started (6 Out-Of-Sample runs)", "WF_Runner", "OOS ratio: 20%"),
                    AgentLogEntry("log_v2", "00:09:40", LogLevel.EXEC, "OOS Period 4/6 passed efficiency test (OOS/IS ratio: 84%)", "WF_Eval", "Robustness score: 88/100"),
                    AgentLogEntry("log_v3", "00:11:15", LogLevel.WARN, "Monte Carlo 1,000 simulation cluster queued behind job #441", "ClusterQueue", "Estimated wait: 4m 12s"),
                    AgentLogEntry("log_v4", "00:13:00", LogLevel.INFO, "3D Parameter Stability Matrix rendered for review", "ParamMatrix", "Stable plateau: RSI 12..18")
                )
            ),
            Agent(
                id = "agent_portfolio",
                name = "Portfolio Agent",
                role = "Correlation & Risk Manager",
                status = AgentStatus.RUNNING,
                currentTask = "Calculating equity curve correlation against 9 live strategies",
                campaignName = "USDJPY H4",
                runtime = "12m",
                lastEvent = "Correlation check completed (<0.25 threshold)",
                currentInstruction = "Ensure asset class concentration does not exceed 35%",
                progressPct = 100,
                logs = listOf(
                    AgentLogEntry("log_p1", "00:11:00", LogLevel.INFO, "Fetching daily returns vector for 9 active portfolio components", "DataPull", "365 daily data points"),
                    AgentLogEntry("log_p2", "00:12:10", LogLevel.EXEC, "Computing Pearson correlation matrix across candidate pool", "CorrEngine", "Max correlation found: 0.18"),
                    AgentLogEntry("log_p3", "00:13:30", LogLevel.SUCCESS, "Portfolio inclusion safety check PASSED for STRAT-8421", "RiskCheck", "Marginal VaR contribution: +0.4%"),
                    AgentLogEntry("log_p4", "00:14:40", LogLevel.INFO, "Approval request payload dispatched to Human Decision Queue", "QueueDispatch", "Approval ID: APP-109")
                )
            ),
            Agent(
                id = "agent_replacement",
                name = "Replacement Agent",
                role = "Alpha Degradation Monitor",
                status = AgentStatus.RUNNING,
                currentTask = "Monitoring live performance degradation on EURUSD H1 #7012",
                campaignName = "System-Wide",
                runtime = "12h 00m",
                lastEvent = "Detected 14% drawdown anomaly in #7012",
                currentInstruction = "Search candidate pool for replacement strategy",
                progressPct = 65,
                logs = listOf(
                    AgentLogEntry("log_rep1", "00:02:10", LogLevel.INFO, "Continuous tracking active for 14 deployed strategies", "MonitorLoop", "Polling interval: 5m"),
                    AgentLogEntry("log_rep2", "00:05:40", LogLevel.WARN, "Performance anomaly on strategy #7012: Current DD (-14.2%) exceeds 95% IS bound (-11.0%)", "AnomalyDetector", "Regime shift suspected"),
                    AgentLogEntry("log_rep3", "00:08:00", LogLevel.EXEC, "Initiating Replacement Search in Candidate Vault", "SearchEngine", "Filters: Same asset (EURUSD), uncorrelated"),
                    AgentLogEntry("log_rep4", "00:12:15", LogLevel.SUCCESS, "Candidate STRAT-8421 identified as optimal replacement for #7012", "MatchEngine", "Improvement: +1.2 Sharpe ratio")
                )
            ),
            Agent(
                id = "agent_data",
                name = "Data Agent",
                role = "Tick Data Quality & Clean-up",
                status = AgentStatus.IDLE,
                currentTask = "Dukascopy EURUSD tick data synchronized",
                campaignName = "Data Pipeline",
                runtime = "5h 10m",
                lastEvent = "Cleaned 12,400,000 tick records",
                currentInstruction = "Standby for next dataset import",
                progressPct = 100,
                logs = listOf(
                    AgentLogEntry("log_d1", "00:01:00", LogLevel.INFO, "Connecting to Dukascopy tick data server", "SyncEngine", "100% bandwidth available"),
                    AgentLogEntry("log_d2", "00:03:20", LogLevel.EXEC, "Cleaning phantom spikes and weekend spread gaps", "DataCleaner", "Fixed 142 bad ticks"),
                    AgentLogEntry("log_d3", "00:05:00", LogLevel.SUCCESS, "12,400,000 tick records committed to local SQLite store", "DBWriter", "Database integrity: VERIFIED")
                )
            )
        )

        private fun initialStrategies() = listOf(
            Strategy(
                id = "STRAT-8421",
                codeNumber = "#8421",
                asset = "EURUSD",
                timeframe = "H1",
                score = 87,
                status = StrategyStatus.CANDIDATE,
                netProfit = "+$14,280",
                profitFactor = 1.92f,
                maxDrawdownPct = 6.4f,
                recoveryFactor = 4.8f,
                sharpeRatio = 2.15f,
                walkForwardPass = true,
                monteCarloPass = true,
                parameterStabilityPass = true,
                marketRegimePass = true,
                correlationStatus = "LOW (0.18)",
                exposureStatus = "ACCEPTABLE (12%)",
                campaignId = "CAMP-027"
            ),
            Strategy(
                id = "STRAT-7218",
                codeNumber = "#7218",
                asset = "GBPUSD",
                timeframe = "M30",
                score = 82,
                status = StrategyStatus.VALIDATED,
                netProfit = "+$9,840",
                profitFactor = 1.75f,
                maxDrawdownPct = 8.1f,
                recoveryFactor = 3.9f,
                sharpeRatio = 1.82f,
                walkForwardPass = true,
                monteCarloPass = true,
                parameterStabilityPass = true,
                marketRegimePass = true,
                correlationStatus = "ACCEPTABLE (0.28)",
                exposureStatus = "ACCEPTABLE (15%)",
                campaignId = "CAMP-028"
            ),
            Strategy(
                id = "STRAT-8392",
                codeNumber = "#8392",
                asset = "EURUSD",
                timeframe = "H1",
                score = 85,
                status = StrategyStatus.REPLACEMENT_READY,
                netProfit = "+$12,950",
                profitFactor = 1.88f,
                maxDrawdownPct = 5.9f,
                recoveryFactor = 4.5f,
                sharpeRatio = 2.05f,
                walkForwardPass = true,
                monteCarloPass = true,
                parameterStabilityPass = true,
                marketRegimePass = true,
                correlationStatus = "LOW (0.15)",
                exposureStatus = "ACCEPTABLE (10%)",
                campaignId = "CAMP-027"
            ),
            Strategy(
                id = "STRAT-7012",
                codeNumber = "#7012",
                asset = "EURUSD",
                timeframe = "H1",
                score = 64,
                status = StrategyStatus.DEGRADED,
                netProfit = "+$18,400",
                profitFactor = 1.25f,
                maxDrawdownPct = 14.2f,
                recoveryFactor = 1.8f,
                sharpeRatio = 0.95f,
                walkForwardPass = true,
                monteCarloPass = false,
                parameterStabilityPass = false,
                marketRegimePass = false,
                correlationStatus = "HIGH (0.52)",
                exposureStatus = "HIGH (28%)",
                campaignId = "CAMP-020",
                rejectionReason = "Walk forward efficiency decayed below 40% threshold over last 90 trading days."
            ),
            Strategy(
                id = "STRAT-8122",
                codeNumber = "#8122",
                asset = "EURUSD",
                timeframe = "H1",
                score = 42,
                status = StrategyStatus.REJECTED,
                netProfit = "+$22,100",
                profitFactor = 2.45f,
                maxDrawdownPct = 19.8f,
                recoveryFactor = 1.2f,
                sharpeRatio = 0.88f,
                walkForwardPass = false,
                monteCarloPass = false,
                parameterStabilityPass = false,
                marketRegimePass = false,
                correlationStatus = "UNACCEPTABLE",
                exposureStatus = "HIGH",
                campaignId = "CAMP-027",
                rejectionReason = "Overfitted: Failed Walk-Forward matrix and parameter sensitivity analysis."
            ),
            Strategy(
                id = "STRAT-6001",
                codeNumber = "#6001",
                asset = "USDJPY",
                timeframe = "H4",
                score = 91,
                status = StrategyStatus.LIVE,
                netProfit = "+$34,120",
                profitFactor = 2.10f,
                maxDrawdownPct = 4.8f,
                recoveryFactor = 6.2f,
                sharpeRatio = 2.40f,
                walkForwardPass = true,
                monteCarloPass = true,
                parameterStabilityPass = true,
                marketRegimePass = true,
                correlationStatus = "OPTIMAL (0.09)",
                exposureStatus = "ACCEPTABLE (8%)",
                campaignId = "CAMP-018"
            )
        )

        private fun initialApprovals() = listOf(
            ApprovalItem(
                id = "APP-8421",
                strategyId = "STRAT-8421",
                title = "Strategy #8421 Portfolio Inclusion",
                requestType = ApprovalType.PORTFOLIO_INCLUSION,
                reason = "Strategy passed all 4 robustness tests (WF, Monte Carlo, Parameter, Regime) with Sharpe 2.15.",
                metricsSummary = "EURUSD H1 · Net $14.2k · Sharpe 2.15 · MaxDD 6.4% · Correlation 0.18",
                riskImpact = "Low correlation with live strategies; adds +12% capital allocation to FX Mean Reversion bucket.",
                recommendedAction = "Approve inclusion in candidate portfolio queue.",
                status = ApprovalStatus.PENDING,
                timestamp = "13:40"
            ),
            ApprovalItem(
                id = "APP-7012",
                strategyId = "STRAT-7012",
                title = "Strategy #7012 Alpha Replacement",
                requestType = ApprovalType.STRATEGY_REPLACEMENT,
                reason = "Strategy #7012 shows performance degradation (DD 14.2%). Replacement candidate #8392 is ready.",
                metricsSummary = "Replace #7012 (Sharpe 0.95) with #8392 (Sharpe 2.05, DD 5.9%)",
                riskImpact = "Reduces active drawdown risk by 8.3% and restores portfolio Sharpe ratio.",
                recommendedAction = "Decommission #7012 and deploy #8392.",
                status = ApprovalStatus.PENDING,
                timestamp = "12:50"
            )
        )

        private fun initialActivityEvents() = listOf(
            ActivityEvent(
                id = "act_101",
                timestamp = "13:42",
                category = "Research",
                source = "Research Agent",
                message = "Completed macro research on ECB rate policy and CFTC positioning.",
                context = "EURUSD H1"
            ),
            ActivityEvent(
                id = "act_102",
                timestamp = "13:39",
                category = "Strategy",
                source = "SQX Agent",
                message = "Generated 250 new candidate strategies in StrategyQuant X pipeline.",
                context = "CAMP-027"
            ),
            ActivityEvent(
                id = "act_103",
                timestamp = "13:31",
                category = "Validation",
                source = "Validation Agent",
                message = "Rejected 63 overfitted strategies during Walk-Forward matrix test.",
                context = "GBPUSD M30"
            ),
            ActivityEvent(
                id = "act_104",
                timestamp = "13:24",
                category = "Portfolio",
                source = "Portfolio Agent",
                message = "Correlation check completed: Strategy #8421 correlation is 0.18 (ACCEPTABLE).",
                context = "STRAT-8421"
            ),
            ActivityEvent(
                id = "act_105",
                timestamp = "12:50",
                category = "Replacement",
                source = "Replacement Agent",
                message = "Performance degradation flagged on #7012. Found 2 replacement candidates.",
                context = "STRAT-7012"
            )
        )

        private fun initialChatMessages() = listOf(
            ChatMessage(
                id = "m1",
                sender = ChatSender.AI,
                authorName = "QuantLab Agent",
                content = "Research is complete for EURUSD H1 Mean Reversion. I found 4 promising hypotheses.\n\nThe strongest candidate is **H-042** (RSI divergence with Bollinger Squeeze). Would you like me to continue with StrategyQuant X generation?",
                timestamp = "13:20",
                contextType = ChatContextType.CAMPAIGN,
                contextName = "EURUSD H1",
                actionText = "Continue with H-042",
                actionType = "CONTINUE_H042"
            ),
            ChatMessage(
                id = "m2",
                sender = ChatSender.USER,
                authorName = "elBoni",
                content = "Continue with H-042 and prioritize robustness over raw return.",
                timestamp = "13:22",
                contextType = ChatContextType.CAMPAIGN,
                contextName = "EURUSD H1"
            ),
            ChatMessage(
                id = "m3",
                sender = ChatSender.AI,
                authorName = "QuantLab Agent",
                content = "Understood. Starting strategy generation with SQX Agent. I have configured a 30% parameter variance constraint and strict Walk-Forward matrix checks.",
                timestamp = "13:23",
                contextType = ChatContextType.CAMPAIGN,
                contextName = "EURUSD H1"
            )
        )
    }
}

object DatabaseProvider {
    @Volatile
    private var _database: QuantLabDatabase? = null

    val database: QuantLabDatabase?
        get() = _database

    @Synchronized
    fun init(context: android.content.Context) {
        if (_database == null) {
            _database = QuantLabDatabase.getInstance(context)
        }
    }
}
