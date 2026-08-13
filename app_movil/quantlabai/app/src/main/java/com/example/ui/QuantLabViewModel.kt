package com.example.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.data.model.*
import com.example.data.repository.QuantLabRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

open class QuantLabViewModel(
    private val repository: QuantLabRepository = QuantLabRepository.instance
) : ViewModel() {

    val systemHealth: StateFlow<SystemHealth> = repository.systemHealth
    open val campaigns: StateFlow<List<Campaign>> = repository.campaigns
    val agents: StateFlow<List<Agent>> = repository.agents
    val strategies: StateFlow<List<Strategy>> = repository.strategies
    val approvals: StateFlow<List<ApprovalItem>> = repository.approvals
    val activityEvents: StateFlow<List<ActivityEvent>> = repository.activityEvents
    val chatMessages: StateFlow<List<ChatMessage>> = repository.chatMessages
    val autonomyPolicy: StateFlow<AutonomyPolicy> = repository.autonomyPolicy

    open val systemHealthUiState: StateFlow<UiState<SystemHealth>> = repository.systemHealthUiState
    open val campaignsUiState: StateFlow<UiState<List<Campaign>>> = repository.campaignsUiState
    open val pipelineRunsUiState: StateFlow<UiState<List<PipelineRun>>> = repository.pipelineRunsUiState
    open val statsUiState: StateFlow<UiState<Stats>> = repository.statsUiState
    open val lastRefreshed: StateFlow<String> = repository.lastRefreshed

    // Selection & Filter State
    private val _selectedCampaignId = MutableStateFlow<String?>("CAMP-027")
    val selectedCampaignId: StateFlow<String?> = _selectedCampaignId.asStateFlow()

    init {
        viewModelScope.launch {
            repository.refreshFromBackend()
            repository.refreshStats()
            repository.refreshPipelineRuns()
            repository.updateLastRefreshed()
        }
    }

    private val _selectedAgentId = MutableStateFlow<String?>("agent_sqx")
    val selectedAgentId: StateFlow<String?> = _selectedAgentId.asStateFlow()

    private val _selectedStrategyId = MutableStateFlow<String?>("STRAT-8421")
    val selectedStrategyId: StateFlow<String?> = _selectedStrategyId.asStateFlow()

    private val _chatContext = MutableStateFlow(ChatContextType.GLOBAL)
    val chatContext: StateFlow<ChatContextType> = _chatContext.asStateFlow()

    private val _chatContextName = MutableStateFlow("Orchestrator")
    val chatContextName: StateFlow<String> = _chatContextName.asStateFlow()

    private val _activeOrchestrator = MutableStateFlow("QuantLab-Orchestrator")
    val activeOrchestrator: StateFlow<String> = _activeOrchestrator.asStateFlow()

    fun setOrchestrator(name: String) {
        _activeOrchestrator.value = name
    }

    fun toggleOrchestrator() {
        _activeOrchestrator.value = if (_activeOrchestrator.value == "QuantLab-Orchestrator") {
            "Guardián-Orchestrator"
        } else {
            "QuantLab-Orchestrator"
        }
    }

    // Filter queries
    private val _strategySearchQuery = MutableStateFlow("")
    val strategySearchQuery: StateFlow<String> = _strategySearchQuery.asStateFlow()

    private val _campaignFilterStatus = MutableStateFlow<CampaignStatus?>(null)
    val campaignFilterStatus: StateFlow<CampaignStatus?> = _campaignFilterStatus.asStateFlow()

    fun selectCampaign(campaignId: String) {
        _selectedCampaignId.value = campaignId
    }

    fun selectAgent(agentId: String) {
        _selectedAgentId.value = agentId
    }

    fun selectStrategy(strategyId: String) {
        _selectedStrategyId.value = strategyId
    }

    fun setChatContext(type: ChatContextType, name: String) {
        _chatContext.value = type
        _chatContextName.value = name
    }

    fun setStrategySearchQuery(query: String) {
        _strategySearchQuery.value = query
    }

    fun setCampaignFilterStatus(status: CampaignStatus?) {
        _campaignFilterStatus.value = status
    }

    fun approveItem(id: String) {
        repository.approveItem(id)
    }

    fun rejectItem(id: String) {
        repository.rejectItem(id)
    }

    fun sendChatMessage(text: String) {
        if (text.isBlank()) return
        repository.sendChatMessage(text, _chatContext.value, _chatContextName.value)
    }

    fun createCampaign(
        name: String,
        asset: String,
        timeframe: String,
        objective: String,
        hypothesis: String
    ) {
        repository.createCampaign(name, asset, timeframe, objective, hypothesis)
    }

    fun toggleAgentStatus(id: String) {
        repository.toggleAgentStatus(id)
    }

    fun updateCampaignStatus(id: String, status: CampaignStatus) {
        repository.updateCampaignStatus(id, status)
    }

    fun replaceStrategy(degradedId: String, candidateId: String) {
        repository.replaceStrategy(degradedId, candidateId)
    }

    fun updateAutonomyPolicy(policy: AutonomyPolicy) {
        repository.updateAutonomyPolicy(policy)
    }

    fun refreshSystemHealth() {
        viewModelScope.launch {
            repository.refreshSystemHealth()
            repository.updateLastRefreshed()
        }
    }

    fun refreshCampaigns() {
        viewModelScope.launch {
            repository.refreshCampaigns()
            repository.updateLastRefreshed()
        }
    }

    fun refreshStats() {
        viewModelScope.launch {
            repository.refreshStats()
            repository.updateLastRefreshed()
        }
    }

    fun refreshPipelineRuns() {
        viewModelScope.launch {
            repository.refreshPipelineRuns()
            repository.updateLastRefreshed()
        }
    }

    fun refreshData() {
        viewModelScope.launch {
            repository.refreshData()
        }
    }
}
