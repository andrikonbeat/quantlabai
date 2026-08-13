package com.example.data.repository

import com.example.data.model.SystemHealth
import com.example.data.model.UiState
import com.example.data.remote.ApiService
import com.example.data.remote.model.ApiCampaign
import com.example.data.remote.model.ApiCampaignDetail
import com.example.data.remote.model.ApiEnvelope
import com.example.data.remote.model.ApiHealth
import com.example.data.remote.model.ApiPipelineRun
import com.example.data.remote.model.ApiStats
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import retrofit2.Response
import java.io.IOException
import java.util.regex.Pattern

class QuantLabRepositoryRefreshTest {

    private lateinit var fakeApiService: FakeApiService
    private lateinit var repository: QuantLabRepository

    @Before
    fun setup() {
        fakeApiService = FakeApiService()
        // databaseProvider omitted so no Room is needed for these tests
        repository = QuantLabRepository(fakeApiService)
    }

    // ---- refreshSystemHealth ----

    @Test
    fun `refreshSystemHealth sets Success on API success`() = runTest {
        fakeApiService.healthResponse = ApiEnvelope(true, ApiHealth(status = "ok", version = "1.0.0"))

        repository.refreshSystemHealth()

        val state = repository.systemHealthUiState.value
        assertTrue(state is UiState.Success)
        assertEquals(true, (state as UiState.Success).data.apiHealthy)
        assertEquals(true, (state as UiState.Success).data.openCodeOnline)
    }

    @Test
    fun `refreshSystemHealth sets Error on API failure without cache`() = runTest {
        fakeApiService.throwError = true

        repository.refreshSystemHealth()

        val state = repository.systemHealthUiState.value
        assertTrue(state is UiState.Error)
    }

    @Test
    fun `refreshSystemHealth transitions Loading then Success`() = runTest {
        fakeApiService.healthResponse = ApiEnvelope(true, ApiHealth(status = "ok", version = "1.0.0"))
        val observed = mutableListOf<UiState<SystemHealth>>()
        val collectJob = launch(UnconfinedTestDispatcher()) {
            repository.systemHealthUiState.collect { observed.add(it) }
        }

        repository.refreshSystemHealth()
        collectJob.cancel()

        assertTrue(observed.any { it is UiState.Loading })
        assertTrue(observed.any { it is UiState.Success })
    }

    // ---- refreshCampaigns ----

    @Test
    fun `refreshCampaigns sets Success on API success`() = runTest {
        fakeApiService.campaignsResponse = ApiEnvelope(true, listOf(campaign("CAMP-TEST")))

        repository.refreshCampaigns()

        val state = repository.campaignsUiState.value
        assertTrue(state is UiState.Success)
        val campaigns = (state as UiState.Success).data
        assertEquals(1, campaigns.size)
        assertEquals("CAMP-TEST", campaigns.first().id)
        assertEquals("EURUSD", campaigns.first().asset)
    }

    @Test
    fun `refreshCampaigns sets Error on API failure without cache`() = runTest {
        fakeApiService.throwError = true

        repository.refreshCampaigns()

        assertTrue(repository.campaignsUiState.value is UiState.Error)
    }

    // ---- refreshStats ----

    @Test
    fun `refreshStats sets Success on API success`() = runTest {
        fakeApiService.statsResponse = ApiEnvelope(true, stats())

        repository.refreshStats()

        val state = repository.statsUiState.value
        assertTrue(state is UiState.Success)
        val stats = (state as UiState.Success).data
        assertEquals(9, stats.totalCampaigns)
        assertEquals(17, stats.totalPipelineRuns)
        assertEquals(4218, stats.totalTrades)
    }

    @Test
    fun `refreshStats sets Error on API failure without cache`() = runTest {
        fakeApiService.throwError = true

        repository.refreshStats()

        assertTrue(repository.statsUiState.value is UiState.Error)
    }

    // ---- refreshPipelineRuns ----

    @Test
    fun `refreshPipelineRuns sets Success on API success`() = runTest {
        fakeApiService.pipelineRunsResponse = ApiEnvelope(true, listOf(pipelineRun()))

        repository.refreshPipelineRuns()

        val state = repository.pipelineRunsUiState.value
        assertTrue(state is UiState.Success)
        val runs = (state as UiState.Success).data
        assertEquals(1, runs.size)
        assertEquals("RUN-001", runs.first().runId)
        assertEquals("completed", runs.first().status)
    }

    @Test
    fun `refreshPipelineRuns sets Error on API failure without cache`() = runTest {
        fakeApiService.throwError = true

        repository.refreshPipelineRuns()

        assertTrue(repository.pipelineRunsUiState.value is UiState.Error)
    }

    // ---- refreshData ----

    @Test
    fun `refreshData updates all UiState flows to Success`() = runTest {
        fakeApiService.healthResponse = ApiEnvelope(true, ApiHealth(status = "ok", version = "1.0.0"))
        fakeApiService.campaignsResponse = ApiEnvelope(true, listOf(campaign("CAMP-REF")))
        fakeApiService.statsResponse = ApiEnvelope(true, stats())
        fakeApiService.pipelineRunsResponse = ApiEnvelope(true, listOf(pipelineRun()))

        repository.refreshData()

        assertTrue(repository.systemHealthUiState.value is UiState.Success)
        assertTrue(repository.campaignsUiState.value is UiState.Success)
        assertTrue(repository.statsUiState.value is UiState.Success)
        assertTrue(repository.pipelineRunsUiState.value is UiState.Success)
    }

    @Test
    fun `refreshData sets flows to Error when API is down`() = runTest {
        fakeApiService.throwError = true

        repository.refreshData()

        assertTrue(repository.systemHealthUiState.value is UiState.Error)
        assertTrue(repository.campaignsUiState.value is UiState.Error)
        assertTrue(repository.statsUiState.value is UiState.Error)
        assertTrue(repository.pipelineRunsUiState.value is UiState.Error)
    }

    @Test
    fun `refreshData updates lastRefreshed timestamp`() = runTest {
        fakeApiService.healthResponse = ApiEnvelope(true, ApiHealth(status = "ok", version = "1.0.0"))
        fakeApiService.campaignsResponse = ApiEnvelope(true, emptyList())
        fakeApiService.statsResponse = ApiEnvelope(true, stats())
        fakeApiService.pipelineRunsResponse = ApiEnvelope(true, emptyList())

        repository.refreshData()

        assertTrue(Pattern.matches("\\d{2}:\\d{2}:\\d{2}", repository.lastRefreshed.value))
    }

    // ---- updateLastRefreshed ----

    @Test
    fun `updateLastRefreshed writes HH mm ss timestamp`() {
        repository.updateLastRefreshed()

        assertTrue(Pattern.matches("\\d{2}:\\d{2}:\\d{2}", repository.lastRefreshed.value))
    }

    private fun campaign(id: String) = ApiCampaign(
        campaignId = id,
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

    private fun stats() = ApiStats(
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

    private fun pipelineRun() = ApiPipelineRun(
        runId = "RUN-001",
        pipelineName = "Test Pipeline",
        status = "completed",
        startedAt = "2025-01-01T00:00:00Z",
        completedAt = "2025-01-01T01:00:00Z",
        duration = 3600.0,
        error = null,
        stages = null,
        configSnapshot = null,
        artifacts = null
    )

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