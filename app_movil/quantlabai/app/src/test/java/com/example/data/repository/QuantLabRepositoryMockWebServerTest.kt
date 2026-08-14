package com.example.data.repository

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import com.example.data.local.QuantLabDatabase
import com.example.data.model.UiState
import com.example.data.remote.ApiService
import com.example.data.remote.model.ApiCampaign
import com.example.data.remote.model.ApiEnvelope
import com.example.data.remote.model.ApiHealth
import com.example.data.remote.model.ApiPipelineRun
import com.example.data.remote.model.ApiStats
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import java.io.IOException

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class QuantLabRepositoryMockWebServerTest {

    private lateinit var server: MockWebServer
    private lateinit var apiService: ApiService
    private lateinit var database: QuantLabDatabase
    private lateinit var repository: QuantLabRepository

    @Before
    fun setup() {
        server = MockWebServer()
        server.start()

        val moshi = com.squareup.moshi.Moshi.Builder()
            .add(com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory())
            .build()

        val retrofit = Retrofit.Builder()
            .baseUrl(server.url("/"))
            .addConverterFactory(MoshiConverterFactory.create(moshi))
            .build()

        apiService = retrofit.create(ApiService::class.java)

        // In-memory database for each test
        val context = ApplicationProvider.getApplicationContext<Context>()
        database = androidx.room.Room.inMemoryDatabaseBuilder(context, QuantLabDatabase::class.java)
            .fallbackToDestructiveMigration()
            .build()

        repository = QuantLabRepository(apiService = apiService, databaseProvider = { database })
    }

    @After
    fun teardown() {
        try {
            database.close()
        } catch (e: Exception) {
            // ignore
        }
        try {
            server.shutdown()
        } catch (e: Exception) {
            // ignore
        }
    }

    @Test
    fun `getSystemHealth returns Success when API returns 200`() = runTest {
        server.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody("""{"success":true,"data":{"status":"ok","version":"1.0.0"}}""")
        )

        val result = repository.getSystemHealth()
        assertTrue(result is UiState.Success)
        assertEquals(true, (result as UiState.Success).data.apiHealthy)
    }

    @Test
    fun `getSystemHealth returns Error when API returns 500`() = runTest {
        server.enqueue(
            MockResponse()
                .setResponseCode(500)
                .setBody("""{"success":false,"data":null}""")
        )

        val result = repository.getSystemHealth()
        assertTrue(result is UiState.Error)
    }

    @Test
    fun `getCampaigns returns Success and caches in Room`() = runTest {
        server.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody("""{"success":true,"data":[{"campaign_id":"CAMP-001","name":"Test","market":"EURUSD","timeframe":"H1","sharpe":1.5,"profit_factor":1.8,"win_rate":0.6,"status":"ACTIVE","total_return":1000.0,"metrics":null,"tags":[],"created":"2025-01-01","path":"/test"}]}""")
        )

        val result = repository.getCampaigns()
        assertTrue(result is UiState.Success)
        val campaigns = (result as UiState.Success).data
        assertEquals(1, campaigns.size)
        assertEquals("CAMP-001", campaigns.first().id)

        // Verify cache: second call should read from Room (no network)
        val cached = repository.getCampaigns()
        assertTrue(cached is UiState.Success)
        assertEquals(1, (cached as UiState.Success).data.size)
    }

    @Test
    fun `getStats returns Success with parsed fields`() = runTest {
        server.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody("""{"success":true,"data":{"sharpe_mean":1.85,"sharpe_std":0.42,"max_drawdown_pct":8.5,"win_rate_mean":0.55,"total_trades":1200,"benchmark_comparison":"+12%","total_campaigns":5,"total_pipeline_runs":3,"generated_at":"2025-01-01T00:00:00Z"}}""")
        )

        val result = repository.getStats()
        assertTrue(result is UiState.Success)
        val stats = (result as UiState.Success).data
        assertEquals(1.85, stats.sharpeMean, 0.001)
        assertEquals(5, stats.totalCampaigns)
        assertEquals(1200, stats.totalTrades)
    }

    @Test
    fun `getPipelineRuns returns Success and caches runs`() = runTest {
        server.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody("""{"success":true,"data":[{"run_id":"RUN-001","pipeline_name":"Test","status":"completed","started_at":"2025-01-01T00:00:00Z","completed_at":"2025-01-01T01:00:00Z","duration":3600.0,"error":null}]}""")
        )

        val result = repository.getPipelineRuns()
        assertTrue(result is UiState.Success)
        val runs = (result as UiState.Success).data
        assertEquals(1, runs.size)
        assertEquals("RUN-001", runs.first().runId)
    }

    @Test
    fun `getCampaign returns Success for valid ID`() = runTest {
        server.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody("""{"success":true,"data":{"campaign_id":"CAMP-999","name":"Detail","market":"GBPUSD","timeframe":"M30","sharpe":2.0,"profit_factor":2.0,"win_rate":0.7,"status":"LIVE","total_return":2000.0,"metrics":null,"tags":null,"created":"2025-01-01","path":"/test","equity_curve":[],"trades":[],"statistics":{},"phases":[]}}""")
        )

        val result = repository.getCampaign("CAMP-999")
        assertTrue(result is UiState.Success)
        assertEquals("CAMP-999", (result as UiState.Success).data.id)
    }

    @Test
    fun `network failure falls back to cache after successful first call`() = runTest {
        // First call succeeds
        server.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody("""{"success":true,"data":{"status":"ok","version":"1.0.0"}}""")
        )
        repository.getSystemHealth()

        // Second call: simulate network failure by shutting down the server
        server.shutdown()

        val result = repository.getSystemHealth()
        // Should fall back to cache
        assertTrue(result is UiState.Success)
        assertEquals(true, (result as UiState.Success).data.apiHealthy)
    }
}
