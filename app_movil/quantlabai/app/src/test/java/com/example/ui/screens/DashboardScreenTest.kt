package com.example.ui.screens

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsNotDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
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
import org.robolectric.annotation.Config

@RunWith(AndroidJUnit4::class)
@Config(sdk = [34])
class DashboardScreenTest {

    @get:Rule
    val composeTestRule = createComposeRule()

    private lateinit var fakeViewModel: FakeQuantLabViewModel

    @Before
    fun setup() {
        fakeViewModel = FakeQuantLabViewModel()
    }

    @Test
    fun `shows loading indicator when systemHealthUiState is Loading`() {
        fakeViewModel.setSystemHealthUiState(UiState.Loading)

        composeTestRule.setContent {
            QuantLabTheme {
                Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    DashboardScreen(
                        viewModel = fakeViewModel,
                        onNavigateToCampaign = {},
                        onNavigateToStrategy = {},
                        onNavigateToNewCampaign = {},
                        onNavigateToApprovals = {}
                    )
                }
            }
        }

        composeTestRule.onNodeWithTag("dashboard_loading").assertIsDisplayed()
    }

    @Test
    fun `shows error card with retry when systemHealthUiState is Error`() {
        fakeViewModel.setSystemHealthUiState(UiState.Error("Network error"))

        composeTestRule.setContent {
            QuantLabTheme {
                Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    DashboardScreen(
                        viewModel = fakeViewModel,
                        onNavigateToCampaign = {},
                        onNavigateToStrategy = {},
                        onNavigateToNewCampaign = {},
                        onNavigateToApprovals = {}
                    )
                }
            }
        }

        composeTestRule.onNodeWithTag("dashboard_error").assertIsDisplayed()
        composeTestRule.onNodeWithTag("dashboard_retry").assertIsDisplayed()
    }

    @Test
    fun `shows metrics from stats when Stats is Success`() {
        val stats = Stats(
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

        composeTestRule.setContent {
            QuantLabTheme {
                Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    DashboardScreen(
                        viewModel = fakeViewModel,
                        onNavigateToCampaign = {},
                        onNavigateToStrategy = {},
                        onNavigateToNewCampaign = {},
                        onNavigateToApprovals = {}
                    )
                }
            }
        }

        fakeViewModel.setSystemHealthUiState(UiState.Success(SystemHealth()))
        fakeViewModel.setStatsUiState(UiState.Success(stats))
        composeTestRule.waitForIdle()

        composeTestRule.onNodeWithText("4,218").assertIsDisplayed()
        composeTestRule.onNodeWithText("9").assertIsDisplayed()
        composeTestRule.onNodeWithText("17").assertIsDisplayed()
    }

    @Test
    fun `shows no campaigns count when campaigns UiState is Error`() {
        composeTestRule.setContent {
            QuantLabTheme {
                Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    DashboardScreen(
                        viewModel = fakeViewModel,
                        onNavigateToCampaign = {},
                        onNavigateToStrategy = {},
                        onNavigateToNewCampaign = {},
                        onNavigateToApprovals = {}
                    )
                }
            }
        }

        fakeViewModel.setSystemHealthUiState(UiState.Success(SystemHealth()))
        fakeViewModel.setCampaignsUiState(UiState.Error("Network error"))
        composeTestRule.waitForIdle()

        composeTestRule.onNodeWithTag("dashboard_campaigns_error").assertIsDisplayed()
    }

    @Test
    fun `shows last refreshed timestamp`() {
        fakeViewModel.setSystemHealthUiState(UiState.Success(SystemHealth()))
        fakeViewModel.setLastRefreshed("14:30")

        composeTestRule.setContent {
            QuantLabTheme {
                Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    DashboardScreen(
                        viewModel = fakeViewModel,
                        onNavigateToCampaign = {},
                        onNavigateToStrategy = {},
                        onNavigateToNewCampaign = {},
                        onNavigateToApprovals = {}
                    )
                }
            }
        }

        composeTestRule.onNodeWithTag("dashboard_last_refresh").assertIsDisplayed()
    }

    @Test
    fun `retry button triggers refresh when error state is shown`() {
        fakeViewModel.setSystemHealthUiState(UiState.Error("Network error"))

        composeTestRule.setContent {
            QuantLabTheme {
                Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    DashboardScreen(
                        viewModel = fakeViewModel,
                        onNavigateToCampaign = {},
                        onNavigateToStrategy = {},
                        onNavigateToNewCampaign = {},
                        onNavigateToApprovals = {}
                    )
                }
            }
        }

        composeTestRule.onNodeWithTag("dashboard_retry").performClick()
        composeTestRule.onNodeWithTag("dashboard_error").assertIsDisplayed()
    }

    private class FakeQuantLabViewModel : QuantLabViewModel() {
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

        fun setLastRefreshed(value: String) {
            _lastRefreshed.value = value
        }
    }
}
