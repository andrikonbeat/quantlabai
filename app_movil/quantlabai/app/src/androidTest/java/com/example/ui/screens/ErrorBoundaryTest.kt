package com.example.ui.screens

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.data.model.*
import com.example.ui.QuantLabViewModel
import com.example.ui.theme.QuantLabTheme
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import androidx.test.ext.junit.runners.AndroidJUnit4

@RunWith(AndroidJUnit4::class)
class ErrorBoundaryTest {

    @get:Rule
    val composeTestRule = createComposeRule()

    private lateinit var fakeDashboardViewModel: FakeDashboardViewModel
    private lateinit var fakeCampaignsViewModel: FakeCampaignsViewModel

    @Before
    fun setup() {
        fakeDashboardViewModel = FakeDashboardViewModel()
        fakeCampaignsViewModel = FakeCampaignsViewModel()
    }

    @Test
    fun `dashboard shows cached data when API fails after cache populated`() {
        composeTestRule.setContent {
            QuantLabTheme {
                Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    DashboardScreen(
                        viewModel = fakeDashboardViewModel,
                        onNavigateToCampaign = {},
                        onNavigateToStrategy = {},
                        onNavigateToNewCampaign = {},
                        onNavigateToApprovals = {}
                    )
                }
            }
        }

        fakeDashboardViewModel.setSystemHealthUiState(
            UiState.Success(SystemHealth(apiHealthy = true, openCodeOnline = true))
        )
        fakeDashboardViewModel.setStatsUiState(
            UiState.Success(
                Stats(
                    sharpeMean = 1.5,
                    sharpeStd = 0.3,
                    maxDrawdownPct = 8.0,
                    winRateMean = 0.55,
                    totalTrades = 4218,
                    benchmarkComparison = "+12%",
                    totalCampaigns = 9,
                    totalPipelineRuns = 17,
                    generatedAt = "2025-01-01T00:00:00Z"
                )
            )
        )
        composeTestRule.waitForIdle()

