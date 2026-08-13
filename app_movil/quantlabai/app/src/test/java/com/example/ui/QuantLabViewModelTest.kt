package com.example.ui

import androidx.test.ext.junit.rules.ActivityScenarioRule
import com.example.MainActivity
import com.example.data.model.*
import com.example.data.remote.ApiService
import com.example.data.repository.QuantLabRepository
import com.example.data.remote.model.ApiCampaign
import com.example.data.remote.model.ApiCampaignDetail
import com.example.data.remote.model.ApiEnvelope
import com.example.data.remote.model.ApiHealth
import com.example.data.remote.model.ApiPipelineRun
import com.example.data.remote.model.ApiStats
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import retrofit2.Response
import java.io.IOException

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class QuantLabViewModelTest {

    @get:Rule
    val activityRule = ActivityScenarioRule(MainActivity::class.java)

    private lateinit var fakeApiService: FakeApiService
    private lateinit var repository: QuantLabRepository
    private lateinit var viewModel: QuantLabViewModel

    @Before
    fun setup() {
        fakeApiService = FakeApiService()
        repository = QuantLabRepository(fakeApiService)
        viewModel = QuantLabViewModel(repository)
    }

    @Test
    fun `init updates systemHealthUiState to Success on API success`() = runTest {
        fakeApiService.healthResponse = ApiEnvelope(
            success = true,
            data = ApiHealth(status = "ok", version = "1.0.0")
        )
        viewModel = QuantLabViewModel(repository)

        val state = viewModel.systemHealthUiState.first { it is UiState.Success }
        assertTrue(state is UiState.Success)
        assertEquals(true, (state as UiState.Success).data.apiHealthy)
    }

    @Test
    fun `init updates campaignsUiState to Success on API success`() = runTest {
        fakeApiService.campaignsResponse = ApiEnvelope(
            success = true,
            data = listOf(
                ApiCampaign(
                    campaignId = "CAMP-TEST",
                    name = "Test Campaign",
                    market = "EURUSD",
                    timeframe = "H1",
                    sharpe = 1.5,
                    profitFactor = 1.8,
                    winRate = 0.6,
                    status = "ACTIVE",
                    totalReturn = 1000.0,
                    metrics = null,
                    tags = emptyList(),
                    created = "2025-01-01",
                    path = "/test"
                )
            )
        )
        viewModel = QuantLabViewModel(repository)

        val state = viewModel.campaignsUiState.first { it is UiState.Success }
        assertTrue(state is UiState.Success)
        val campaigns = (state as UiState.Success).data
        assertEquals(1, campaigns.size)
        assertEquals("CAMP-TEST", campaigns.first().id)
    }

    @Test
    fun `init updates statsUiState to Success on API success`() = runTest {
        fakeApiService.statsResponse = ApiEnvelope(
            success = true,
            data = ApiStats(
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
        viewModel = QuantLabViewModel(repository)

        val state = viewModel.statsUiState.first { it is UiState.Success }
        assertTrue(state is UiState.Success)
        val stats = (state as UiState.Success).data
        assertEquals(4218, stats.totalTrades)
        assertEquals(9, stats.totalCampaigns)
    }

    @Test
    fun `init updates legacy systemHealth StateFlow`() = runTest {
        fakeApiService.healthResponse = ApiEnvelope(
            success = true,
            data = ApiHealth(status = "ok", version = "1.0.0")
        )

        val health = viewModel.systemHealth.first()
        assertEquals(true, health.apiHealthy)
    }

    @Test
    fun `refresh triggers UiState update to Loading then Success`() = runTest {
        fakeApiService.healthResponse = ApiEnvelope(
            success = true,
            data = ApiHealth(status = "ok", version = "1.0.0")
        )

        viewModel.refreshSystemHealth()
        val state = viewModel.systemHealthUiState.first()
        assertTrue(state is UiState.Success)
    }

    @Test
    fun `init sets UiState to Error on API failure with no cache`() = runTest {
        fakeApiService.throwError = true

        val healthState = viewModel.systemHealthUiState.first()
        assertTrue(healthState is UiState.Error)
    }

    @Test
    fun `init sets campaignsUiState to Error on API failure with no cache`() = runTest {
        fakeApiService.throwError = true
        viewModel.refreshCampaigns()
        val campaignsState = viewModel.campaignsUiState.value
        assertTrue(campaignsState is UiState.Error)
    }

    @Test
    fun `refreshSystemHealth propagates Error on API failure`() = runTest {
        fakeApiService.healthResponse = ApiEnvelope(
            success = true,
            data = ApiHealth(status = "ok", version = "1.0.0")
        )

        viewModel.systemHealthUiState.first()

        fakeApiService.throwError = true
        viewModel.refreshSystemHealth()

        val state = viewModel.systemHealthUiState.first()
        assertTrue(state is UiState.Error)
    }

    @Test
    fun `refreshCampaigns propagates Error on API failure`() = runTest {
        fakeApiService.campaignsResponse = ApiEnvelope(
            success = true,
            data = listOf(
                ApiCampaign(
                    campaignId = "CAMP-TEST",
                    name = "Test",
                    market = "EURUSD",
                    timeframe = "H1",
                    sharpe = 1.5,
                    profitFactor = 1.8,
                    winRate = 0.6,
                    status = "ACTIVE",
                    totalReturn = 1000.0,
                    metrics = null,
                    tags = emptyList(),
                    created = "2025-01-01",
                    path = "/test"
                )
            )
        )

        viewModel.campaignsUiState.first()

        fakeApiService.throwError = true
        viewModel.refreshCampaigns()

        val state = viewModel.campaignsUiState.first()
        assertTrue(state is UiState.Error)
    }

    @Test
    fun `systemHealthUiState loading then success on init`() = runTest {
        fakeApiService.healthResponse = ApiEnvelope(
            success = true,
            data = ApiHealth(status = "ok", version = "1.0.0")
        )
        viewModel = QuantLabViewModel(repository)

        val state = viewModel.systemHealthUiState.first { it is UiState.Success }
        assertTrue(state is UiState.Success)
        assertEquals(true, (state as UiState.Success).data.apiHealthy)
    }

    @Test
    fun `refreshData updates all UiState flows`() = runTest {
        fakeApiService.healthResponse = ApiEnvelope(
            success = true,
            data = ApiHealth(status = "ok", version = "1.0.0")
        )
        fakeApiService.campaignsResponse = ApiEnvelope(
            success = true,
            data = listOf(
                ApiCampaign(
                    campaignId = "CAMP-REFRESH",
                    name = "Refreshed Campaign",
                    market = "GBPUSD",
                    timeframe = "M30",
                    sharpe = 2.0,
                    profitFactor = 2.0,
                    winRate = 0.7,
                    status = "ACTIVE",
                    totalReturn = 2000.0,
                    metrics = null,
                    tags = emptyList(),
                    created = "2025-01-02",
                    path = "/refresh"
                )
            )
        )
        fakeApiService.statsResponse = ApiEnvelope(
            success = true,
            data = ApiStats(
                sharpeMean = 2.0,
                sharpeStd = 0.2,
                maxDrawdownPct = 5.0,
                winRateMean = 0.65,
                totalTrades = 5000,
                benchmarkComparison = "+20%",
                totalCampaigns = 12,
                totalPipelineRuns = 25,
                generatedAt = "2025-01-02T00:00:00Z"
            )
        )
        fakeApiService.pipelineRunsResponse = ApiEnvelope(
            success = true,
            data = listOf(
                ApiPipelineRun(
                    runId = "RUN-001",
                    pipelineName = "Test Pipeline",
                    status = "completed",
                    startedAt = "2025-01-02T00:00:00Z",
                    completedAt = "2025-01-02T01:00:00Z",
                    duration = 3600.0,
                    error = null,
                    stages = null,
                    configSnapshot = null,
                    artifacts = null
                )
            )
        )

        viewModel.refreshData()

        assertTrue(viewModel.systemHealthUiState.value is UiState.Success)
        assertTrue(viewModel.campaignsUiState.value is UiState.Success)
        assertTrue(viewModel.statsUiState.value is UiState.Success)
        assertTrue(viewModel.pipelineRunsUiState.value is UiState.Success)
    }

    @Test
    fun `refreshData updates lastRefreshed timestamp`() = runTest {
        fakeApiService.healthResponse = ApiEnvelope(
            success = true,
            data = ApiHealth(status = "ok", version = "1.0.0")
        )
        fakeApiService.campaignsResponse = ApiEnvelope(
            success = true,
            data = emptyList()
        )
        fakeApiService.statsResponse = ApiEnvelope(
            success = true,
            data = ApiStats(
                sharpeMean = 1.0,
                sharpeStd = 0.2,
                maxDrawdownPct = 10.0,
                winRateMean = 0.5,
                totalTrades = 100,
                benchmarkComparison = null,
                totalCampaigns = 5,
                totalPipelineRuns = 10,
                generatedAt = "2025-01-01T00:00:00Z"
            )
        )
        fakeApiService.pipelineRunsResponse = ApiEnvelope(
            success = true,
            data = emptyList()
        )

        viewModel.refreshData()

        val timestamp = viewModel.lastRefreshed.value
        assertNotNull(timestamp)
        assertTrue(timestamp.isNotBlank())
    }

    private class FakeApiService : ApiService {
        var healthResponse: ApiEnvelope<ApiHealth>? = null
        var campaignsResponse: ApiEnvelope<List<ApiCampaign>>? = null
        var statsResponse: ApiEnvelope<ApiStats>? = null
        var pipelineRunsResponse: ApiEnvelope<List<ApiPipelineRun>>? = null
        var throwError: Boolean = false

        override suspend fun getHealth(): Response<ApiEnvelope<ApiHealth>> {
            if (throwError) throw IOException("Network error")
            return Response.success(healthResponse)
        }

        override suspend fun getCampaigns(): Response<ApiEnvelope<List<ApiCampaign>>> {
            if (throwError) throw IOException("Network error")
            return Response.success(campaignsResponse)
        }

        override suspend fun getCampaign(id: String): Response<ApiEnvelope<ApiCampaignDetail>> {
            if (throwError) throw IOException("Network error")
            return Response.success(ApiEnvelope(false, null))
        }

        override suspend fun getPipelineRuns(): Response<ApiEnvelope<List<ApiPipelineRun>>> {
            if (throwError) throw IOException("Network error")
            return Response.success(pipelineRunsResponse)
        }

        override suspend fun getStats(): Response<ApiEnvelope<ApiStats>> {
            if (throwError) throw IOException("Network error")
            return Response.success(statsResponse)
        }
    }
}
