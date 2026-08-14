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
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.data.model.Campaign
import com.example.data.model.CampaignStatus
import com.example.data.model.UiState
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
class CampaignsScreenTest {

    @get:Rule
    val composeTestRule = createComposeRule()

    private lateinit var fakeViewModel: FakeQuantLabViewModel

    @Before
    fun setup() {
        fakeViewModel = FakeQuantLabViewModel()
    }

    @Test
    fun `shows loading state when campaignsUiState is Loading`() {
        fakeViewModel.setCampaignsUiState(UiState.Loading)

        composeTestRule.setContent {
            QuantLabTheme {
                Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    CampaignsScreen(
                        viewModel = fakeViewModel,
                        onNavigateToCampaignDetail = {},
                        onNavigateToNewCampaign = {}
                    )
                }
            }
        }

        composeTestRule.onNodeWithTag("campaigns_loading").assertIsDisplayed()
    }

    @Test
    fun `shows error state with retry when campaignsUiState is Error`() {
        fakeViewModel.setCampaignsUiState(UiState.Error("Network error"))

        composeTestRule.setContent {
            QuantLabTheme {
                Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    CampaignsScreen(
                        viewModel = fakeViewModel,
                        onNavigateToCampaignDetail = {},
                        onNavigateToNewCampaign = {}
                    )
                }
            }
        }

        composeTestRule.onNodeWithTag("campaigns_error").assertIsDisplayed()
        composeTestRule.onNodeWithTag("campaigns_retry").assertIsDisplayed()
    }

    @Test
    fun `retry button triggers refresh when error state is shown`() {
        fakeViewModel.setCampaignsUiState(UiState.Error("Network error"))

        composeTestRule.setContent {
            QuantLabTheme {
                Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    CampaignsScreen(
                        viewModel = fakeViewModel,
                        onNavigateToCampaignDetail = {},
                        onNavigateToNewCampaign = {}
                    )
                }
            }
        }

        composeTestRule.onNodeWithTag("campaigns_retry").performClick()
        composeTestRule.onNodeWithTag("campaigns_error").assertIsDisplayed()
    }

    @Test
    fun `shows empty state when campaigns list is empty`() {
        fakeViewModel.setCampaignsUiState(UiState.Success(emptyList()))

        composeTestRule.setContent {
            QuantLabTheme {
                Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    CampaignsScreen(
                        viewModel = fakeViewModel,
                        onNavigateToCampaignDetail = {},
                        onNavigateToNewCampaign = {}
                    )
                }
            }
        }

        composeTestRule.onNodeWithTag("campaigns_empty").assertIsDisplayed()
    }

    @Test
    fun `shows campaigns list when Success with data`() {
        val campaigns = listOf(
            Campaign(
                id = "CAMP-001",
                name = "Test Campaign",
                asset = "EURUSD",
                timeframe = "H1",
                objective = "Test",
                hypothesis = "H-001",
                progressPct = 50,
                currentStage = com.example.data.model.PipelineStage.GENERATION,
                activeAgents = 2,
                waitingAgents = 0,
                generatedCount = 100,
                passedFiltersCount = 10,
                status = CampaignStatus.ACTIVE,
                lastEvent = "Testing",
                updatedAt = "12:00"
            )
        )
        fakeViewModel.setCampaignsUiState(UiState.Success(campaigns))

        composeTestRule.setContent {
            QuantLabTheme {
                Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    CampaignsScreen(
                        viewModel = fakeViewModel,
                        onNavigateToCampaignDetail = {},
                        onNavigateToNewCampaign = {}
                    )
                }
            }
        }

        composeTestRule.onNodeWithTag("campaigns_list").assertIsDisplayed()
        composeTestRule.onNodeWithText("Test Campaign").assertIsDisplayed()
    }

    @Test
    fun `search filter works on campaigns list`() {
        val campaigns = listOf(
            Campaign(
                id = "CAMP-EUR",
                name = "EURUSD Strategy",
                asset = "EURUSD",
                timeframe = "H1",
                objective = "Test",
                hypothesis = "H-001",
                progressPct = 50,
                currentStage = com.example.data.model.PipelineStage.GENERATION,
                activeAgents = 2,
                waitingAgents = 0,
                generatedCount = 100,
                passedFiltersCount = 10,
                status = CampaignStatus.ACTIVE,
                lastEvent = "Testing",
                updatedAt = "12:00"
            ),
            Campaign(
                id = "CAMP-GBP",
                name = "GBPUSD Strategy",
                asset = "GBPUSD",
                timeframe = "H1",
                objective = "Test",
                hypothesis = "H-002",
                progressPct = 30,
                currentStage = com.example.data.model.PipelineStage.HYPOTHESIS,
                activeAgents = 1,
                waitingAgents = 0,
                generatedCount = 50,
                passedFiltersCount = 5,
                status = CampaignStatus.ACTIVE,
                lastEvent = "Testing",
                updatedAt = "11:00"
            )
        )
        fakeViewModel.setCampaignsUiState(UiState.Success(campaigns))

        composeTestRule.setContent {
            QuantLabTheme {
                Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    CampaignsScreen(
                        viewModel = fakeViewModel,
                        onNavigateToCampaignDetail = {},
                        onNavigateToNewCampaign = {}
                    )
                }
            }
        }

        composeTestRule.onNodeWithText("EURUSD Strategy").assertIsDisplayed()
        composeTestRule.onNodeWithText("GBPUSD Strategy").assertIsDisplayed()
    }

    private class FakeQuantLabViewModel : QuantLabViewModel() {
        private val _campaignsUiState = MutableStateFlow<UiState<List<Campaign>>>(UiState.Loading)
        private val _campaignsStateFlow = MutableStateFlow<List<Campaign>>(emptyList())

        override val campaignsUiState: StateFlow<UiState<List<Campaign>>> = _campaignsUiState.asStateFlow()
        override val campaigns: StateFlow<List<Campaign>> = _campaignsStateFlow.asStateFlow()

        fun setCampaignsUiState(state: UiState<List<Campaign>>) {
            _campaignsUiState.value = state
        }
    }
}