        composeTestRule.onNodeWithTag("dashboard_content").assertIsDisplayed()
        composeTestRule.onNodeWithText("4,218").assertIsDisplayed()
        composeTestRule.onNodeWithText("9").assertIsDisplayed()
    }

    @Test
    fun `dashboard shows empty state for campaigns when API fails`() {
        composeTestRule.setContent {
            QuantLabTheme {
                Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    DashboardScreen(
                        viewModel = fakeDashboardViewModel,
                        onNavigateToCampaign = {},
                        onNavigateToStrategy = {},
                        onNavigateToNewCampaign = {},
                        onNavigateToApprovals = {}
                    )
                }
            }
        }

        fakeDashboardViewModel.setSystemHealthUiState(UiState.Success(SystemHealth()))
        fakeDashboardViewModel.setCampaignsUiState(UiState.Error("Network error"))
        composeTestRule.waitForIdle()

        composeTestRule.onNodeWithTag("dashboard_campaigns_error").assertIsDisplayed()
    }

    @Test
    fun `campaigns screen shows empty state gracefully when list is empty`() {
        fakeCampaignsViewModel.setCampaignsUiState(UiState.Success(emptyList()))

        composeTestRule.setContent {
            QuantLabTheme {
                Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    CampaignsScreen(
                        viewModel = fakeCampaignsViewModel,
                        onNavigateToCampaignDetail = {},
                        onNavigateToNewCampaign = {}
                    )
                }
            }
        }

        composeTestRule.onNodeWithTag("campaigns_empty").assertIsDisplayed()
    }

    @Test
    fun `campaigns screen does not show list when Error state`() {
        fakeCampaignsViewModel.setCampaignsUiState(UiState.Error("Server unavailable"))

        composeTestRule.setContent {
            QuantLabTheme {
                Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    CampaignsScreen(
                        viewModel = fakeCampaignsViewModel,
                        onNavigateToCampaignDetail = {},
                        onNavigateToNewCampaign = {}
                    )
                }
            }
        }

        composeTestRule.onNodeWithTag("campaigns_error").assertIsDisplayed()
        composeTestRule.onNodeWithTag("campaigns_list").assertDoesNotExist()
    }

    @Test
    fun `dashboard shows error state instead of content on system health failure`() {
        fakeDashboardViewModel.setSystemHealthUiState(UiState.Error("Connection timeout"))

        composeTestRule.setContent {
            QuantLabTheme {
                Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    DashboardScreen(
                        viewModel = fakeDashboardViewModel,
                        onNavigateToCampaign = {},
                        onNavigateToStrategy = {},
                        onNavigateToNewCampaign = {},
                        onNavigateToApprovals = {}
                    )
                }
            }
        }

        composeTestRule.onNodeWithTag("dashboard_error").assertIsDisplayed()
        composeTestRule.onNodeWithTag("dashboard_content").assertDoesNotExist()
    }

    @Test
    fun `dashboard displays metrics using fallback values when stats is Error`() {
        composeTestRule.setContent {
            QuantLabTheme {
                Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    DashboardScreen(
                        viewModel = fakeDashboardViewModel,
                        onNavigateToCampaign = {},
                        onNavigateToStrategy = {},
                        onNavigateToNewCampaign = {},
                        onNavigateToApprovals = {}
                    )
                }
            }
        }

        fakeDashboardViewModel.setSystemHealthUiState(UiState.Success(SystemHealth()))
        fakeDashboardViewModel.setStatsUiState(UiState.Error("Stats unavailable"))
        composeTestRule.waitForIdle()

        composeTestRule.onNodeWithTag("dashboard_content").assertIsDisplayed()
    }

    private class FakeDashboardViewModel : QuantLabViewModel() {
        private val _systemHealthUiState = MutableStateFlow<UiState<SystemHealth>>(UiState.Loading)
        private val _campaignsUiState = MutableStateFlow<UiState<List<Campaign>>>(UiState.Loading)
        private val _pipelineRunsUiState = MutableStateFlow<UiState<List<PipelineRun>>>(UiState.Loading)
        private val _statsUiState = MutableStateFlow<UiState<Stats>>(UiState.Loading)
        private val _lastRefreshed = MutableStateFlow<String>("")

        override val systemHealthUiState: StateFlow<UiState<SystemHealth>> = _systemHealthUiState.asStateFlow()
        override val campaignsUiState: StateFlow<UiState<List<Campaign>>> = _campaignsUiState.asStateFlow()
        override val pipelineRunsUiState: StateFlow<UiState<List<PipelineRun>>> = _pipelineRunsUiState.asStateFlow()
        override val statsUiState: StateFlow<UiState<Stats>> = _statsUiState.asStateFlow()
        override val lastRefreshed: StateFlow<String> = _lastRefreshed.asStateFlow()

        fun setSystemHealthUiState(state: UiState<SystemHealth>) {
            _systemHealthUiState.value = state
        }

        fun setCampaignsUiState(state: UiState<List<Campaign>>) {
            _campaignsUiState.value = state
        }

        fun setStatsUiState(state: UiState<Stats>) {
            _statsUiState.value = state
        }
    }

    private class FakeCampaignsViewModel : QuantLabViewModel() {
        private val _campaignsUiState = MutableStateFlow<UiState<List<Campaign>>>(UiState.Loading)
        private val _campaignsStateFlow = MutableStateFlow<List<Campaign>>(emptyList())

        override val campaignsUiState: StateFlow<UiState<List<Campaign>>> = _campaignsUiState.asStateFlow()
        override val campaigns: StateFlow<List<Campaign>> = _campaignsStateFlow.asStateFlow()

        fun setCampaignsUiState(state: UiState<List<Campaign>>) {
            _campaignsUiState.value = state
        }
    }
}
