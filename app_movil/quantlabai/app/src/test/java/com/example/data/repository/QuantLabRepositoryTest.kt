package com.example.data.repository

import com.example.data.model.*
import com.example.data.remote.ApiService
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
import org.junit.Test
import retrofit2.Response
import java.io.IOException

class QuantLabRepositoryTest {

    private lateinit var fakeApiService: FakeApiService
    private lateinit var repository: QuantLabRepository

    @Before
    fun setup() {
        fakeApiService = FakeApiService()
        repository = QuantLabRepository(fakeApiService)
    }

    @Test
    fun `refreshFromBackend updates systemHealth on success`() = runTest {
        fakeApiService.healthResponse = ApiEnvelope(
            success = true,
            data = ApiHealth(status = "ok", version = "0.1.0")
        )

        repository.refreshFromBackend()
        val health = repository.systemHealth.first()
        assertEquals(true, health.openCodeOnline)
        assertEquals(true, health.apiHealthy)
    }

    @Test
    fun `refreshFromBackend updates campaigns on success`() = runTest {
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

        repository.refreshFromBackend()
        val campaigns = repository.campaigns.first()
        assertEquals(1, campaigns.size)
        assertEquals("CAMP-TEST", campaigns.first().id)
        assertEquals("EURUSD", campaigns.first().asset)
    }

    @Test
    fun `refreshFromBackend keeps existing data on network failure`() = runTest {
        fakeApiService.throwError = true

        val originalHealth = repository.systemHealth.first()
        repository.refreshFromBackend()
        val healthAfterFailure = repository.systemHealth.first()
        assertEquals(originalHealth, healthAfterFailure)
    }

    @Test
    fun `approveItem still works locally`() = runTest {
        val approvals = repository.approvals.first()
        val targetId = approvals.first().id
        repository.approveItem(targetId)
        val updated = repository.approvals.first()
        assertEquals(ApprovalStatus.APPROVED, updated.first { it.id == targetId }.status)
    }

    private class FakeApiService : ApiService {
        var healthResponse: ApiEnvelope<ApiHealth>? = null
        var campaignsResponse: ApiEnvelope<List<ApiCampaign>>? = null
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
            throw NotImplementedError()
        }

        override suspend fun getPipelineRuns(): Response<ApiEnvelope<List<ApiPipelineRun>>> {
            throw NotImplementedError()
        }

        override suspend fun getStats(): Response<ApiEnvelope<ApiStats>> {
            throw NotImplementedError()
        }
    }
}
