package com.example.data.repository

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.example.data.local.QuantLabDatabase
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
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import retrofit2.Response
import java.io.IOException

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class QuantLabRepositoryUiStateTest {

    private lateinit var fakeApiService: FakeApiService
    private lateinit var database: QuantLabDatabase
    private lateinit var repository: QuantLabRepository

    @Before
    fun setup() {
        fakeApiService = FakeApiService()
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        database = Room.inMemoryDatabaseBuilder(context, QuantLabDatabase::class.java)
            .fallbackToDestructiveMigration(false)
            .build()
        repository = QuantLabRepository(fakeApiService, { database })
    }

    @Test
    fun `getSystemHealth returns Success when API succeeds`() = runTest {
        fakeApiService.healthResponse = ApiEnvelope(
            success = true,
            data = ApiHealth(status = "ok", version = "1.0.0")
        )

        val result = repository.getSystemHealth()
        assertTrue(result is UiState.Success)
        assertEquals(true, (result as UiState.Success).data.apiHealthy)
    }

    @Test
    fun `getSystemHealth falls back to cache on API failure`() = runTest {
        // First, seed cache
        fakeApiService.healthResponse = ApiEnvelope(
            success = true,
            data = ApiHealth(status = "ok", version = "1.0.0")
        )
        repository.getSystemHealth()

        // Now simulate failure
        fakeApiService.throwError = true
        val result = repository.getSystemHealth()
        assertTrue(result is UiState.Success)
        assertEquals(true, (result as UiState.Success).data.apiHealthy)
    }

    @Test
    fun `getSystemHealth returns Error when no cache and API fails`() = runTest {
        fakeApiService.throwError = true
        val result = repository.getSystemHealth()
        assertTrue(result is UiState.Error)
    }

    @Test
    fun `getCampaigns returns Success and caches when API succeeds`() = runTest {
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

        val result = repository.getCampaigns()
        assertTrue(result is UiState.Success)
        val campaigns = (result as UiState.Success).data
        assertEquals(1, campaigns.size)
        assertEquals("CAMP-TEST", campaigns.first().id)
    }

    @Test
    fun `getCampaigns falls back to cache on API failure`() = runTest {
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
        repository.getCampaigns()

        fakeApiService.throwError = true
        val result = repository.getCampaigns()
        assertTrue(result is UiState.Success)
        assertEquals(1, (result as UiState.Success).data.size)
    }

    @Test
    fun `StateFlow outputs are updated after getCampaigns`() = runTest {
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

        repository.getCampaigns()
        val campaigns = repository.campaigns.first()
        assertEquals(1, campaigns.size)
        assertEquals("CAMP-TEST", campaigns.first().id)
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
            if (throwError) throw IOException("Network error")
            return Response.success(ApiEnvelope(false, null))
        }

        override suspend fun getPipelineRuns(): Response<ApiEnvelope<List<ApiPipelineRun>>> {
            if (throwError) throw IOException("Network error")
            return Response.success(ApiEnvelope(false, emptyList()))
        }

        override suspend fun getStats(): Response<ApiEnvelope<ApiStats>> {
            if (throwError) throw IOException("Network error")
            return Response.success(ApiEnvelope(false, null))
        }
    }
}
